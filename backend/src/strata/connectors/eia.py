"""EIA (Energy Information Administration) API v2 client.

Typed wrappers for the EIA Open Data API v2 with disk caching
and conversion to Strata AtomicPrimitive / Source YAML format.

API reference: https://www.eia.gov/opendata/documentation.php
Rate limits: 5,000 requests/hour with a registered API key.
Max 5,000 rows per request.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, NotRequired, TypedDict

import httpx

# ═══════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════


class EIAFrequency(StrEnum):
    """Observation frequency codes accepted by the EIA API v2."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class EIASector(StrEnum):
    """Electricity retail-sales sector codes."""

    RESIDENTIAL = "RES"
    COMMERCIAL = "COM"
    INDUSTRIAL = "IND"
    TRANSPORTATION = "TRA"
    OTHER = "OTH"
    ALL = "ALL"


class EIARoute(StrEnum):
    """Common EIA API v2 data routes."""

    ELECTRICITY_RETAIL = "electricity/retail-sales"
    ELECTRICITY_GENERATION = "electricity/electric-power-operational-data"
    PETROLEUM_PRICES = "petroleum/pri/spt"
    PETROLEUM_SUPPLY = "petroleum/sum/sndw"
    NATURAL_GAS_PRICES = "natural-gas/pri/sum"
    NATURAL_GAS_SUPPLY = "natural-gas/sum/lsum"
    COAL_PRODUCTION = "coal/mine-production"
    TOTAL_ENERGY = "total-energy"
    STEO = "steo"
    INTERNATIONAL = "international"
    NUCLEAR = "nuclear-outages/us-nuclear-outages"
    RENEWABLE = "electricity/electric-power-operational-data"
    GENERATOR_CAPACITY = "electricity/operating-generator-capacity"
    CO2_EMISSIONS = "co2-emissions/co2-emissions-aggregates"
    PETROLEUM_CONSUMPTION = "petroleum/cons/psup"
    NATURAL_GAS_CONSUMPTION = "natural-gas/cons/sum"


class EIAState(StrEnum):
    """US state / territory codes used in EIA facets, plus national."""

    US = "US"
    AL = "AL"
    AK = "AK"
    AZ = "AZ"
    AR = "AR"
    CA = "CA"
    CO = "CO"
    CT = "CT"
    DE = "DE"
    FL = "FL"
    GA = "GA"
    HI = "HI"
    ID = "ID"
    IL = "IL"
    IN = "IN"
    IA = "IA"
    KS = "KS"
    KY = "KY"
    LA = "LA"
    ME = "ME"
    MD = "MD"
    MA = "MA"
    MI = "MI"
    MN = "MN"
    MS = "MS"
    MO = "MO"
    MT = "MT"
    NE = "NE"
    NV = "NV"
    NH = "NH"
    NJ = "NJ"
    NM = "NM"
    NY = "NY"
    NC = "NC"
    ND = "ND"
    OH = "OH"
    OK = "OK"
    OR = "OR"
    PA = "PA"
    RI = "RI"
    SC = "SC"
    SD = "SD"
    TN = "TN"
    TX = "TX"
    UT = "UT"
    VT = "VT"
    VA = "VA"
    WA = "WA"
    WV = "WV"
    WI = "WI"
    WY = "WY"
    DC = "DC"


# ═══════════════════════════════════════════════════════════════════
# TypedDicts — raw EIA JSON response shapes
# ═══════════════════════════════════════════════════════════════════


class EIADataPointRaw(TypedDict, total=False):
    period: str
    stateId: str
    stateDescription: str
    sectorId: str
    sectorName: str
    seriesId: str
    seriesDescription: str
    value: float | str | None
    units: str
    unit: str
    fuelTypeId: str
    fuelTypeDescription: str
    duoarea: str
    areaName: str
    product: str
    productName: str
    process: str
    processName: str


class EIAResponseRaw(TypedDict, total=False):
    total: int
    dateFormat: str
    frequency: str
    data: list[dict[str, Any]]
    description: str
    warnings: list[str]


class EIAMetadataRaw(TypedDict, total=False):
    id: str
    name: str
    description: str
    frequency: list[dict[str, str]]
    facets: dict[str, dict[str, str]]
    data: NotRequired[dict[str, dict[str, str]]]
    routes: NotRequired[list[dict[str, str]]]
    startPeriod: NotRequired[str]
    endPeriod: NotRequired[str]


# ═══════════════════════════════════════════════════════════════════
# Dataclasses — validated internal models
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class EIADataPoint:
    """A single data observation from the EIA API."""

    period: str
    state: str
    state_name: str
    sector: str
    sector_name: str
    value: float | None
    units: str
    series_id: str


@dataclass(frozen=True, slots=True)
class EIASeriesMetadata:
    """Metadata describing an EIA data route."""

    route: str
    name: str
    description: str
    frequency: tuple[str, ...]
    facets: tuple[str, ...]
    data_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EIAForecast:
    """A single forecast point from STEO or AEO."""

    period: str
    series_id: str
    value: float | None
    units: str
    description: str


@dataclass(frozen=True, slots=True)
class EIAResponse:
    """Standard return type for every EIA client call."""

    kind: str
    data_points: tuple[EIADataPoint, ...] = ()
    metadata: tuple[EIASeriesMetadata, ...] = ()
    forecasts: tuple[EIAForecast, ...] = ()
    total: int = 0
    cached: bool = False
    cache_age_seconds: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# Response parsing
