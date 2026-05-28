"""BLS Public Data API v2 client.

Typed wrappers for all seven BLS API v2 signatures with disk caching
and conversion to Strata AtomicPrimitive / Source YAML format.

API reference: https://www.bls.gov/developers/api_signature_v2.htm
Registered limits: 500 queries/day · 50 series/query · 20 years/query.
Unregistered: 25 series · 10 years · no catalog/calculations/aspects.
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


class BLSStatus(StrEnum):
    REQUEST_SUCCEEDED = "REQUEST_SUCCEEDED"
    REQUEST_FAILED = "REQUEST_FAILED"
    REQUEST_NOT_PROCESSED = "REQUEST_NOT_PROCESSED"


class BLSPeriodKind(StrEnum):
    MONTHLY = "M"
    QUARTERLY = "Q"
    SEMIANNUAL = "S"
    ANNUAL = "A"


class BLSSurvey(StrEnum):
    """Common BLS survey abbreviations (non-exhaustive)."""

    CPI_AVERAGE_PRICE = "AP"
    BUSINESS_EMPLOYMENT_DYNAMICS = "BD"
    CURRENT_EMPLOYMENT_STATS = "CE"
    CPI_ALL_URBAN = "CU"
    CPI_URBAN_WAGE = "CW"
    EMPLOYMENT_COST_INDEX = "CI"
    JOLTS = "JT"
    LOCAL_AREA_UNEMPLOYMENT = "LA"
    LABOR_FORCE_STATS = "LN"
    OES = "OE"
    PPI = "PC"
    QCEW = "EN"
    AMERICAN_TIME_USE = "TU"
    MODELED_WAGE_ESTIMATES = "WM"


# ═══════════════════════════════════════════════════════════════════
# TypedDicts — raw BLS JSON response shapes
# ═══════════════════════════════════════════════════════════════════


class FootnoteRaw(TypedDict, total=False):
    code: str
    text: str


class AspectRaw(TypedDict, total=False):
    name: str
    value: str
    footnotes: list[FootnoteRaw]


class DataPointRaw(TypedDict):
    year: str
    period: str
    periodName: str
    value: str
    footnotes: list[FootnoteRaw]
    latest: NotRequired[str]
    aspects: NotRequired[list[AspectRaw]]
    calculations: NotRequired[dict[str, dict[str, str]]]


class CatalogRaw(TypedDict, total=False):
    series_title: str
    series_id: str
    seasonality: str
    survey_name: str
    survey_abbreviation: str
    measure_data_type: str
    commerce_industry: str
    occupation: str
    occupation_work_class: str
    area: str


class SeriesRaw(TypedDict):
    seriesID: str
    data: list[DataPointRaw]
    catalog: NotRequired[CatalogRaw]


class SurveyRaw(TypedDict):
    survey_name: str
    survey_abbreviation: str
    allowsNetChange: NotRequired[str]
    allowsPercentChange: NotRequired[str]
    hasAnnualAverages: NotRequired[str]


class SeriesRequestPayload(TypedDict, total=False):
    """POST body for multi-series requests."""

    seriesid: list[str]
    startyear: str
    endyear: str
    catalog: bool
    calculations: bool
    annualaverage: bool
    aspects: bool
    registrationkey: str


# ═══════════════════════════════════════════════════════════════════
# Dataclasses — validated internal models
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class Footnote:
    code: str
    text: str


@dataclass(frozen=True, slots=True)
class Aspect:
    name: str
    value: str


@dataclass(frozen=True, slots=True)
class DataPoint:
    year: int
    period: str
    period_name: str
    value: float
    latest: bool = False
    footnotes: tuple[Footnote, ...] = ()
    aspects: tuple[Aspect, ...] = ()

    @property
    def is_monthly(self) -> bool:
        return self.period.startswith("M") and self.period != "M13"

    @property
    def is_annual(self) -> bool:
        return self.period in ("M13", "A01")


@dataclass(frozen=True, slots=True)
class Catalog:
    series_title: str = ""
    series_id: str = ""
    seasonality: str = ""
    survey_name: str = ""
    survey_abbreviation: str = ""
    measure_data_type: str = ""
    area: str = ""
    occupation: str = ""
    industry: str = ""


@dataclass(frozen=True, slots=True)
class Series:
    series_id: str
    data: tuple[DataPoint, ...]
    catalog: Catalog | None = None

    def latest_value(self) -> DataPoint | None:
        for pt in self.data:
            if pt.latest:
                return pt
        return self.data[0] if self.data else None

    def annual_average(self, year: int) -> DataPoint | None:
        for pt in self.data:
            if pt.year == year and pt.is_annual:
                return pt
        return None

    def monthly(self, year: int, month: int) -> DataPoint | None:
        target = f"M{month:02d}"
        for pt in self.data:
            if pt.year == year and pt.period == target:
                return pt
        return None


@dataclass(frozen=True, slots=True)
class SurveyInfo:
    name: str
    abbreviation: str
    allows_net_change: bool = False
    allows_pct_change: bool = False
    has_annual_averages: bool = False


@dataclass(frozen=True, slots=True)
class BLSResponse:
    """Standard return type for every BLS client call."""

    status: BLSStatus
    response_time_ms: int
    messages: tuple[str, ...]
    series: tuple[Series, ...] = ()
    surveys: tuple[SurveyInfo, ...] = ()
    popular_ids: tuple[str, ...] = ()
    cached: bool = False
    cache_age_seconds: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# Response parsing
# ═══════════════════════════════════════════════════════════════════


def _parse_footnote(raw: dict[str, Any]) -> Footnote:
    return Footnote(code=str(raw.get("code", "")), text=str(raw.get("text", "")))


def _parse_aspect(raw: dict[str, Any]) -> Aspect:
    return Aspect(name=str(raw.get("name", "")), value=str(raw.get("value", "")))


def _parse_data_point(raw: dict[str, Any]) -> DataPoint:
    footnotes = tuple(_parse_footnote(f) for f in raw.get("footnotes", []) if f)
    aspects = tuple(_parse_aspect(a) for a in raw.get("aspects", []) if a)
    value_str = str(raw.get("value", "0"))
    try:
        value = float(value_str.replace(",", ""))
    except ValueError:
        value = 0.0
    return DataPoint(
        year=int(raw["year"]),
        period=str(raw["period"]),
        period_name=str(raw.get("periodName", "")),
        value=value,
        latest=str(raw.get("latest", "")).lower() == "true",
        footnotes=footnotes,
        aspects=aspects,
    )


def _parse_catalog(raw: dict[str, Any]) -> Catalog:
    return Catalog(
        series_title=str(raw.get("series_title", "")),
        series_id=str(raw.get("series_id", "")),
        seasonality=str(raw.get("seasonality", "")),
        survey_name=str(raw.get("survey_name", "")),
        survey_abbreviation=str(raw.get("survey_abbreviation", "")),
        measure_data_type=str(raw.get("measure_data_type", "")),
        area=str(raw.get("area", "")),
        occupation=str(raw.get("occupation", "")),
        industry=str(raw.get("commerce_industry", "")),
    )


def _parse_series(raw: dict[str, Any]) -> Series:
    data = tuple(_parse_data_point(dp) for dp in raw.get("data", []))
    catalog_raw = raw.get("catalog")
    catalog = _parse_catalog(dict(catalog_raw)) if isinstance(catalog_raw, dict) else None
    return Series(
        series_id=str(raw["seriesID"]),
        data=data,
        catalog=catalog,
    )


def _parse_survey(raw: dict[str, Any]) -> SurveyInfo:
    return SurveyInfo(
        name=str(raw.get("survey_name", "")),
        abbreviation=str(raw.get("survey_abbreviation", "")),
        allows_net_change=str(raw.get("allowsNetChange", "")).lower() == "true",
        allows_pct_change=str(raw.get("allowsPercentChange", "")).lower() == "true",
        has_annual_averages=str(raw.get("hasAnnualAverages", "")).lower() == "true",
    )


def _parse_api_response(raw: dict[str, Any], *, kind: str = "series") -> BLSResponse:
    status = BLSStatus(raw.get("status", "REQUEST_FAILED"))
    messages = tuple(str(m) for m in raw.get("message", []))
    response_time = int(raw.get("responseTime", 0))

    results_raw: object = raw.get("Results", {})
    if isinstance(results_raw, list):
        results_raw = results_raw[0] if results_raw else {}
    results: dict[str, Any] = dict(results_raw) if isinstance(results_raw, dict) else {}

    series: tuple[Series, ...] = ()
    surveys: tuple[SurveyInfo, ...] = ()
    popular_ids: tuple[str, ...] = ()

    if kind == "series":
        series = tuple(_parse_series(s) for s in results.get("series", []))
    elif kind == "survey":
        surveys = tuple(_parse_survey(s) for s in results.get("survey", []))
    elif kind == "popular":
        popular_ids = tuple(str(s.get("seriesID", "")) for s in results.get("series", []))

    return BLSResponse(
        status=status,
        response_time_ms=response_time,
        messages=messages,
        series=series,
        surveys=surveys,
        popular_ids=popular_ids,
    )


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
        return self._dir / f"bls_{key}.json"

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
        for f in self._dir.glob("bls_*.json"):
            f.unlink()
            count += 1
        return count


# ═══════════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════════

_BASE = "https://api.bls.gov/publicAPI/v2"
MAX_SERIES = 50
MAX_YEARS = 20


class BLSClientError(RuntimeError):
    """Raised on BLS API errors or client-side validation failures."""


class BLSClient:
    """Typed client for all seven BLS Public Data API v2 signatures.

    Usage::

        client = BLSClient(api_key="your-key")
        resp = client.get_series("CUUR0000SA0", start_year=2020, end_year=2024)
        for pt in resp.series[0].data:
            print(pt.year, pt.period_name, pt.value)
    """

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: Path | None = None,
        cache_ttl: int = 86400,
        timeout: float = 30.0,
    ) -> None:
        self._key = api_key
        self._http = httpx.Client(
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )
        default_cache = Path.home() / ".strata" / "cache" / "bls"
        self._cache = _DiskCache(cache_dir or default_cache, cache_ttl)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> BLSClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ── internal helpers ─────────────────────────────────────────

    def _cache_key(self, method: str, url: str, payload: dict[str, Any] | None) -> str:
        parts = [method, url]
        if payload is not None:
            parts.append(json.dumps(payload, sort_keys=True))
        return "|".join(parts)

    def _request(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
        *,
        kind: str = "series",
    ) -> BLSResponse:
        ck = self._cache_key(method, url, payload)
        cached = self._cache.get(ck)
        if cached is not None:
            data, age = cached
            resp = _parse_api_response(data, kind=kind)
            return replace(resp, cached=True, cache_age_seconds=round(age, 1))

        http_resp = self._http.get(url) if method == "GET" else self._http.post(url, json=payload)
        http_resp.raise_for_status()

        raw: dict[str, Any] = http_resp.json()
        status = str(raw.get("status", ""))
        if status != BLSStatus.REQUEST_SUCCEEDED:
            msgs = [str(m) for m in raw.get("message", [])]
            raise BLSClientError(f"BLS API {status}: {'; '.join(msgs)}")

        self._cache.put(ck, raw)
        return _parse_api_response(raw, kind=kind)

    def _build_payload(
        self,
        series_ids: list[str],
        start_year: int | None = None,
        end_year: int | None = None,
        *,
        catalog: bool = False,
        calculations: bool = False,
        annual_average: bool = False,
        aspects: bool = False,
    ) -> dict[str, Any]:
        if len(series_ids) > MAX_SERIES:
            raise BLSClientError(f"Max {MAX_SERIES} series per request, got {len(series_ids)}")
        if (
            start_year is not None
            and end_year is not None
            and (end_year - start_year + 1) > MAX_YEARS
        ):
            raise BLSClientError(f"Max {MAX_YEARS} year span, got {end_year - start_year + 1}")

        payload: dict[str, Any] = {"seriesid": series_ids}
        if start_year is not None:
            payload["startyear"] = str(start_year)
        if end_year is not None:
            payload["endyear"] = str(end_year)
        if self._key:
            payload["registrationkey"] = self._key
        if catalog:
            payload["catalog"] = True
        if calculations:
            payload["calculations"] = True
        if annual_average:
            payload["annualaverage"] = True
        if aspects:
            payload["aspects"] = True
        return payload

    # ── Signature 1: single series (GET, 3 years) ───────────────

    def get_series(self, series_id: str) -> BLSResponse:
        """Retrieve data for a single series (past 3 years)."""
        return self._request("GET", f"{_BASE}/timeseries/data/{series_id}")

    # ── Signature 2: multiple series (POST) ──────────────────────

    def get_multiple_series(
        self,
        series_ids: list[str],
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> BLSResponse:
        """Retrieve data for multiple series (up to 50)."""
        payload = self._build_payload(series_ids, start_year, end_year)
        return self._request("POST", f"{_BASE}/timeseries/data/", payload)

    # ── Signature 3: series with optional params (POST) ──────────

    def get_series_with_options(
        self,
        series_ids: list[str],
        start_year: int,
        end_year: int,
        *,
        catalog: bool = False,
        calculations: bool = False,
        annual_average: bool = False,
        aspects: bool = False,
    ) -> BLSResponse:
        """Retrieve series with catalog, calculations, averages, aspects."""
        payload = self._build_payload(
            series_ids,
            start_year,
            end_year,
            catalog=catalog,
            calculations=calculations,
            annual_average=annual_average,
            aspects=aspects,
        )
        return self._request("POST", f"{_BASE}/timeseries/data/", payload)

    # ── Signature 4: latest data point (GET) ─────────────────────

    def get_latest(self, series_id: str) -> BLSResponse:
        """Retrieve the most recent data point for a series."""
        return self._request("GET", f"{_BASE}/timeseries/data/{series_id}?latest=true")

    # ── Signature 5: popular series (GET) ────────────────────────

    def get_popular(self, survey: str | None = None) -> BLSResponse:
        """Retrieve the 25 most popular series IDs (optionally by survey)."""
        url = f"{_BASE}/timeseries/popular"
        if survey:
            url += f"?survey={survey}"
        return self._request("GET", url, kind="popular")

    # ── Signature 6: all surveys (GET) ───────────────────────────

    def get_all_surveys(self) -> BLSResponse:
        """Retrieve a list of all BLS surveys."""
        return self._request("GET", f"{_BASE}/surveys", kind="survey")

    # ── Signature 7: single survey (GET) ─────────────────────────

    def get_survey(self, abbreviation: str) -> BLSResponse:
        """Retrieve metadata for a single BLS survey."""
        return self._request("GET", f"{_BASE}/surveys/{abbreviation}", kind="survey")

    # ── Bulk helpers ─────────────────────────────────────────────

    def get_series_batch(
        self,
        series_ids: list[str],
        start_year: int,
        end_year: int,
        *,
        catalog: bool = False,
        calculations: bool = False,
        annual_average: bool = False,
        aspects: bool = False,
    ) -> BLSResponse:
        """Auto-chunks into MAX_SERIES batches and merges results."""
        all_series: list[Series] = []
        last_resp: BLSResponse | None = None
        for i in range(0, len(series_ids), MAX_SERIES):
            chunk = series_ids[i : i + MAX_SERIES]
            resp = self.get_series_with_options(
                chunk,
                start_year,
                end_year,
                catalog=catalog,
                calculations=calculations,
                annual_average=annual_average,
                aspects=aspects,
            )
            all_series.extend(resp.series)
            last_resp = resp
        if last_resp is None:
            raise BLSClientError("No series IDs provided")
        return replace(last_resp, series=tuple(all_series))

    # ── Cache management ─────────────────────────────────────────

    def clear_cache(self) -> int:
        """Remove all cached BLS responses. Returns count deleted."""
        return self._cache.clear()


# ═══════════════════════════════════════════════════════════════════
# Strata format converters
# ═══════════════════════════════════════════════════════════════════


def _pick_data_point(
    series: Series,
    year: int | None,
    period: str | None,
) -> DataPoint:
    """Select a specific data point from a series, or fall back to latest."""
    if year is not None and period is not None:
        pt = next(
            (dp for dp in series.data if dp.year == year and dp.period == period),
            None,
        )
        if pt is not None:
            return pt
    if year is not None:
        pt = series.annual_average(year)
        if pt is not None:
            return pt
        pt = next((dp for dp in series.data if dp.year == year), None)
        if pt is not None:
            return pt
    pt = series.latest_value()
    if pt is not None:
        return pt
    raise BLSClientError(f"No data point found for series {series.series_id}")


def _snapshot_hash(series_id: str, point: DataPoint) -> str:
    """Content-hash a data point for source pinning (Q5)."""
    content = json.dumps(
        {
            "series_id": series_id,
            "year": point.year,
            "period": point.period,
            "value": point.value,
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()


def _as_of_date(point: DataPoint) -> str:
    """Derive an as_of date from the data point's year/period."""
    if point.is_monthly and point.period.startswith("M"):
        month = int(point.period[1:])
        return date(point.year, month, 28).isoformat()
    return date(point.year, 12, 31).isoformat()


