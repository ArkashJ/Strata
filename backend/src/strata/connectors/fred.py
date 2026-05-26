"""FRED (Federal Reserve Economic Data) API client.

Typed wrappers for all seven FRED API endpoints with disk caching
and conversion to Strata AtomicPrimitive / Source YAML format.

API reference: https://fred.stlouisfed.org/docs/api/fred/
Rate limits: 120 requests/minute with a registered API key.
"""

from __future__ import annotations

import hashlib
import json
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


class FREDFrequency(StrEnum):
    """Observation frequency codes accepted by the FRED API."""

    DAILY = "d"
    WEEKLY = "w"
    BIWEEKLY = "bw"
    MONTHLY = "m"
    QUARTERLY = "q"
    SEMIANNUAL = "sa"
    ANNUAL = "a"


class FREDUnits(StrEnum):
    """Data value transformation codes for observation requests."""

    LEVELS = "lin"
    CHANGE = "chg"
    CHANGE_YEAR_AGO = "ch1"
    PCT_CHANGE = "pch"
    PCT_CHANGE_YEAR_AGO = "pc1"
    COMPOUNDED_ANNUAL_PCT_CHANGE = "pca"
    CONTINUOUSLY_COMPOUNDED_RATE = "cch"
    CONTINUOUSLY_COMPOUNDED_ANNUAL_RATE = "cca"
    LOG = "log"


class FREDOrderBy(StrEnum):
    """Sort field options for search results."""

    SEARCH_RANK = "search_rank"
    SERIES_ID = "series_id"
    TITLE = "title"
    UNITS = "units"
    FREQUENCY = "frequency"
    SEASONAL_ADJUSTMENT = "seasonal_adjustment"
    REALTIME_START = "realtime_start"
    REALTIME_END = "realtime_end"
    LAST_UPDATED = "last_updated"
    OBSERVATION_START = "observation_start"
    OBSERVATION_END = "observation_end"
    POPULARITY = "popularity"
    GROUP_POPULARITY = "group_popularity"


class FREDSortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class FREDSearchType(StrEnum):
    FULL_TEXT = "full_text"
    SERIES_ID = "series_id"


class FREDSeasonalAdjustment(StrEnum):
    """Common seasonal adjustment codes in FRED series metadata."""

    SEASONALLY_ADJUSTED = "Seasonally Adjusted"
    NOT_SEASONALLY_ADJUSTED = "Not Seasonally Adjusted"
    SEASONALLY_ADJUSTED_ANNUAL_RATE = "Seasonally Adjusted Annual Rate"


# ═══════════════════════════════════════════════════════════════════
# TypedDicts — raw FRED JSON response shapes
# ═══════════════════════════════════════════════════════════════════


class ObservationRaw(TypedDict):
    realtime_start: str
    realtime_end: str
    date: str
    value: str


class SeriesInfoRaw(TypedDict):
    id: str
    realtime_start: str
    realtime_end: str
    title: str
    observation_start: str
    observation_end: str
    frequency: str
    frequency_short: str
    units: str
    units_short: str
    seasonal_adjustment: str
    seasonal_adjustment_short: str
    last_updated: str
    popularity: NotRequired[int]
    notes: NotRequired[str]


class CategoryRaw(TypedDict):
    id: int
    name: str
    parent_id: int


class ReleaseRaw(TypedDict):
    id: int
    realtime_start: str
    realtime_end: str
    name: str
    press_release: bool
    link: NotRequired[str]
    notes: NotRequired[str]


# ═══════════════════════════════════════════════════════════════════
# Dataclasses — validated internal models
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class Observation:
    date: str
    value: float | None
    realtime_start: str = ""
    realtime_end: str = ""

    @property
    def has_value(self) -> bool:
        return self.value is not None


@dataclass(frozen=True, slots=True)
class SeriesInfo:
    id: str
    title: str
    frequency: str
    frequency_short: str
    units: str
    units_short: str
    seasonal_adjustment: str
    seasonal_adjustment_short: str
    observation_start: str
    observation_end: str
    last_updated: str
    popularity: int = 0
    notes: str = ""

    def display_label(self) -> str:
        """Human-readable label: title + units + seasonal adjustment."""
        parts = [self.title]
        if self.units_short:
            parts.append(f"({self.units_short})")
        if self.seasonal_adjustment_short:
            parts.append(f"[{self.seasonal_adjustment_short}]")
        return " ".join(parts)


@dataclass(frozen=True, slots=True)
class Category:
    id: int
    name: str
    parent_id: int


