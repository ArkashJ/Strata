"""World Bank Open Data API v2 client.

Typed wrappers for the World Bank Indicators API with disk caching
and conversion to Strata AtomicPrimitive / Source YAML format.

API reference: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
No authentication required. No published rate limits.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, TypedDict, cast

import httpx

# ═══════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════


class WBIncomeLevel(StrEnum):
    HIGH = "HIC"
    UPPER_MIDDLE = "UMC"
    LOWER_MIDDLE = "LMC"
    LOW = "LIC"


class WBRegion(StrEnum):
    NORTH_AMERICA = "NAC"
    EUROPE_CENTRAL_ASIA = "ECS"
    EAST_ASIA_PACIFIC = "EAS"
    LATIN_AMERICA = "LCN"
    SOUTH_ASIA = "SAS"
    SUB_SAHARAN_AFRICA = "SSF"
    MIDDLE_EAST_NORTH_AFRICA = "MEA"


class WBIndicatorGroup(StrEnum):
    """Common indicator categories for market-sizing."""

    GDP = "NY.GDP.MKTP.CD"
    GDP_GROWTH = "NY.GDP.MKTP.KD.ZG"
    GDP_PER_CAPITA = "NY.GDP.PCAP.CD"
    POPULATION = "SP.POP.TOTL"
    LABOR_FORCE = "SL.TLF.TOTL.IN"
    UNEMPLOYMENT = "SL.UEM.TOTL.ZS"
    INTERNET_USERS_PCT = "IT.NET.USER.ZS"
    MOBILE_SUBSCRIPTIONS = "IT.CEL.SETS.P2"
    HOUSEHOLD_CONSUMPTION = "NE.CON.PRVT.CD"
    FDI_INFLOWS = "BX.KLT.DINV.CD.WD"
    INFLATION = "FP.CPI.TOTL.ZG"
    LENDING_RATE = "FR.INR.LEND"
    CURRENT_ACCOUNT = "BN.CAB.XOKA.CD"


# ═══════════════════════════════════════════════════════════════════
# TypedDicts — raw World Bank JSON response shapes
# ═══════════════════════════════════════════════════════════════════


class IndicatorValueRaw(TypedDict, total=False):
    indicator: dict[str, str]
    country: dict[str, str]
    countryiso3code: str
    date: str
    value: float | None
    unit: str
    obs_status: str
    decimal: int


class IndicatorInfoRaw(TypedDict, total=False):
    id: str
    name: str
    unit: str
    source: dict[str, str]
    sourceNote: str
    sourceOrganization: str


class CountryRaw(TypedDict, total=False):
    id: str
    iso2Code: str
    name: str
    region: dict[str, str]
    capitalCity: str
    longitude: str
    latitude: str
    incomeLevel: dict[str, str]


class PaginationRaw(TypedDict, total=False):
    page: int
    pages: int
    per_page: int | str
    total: int


# ═══════════════════════════════════════════════════════════════════
# Dataclasses — validated internal models
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class IndicatorValue:
    indicator_id: str
    indicator_name: str
    country_code: str
    country_name: str
    date: str
    value: float | None


@dataclass(frozen=True, slots=True)
class IndicatorInfo:
    id: str
    name: str
    unit: str
    source_note: str
    source_organization: str


@dataclass(frozen=True, slots=True)
class Country:
    code: str
    iso3_code: str
    name: str
    region: str
    capital_city: str
    income_level: str


@dataclass(frozen=True, slots=True)
class WBResponse:
    """Standard return type for every World Bank client call."""

    kind: str
    values: tuple[IndicatorValue, ...] = ()
    indicators: tuple[IndicatorInfo, ...] = ()
    countries: tuple[Country, ...] = ()
    total: int = 0
    pages: int = 0
    cached: bool = False
    cache_age_seconds: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# Response parsing
# ═══════════════════════════════════════════════════════════════════


def _parse_indicator_value(raw: dict[str, Any]) -> IndicatorValue:
    indicator: dict[str, str] = raw.get("indicator", {})
    country: dict[str, str] = raw.get("country", {})
    raw_value: object = raw.get("value")
    value: float | None = None
    if raw_value is not None:
        try:
            value = float(raw_value)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            value = None
    return IndicatorValue(
        indicator_id=str(indicator.get("id", "")),
        indicator_name=str(indicator.get("value", "")),
        country_code=str(country.get("id", "")),
        country_name=str(country.get("value", "")),
        date=str(raw.get("date", "")),
        value=value,
    )


def _parse_indicator_info(raw: dict[str, Any]) -> IndicatorInfo:
    return IndicatorInfo(
        id=str(raw.get("id", "")),
        name=str(raw.get("name", "")),
        unit=str(raw.get("unit", "")),
        source_note=str(raw.get("sourceNote", "")),
        source_organization=str(raw.get("sourceOrganization", "")),
    )


def _parse_country(raw: dict[str, Any]) -> Country:
    region: dict[str, str] = raw.get("region", {})
    income: dict[str, str] = raw.get("incomeLevel", {})
    return Country(
        code=str(raw.get("iso2Code", raw.get("id", ""))),
        iso3_code=str(raw.get("id", "")),
        name=str(raw.get("name", "")),
        region=str(region.get("value", "")),
        capital_city=str(raw.get("capitalCity", "")),
        income_level=str(income.get("value", "")),
    )


def _parse_pagination(meta: dict[str, Any]) -> tuple[int, int]:
    """Extract (total, pages) from the metadata object."""
    total = int(meta.get("total", 0))
    pages = int(meta.get("pages", 0))
    return total, pages


def _parse_response(raw: list[Any], *, kind: str) -> WBResponse:
    """Parse the two-element array [metadata, data_array] response."""
    if not raw or len(raw) < 2:
        meta = raw[0] if raw else {}
        total_count, page_count = _parse_pagination(meta) if meta else (0, 0)
        return WBResponse(kind=kind, total=total_count, pages=page_count)

    meta: dict[str, Any] = raw[0]
    data: list[dict[str, Any]] = raw[1] if raw[1] is not None else []
    total_count, page_count = _parse_pagination(meta)

    values: tuple[IndicatorValue, ...] = ()
    indicators: tuple[IndicatorInfo, ...] = ()
    countries: tuple[Country, ...] = ()

    if kind == "indicator":
        values = tuple(_parse_indicator_value(v) for v in data)
    elif kind == "indicator_info":
        indicators = tuple(_parse_indicator_info(i) for i in data)
    elif kind == "country":
        countries = tuple(_parse_country(c) for c in data)

    return WBResponse(
        kind=kind,
        values=values,
        indicators=indicators,
        countries=countries,
        total=total_count,
        pages=page_count,
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
        return self._dir / f"wb_{key}.json"

    def get(self, params: str) -> tuple[list[Any], float] | None:
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
            data: list[Any] = raw.get("_data", [])
            return data, age
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            path.unlink(missing_ok=True)
            return None

    def put(self, params: str, data: list[Any]) -> None:
        path = self._path(self._key(params))
        payload: dict[str, Any] = {"_ts": time.time(), "_data": data}
        path.write_text(json.dumps(payload, indent=2))

    def clear(self) -> int:
        count = 0
        for f in self._dir.glob("wb_*.json"):
            f.unlink()
            count += 1
        return count


# ═══════════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════════

_BASE = "https://api.worldbank.org/v2"


class WorldBankClientError(RuntimeError):
    """Raised on World Bank API errors or client-side validation failures."""


class WorldBankClient:
    """Typed client for the World Bank Indicators API v2.

    Usage::

        client = WorldBankClient()
        resp = client.get_indicator("NY.GDP.MKTP.CD", country="US",
                                    date_range="2019:2023")
        for v in resp.values:
            print(v.date, v.value)
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        cache_ttl: int = 604800,
        timeout: float = 30.0,
    ) -> None:
        self._http = httpx.Client(timeout=timeout)
        default_cache = Path.home() / ".strata" / "cache" / "worldbank"
        self._cache = _DiskCache(cache_dir or default_cache, cache_ttl)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> WorldBankClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ── internal helpers ─────────────────────────────────────────

    def _cache_key(self, url: str, params: dict[str, str]) -> str:
        parts = [url, json.dumps(params, sort_keys=True)]
        return "|".join(parts)

    def _request(
        self,
        url: str,
        params: dict[str, str],
        *,
        kind: str,
    ) -> WBResponse:
        params["format"] = "json"

        ck = self._cache_key(url, params)
        cached = self._cache.get(ck)
        if cached is not None:
            data, age = cached
            resp = _parse_response(data, kind=kind)
            return replace(resp, cached=True, cache_age_seconds=round(age, 1))

        http_resp = self._http.get(url, params=params)
        http_resp.raise_for_status()

        body: Any = http_resp.json()

        if isinstance(body, dict):
            body_dict = cast(dict[str, Any], body)
            raw_msgs: list[Any] = body_dict.get("message", [])
            if raw_msgs:
                msg_texts: list[str] = []
                for m in raw_msgs:
                    if isinstance(m, dict):
                        md = cast(dict[str, Any], m)
                        msg_texts.append(str(md.get("value", md)))
                    else:
                        msg_texts.append(str(m))
                raise WorldBankClientError(f"World Bank API error: {'; '.join(msg_texts)}")
            raise WorldBankClientError(
                f"World Bank API returned unexpected dict: {list(body_dict.keys())}"
            )

        if not isinstance(body, list):
            raise WorldBankClientError(
                f"World Bank API returned unexpected type: {type(body).__name__}"
            )

        raw = cast(list[Any], body)
        self._cache.put(ck, raw)
        return _parse_response(raw, kind=kind)

    def _request_all_pages(
        self,
        url: str,
        params: dict[str, str],
        *,
        kind: str,
        per_page: int = 100,
    ) -> WBResponse:
        """Fetch all pages and merge results."""
        params["per_page"] = str(per_page)
        params["page"] = "1"

        first = self._request(url, params, kind=kind)
        if first.pages <= 1:
            return first

        all_values = list(first.values)
        all_indicators = list(first.indicators)
        all_countries = list(first.countries)

        for page in range(2, first.pages + 1):
            page_params = {**params, "page": str(page)}
            resp = self._request(url, page_params, kind=kind)
            all_values.extend(resp.values)
            all_indicators.extend(resp.indicators)
            all_countries.extend(resp.countries)

        return replace(
            first,
            values=tuple(all_values),
            indicators=tuple(all_indicators),
            countries=tuple(all_countries),
        )

    # ── indicator time-series ────────────────────────────────────

    def get_indicator(
        self,
        indicator: str,
        country: str = "US",
        date_range: str | None = None,
        per_page: int = 100,
    ) -> WBResponse:
        """Retrieve time-series data for an indicator and country.

        Args:
            indicator: World Bank indicator code (e.g. "NY.GDP.MKTP.CD").
            country: ISO 3166-1 alpha-2 code, "WLD", or income group.
            date_range: Year range like "2019:2023". None for all available.
            per_page: Results per page (max 1000).
        """
        url = f"{_BASE}/country/{country}/indicator/{indicator}"
        params: dict[str, str] = {"per_page": str(per_page)}
        if date_range is not None:
            params["date"] = date_range
        return self._request_all_pages(url, params, kind="indicator", per_page=per_page)

    # ── indicator metadata ───────────────────────────────────────

    def get_indicator_info(self, indicator: str) -> WBResponse:
        """Retrieve metadata for a single indicator."""
        url = f"{_BASE}/indicator/{indicator}"
        return self._request(url, {}, kind="indicator_info")

    # ── country endpoints ────────────────────────────────────────

    def get_countries(self, income_level: str | None = None) -> WBResponse:
        """Retrieve list of countries, optionally filtered by income level."""
        url = f"{_BASE}/country"
        params: dict[str, str] = {"per_page": "300"}
        if income_level is not None:
            params["incomeLevel"] = income_level
        return self._request_all_pages(url, params, kind="country", per_page=300)

    def get_country(self, code: str) -> WBResponse:
        """Retrieve metadata for a single country."""
        url = f"{_BASE}/country/{code}"
        return self._request(url, {}, kind="country")

    # ── multi-country convenience ────────────────────────────────

    def get_indicator_multi_country(
        self,
        indicator: str,
        countries: list[str],
        date_range: str | None = None,
    ) -> WBResponse:
        """Fetch an indicator for multiple countries in one request.

        The World Bank API accepts semicolon-separated country codes.
        """
        country_str = ";".join(countries)
        url = f"{_BASE}/country/{country_str}/indicator/{indicator}"
        params: dict[str, str] = {"per_page": "1000"}
        if date_range is not None:
            params["date"] = date_range
        return self._request_all_pages(url, params, kind="indicator", per_page=1000)

    # ── cache management ─────────────────────────────────────────

    def clear_cache(self) -> int:
        """Remove all cached World Bank responses. Returns count deleted."""
        return self._cache.clear()


