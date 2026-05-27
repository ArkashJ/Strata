"""USDA NASS QuickStats API client.

Typed wrappers for the USDA National Agricultural Statistics Service
QuickStats API with disk caching and conversion to Strata
AtomicPrimitive / Source YAML format.

API reference: https://quickstats.nass.usda.gov/api
Rate limits: 50 requests/day per API key.
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
from typing import Any, NotRequired, TypedDict, cast

import httpx

# ═══════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════


class NASSSource(StrEnum):
    """Data source programs."""

    SURVEY = "SURVEY"
    CENSUS = "CENSUS"


class NASSSector(StrEnum):
    """Sector categories."""

    CROPS = "CROPS"
    ANIMALS_AND_PRODUCTS = "ANIMALS & PRODUCTS"
    ECONOMICS = "ECONOMICS"
    DEMOGRAPHICS = "DEMOGRAPHICS"
    ENVIRONMENTAL = "ENVIRONMENTAL"


class NASSFrequency(StrEnum):
    """Observation frequency."""

    ANNUAL = "ANNUAL"
    MONTHLY = "MONTHLY"
    WEEKLY = "WEEKLY"
    POINT_IN_TIME = "POINT IN TIME"


class NASSAggLevel(StrEnum):
    """Geographic aggregation level."""

    NATIONAL = "NATIONAL"
    STATE = "STATE"
    COUNTY = "COUNTY"
    REGION = "REGION : MULTI-STATE"
    WATERSHED = "WATERSHED"
    ZIP_CODE = "ZIP CODE"


class NASSCommodity(StrEnum):
    """Common agricultural commodities."""

    CORN = "CORN"
    SOYBEANS = "SOYBEANS"
    WHEAT = "WHEAT"
    COTTON = "COTTON"
    RICE = "RICE"
    CATTLE = "CATTLE"
    HOGS = "HOGS"
    CHICKENS = "CHICKENS"
    MILK = "MILK"
    EGGS = "EGGS"
    HAY = "HAY"
    TOBACCO = "TOBACCO"
    SUGAR = "SUGAR"
    VEGETABLES = "VEGETABLES"
    FRUITS = "FRUITS"


class NASSStatistic(StrEnum):
    """Statistical category descriptors."""

    PRODUCTION = "PRODUCTION"
    AREA_HARVESTED = "AREA HARVESTED"
    AREA_PLANTED = "AREA PLANTED"
    YIELD = "YIELD"
    PRICE_RECEIVED = "PRICE RECEIVED"
    HEAD = "HEAD"
    INVENTORY = "INVENTORY"
    SALES = "SALES"
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    VALUE_OF_PRODUCTION = "VALUE OF PRODUCTION"


# ═══════════════════════════════════════════════════════════════════
# TypedDicts — raw NASS JSON response shapes
# ═══════════════════════════════════════════════════════════════════


class NASSRecordRaw(TypedDict, total=False):
    source_desc: str
    sector_desc: str
    group_desc: str
    commodity_desc: str
    class_desc: str
    prodn_practice_desc: str
    util_practice_desc: str
    statisticcat_desc: str
    unit_desc: str
    short_desc: str
    domain_desc: str
    domaincat_desc: str
    agg_level_desc: str
    state_alpha: str
    state_name: str
    state_fips_code: str
    county_name: str
    county_code: str
    year: int
    freq_desc: str
    begin_code: int
    end_code: int
    reference_period_desc: str
    Value: str
    CV: NotRequired[str]


class NASSResponseRaw(TypedDict):
    data: list[NASSRecordRaw]


class NASSCountResponseRaw(TypedDict):
    count: int


class NASSParamValuesRaw(TypedDict):
    # Keys are dynamic param names, each mapping to a dict with the param name
    # pointing to a list of strings. Example: {"commodity_desc": ["CORN", ...]}
    pass


# ═══════════════════════════════════════════════════════════════════
# Dataclasses — validated internal models
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class NASSRecord:
    """A single data record from the NASS QuickStats API."""

    source: str
    sector: str
    group: str
    commodity: str
    class_desc: str
    prodn_practice: str
    util_practice: str
    statistic_category: str
    unit: str
    short_desc: str
    domain: str
    domaincat: str
    agg_level: str
    state_alpha: str
    state_name: str
    state_fips: str
    county_name: str
    county_code: str
    year: int
    frequency: str
    reference_period: str
    value: float | None
    cv_pct: str


@dataclass(frozen=True, slots=True)
class NASSParamValues:
    """Valid values for a NASS API parameter."""

    param_name: str
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NASSResponse:
    """Standard return type for every NASS client call."""

    kind: str
    records: tuple[NASSRecord, ...] = ()
    param_values: tuple[NASSParamValues, ...] = ()
    count: int = 0
    total: int = 0
    cached: bool = False
    cache_age_seconds: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# Response parsing
# ═══════════════════════════════════════════════════════════════════

# Sentinel values the NASS API uses instead of numeric data
_SUPPRESSED_VALUES: frozenset[str] = frozenset(
    {
        "(D)",  # Withheld to avoid disclosing data for individual operations
        "(NA)",  # Not available
        "(Z)",  # Less than half the rounding unit
        "(S)",  # Insufficient number of observations
        "(H)",  # Suppressed due to CV threshold
        "(X)",  # Not applicable
        "",  # Empty string
    }
)


def _parse_value(raw_value: str) -> float | None:
    """Parse a NASS value string to float, handling comma formatting and sentinels."""
    stripped = raw_value.strip()
    if stripped in _SUPPRESSED_VALUES:
        return None
    try:
        return float(stripped.replace(",", ""))
    except (ValueError, TypeError):
        return None


def _parse_record(raw: dict[str, Any]) -> NASSRecord:
    """Parse a single NASS data record from the API response."""
    raw_value = str(raw.get("Value", ""))
    raw_cv = str(raw.get("CV (%)", raw.get("CV", "")))

    return NASSRecord(
        source=str(raw.get("source_desc", "")),
        sector=str(raw.get("sector_desc", "")),
        group=str(raw.get("group_desc", "")),
        commodity=str(raw.get("commodity_desc", "")),
        class_desc=str(raw.get("class_desc", "")),
        prodn_practice=str(raw.get("prodn_practice_desc", "")),
        util_practice=str(raw.get("util_practice_desc", "")),
        statistic_category=str(raw.get("statisticcat_desc", "")),
        unit=str(raw.get("unit_desc", "")),
        short_desc=str(raw.get("short_desc", "")),
        domain=str(raw.get("domain_desc", "")),
        domaincat=str(raw.get("domaincat_desc", "")),
        agg_level=str(raw.get("agg_level_desc", "")),
        state_alpha=str(raw.get("state_alpha", "")),
        state_name=str(raw.get("state_name", "")),
        state_fips=str(raw.get("state_fips_code", "")),
        county_name=str(raw.get("county_name", "")),
        county_code=str(raw.get("county_code", "")),
        year=int(raw.get("year", 0)),
        frequency=str(raw.get("freq_desc", "")),
        reference_period=str(raw.get("reference_period_desc", "")),
        value=_parse_value(raw_value),
        cv_pct=raw_cv,
    )


def _parse_data_response(raw: dict[str, Any]) -> NASSResponse:
    """Parse a data response from the api_GET endpoint."""
    data: list[dict[str, Any]] = raw.get("data", [])
    records = tuple(_parse_record(r) for r in data)
    return NASSResponse(
        kind="data",
        records=records,
        count=len(records),
        total=len(records),
    )


def _parse_count_response(raw: dict[str, Any]) -> NASSResponse:
    """Parse a count response from the get_counts endpoint."""
    count_val = int(raw.get("count", 0))
    return NASSResponse(
        kind="count",
        count=count_val,
        total=count_val,
    )


def _parse_param_values_response(
    raw: dict[str, Any],
    param_name: str,
) -> NASSResponse:
    """Parse a param values response from the get_param_values endpoint."""
    # Response format: {param_name: ["val1", "val2", ...]}
    values_list: list[str] = raw.get(param_name, [])
    pv = NASSParamValues(
        param_name=param_name,
        values=tuple(str(v) for v in values_list),
    )
    return NASSResponse(
        kind="param_values",
        param_values=(pv,),
        count=len(values_list),
        total=len(values_list),
    )


# ═══════════════════════════════════════════════════════════════════
# Disk cache
# ═══════════════════════════════════════════════════════════════════


class _DiskCache:
    """JSON-on-disk cache keyed by request hash, with configurable TTL."""

    def __init__(self, directory: Path, ttl_seconds: int = 604800) -> None:
        self._dir = directory
        self._ttl = ttl_seconds
        self._dir.mkdir(parents=True, exist_ok=True)

    def _key(self, params: str) -> str:
        return hashlib.sha256(params.encode()).hexdigest()[:16]

    def _path(self, key: str) -> Path:
        return self._dir / f"nass_{key}.json"

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
        for f in self._dir.glob("nass_*.json"):
            f.unlink()
            count += 1
        return count


# ═══════════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════════

_BASE = "https://quickstats.nass.usda.gov/api"


class NASSClientError(RuntimeError):
    """Raised on NASS API errors or client-side validation failures."""


class NASSClient:
    """Typed client for the USDA NASS QuickStats API with disk caching.

    Usage::

        client = NASSClient(api_key="your-key")
        resp = client.get_production(NASSCommodity.CORN, year=2023)
        for r in resp.records:
            print(r.year, r.value, r.unit)

    The API key can also be set via the ``STRATA_USDA_NASS_API_KEY``
    environment variable.
    """

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: Path | None = None,
        cache_ttl: int = 604800,
        timeout: float = 30.0,
    ) -> None:
        self._key = api_key or os.environ.get("STRATA_USDA_NASS_API_KEY", "")
        if not self._key:
            raise NASSClientError(
                "NASS API key required. Pass api_key= or set "
                "STRATA_USDA_NASS_API_KEY environment variable."
            )
        self._http = httpx.Client(timeout=timeout)
        default_cache = Path.home() / ".strata" / "cache" / "nass"
        self._cache = _DiskCache(cache_dir or default_cache, cache_ttl)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> NASSClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ── internal helpers ─────────────────────────────────────────

    def _base_params(self) -> dict[str, str]:
        """Params required on every NASS request."""
        return {"key": self._key, "format": "JSON"}

    def _cache_key(self, url: str, params: dict[str, str]) -> str:
        # Exclude the API key from cache keys for portability
        filtered = {k: v for k, v in sorted(params.items()) if k != "key"}
        parts = [url, json.dumps(filtered, sort_keys=True)]
        return "|".join(parts)

    def _request(
        self,
        endpoint: str,
        params: dict[str, str],
        *,
        kind: str,
        param_name: str = "",
    ) -> NASSResponse:
        url = f"{_BASE}/{endpoint}"
        all_params = {**self._base_params(), **params}
        ck = self._cache_key(url, all_params)

        cached = self._cache.get(ck)
        if cached is not None:
            data, age = cached
            if kind == "data":
                resp = _parse_data_response(data)
            elif kind == "count":
                resp = _parse_count_response(data)
            elif kind == "param_values":
                resp = _parse_param_values_response(data, param_name)
            else:
                resp = _parse_data_response(data)
            return replace(resp, cached=True, cache_age_seconds=round(age, 1))

        http_resp = self._http.get(url, params=all_params)
        http_resp.raise_for_status()

        body: Any = http_resp.json()

        if not isinstance(body, dict):
            raise NASSClientError(f"NASS API returned unexpected type: {type(body).__name__}")

        body_dict = cast(dict[str, Any], body)

        # Check for API error messages
        if "error" in body_dict:
            err_list: list[str] = body_dict["error"]
            raise NASSClientError(f"NASS API error: {'; '.join(str(e) for e in err_list)}")

        self._cache.put(ck, body_dict)

        if kind == "data":
            return _parse_data_response(body_dict)
        if kind == "count":
            return _parse_count_response(body_dict)
        if kind == "param_values":
            return _parse_param_values_response(body_dict, param_name)
        return _parse_data_response(body_dict)

    def _build_query_params(
        self,
        *,
        source: str | NASSSource | None = None,
        sector: str | NASSSector | None = None,
        group: str | None = None,
        commodity: str | NASSCommodity | None = None,
        statistic: str | NASSStatistic | None = None,
        unit: str | None = None,
        domain: str | None = None,
        agg_level: str | NASSAggLevel | None = None,
        state_alpha: str | None = None,
        state_name: str | None = None,
        county_name: str | None = None,
        year: int | None = None,
        frequency: str | NASSFrequency | None = None,
        reference_period: str | None = None,
    ) -> dict[str, str]:
        """Build query parameter dict from keyword arguments."""
        params: dict[str, str] = {}
        if source is not None:
            params["source_desc"] = str(source)
        if sector is not None:
            params["sector_desc"] = str(sector)
        if group is not None:
            params["group_desc"] = group
        if commodity is not None:
            params["commodity_desc"] = str(commodity)
        if statistic is not None:
            params["statisticcat_desc"] = str(statistic)
        if unit is not None:
            params["unit_desc"] = unit
        if domain is not None:
            params["domain_desc"] = domain
        if agg_level is not None:
            params["agg_level_desc"] = str(agg_level)
        if state_alpha is not None:
            params["state_alpha"] = state_alpha
        if state_name is not None:
            params["state_name"] = state_name
        if county_name is not None:
            params["county_name"] = county_name
        if year is not None:
            params["year"] = str(year)
        if frequency is not None:
            params["freq_desc"] = str(frequency)
        if reference_period is not None:
            params["reference_period_desc"] = reference_period
        return params

    # ── core API endpoints ───────────────────────────────────────

    def get_data(
        self,
        *,
        source: str | NASSSource | None = None,
        sector: str | NASSSector | None = None,
        group: str | None = None,
        commodity: str | NASSCommodity | None = None,
        statistic: str | NASSStatistic | None = None,
        unit: str | None = None,
        domain: str | None = None,
        agg_level: str | NASSAggLevel | None = None,
        state_alpha: str | None = None,
        state_name: str | None = None,
        county_name: str | None = None,
        year: int | None = None,
        frequency: str | NASSFrequency | None = None,
        reference_period: str | None = None,
    ) -> NASSResponse:
        """Fetch data records from the NASS QuickStats api_GET endpoint.

        At least one filter parameter should be provided to avoid
        exceeding the 50,000 record limit.
        """
        params = self._build_query_params(
            source=source,
            sector=sector,
            group=group,
            commodity=commodity,
            statistic=statistic,
            unit=unit,
            domain=domain,
            agg_level=agg_level,
            state_alpha=state_alpha,
            state_name=state_name,
            county_name=county_name,
            year=year,
            frequency=frequency,
            reference_period=reference_period,
        )
        return self._request("api_GET", params, kind="data")

    def get_counts(
        self,
        *,
        source: str | NASSSource | None = None,
        sector: str | NASSSector | None = None,
        group: str | None = None,
        commodity: str | NASSCommodity | None = None,
        statistic: str | NASSStatistic | None = None,
        unit: str | None = None,
        domain: str | None = None,
        agg_level: str | NASSAggLevel | None = None,
        state_alpha: str | None = None,
        state_name: str | None = None,
        county_name: str | None = None,
        year: int | None = None,
        frequency: str | NASSFrequency | None = None,
        reference_period: str | None = None,
    ) -> NASSResponse:
        """Return the count of records matching the given filters.

        Useful for pre-checking query size before fetching full data,
        since api_GET is capped at 50,000 records per request.
        """
        params = self._build_query_params(
            source=source,
            sector=sector,
            group=group,
            commodity=commodity,
            statistic=statistic,
            unit=unit,
            domain=domain,
            agg_level=agg_level,
            state_alpha=state_alpha,
            state_name=state_name,
            county_name=county_name,
            year=year,
            frequency=frequency,
            reference_period=reference_period,
        )
        return self._request("get_counts", params, kind="count")

    def get_param_values(self, param_name: str) -> NASSResponse:
        """Retrieve all valid values for a given API parameter.

        Args:
            param_name: Parameter name, e.g. ``"commodity_desc"``,
                ``"state_alpha"``, ``"statisticcat_desc"``.
        """
        params = {"param": param_name}
        return self._request(
            "get_param_values",
            params,
            kind="param_values",
            param_name=param_name,
        )

    # ── convenience query methods ────────────────────────────────

    def get_production(
        self,
        commodity: str | NASSCommodity,
        *,
        year: int | None = None,
        state: str | None = None,
        agg_level: str | NASSAggLevel = NASSAggLevel.NATIONAL,
    ) -> NASSResponse:
        """Fetch production data for a commodity.

        Args:
            commodity: Commodity name (e.g. ``NASSCommodity.CORN``).
            year: Filter to a specific year.
            state: Two-letter state code (e.g. ``"IA"``).
            agg_level: Geographic aggregation level.
        """
        return self.get_data(
            commodity=commodity,
            statistic=NASSStatistic.PRODUCTION,
            agg_level=agg_level,
            year=year,
            state_alpha=state,
            frequency=NASSFrequency.ANNUAL,
            reference_period="YEAR",
        )

    def get_acreage(
        self,
        commodity: str | NASSCommodity,
        *,
        year: int | None = None,
        state: str | None = None,
        planted: bool = True,
        agg_level: str | NASSAggLevel = NASSAggLevel.NATIONAL,
    ) -> NASSResponse:
        """Fetch area planted or area harvested for a commodity.

        Args:
            commodity: Commodity name.
            year: Filter to a specific year.
            state: Two-letter state code.
            planted: If True, fetch area planted; if False, area harvested.
            agg_level: Geographic aggregation level.
        """
        stat = NASSStatistic.AREA_PLANTED if planted else NASSStatistic.AREA_HARVESTED
        return self.get_data(
            commodity=commodity,
            statistic=stat,
            agg_level=agg_level,
            year=year,
            state_alpha=state,
            frequency=NASSFrequency.ANNUAL,
            reference_period="YEAR",
        )

    def get_yield(
        self,
        commodity: str | NASSCommodity,
        *,
        year: int | None = None,
        state: str | None = None,
        agg_level: str | NASSAggLevel = NASSAggLevel.NATIONAL,
    ) -> NASSResponse:
        """Fetch crop yield data for a commodity.

        Args:
            commodity: Commodity name.
            year: Filter to a specific year.
            state: Two-letter state code.
            agg_level: Geographic aggregation level.
        """
        return self.get_data(
            commodity=commodity,
            statistic=NASSStatistic.YIELD,
            agg_level=agg_level,
            year=year,
            state_alpha=state,
            frequency=NASSFrequency.ANNUAL,
            reference_period="YEAR",
        )

    def get_prices(
        self,
        commodity: str | NASSCommodity,
        *,
        year: int | None = None,
        state: str | None = None,
        agg_level: str | NASSAggLevel = NASSAggLevel.NATIONAL,
    ) -> NASSResponse:
        """Fetch prices received by farmers for a commodity.

        Args:
            commodity: Commodity name.
            year: Filter to a specific year.
            state: Two-letter state code.
            agg_level: Geographic aggregation level.
        """
        return self.get_data(
            commodity=commodity,
            statistic=NASSStatistic.PRICE_RECEIVED,
            agg_level=agg_level,
            year=year,
            state_alpha=state,
            frequency=NASSFrequency.ANNUAL,
            reference_period="YEAR",
        )

    def get_livestock_inventory(
        self,
        commodity: str | NASSCommodity,
        *,
        year: int | None = None,
        state: str | None = None,
        agg_level: str | NASSAggLevel = NASSAggLevel.NATIONAL,
    ) -> NASSResponse:
        """Fetch livestock inventory (head count) for a commodity.

        Args:
            commodity: Livestock commodity (e.g. ``NASSCommodity.CATTLE``).
            year: Filter to a specific year.
            state: Two-letter state code.
            agg_level: Geographic aggregation level.
        """
        return self.get_data(
            sector=NASSSector.ANIMALS_AND_PRODUCTS,
            commodity=commodity,
            statistic=NASSStatistic.INVENTORY,
            agg_level=agg_level,
            year=year,
            state_alpha=state,
            frequency=NASSFrequency.ANNUAL,
        )

    def get_farm_income(
        self,
        *,
        year: int | None = None,
        state: str | None = None,
        agg_level: str | NASSAggLevel = NASSAggLevel.NATIONAL,
    ) -> NASSResponse:
        """Fetch farm income data.

        Args:
            year: Filter to a specific year.
            state: Two-letter state code.
            agg_level: Geographic aggregation level.
        """
        return self.get_data(
            sector=NASSSector.ECONOMICS,
            statistic=NASSStatistic.INCOME,
            agg_level=agg_level,
            year=year,
            state_alpha=state,
            frequency=NASSFrequency.ANNUAL,
        )

    def get_farm_expenses(
        self,
        *,
        year: int | None = None,
        state: str | None = None,
        agg_level: str | NASSAggLevel = NASSAggLevel.NATIONAL,
    ) -> NASSResponse:
        """Fetch farm expense data.

        Args:
            year: Filter to a specific year.
            state: Two-letter state code.
            agg_level: Geographic aggregation level.
        """
        return self.get_data(
            sector=NASSSector.ECONOMICS,
            statistic=NASSStatistic.EXPENSE,
            agg_level=agg_level,
            year=year,
            state_alpha=state,
            frequency=NASSFrequency.ANNUAL,
        )

    def get_census_data(
        self,
        commodity: str | NASSCommodity,
        *,
        year: int | None = None,
        state: str | None = None,
        agg_level: str | NASSAggLevel = NASSAggLevel.NATIONAL,
    ) -> NASSResponse:
        """Fetch Census of Agriculture data for a commodity.

        The Census of Agriculture is conducted every 5 years
        (2017, 2022, etc.).

        Args:
            commodity: Commodity name.
            year: Census year (e.g. 2017, 2022).
            state: Two-letter state code.
            agg_level: Geographic aggregation level.
        """
        return self.get_data(
            source=NASSSource.CENSUS,
            commodity=commodity,
            agg_level=agg_level,
            year=year,
            state_alpha=state,
        )

    def get_crop_progress(
        self,
        commodity: str | NASSCommodity,
        *,
        year: int | None = None,
        state: str | None = None,
        agg_level: str | NASSAggLevel = NASSAggLevel.NATIONAL,
    ) -> NASSResponse:
        """Fetch weekly crop progress reports.

        Args:
            commodity: Commodity name.
            year: Filter to a specific year.
            state: Two-letter state code.
            agg_level: Geographic aggregation level.
        """
        return self.get_data(
            source=NASSSource.SURVEY,
            commodity=commodity,
            agg_level=agg_level,
            year=year,
            state_alpha=state,
            frequency=NASSFrequency.WEEKLY,
        )

    def get_state_rankings(
        self,
        commodity: str | NASSCommodity,
        statistic: str | NASSStatistic,
        *,
        year: int | None = None,
    ) -> NASSResponse:
        """Fetch state-level data for ranking states by a statistic.

        Returns one record per state for the given commodity and
        statistic, allowing downstream ranking by value.

        Args:
            commodity: Commodity name.
            statistic: Statistic category to rank by.
            year: Filter to a specific year.
        """
        return self.get_data(
            commodity=commodity,
            statistic=statistic,
            agg_level=NASSAggLevel.STATE,
            year=year,
            frequency=NASSFrequency.ANNUAL,
            reference_period="YEAR",
        )

    def get_commodity_trends(
        self,
        commodity: str | NASSCommodity,
        start_year: int,
        end_year: int,
        *,
        statistic: str | NASSStatistic = NASSStatistic.PRODUCTION,
        state: str | None = None,
        agg_level: str | NASSAggLevel = NASSAggLevel.NATIONAL,
    ) -> NASSResponse:
        """Fetch multi-year trend data for a commodity.

        The NASS API supports year ranges via comma-separated or
        ``__LE`` / ``__GE`` operators. This method fetches each year
        individually and merges them because the API does not natively
        support year ranges in a single parameter.

        Args:
            commodity: Commodity name.
            start_year: First year of the range (inclusive).
            end_year: Last year of the range (inclusive).
            statistic: Statistic category.
            state: Two-letter state code.
            agg_level: Geographic aggregation level.
        """
        # NASS supports year__GE and year__LE for range queries
        params = self._build_query_params(
            commodity=commodity,
            statistic=statistic,
            agg_level=agg_level,
            state_alpha=state,
            frequency=NASSFrequency.ANNUAL,
            reference_period="YEAR",
        )
        params["year__GE"] = str(start_year)
        params["year__LE"] = str(end_year)
        return self._request("api_GET", params, kind="data")

    def get_national_totals(
        self,
        commodity: str | NASSCommodity,
        *,
        year: int | None = None,
        statistic: str | NASSStatistic = NASSStatistic.PRODUCTION,
    ) -> NASSResponse:
        """Fetch national-level totals for a commodity.

        Args:
            commodity: Commodity name.
            year: Filter to a specific year.
            statistic: Statistic category.
        """
        return self.get_data(
            commodity=commodity,
            statistic=statistic,
            agg_level=NASSAggLevel.NATIONAL,
            year=year,
            frequency=NASSFrequency.ANNUAL,
            reference_period="YEAR",
        )

    # ── cache management ─────────────────────────────────────────

    def clear_cache(self) -> int:
        """Remove all cached NASS responses. Returns count deleted."""
        return self._cache.clear()


# ═══════════════════════════════════════════════════════════════════
# Strata format converters
# ═══════════════════════════════════════════════════════════════════


def _pick_record(
    records: tuple[NASSRecord, ...],
    year: int | None,
) -> NASSRecord:
    """Select a specific year's record, preferring the requested year."""
    non_null = [r for r in records if r.value is not None]

    if year is not None:
        match = next((r for r in non_null if r.year == year), None)
        if match is not None:
            return match

    if non_null:
        # Pick the most recent non-null record
        return sorted(non_null, key=lambda r: r.year, reverse=True)[0]

    if records:
        return records[0]

    raise NASSClientError("No NASS records to convert")