@dataclass(frozen=True, slots=True)
class Release:
    id: int
    name: str
    press_release: bool
    link: str = ""
    notes: str = ""


@dataclass(frozen=True, slots=True)
class FREDResponse:
    """Standard return type for every FRED client call."""

    status: str
    observations: tuple[Observation, ...] = ()
    series_list: tuple[SeriesInfo, ...] = ()
    categories: tuple[Category, ...] = ()
    releases: tuple[Release, ...] = ()
    count: int = 0
    cached: bool = False
    cache_age_seconds: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# Response parsing
# ═══════════════════════════════════════════════════════════════════


def _parse_observation(raw: dict[str, Any]) -> Observation | None:
    """Parse a single observation, returning None for missing values."""
    value_str = str(raw.get("value", "."))
    if value_str == ".":
        return Observation(
            date=str(raw.get("date", "")),
            value=None,
            realtime_start=str(raw.get("realtime_start", "")),
            realtime_end=str(raw.get("realtime_end", "")),
        )
    try:
        value = float(value_str.replace(",", ""))
    except ValueError:
        return None
    return Observation(
        date=str(raw.get("date", "")),
        value=value,
        realtime_start=str(raw.get("realtime_start", "")),
        realtime_end=str(raw.get("realtime_end", "")),
    )


def _parse_series_info(raw: dict[str, Any]) -> SeriesInfo:
    return SeriesInfo(
        id=str(raw.get("id", "")),
        title=str(raw.get("title", "")),
        frequency=str(raw.get("frequency", "")),
        frequency_short=str(raw.get("frequency_short", "")),
        units=str(raw.get("units", "")),
        units_short=str(raw.get("units_short", "")),
        seasonal_adjustment=str(raw.get("seasonal_adjustment", "")),
        seasonal_adjustment_short=str(raw.get("seasonal_adjustment_short", "")),
        observation_start=str(raw.get("observation_start", "")),
        observation_end=str(raw.get("observation_end", "")),
        last_updated=str(raw.get("last_updated", "")),
        popularity=int(raw.get("popularity", 0)),
        notes=str(raw.get("notes", "")),
    )


def _parse_category(raw: dict[str, Any]) -> Category:
    return Category(
        id=int(raw.get("id", 0)),
        name=str(raw.get("name", "")),
        parent_id=int(raw.get("parent_id", 0)),
    )


def _parse_release(raw: dict[str, Any]) -> Release:
    return Release(
        id=int(raw.get("id", 0)),
        name=str(raw.get("name", "")),
        press_release=bool(raw.get("press_release", False)),
        link=str(raw.get("link", "")),
        notes=str(raw.get("notes", "")),
    )


def _parse_observations_response(raw: dict[str, Any]) -> FREDResponse:
    obs_raw: list[dict[str, Any]] = raw.get("observations", [])
    parsed = [_parse_observation(o) for o in obs_raw]
    observations = tuple(o for o in parsed if o is not None)
    return FREDResponse(
        status="ok",
        observations=observations,
        count=int(raw.get("count", len(observations))),
    )


def _parse_series_response(raw: dict[str, Any]) -> FREDResponse:
    """Parse a response containing a single series (fred/series)."""
    serieses_raw: list[dict[str, Any]] = raw.get("seriess", [])
    series_list = tuple(_parse_series_info(s) for s in serieses_raw)
    return FREDResponse(
        status="ok",
        series_list=series_list,
        count=len(series_list),
    )


def _parse_search_response(raw: dict[str, Any]) -> FREDResponse:
    serieses_raw: list[dict[str, Any]] = raw.get("seriess", [])
    series_list = tuple(_parse_series_info(s) for s in serieses_raw)
    return FREDResponse(
        status="ok",
        series_list=series_list,
        count=int(raw.get("count", len(series_list))),
    )


def _parse_categories_response(raw: dict[str, Any]) -> FREDResponse:
    cats_raw: list[dict[str, Any]] = raw.get("categories", [])
    categories = tuple(_parse_category(c) for c in cats_raw)
    return FREDResponse(
        status="ok",
        categories=categories,
        count=len(categories),
    )


def _parse_releases_response(raw: dict[str, Any]) -> FREDResponse:
    rels_raw: list[dict[str, Any]] = raw.get("releases", [])
    releases = tuple(_parse_release(r) for r in rels_raw)
    return FREDResponse(
        status="ok",
        releases=releases,
        count=len(releases),
    )