# ═══════════════════════════════════════════════════════════════════


def _safe_float(raw: object) -> float | None:
    """Convert a raw value to float, returning None on failure."""
    if raw is None:
        return None
    try:
        return float(raw)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None


def _parse_data_point(raw: dict[str, Any]) -> EIADataPoint:
    return EIADataPoint(
        period=str(raw.get("period", "")),
        state=str(raw.get("stateId", raw.get("duoarea", ""))),
        state_name=str(raw.get("stateDescription", raw.get("areaName", ""))),
        sector=str(raw.get("sectorId", raw.get("fuelTypeId", ""))),
        sector_name=str(raw.get("sectorName", raw.get("fuelTypeDescription", ""))),
        value=_safe_float(raw.get("value")),
        units=str(raw.get("units", raw.get("unit", ""))),
        series_id=str(raw.get("seriesId", raw.get("msn", ""))),
    )


def _parse_forecast(raw: dict[str, Any]) -> EIAForecast:
    return EIAForecast(
        period=str(raw.get("period", "")),
        series_id=str(raw.get("seriesId", "")),
        value=_safe_float(raw.get("value")),
        units=str(raw.get("units", raw.get("unit", ""))),
        description=str(raw.get("seriesDescription", "")),
    )


def _parse_metadata(raw: dict[str, Any], *, route: str) -> EIASeriesMetadata:
    freq_list: list[dict[str, str]] = raw.get("frequency", [])
    facets_dict: dict[str, Any] = raw.get("facets", {})
    data_dict: dict[str, Any] = raw.get("data", {})
    return EIASeriesMetadata(
        route=route,
        name=str(raw.get("name", "")),
        description=str(raw.get("description", "")),
        frequency=tuple(str(f.get("id", "")) for f in freq_list),
        facets=tuple(facets_dict.keys()),
        data_fields=tuple(data_dict.keys()),
    )


def _parse_data_response(raw: dict[str, Any], *, kind: str) -> EIAResponse:
    """Parse the EIA v2 response envelope for data requests."""
    response_body: dict[str, Any] = raw.get("response", {})
    data_list: list[dict[str, Any]] = response_body.get("data", [])
    total = int(response_body.get("total", len(data_list)))

    if kind == "forecast":
        forecasts = tuple(_parse_forecast(d) for d in data_list)
        return EIAResponse(kind=kind, forecasts=forecasts, total=total)

    data_points = tuple(_parse_data_point(d) for d in data_list)
    return EIAResponse(kind=kind, data_points=data_points, total=total)


def _parse_metadata_response(raw: dict[str, Any], *, route: str) -> EIAResponse:
    """Parse the EIA v2 response envelope for metadata requests."""
    response_body: dict[str, Any] = raw.get("response", {})
    meta = _parse_metadata(response_body, route=route)
    return EIAResponse(kind="metadata", metadata=(meta,), total=1)


# ═══════════════════════════════════════════════════════════════════
# Disk cache
# ═══════════════════════════════════════════════════════════════════


class _DiskCache:
    """JSON-on-disk cache keyed by request hash, with configurable TTL."""

    def __init__(self, directory: Path, ttl_seconds: int = 86400) -> None:
        self._dir = directory
        self._ttl = ttl_seconds
        self._dir.mkdir(parents=True, exist_ok=True)

    def _key(self, params: str) -> str:
        return hashlib.sha256(params.encode()).hexdigest()[:16]

    def _path(self, key: str) -> Path:
        return self._dir / f"eia_{key}.json"

    def get(self, params: str) -> tuple[dict[str, Any], float] | None:
        path = self._path(self._key(params))
        if not path.exists():
            return None
        try:
            raw: dict[str, Any] = json.loads(path.read_text())
            ts = float(raw.get("_ts", 0))
            age = time.time() - ts
            if age > self._ttl:
                path.unlink(missing_ok=True)
                return None
            data: dict[str, Any] = raw.get("_data", {})
            return data, age
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            path.unlink(missing_ok=True)
            return None

    def put(self, params: str, data: dict[str, Any]) -> None:
        path = self._path(self._key(params))
        payload: dict[str, Any] = {"_ts": time.time(), "_data": data}
        path.write_text(json.dumps(payload, indent=2))

    def clear(self) -> int:
        count = 0
        for f in self._dir.glob("eia_*.json"):
            f.unlink()
            count += 1
        return count


# ═══════════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════════

_BASE = "https://api.eia.gov/v2"


class EIAClientError(RuntimeError):
    """Raised on EIA API errors or client-side validation failures."""