def series_to_primitive_yaml(
    series: Series,
    *,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    source_url: str,
    year: int | None = None,
    period: str | None = None,
    geo_codes: tuple[str, ...] = ("US",),
    geo_level: str = "country",
    geo_perspective: str = "supply",
    unit_kind: str = "stock",
    unit_dimension: str = "people",
    unit_denominator: str | None = None,
    unit_currency: str | None = None,
    distribution_shape: str = "normal",
    delivery_mode: str = "n/a",
) -> dict[str, Any]:
    """Convert a BLS Series to a Strata AtomicPrimitive YAML dict.

    Returns a dict ready for ``yaml.dump()`` that conforms to the
    AtomicPrimitive schema (models/primitive.py).
    """
    point = _pick_data_point(series, year, period)
    source_slug = f"bls-{series.series_id.lower()}-{point.year}"
    sha = _snapshot_hash(series.series_id, point)

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
        "as_of": _as_of_date(point),
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


def series_to_source_yaml(
    series: Series,
    *,
    source_url: str,
    year: int,
    description: str = "",
) -> dict[str, Any]:
    """Convert a BLS Series to a Strata source_registry YAML dict."""
    source_slug = f"bls-{series.series_id.lower()}-{year}"
    point = _pick_data_point(series, year, None)
    sha = _snapshot_hash(series.series_id, point)

    return {
        "kind": "source_registry",
        "slug": source_slug,
        "tier": "regulator",
        "url": source_url,
        "accessed": date.today().isoformat(),
        "snapshot_sha256": sha,
        "description": description or f"BLS series {series.series_id}, {year} data.",
    }


def capabilities() -> list[CapabilitySpec]:
    """Methods exposed to the LLM router (spec §5)."""
    from ._capability import CapabilityArg, CapabilitySpec

    return [
        CapabilitySpec(
            connector="bls",
            method="get_series",
            description=(
                "BLS time series by series ID (employment, wages, CPI). "
                "Use for US labor/inflation regulator data."
            ),
            returns="atomic primitive observations, unit varies, tier=regulator",
            args=[
                CapabilityArg(
                    name="series_id",
                    type="str",
                    description="BLS series ID (e.g. CES0500000001)",
                    example="CES0500000001",
                ),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="bls",
            method="get_latest",
            description="Latest single value for a BLS series.",
            returns="atomic primitive, unit varies, tier=regulator",
            args=[
                CapabilityArg(
                    name="series_id",
                    type="str",
                    description="BLS series ID",
                    example="CUUR0000SA0",
                ),
            ],
            source_tier="regulator",
        ),
    ]


from ._capability import CapabilitySpec as CapabilitySpec  # noqa: E402