_PARSERS: dict[str, Any] = {
    "observations": _parse_observations_response,
    "series": _parse_series_response,
    "search": _parse_search_response,
    "categories": _parse_categories_response,
    "releases": _parse_releases_response,
}


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
        return self._dir / f"fred_{key}.json"

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
        for f in self._dir.glob("fred_*.json"):
            f.unlink()
            count += 1
        return count


# ═══════════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════════

_BASE = "https://api.stlouisfed.org/fred"


class FREDClientError(RuntimeError):
    """Raised on FRED API errors or client-side validation failures."""


class FREDClient:
    """Typed client for the FRED API with disk caching.

    Usage::

        client = FREDClient(api_key="your-32-char-key")
        resp = client.get_observations("GDPC1", observation_start="2020-01-01")
        for obs in resp.observations:
            print(obs.date, obs.value)
    """

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: Path | None = None,
        cache_ttl: int = 86400,
        timeout: float = 30.0,
    ) -> None:
        self._key = api_key
        self._http = httpx.Client(timeout=timeout)
        default_cache = Path.home() / ".strata" / "cache" / "fred"
        self._cache = _DiskCache(cache_dir or default_cache, cache_ttl)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> FREDClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ── internal helpers ─────────────────────────────────────────

    def _base_params(self) -> dict[str, str]:
        """Params required on every FRED request."""
        params: dict[str, str] = {"file_type": "json"}
        if self._key:
            params["api_key"] = self._key
        return params

    def _cache_key(self, url: str, params: dict[str, str]) -> str:
        parts = [url, json.dumps(params, sort_keys=True)]
        return "|".join(parts)

    def _request(
        self,
        endpoint: str,
        params: dict[str, str],
        *,
        kind: str = "observations",
    ) -> FREDResponse:
        url = f"{_BASE}/{endpoint}"
        all_params = {**self._base_params(), **params}
        ck = self._cache_key(url, all_params)

        cached = self._cache.get(ck)
        if cached is not None:
            data, age = cached
            parser = _PARSERS.get(kind, _parse_observations_response)
            resp: FREDResponse = parser(data)
            return replace(resp, cached=True, cache_age_seconds=round(age, 1))

        http_resp = self._http.get(url, params=all_params)
        http_resp.raise_for_status()

        raw: dict[str, Any] = http_resp.json()

        if "error_code" in raw or "error_message" in raw:
            code = raw.get("error_code", "unknown")
            msg = raw.get("error_message", "Unknown FRED API error")
            raise FREDClientError(f"FRED API error {code}: {msg}")

        self._cache.put(ck, raw)
        parser = _PARSERS.get(kind, _parse_observations_response)
        return parser(raw)

    # ── Endpoint 1: series metadata ─────────────────────────────

    def get_series(self, series_id: str) -> FREDResponse:
        """Retrieve metadata for a single FRED series."""
        return self._request(
            "series",
            {"series_id": series_id},
            kind="series",
        )

    # ── Endpoint 2: series observations (the main one) ──────────

    def get_observations(
        self,
        series_id: str,
        observation_start: str | None = None,
        observation_end: str | None = None,
        units: str = "lin",
        frequency: str | None = None,
        sort_order: str = "asc",
        limit: int = 100000,
        offset: int = 0,
    ) -> FREDResponse:
        """Retrieve data values for a series.

        Args:
            series_id: FRED series ID (e.g. "GDPC1", "PAYEMS").
            observation_start: Start date "YYYY-MM-DD" (default: 1776-07-04).
            observation_end: End date "YYYY-MM-DD" (default: 9999-12-31).
            units: Data value transformation (see FREDUnits).
            frequency: Aggregation frequency (see FREDFrequency).
            sort_order: "asc" or "desc".
            limit: Max observations (FRED max is 100000).
            offset: Pagination offset.
        """
        params: dict[str, str] = {
            "series_id": series_id,
            "units": units,
            "sort_order": sort_order,
            "limit": str(limit),
            "offset": str(offset),
        }
        if observation_start:
            params["observation_start"] = observation_start
        if observation_end:
            params["observation_end"] = observation_end
        if frequency:
            params["frequency"] = frequency
        return self._request("series/observations", params, kind="observations")

    # ── Endpoint 3: search series ───────────────────────────────

    def search_series(
        self,
        search_text: str,
        search_type: str = "full_text",
        limit: int = 100,
        order_by: str = "search_rank",
        sort_order: str = "asc",
    ) -> FREDResponse:
        """Search for FRED series by keywords or series ID.

        Args:
            search_text: Keywords or series ID to search for.
            search_type: "full_text" or "series_id".
            limit: Max results (FRED max is 1000).
            order_by: Sort field (see FREDOrderBy).
            sort_order: "asc" or "desc".
        """
        return self._request(
            "series/search",
            {
                "search_text": search_text,
                "search_type": search_type,
                "limit": str(limit),
                "order_by": order_by,
                "sort_order": sort_order,
            },
            kind="search",
        )

    # ── Endpoint 4: series categories ───────────────────────────

    def get_series_categories(self, series_id: str) -> FREDResponse:
        """Get the categories that a series belongs to."""
        return self._request(
            "series/categories",
            {"series_id": series_id},
            kind="categories",
        )

    # ── Endpoint 5: category series ─────────────────────────────

    def get_category_series(
        self,
        category_id: int,
        limit: int = 1000,
        order_by: str = "series_id",
        sort_order: str = "asc",
    ) -> FREDResponse:
        """Get all series in a FRED category."""
        return self._request(
            "category/series",
            {
                "category_id": str(category_id),
                "limit": str(limit),
                "order_by": order_by,
                "sort_order": sort_order,
            },
            kind="search",
        )

    # ── Endpoint 6: all releases ────────────────────────────────

    def get_releases(
        self,
        limit: int = 1000,
        order_by: str = "release_id",
        sort_order: str = "asc",
    ) -> FREDResponse:
        """Get all FRED data releases."""
        return self._request(
            "releases",
            {
                "limit": str(limit),
                "order_by": order_by,
                "sort_order": sort_order,
            },
            kind="releases",
        )

    # ── Endpoint 7: release series ──────────────────────────────

    def get_release_series(
        self,
        release_id: int,
        limit: int = 1000,
        order_by: str = "series_id",
        sort_order: str = "asc",
    ) -> FREDResponse:
        """Get all series on a specific release."""
        return self._request(
            "release/series",
            {
                "release_id": str(release_id),
                "limit": str(limit),
                "order_by": order_by,
                "sort_order": sort_order,
            },
            kind="search",
        )

    # ── Cache management ─────────────────────────────────────────

    def clear_cache(self) -> int:
        """Remove all cached FRED responses. Returns count deleted."""
        return self._cache.clear()