class EIAClient:
    """Typed client for the EIA Open Data API v2.

    Usage::

        client = EIAClient(api_key="your-key")
        resp = client.get_electricity_prices(state="US", start="2020-01")
        for dp in resp.data_points:
            print(dp.period, dp.value, dp.units)
    """

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: Path | None = None,
        cache_ttl: int = 86400,
        timeout: float = 30.0,
    ) -> None:
        self._key = api_key or os.environ.get("STRATA_EIA_API_KEY")
        self._http = httpx.Client(timeout=timeout)
        default_cache = Path.home() / ".strata" / "cache" / "eia"
        self._cache = _DiskCache(cache_dir or default_cache, cache_ttl)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> EIAClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ── internal helpers ─────────────────────────────────────────

    def _base_params(self) -> dict[str, str]:
        """Params required on every EIA request."""
        params: dict[str, str] = {}
        if self._key:
            params["api_key"] = self._key
        return params

    def _cache_key(self, url: str, params: dict[str, str]) -> str:
        parts = [url, json.dumps(params, sort_keys=True)]
        return "|".join(parts)

    def _request_data(
        self,
        route: str,
        params: dict[str, str],
        *,
        kind: str = "data",
    ) -> EIAResponse:
        """Fetch data from ``/v2/{route}/data``."""
        url = f"{_BASE}/{route}/data"
        all_params = {**self._base_params(), **params}
        ck = self._cache_key(url, all_params)

        cached = self._cache.get(ck)
        if cached is not None:
            data, age = cached
            resp = _parse_data_response(data, kind=kind)
            return replace(resp, cached=True, cache_age_seconds=round(age, 1))

        http_resp = self._http.get(url, params=all_params)
        http_resp.raise_for_status()

        raw: dict[str, Any] = http_resp.json()
        response_body: dict[str, Any] = raw.get("response", {})

        # Check for API-level warnings or errors
        raw_warnings: list[Any] = response_body.get("warnings", [])
        for w_entry in raw_warnings:
            w_str = str(w_entry)
            if "error" in w_str.lower():
                raise EIAClientError(f"EIA API error: {w_str}")

        # Check for error response shapes
        if "error" in raw:
            raise EIAClientError(f"EIA API error: {raw.get('error', 'Unknown error')}")

        self._cache.put(ck, raw)
        return _parse_data_response(raw, kind=kind)

    def _request_metadata(self, route: str) -> EIAResponse:
        """Fetch metadata from ``/v2/{route}`` (no /data suffix)."""
        url = f"{_BASE}/{route}"
        all_params = self._base_params()
        ck = self._cache_key(url, all_params)

        cached = self._cache.get(ck)
        if cached is not None:
            data, age = cached
            resp = _parse_metadata_response(data, route=route)
            return replace(resp, cached=True, cache_age_seconds=round(age, 1))

        http_resp = self._http.get(url, params=all_params)
        http_resp.raise_for_status()

        raw: dict[str, Any] = http_resp.json()

        if "error" in raw:
            raise EIAClientError(f"EIA API error: {raw.get('error', 'Unknown error')}")

        self._cache.put(ck, raw)
        return _parse_metadata_response(raw, route=route)

    @staticmethod
    def _build_facets(facets: dict[str, str | list[str]]) -> dict[str, str]:
        """Encode facets into the ``facets[key][]=value`` query format.

        The EIA v2 API expects repeated keys like
        ``facets[sectorId][]=RES&facets[stateId][]=US``.
        httpx handles repeated keys via list values, but for simple
        single-value facets we flatten into the bracket notation that
        the EIA API expects as plain query-string keys.
        """
        params: dict[str, str] = {}
        for key, val in facets.items():
            if isinstance(val, list):
                for i, v in enumerate(val):
                    params[f"facets[{key}][{i}]"] = v
            else:
                params[f"facets[{key}][]"] = val
        return params

    # ── core generic endpoints ───────────────────────────────────

    def get_data(
        self,
        route: str,
        *,
        data_fields: list[str] | None = None,
        facets: dict[str, str | list[str]] | None = None,
        frequency: str | None = None,
        start: str | None = None,
        end: str | None = None,
        sort: list[dict[str, str]] | None = None,
        length: int = 5000,
    ) -> EIAResponse:
        """Core data fetch — any EIA v2 route.

        Args:
            route: EIA route path (e.g. "electricity/retail-sales").
            data_fields: List of data columns (e.g. ["value", "price"]).
            facets: Facet filters (e.g. {"sectorId": "RES"}).
            frequency: "monthly", "quarterly", or "annual".
            start: Start period (e.g. "2020-01").
            end: End period (e.g. "2024-01").
            sort: Sort spec (e.g. [{"column": "period", "direction": "desc"}]).
            length: Max rows to return (up to 5000).
        """
        params: dict[str, str] = {"length": str(length)}

        if data_fields:
            for field in data_fields:
                params["data[]"] = field
        if frequency:
            params["frequency"] = frequency
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if sort:
            for i, s in enumerate(sort):
                col = s.get("column", "period")
                direction = s.get("direction", "desc")
                params[f"sort[{i}][column]"] = col
                params[f"sort[{i}][direction]"] = direction
        if facets:
            params.update(self._build_facets(facets))

        return self._request_data(route, params)

    def get_metadata(self, route: str) -> EIAResponse:
        """Retrieve metadata for an EIA route.

        Args:
            route: EIA route path (e.g. "electricity/retail-sales").
        """
        return self._request_metadata(route)

    # ── electricity endpoints ────────────────────────────────────

    def get_electricity_prices(
        self,
        state: str = "US",
        sector: str = "ALL",
        start: str | None = None,
        end: str | None = None,
        frequency: str = "monthly",
    ) -> EIAResponse:
        """Retail electricity prices (cents per kWh).

        Args:
            state: State code (e.g. "US", "CA", "TX").
            sector: Sector code (RES, COM, IND, TRA, OTH, ALL).
            start: Start period (e.g. "2020-01").
            end: End period (e.g. "2024-01").
            frequency: "monthly", "quarterly", or "annual".
        """
        return self.get_data(
            EIARoute.ELECTRICITY_RETAIL,
            data_fields=["price"],
            facets={"stateId": state, "sectorId": sector},
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    def get_electricity_sales(
        self,
        state: str = "US",
        sector: str = "ALL",
        start: str | None = None,
        end: str | None = None,
        frequency: str = "monthly",
    ) -> EIAResponse:
        """Retail electricity sales volume (million kWh).

        Args:
            state: State code.
            sector: Sector code.
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        return self.get_data(
            EIARoute.ELECTRICITY_RETAIL,
            data_fields=["sales"],
            facets={"stateId": state, "sectorId": sector},
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    def get_electricity_generation(
        self,
        state: str = "US",
        fuel_type: str | None = None,
        start: str | None = None,
        end: str | None = None,
        frequency: str = "monthly",
    ) -> EIAResponse:
        """Electricity generation by fuel type (thousand MWh).

        Args:
            state: State code.
            fuel_type: Fuel type ID (e.g. "SUN", "WND", "NG", "COL").
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        facets: dict[str, str | list[str]] = {"stateId": state}
        if fuel_type:
            facets["fueltypeid"] = fuel_type
        return self.get_data(
            EIARoute.ELECTRICITY_GENERATION,
            data_fields=["generation"],
            facets=facets,
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    def get_electricity_customers(
        self,
        state: str = "US",
        sector: str = "ALL",
        start: str | None = None,
        end: str | None = None,
        frequency: str = "monthly",
    ) -> EIAResponse:
        """Retail electricity customer counts.

        Args:
            state: State code.
            sector: Sector code.
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        return self.get_data(
            EIARoute.ELECTRICITY_RETAIL,
            data_fields=["customers"],
            facets={"stateId": state, "sectorId": sector},
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    # ── petroleum endpoints ──────────────────────────────────────

    def get_petroleum_prices(
        self,
        product: str | None = None,
        start: str | None = None,
        end: str | None = None,
        frequency: str = "monthly",
    ) -> EIAResponse:
        """Petroleum spot prices (dollars per barrel).

        Args:
            product: Product code (e.g. "EPCBRENT" for Brent, "EPCWTI" for WTI).
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        facets: dict[str, str | list[str]] = {}
        if product:
            facets["product"] = product
        return self.get_data(
            EIARoute.PETROLEUM_PRICES,
            data_fields=["value"],
            facets=facets if facets else None,
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    def get_petroleum_supply(
        self,
        product: str | None = None,
        start: str | None = None,
        end: str | None = None,
        frequency: str = "monthly",
    ) -> EIAResponse:
        """Petroleum supply and disposition (thousand barrels per day).

        Args:
            product: Product code.
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        facets: dict[str, str | list[str]] = {}
        if product:
            facets["product"] = product
        return self.get_data(
            EIARoute.PETROLEUM_SUPPLY,
            data_fields=["value"],
            facets=facets if facets else None,
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    # ── natural gas endpoints ────────────────────────────────────

    def get_natural_gas_prices(
        self,
        start: str | None = None,
        end: str | None = None,
        frequency: str = "monthly",
    ) -> EIAResponse:
        """Natural gas prices (dollars per thousand cubic feet).

        Args:
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        return self.get_data(
            EIARoute.NATURAL_GAS_PRICES,
            data_fields=["value"],
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    def get_natural_gas_supply(
        self,
        start: str | None = None,
        end: str | None = None,
        frequency: str = "monthly",
    ) -> EIAResponse:
        """Natural gas supply summary (million cubic feet).

        Args:
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        return self.get_data(
            EIARoute.NATURAL_GAS_SUPPLY,
            data_fields=["value"],
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    # ── coal endpoints ───────────────────────────────────────────

    def get_coal_production(
        self,
        state: str | None = None,
        start: str | None = None,
        end: str | None = None,
        frequency: str = "annual",
    ) -> EIAResponse:
        """Coal mine production (short tons).

        Args:
            state: State code.
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        facets: dict[str, str | list[str]] = {}
        if state:
            facets["stateId"] = state
        return self.get_data(
            EIARoute.COAL_PRODUCTION,
            data_fields=["production"],
            facets=facets if facets else None,
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    # ── total energy endpoints ───────────────────────────────────

    def get_total_energy(
        self,
        series_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
        frequency: str = "monthly",
    ) -> EIAResponse:
        """Monthly Energy Review series.

        Args:
            series_id: MSN code (e.g. "ELETPUS" for total electricity).
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        facets: dict[str, str | list[str]] = {}
        if series_id:
            facets["msn"] = series_id
        return self.get_data(
            EIARoute.TOTAL_ENERGY,
            data_fields=["value"],
            facets=facets if facets else None,
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    def get_energy_consumption(
        self,
        sector: str | None = None,
        start: str | None = None,
        end: str | None = None,
        frequency: str = "monthly",
    ) -> EIAResponse:
        """Energy consumption by sector (trillion Btu).

        Uses the total-energy route with consumption MSN codes.

        Args:
            sector: Sector filter — maps to MSN prefix
                    (e.g. "residential", "commercial", "industrial",
                    "transportation").
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        _sector_msn: dict[str, str] = {
            "residential": "TERCBUS",
            "commercial": "TECCBUS",
            "industrial": "TEICBUS",
            "transportation": "TEACBUS",
        }
        facets: dict[str, str | list[str]] = {}
        if sector:
            msn = _sector_msn.get(sector.lower(), sector)
            facets["msn"] = msn
        return self.get_data(
            EIARoute.TOTAL_ENERGY,
            data_fields=["value"],
            facets=facets if facets else None,
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    # ── renewable / nuclear endpoints ────────────────────────────

    def get_renewable_generation(
        self,
        state: str = "US",
        start: str | None = None,
        end: str | None = None,
        frequency: str = "monthly",
    ) -> EIAResponse:
        """Renewable electricity generation (thousand MWh).

        Fetches wind + solar + hydro + other renewables combined.

        Args:
            state: State code.
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        return self.get_data(
            EIARoute.RENEWABLE,
            data_fields=["generation"],
            facets={
                "stateId": state,
                "fueltypeid": ["SUN", "WND", "WAT", "GEO", "WAS", "OOG"],
            },
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    def get_nuclear_capacity(
        self,
        start: str | None = None,
        end: str | None = None,
        frequency: str = "monthly",
    ) -> EIAResponse:
        """Nuclear power plant outages and capacity data.

        Args:
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        return self.get_data(
            EIARoute.NUCLEAR,
            data_fields=["value"],
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    # ── forecast endpoints ───────────────────────────────────────

    def get_steo_forecast(
        self,
        series_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
        frequency: str = "monthly",
    ) -> EIAResponse:
        """Short-Term Energy Outlook (STEO) forecast.

        Args:
            series_id: STEO series ID (e.g. "PAPR_WORLD" for world oil price).
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        facets: dict[str, str | list[str]] = {}
        if series_id:
            facets["seriesId"] = series_id
        params: dict[str, str] = {
            "frequency": frequency,
            "length": "5000",
            "data[]": "value",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
        }
        if facets:
            params.update(self._build_facets(facets))
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        return self._request_data(
            EIARoute.STEO,
            params,
            kind="forecast",
        )

    # ── international endpoints ──────────────────────────────────

    def get_international_data(
        self,
        country: str | None = None,
        start: str | None = None,
        end: str | None = None,
        frequency: str = "annual",
    ) -> EIAResponse:
        """International energy data.

        Args:
            country: ISO 3166-1 alpha-3 country code (e.g. "USA", "CHN").
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        facets: dict[str, str | list[str]] = {}
        if country:
            facets["countryRegionId"] = country
        return self.get_data(
            EIARoute.INTERNATIONAL,
            data_fields=["value"],
            facets=facets if facets else None,
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    # ── comparison / breakdown convenience ───────────────────────

    def get_state_comparison(
        self,
        states: list[str],
        data_field: str = "price",
        start: str | None = None,
        end: str | None = None,
        frequency: str = "annual",
    ) -> EIAResponse:
        """Compare electricity data across multiple states.

        Args:
            states: List of state codes (e.g. ["CA", "TX", "NY"]).
            data_field: Data column to fetch (price, sales, revenue, customers).
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        return self.get_data(
            EIARoute.ELECTRICITY_RETAIL,
            data_fields=[data_field],
            facets={"stateId": states, "sectorId": "ALL"},
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    def get_sector_breakdown(
        self,
        state: str = "US",
        start: str | None = None,
        end: str | None = None,
        frequency: str = "annual",
    ) -> EIAResponse:
        """Electricity price/sales breakdown by sector for a state.

        Returns data for RES, COM, IND, and TRA sectors.

        Args:
            state: State code.
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        return self.get_data(
            EIARoute.ELECTRICITY_RETAIL,
            data_fields=["price", "sales", "revenue", "customers"],
            facets={
                "stateId": state,
                "sectorId": ["RES", "COM", "IND", "TRA"],
            },
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    # ── capacity / capital-stock endpoints ───────────────────────

    def get_generator_capacity(
        self,
        fuel: str | None = None,
        state: str | None = None,
        status: str | None = None,
        start: str | None = None,
        end: str | None = None,
        frequency: str = "monthly",
    ) -> EIAResponse:
        """Operating generator nameplate capacity (megawatts).

        Args:
            fuel: Energy-source code (e.g. "SUN", "WND", "NG").
            state: State (plant) code.
            status: Plant status code (e.g. "OP"=operating, "P"=planned).
            start: Start period (YYYY-MM).
            end: End period.
            frequency: Observation frequency.
        """
        facets: dict[str, str | list[str]] = {}
        if fuel:
            facets["energy_source_code"] = fuel
        if state:
            facets["stateid"] = state
        if status:
            facets["status"] = status
        return self.get_data(
            EIARoute.GENERATOR_CAPACITY,
            data_fields=["nameplate-capacity-mw", "net-summer-capacity-mw"],
            facets=facets if facets else None,
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    def get_electricity_capacity_factor(
        self,
        plant_type: str | None = None,
        state: str = "US",
        start: str | None = None,
        end: str | None = None,
        frequency: str = "monthly",
    ) -> EIAResponse:
        """Electricity capacity factor by plant/fuel type.

        Derived from the electric-power-operational-data route's
        ``capacity-factor`` field.

        Args:
            plant_type: Fuel-type ID (e.g. "SUN", "WND", "NG", "NUC").
            state: State code.
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        facets: dict[str, str | list[str]] = {"location": state}
        if plant_type:
            facets["fueltypeid"] = plant_type
        return self.get_data(
            EIARoute.ELECTRICITY_GENERATION,
            data_fields=["capacity-factor"],
            facets=facets,
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    # ── transportation / EV endpoints ────────────────────────────

    def get_ev_sales_stock(
        self,
        metric: str = "stock",
        region: str | None = None,
        start: str | None = None,
        end: str | None = None,
        frequency: str = "annual",
    ) -> EIAResponse:
        """Electric-vehicle sales or stock from the International route.

        EV adoption data is published under the international energy route
        with EV-specific product/activity facets.

        Args:
            metric: "stock" (vehicles on the road) or "sales" (new units).
            region: Country/region code (e.g. "USA", "WORL").
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        facets: dict[str, str | list[str]] = {"productId": "33"}
        if region:
            facets["countryRegionId"] = region
        if metric.lower() == "sales":
            facets["activityId"] = "10"
        else:
            facets["activityId"] = "33"
        return self.get_data(
            EIARoute.INTERNATIONAL,
            data_fields=["value"],
            facets=facets,
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    # ── emissions endpoints ───────────────────────────────────────

    def get_co2_emissions(
        self,
        sector: str | None = None,
        fuel: str | None = None,
        state: str | None = None,
        start: str | None = None,
        end: str | None = None,
        frequency: str = "annual",
    ) -> EIAResponse:
        """Energy-related CO2 emissions (million metric tons).

        Args:
            sector: Sector ID (e.g. "TT"=total, "EC"=electric power).
            fuel: Fuel ID (e.g. "TO"=all fuels, "CO"=coal, "NG"=natural gas).
            state: State code.
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        facets: dict[str, str | list[str]] = {}
        if sector:
            facets["sectorId"] = sector
        if fuel:
            facets["fuelId"] = fuel
        if state:
            facets["stateId"] = state
        return self.get_data(
            EIARoute.CO2_EMISSIONS,
            data_fields=["value"],
            facets=facets if facets else None,
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    # ── consumption endpoints ─────────────────────────────────────

    def get_petroleum_consumption(
        self,
        product: str | None = None,
        region: str | None = None,
        start: str | None = None,
        end: str | None = None,
        frequency: str = "monthly",
    ) -> EIAResponse:
        """Petroleum product supplied / consumption (thousand barrels per day).

        Args:
            product: Product code (e.g. "EPM0"=motor gasoline, "EPD2D"=diesel).
            region: Region/PADD code (duoarea).
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        facets: dict[str, str | list[str]] = {}
        if product:
            facets["product"] = product
        if region:
            facets["duoarea"] = region
        return self.get_data(
            EIARoute.PETROLEUM_CONSUMPTION,
            data_fields=["value"],
            facets=facets if facets else None,
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    def get_natural_gas_consumption(
        self,
        end_use: str | None = None,
        state: str | None = None,
        start: str | None = None,
        end: str | None = None,
        frequency: str = "monthly",
    ) -> EIAResponse:
        """Natural gas consumption by end use (million cubic feet).

        Args:
            end_use: Process/end-use code (e.g. "VRS"=residential,
                "VCS"=commercial, "VIN"=industrial, "VEU"=electric power).
            state: State code (duoarea).
            start: Start period.
            end: End period.
            frequency: Observation frequency.
        """
        facets: dict[str, str | list[str]] = {}
        if end_use:
            facets["process"] = end_use
        if state:
            facets["duoarea"] = state
        return self.get_data(
            EIARoute.NATURAL_GAS_CONSUMPTION,
            data_fields=["value"],
            facets=facets if facets else None,
            frequency=frequency,
            start=start,
            end=end,
            sort=[{"column": "period", "direction": "desc"}],
        )

    # ── projection endpoints ──────────────────────────────────────

    def get_aeo_projection(
        self,
        series_id: str | None = None,
        scenario: str = "ref2023",
        aeo_year: str = "2023",
        start: str | None = None,
        end: str | None = None,
    ) -> EIAResponse:
        """Annual Energy Outlook (AEO) long-term projection.

        The AEO route is versioned by release year
        (``aeo/{year}/data``) and filtered by a scenario case.

        Args:
            series_id: AEO series ID to filter on.
            scenario: Case ID (e.g. "ref2023"=reference case).
            aeo_year: AEO release year.
            start: Start period.
            end: End period.
        """
        facets: dict[str, str | list[str]] = {"scenario": scenario}
        if series_id:
            facets["seriesId"] = series_id
        params: dict[str, str] = {
            "length": "5000",
            "data[]": "value",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
        }
        params.update(self._build_facets(facets))
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        return self._request_data(f"aeo/{aeo_year}", params, kind="forecast")

    # ── cache management ─────────────────────────────────────────

    def clear_cache(self) -> int:
        """Remove all cached EIA responses. Returns count deleted."""
        return self._cache.clear()


# ═══════════════════════════════════════════════════════════════════
# Strata format converters
# ═══════════════════════════════════════════════════════════════════


def _pick_data_point(
    data_points: tuple[EIADataPoint, ...],
    year: int | None,
) -> EIADataPoint:
    """Select a specific period's data point, preferring the requested year."""
    non_null = [dp for dp in data_points if dp.value is not None]

    if year is not None:
        year_str = str(year)
        match = next((dp for dp in non_null if dp.period.startswith(year_str)), None)
        if match is not None:
            return match

    if non_null:
        # EIA returns most-recent first when sorted desc; pick the latest
        return non_null[0]

    if data_points:
        return data_points[0]

    raise EIAClientError("No data points to convert")


def _snapshot_hash(
    route: str,
    period: str,
    state: str,
    sector: str,
    value: float | None,
) -> str:
    """Content-hash a data point for source pinning (Q5)."""
    content = json.dumps(
        {
            "route": route,
            "period": period,
            "state": state,
            "sector": sector,
            "value": value,
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()


def datapoint_to_primitive_yaml(
    data_points: tuple[EIADataPoint, ...],
    *,
    route: str,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    source_url: str,
    year: int | None = None,
    geo_codes: tuple[str, ...] = ("US",),
    geo_level: str = "country",
    geo_perspective: str = "supply",
    unit_kind: str = "stock",
    unit_dimension: str = "energy",
    unit_denominator: str | None = None,
    unit_currency: str | None = None,
    distribution_shape: str = "normal",
    delivery_mode: str = "n/a",
) -> dict[str, Any]:
    """Convert EIA data points to a Strata AtomicPrimitive YAML dict.

    Returns a dict ready for ``yaml.dump()`` that conforms to the
    AtomicPrimitive schema (models/primitive.py).
    """
    dp = _pick_data_point(data_points, year)
    route_slug = route.replace("/", "-").lower()
    state_slug = dp.state.lower() if dp.state else "us"
    period_slug = dp.period.replace("-", "")
    source_slug = f"eia-{route_slug}-{state_slug}-{period_slug}"
    sha = _snapshot_hash(route, dp.period, dp.state, dp.sector, dp.value)

    unit: dict[str, str] = {"kind": unit_kind, "dimension": unit_dimension}
    if unit_denominator:
        unit["denominator"] = unit_denominator
    if unit_currency:
        unit["currency"] = unit_currency

    # Derive as_of from the period (YYYY-MM or YYYY)
    as_of = dp.period
    if len(as_of) == 4:
        as_of = f"{as_of}-12-31"
    elif len(as_of) == 7:
        as_of = f"{as_of}-01"

    return {
        "kind": "atomic_primitive",
        "slug": primitive_slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": name,
        "description": description,
        "value": dp.value,
        "unit": unit,
        "as_of": as_of,
        "geo": {"level": geo_level, "codes": list(geo_codes)},
        "geo_perspective": geo_perspective,
        "distribution_shape": distribution_shape,
        "delivery_mode": delivery_mode,
        "source": {
            "slug": source_slug,
            "tier": "regulator",
            "url": source_url,
            "accessed": date.today().isoformat(),
            "snapshot_sha256": sha,
        },
    }


def datapoint_to_source_yaml(
    data_points: tuple[EIADataPoint, ...],
    *,
    route: str,
    source_url: str,
    year: int,
    description: str = "",
) -> dict[str, Any]:
    """Convert EIA data points to a Strata source_registry YAML dict."""
    dp = _pick_data_point(data_points, year)
    route_slug = route.replace("/", "-").lower()
    state_slug = dp.state.lower() if dp.state else "us"
    period_slug = dp.period.replace("-", "")
    source_slug = f"eia-{route_slug}-{state_slug}-{period_slug}"
    sha = _snapshot_hash(route, dp.period, dp.state, dp.sector, dp.value)

    return {
        "kind": "source_registry",
        "slug": source_slug,
        "tier": "regulator",
        "url": source_url,
        "accessed": date.today().isoformat(),
        "snapshot_sha256": sha,
        "description": description
        or (f"EIA {route} for {dp.state_name or dp.state}, {dp.period} data."),
    }


def capabilities() -> list[CapabilitySpec]:
    """Methods exposed to the LLM router (spec §5)."""
    from ._capability import CapabilityArg, CapabilitySpec

    return [
        CapabilitySpec(
            connector="eia",
            method="get_electricity_prices",
            description="Average retail electricity price by state/sector.",
            returns="atomic primitive, unit=currency USD per MWh, tier=regulator",
            args=[
                CapabilityArg(
                    name="state",
                    type="str",
                    description="US state code or 'US'",
                    example="US",
                ),
                CapabilityArg(
                    name="sector",
                    type="str",
                    description="Sector (RES/COM/IND/ALL)",
                    example="ALL",
                ),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="eia",
            method="get_electricity_sales",
            description="Retail electricity sales in MWh.",
            returns="atomic primitive, unit=count MWh, tier=regulator",
            args=[
                CapabilityArg(
                    name="state",
                    type="str",
                    description="US state code or 'US'",
                    example="US",
                ),
                CapabilityArg(
                    name="sector",
                    type="str",
                    description="Sector (RES/COM/IND/ALL)",
                    example="ALL",
                ),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="eia",
            method="get_electricity_generation",
            description="Electricity generation by fuel type (thousand MWh).",
            returns="atomic primitive, unit=count MWh, tier=regulator",
            args=[
                CapabilityArg(
                    name="state", type="str", description="US state code or 'US'", example="US"
                ),
                CapabilityArg(
                    name="fuel_type",
                    type="str",
                    description="Fuel ID (SUN/WND/NG/COL)",
                    example="SUN",
                    required=False,
                ),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="eia",
            method="get_generator_capacity",
            description=(
                "Operating generator nameplate / net-summer capacity in MW by fuel and state. "
                "Energy capital-stock anchor."
            ),
            returns="atomic primitive, unit=power MW, tier=regulator",
            args=[
                CapabilityArg(
                    name="fuel",
                    type="str",
                    description="Energy-source code (SUN/WND/NG)",
                    example="SUN",
                    required=False,
                ),
                CapabilityArg(
                    name="state",
                    type="str",
                    description="Plant state code",
                    example="CA",
                    required=False,
                ),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="eia",
            method="get_electricity_capacity_factor",
            description="Electricity capacity factor by plant/fuel type.",
            returns="atomic primitive, unit=ratio, tier=regulator",
            args=[
                CapabilityArg(
                    name="plant_type",
                    type="str",
                    description="Fuel type ID (SUN/WND/NUC)",
                    example="SUN",
                    required=False,
                ),
                CapabilityArg(
                    name="state",
                    type="str",
                    description="State code or 'US'",
                    example="US",
                    required=False,
                ),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="eia",
            method="get_petroleum_prices",
            description="Petroleum spot prices (USD per barrel).",
            returns="atomic primitive, unit=USD per barrel, tier=regulator",
            args=[
                CapabilityArg(
                    name="product",
                    type="str",
                    description="Product code (EPCBRENT/EPCWTI)",
                    example="EPCWTI",
                    required=False,
                ),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="eia",
            method="get_petroleum_consumption",
            description="Petroleum product supplied / consumption (thousand barrels/day).",
            returns="atomic primitive, unit=barrels per day, tier=regulator",
            args=[
                CapabilityArg(
                    name="product",
                    type="str",
                    description="Product code (EPM0=gasoline)",
                    example="EPM0",
                    required=False,
                ),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="eia",
            method="get_natural_gas_prices",
            description="Natural gas prices (USD per thousand cubic feet).",
            returns="atomic primitive, unit=USD per mcf, tier=regulator",
            args=[],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="eia",
            method="get_natural_gas_consumption",
            description="Natural gas consumption by end use (million cubic feet).",
            returns="atomic primitive, unit=cubic feet, tier=regulator",
            args=[
                CapabilityArg(
                    name="end_use",
                    type="str",
                    description="End-use code (VRS/VCS/VIN/VEU)",
                    example="VEU",
                    required=False,
                ),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="eia",
            method="get_co2_emissions",
            description="Energy-related CO2 emissions (million metric tons) by sector/fuel/state.",
            returns="atomic primitive, unit=metric tons CO2, tier=regulator",
            args=[
                CapabilityArg(
                    name="sector",
                    type="str",
                    description="Sector ID (TT=total, EC=electric)",
                    example="TT",
                    required=False,
                ),
                CapabilityArg(
                    name="fuel",
                    type="str",
                    description="Fuel ID (TO=all, CO=coal)",
                    example="TO",
                    required=False,
                ),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="eia",
            method="get_ev_sales_stock",
            description="Electric-vehicle stock or sales by region (international route).",
            returns="atomic primitive, unit=vehicles, tier=regulator",
            args=[
                CapabilityArg(
                    name="metric",
                    type="str",
                    description="stock|sales",
                    example="stock",
                    required=False,
                ),
                CapabilityArg(
                    name="region",
                    type="str",
                    description="Country/region code",
                    example="USA",
                    required=False,
                ),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="eia",
            method="get_total_energy",
            description="Monthly Energy Review series (total primary energy aggregates).",
            returns="atomic primitive, unit varies (trillion Btu), tier=regulator",
            args=[
                CapabilityArg(
                    name="series_id",
                    type="str",
                    description="MSN code (ELETPUS)",
                    example="ELETPUS",
                    required=False,
                ),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="eia",
            method="get_steo_forecast",
            description="Short-Term Energy Outlook forecast series.",
            returns="forecast point, unit varies, tier=regulator",
            args=[
                CapabilityArg(
                    name="series_id",
                    type="str",
                    description="STEO series ID",
                    example="PAPR_WORLD",
                    required=False,
                ),
            ],
            source_tier="regulator",
            is_fragile=True,
        ),
        CapabilitySpec(
            connector="eia",
            method="get_aeo_projection",
            description="Annual Energy Outlook long-term projection by scenario.",
            returns="forecast point, unit varies, tier=regulator",
            args=[
                CapabilityArg(
                    name="series_id",
                    type="str",
                    description="AEO series ID",
                    example="cons_NA_elep",
                    required=False,
                ),
                CapabilityArg(
                    name="scenario",
                    type="str",
                    description="Case ID (ref2023)",
                    example="ref2023",
                    required=False,
                ),
            ],
            source_tier="regulator",
            is_fragile=True,
        ),
    ]


from ._capability import CapabilitySpec as CapabilitySpec  # noqa: E402