# ═══════════════════════════════════════════════════════════════════
# Strata format converters
# ═══════════════════════════════════════════════════════════════════


def _pick_value(
    values: tuple[IndicatorValue, ...],
    year: int | None,
) -> IndicatorValue:
    """Select a specific year's value, preferring the requested year."""
    non_null = [v for v in values if v.value is not None]

    if year is not None:
        match = next((v for v in non_null if v.date == str(year)), None)
        if match is not None:
            return match

    if non_null:
        # WB returns most-recent first; pick the latest non-null value
        return non_null[0]

    if values:
        return values[0]

    raise WorldBankClientError("No indicator values to convert")


def _snapshot_hash(indicator_id: str, country_code: str, date_str: str, value: float | None) -> str:
    """Content-hash a data point for source pinning (Q5)."""
    content = json.dumps(
        {
            "indicator_id": indicator_id,
            "country_code": country_code,
            "date": date_str,
            "value": value,
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()


def indicator_to_primitive_yaml(
    values: tuple[IndicatorValue, ...],
    *,
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
    unit_dimension: str = "currency",
    unit_denominator: str | None = None,
    unit_currency: str | None = "USD",
    distribution_shape: str = "normal",
    delivery_mode: str = "n/a",
) -> dict[str, Any]:
    """Convert World Bank indicator values to a Strata AtomicPrimitive YAML dict.

    Returns a dict ready for ``yaml.dump()`` that conforms to the
    AtomicPrimitive schema (models/primitive.py).
    """
    point = _pick_value(values, year)
    source_slug = f"wb-{point.indicator_id.lower().replace('.', '-')}-{point.country_code.lower()}-{point.date}"
    sha = _snapshot_hash(point.indicator_id, point.country_code, point.date, point.value)

    unit: dict[str, str] = {"kind": unit_kind, "dimension": unit_dimension}
    if unit_denominator:
        unit["denominator"] = unit_denominator
    if unit_currency:
        unit["currency"] = unit_currency

    return {
        "kind": "atomic_primitive",
        "slug": primitive_slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": name,
        "description": description,
        "value": point.value,
        "unit": unit,
        "as_of": f"{point.date}-12-31",
        "geo": {"level": geo_level, "codes": list(geo_codes)},
        "geo_perspective": geo_perspective,
        "distribution_shape": distribution_shape,
        "delivery_mode": delivery_mode,
        "source": {
            "slug": source_slug,
            "tier": "aggregator",
            "url": source_url,
            "accessed": date.today().isoformat(),
            "snapshot_sha256": sha,
        },
    }


def indicator_to_source_yaml(
    values: tuple[IndicatorValue, ...],
    *,
    source_url: str,
    year: int,
    description: str = "",
) -> dict[str, Any]:
    """Convert World Bank indicator values to a Strata source_registry YAML dict."""
    point = _pick_value(values, year)
    source_slug = f"wb-{point.indicator_id.lower().replace('.', '-')}-{point.country_code.lower()}-{point.date}"
    sha = _snapshot_hash(point.indicator_id, point.country_code, point.date, point.value)

    return {
        "kind": "source_registry",
        "slug": source_slug,
        "tier": "aggregator",
        "url": source_url,
        "accessed": date.today().isoformat(),
        "snapshot_sha256": sha,
        "description": description
        or f"World Bank {point.indicator_id} for {point.country_name}, {point.date} data.",
    }