# ═══════════════════════════════════════════════════════════════════
# Strata format converters
# ═══════════════════════════════════════════════════════════════════


def _pick_observation(
    observations: tuple[Observation, ...],
    year: int | None,
) -> Observation:
    """Select a specific observation by year, or fall back to latest with a value."""
    valid = tuple(o for o in observations if o.has_value)
    if not valid:
        raise FREDClientError("No valid observations (all values are missing)")

    if year is not None:
        year_str = str(year)
        for obs in reversed(valid):
            if obs.date.startswith(year_str):
                return obs
        raise FREDClientError(f"No observation found for year {year}")

    return valid[-1]


def _snapshot_hash(series_id: str, obs: Observation) -> str:
    """Content-hash an observation for source pinning (Q5)."""
    content = json.dumps(
        {
            "series_id": series_id,
            "date": obs.date,
            "value": obs.value,
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()


def _as_of_date(obs: Observation) -> str:
    """Derive an as_of date from the observation's date field."""
    return obs.date


def observations_to_primitive_yaml(
    series_info: SeriesInfo,
    observations: tuple[Observation, ...],
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
    unit_currency: str | None = None,
    distribution_shape: str = "normal",
    delivery_mode: str = "n/a",
) -> dict[str, Any]:
    """Convert FRED observations to a Strata AtomicPrimitive YAML dict.

    Returns a dict ready for ``yaml.dump()`` that conforms to the
    AtomicPrimitive schema (models/primitive.py).
    """
    obs = _pick_observation(observations, year)
    obs_year = int(obs.date[:4])
    source_slug = f"fred-{series_info.id.lower()}-{obs_year}"
    sha = _snapshot_hash(series_info.id, obs)

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
        "value": obs.value,
        "unit": unit,
        "as_of": _as_of_date(obs),
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


def observations_to_source_yaml(
    series_info: SeriesInfo,
    observations: tuple[Observation, ...],
    *,
    source_url: str,
    year: int,
    description: str = "",
) -> dict[str, Any]:
    """Convert FRED observations to a Strata source_registry YAML dict."""
    source_slug = f"fred-{series_info.id.lower()}-{year}"
    obs = _pick_observation(observations, year)
    sha = _snapshot_hash(series_info.id, obs)

    return {
        "kind": "source_registry",
        "slug": source_slug,
        "tier": "regulator",
        "url": source_url,
        "accessed": date.today().isoformat(),
        "snapshot_sha256": sha,
        "description": description or f"FRED series {series_info.id}, {year} data.",
    }