def _snapshot_hash(record: NASSRecord) -> str:
    """Content-hash a data record for source pinning (Q5)."""
    content = json.dumps(
        {
            "commodity": record.commodity,
            "statistic_category": record.statistic_category,
            "state_alpha": record.state_alpha,
            "year": record.year,
            "value": record.value,
            "unit": record.unit,
            "short_desc": record.short_desc,
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()


def _nass_unit_to_strata_unit(
    unit_desc: str,
    statistic_category: str,
) -> dict[str, str]:
    """Map a NASS unit_desc string to a Strata unit dict.

    Returns a dict with keys: kind, dimension, and optionally
    currency and denominator.
    """
    unit_lower = unit_desc.upper()

    # Currency-based units
    if "$" in unit_desc or "DOLLARS" in unit_lower:
        unit: dict[str, str] = {
            "kind": "stock",
            "dimension": "currency",
            "currency": "USD",
        }
        return unit

    # Area units
    if "ACRES" in unit_lower:
        return {"kind": "stock", "dimension": "area"}

    # Weight / volume units
    if "BU" in unit_lower or "BUSHELS" in unit_lower:
        return {"kind": "stock", "dimension": "volume"}
    if "LB" in unit_lower or "POUNDS" in unit_lower:
        return {"kind": "stock", "dimension": "weight"}
    if "TONS" in unit_lower or "CWT" in unit_lower:
        return {"kind": "stock", "dimension": "weight"}
    if "GALLONS" in unit_lower:
        return {"kind": "stock", "dimension": "volume"}

    # Count-based units
    if "HEAD" in unit_lower:
        return {"kind": "stock", "dimension": "count"}
    if "OPERATIONS" in unit_lower or "FARMS" in unit_lower:
        return {"kind": "stock", "dimension": "count"}

    # Rate units
    if "BU / ACRE" in unit_lower or "/ ACRE" in unit_lower:
        return {"kind": "rate", "dimension": "volume", "denominator": "area"}
    if "$ / " in unit_desc:
        return {
            "kind": "rate",
            "dimension": "currency",
            "currency": "USD",
            "denominator": "unit",
        }

    # Percentage
    if "PCT" in unit_lower or "%" in unit_desc:
        return {"kind": "ratio", "dimension": "percentage"}

    # Default
    return {"kind": "stock", "dimension": "quantity"}


def _geo_from_record(record: NASSRecord) -> dict[str, Any]:
    """Build a Strata geo dict from a NASS record."""
    if record.agg_level == NASSAggLevel.NATIONAL or record.state_alpha == "US":
        return {"level": "country", "codes": ["US"]}
    if record.agg_level == NASSAggLevel.STATE and record.state_alpha:
        return {"level": "state", "codes": [f"US-{record.state_alpha}"]}
    if record.agg_level == NASSAggLevel.COUNTY and record.state_alpha:
        county_label = record.county_name.strip() if record.county_name else "unknown"
        return {
            "level": "county",
            "codes": [f"US-{record.state_alpha}"],
            "detail": county_label,
        }
    return {"level": "country", "codes": ["US"]}


def record_to_primitive_yaml(
    records: tuple[NASSRecord, ...],
    *,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    source_url: str = "https://quickstats.nass.usda.gov/",
    year: int | None = None,
    geo_perspective: str = "supply",
    distribution_shape: str = "normal",
    delivery_mode: str = "n/a",
) -> dict[str, Any]:
    """Convert NASS records to a Strata AtomicPrimitive YAML dict.

    Returns a dict ready for ``yaml.dump()`` that conforms to the
    AtomicPrimitive schema (models/primitive.py).
    """
    record = _pick_record(records, year)
    sha = _snapshot_hash(record)

    commodity_slug = record.commodity.lower().replace(" ", "-")
    stat_slug = record.statistic_category.lower().replace(" ", "-")
    state_slug = record.state_alpha.lower() if record.state_alpha else "us"
    source_slug = f"nass-{commodity_slug}-{stat_slug}-{state_slug}-{record.year}"

    unit = _nass_unit_to_strata_unit(record.unit, record.statistic_category)
    geo = _geo_from_record(record)

    return {
        "kind": "atomic_primitive",
        "slug": primitive_slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": name,
        "description": description,
        "value": record.value,
        "unit": unit,
        "as_of": f"{record.year}-12-31",
        "geo": geo,
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


def record_to_source_yaml(
    records: tuple[NASSRecord, ...],
    *,
    source_url: str = "https://quickstats.nass.usda.gov/",
    year: int | None = None,
    description: str = "",
) -> dict[str, Any]:
    """Convert NASS records to a Strata source_registry YAML dict."""
    record = _pick_record(records, year)
    sha = _snapshot_hash(record)

    commodity_slug = record.commodity.lower().replace(" ", "-")
    stat_slug = record.statistic_category.lower().replace(" ", "-")
    state_slug = record.state_alpha.lower() if record.state_alpha else "us"
    source_slug = f"nass-{commodity_slug}-{stat_slug}-{state_slug}-{record.year}"

    return {
        "kind": "source_registry",
        "slug": source_slug,
        "tier": "regulator",
        "url": source_url,
        "accessed": date.today().isoformat(),
        "snapshot_sha256": sha,
        "description": description
        or (
            f"USDA NASS {record.commodity} {record.statistic_category} "
            f"for {record.state_name or 'US'}, {record.year} data."
        ),
    }
