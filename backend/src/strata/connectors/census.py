"""US Census Bureau API client.

Typed wrappers for County Business Patterns (CBP), Statistics of US
Businesses (SUSB), Annual Business Survey (ABS), and Economic Census
datasets with disk caching and conversion to Strata AtomicPrimitive /
Source YAML format.

API reference: https://www.census.gov/data/developers/data-sets.html
Response format: JSON arrays — first row is column headers, remaining
rows are data. No authentication required for basic access; an API key
raises rate limits.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, TypedDict, cast

import httpx

# ═══════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════


class CensusDataset(StrEnum):
    """Supported Census Bureau datasets for market sizing."""

    CBP = "cbp"
    SUSB = "susb"
    ABS = "abscs"
    ECONOMIC_CENSUS = "ecnbasic"


class CensusGeoLevel(StrEnum):
    """Geography specifications for the ``for`` query parameter."""

    US = "us:*"
    STATE = "state:*"
    COUNTY = "county:*"
    MSA = "metropolitan statistical area/micropolitan statistical area:*"


class CensusNAICS(StrEnum):
    """Common NAICS codes for tech market sizing."""

    ALL_SECTORS = "00"
    SOFTWARE_PUBLISHERS = "5112"
    DATA_PROCESSING = "5182"
    INTERNET_PUBLISHING = "5191"
    COMPUTER_SYSTEMS_DESIGN = "5415"
    MANAGEMENT_CONSULTING = "5416"
    SCIENTIFIC_RD = "5417"
    DEPOSITORY_CREDIT = "5221"
    INSURANCE_AGENCIES = "5242"


# Census sentinel values indicating suppressed / withheld / unavailable data
_CENSUS_MISSING: frozenset[str] = frozenset({"S", "D", "N", "X", "Z", ""})


# ═══════════════════════════════════════════════════════════════════
# TypedDicts — raw Census JSON response shapes
# ═══════════════════════════════════════════════════════════════════


class CBPRecordRaw(TypedDict, total=False):
    """Raw column values from County Business Patterns."""

    NAICS2017: str
    NAICS2017_LABEL: str
    ESTAB: str
    EMP: str
    PAYANN: str
    EMPSZES: str
    state: str
    county: str
    us: str


class SUSBRecordRaw(TypedDict, total=False):
    """Raw column values from Statistics of US Businesses."""

    NAICS2017: str
    NAICS2017_LABEL: str
    FIRM: str
    ESTAB: str
    EMP: str
    PAYANN: str
    RCPSZFI: str
    us: str


class EconomicCensusRecordRaw(TypedDict, total=False):
    """Raw column values from the Economic Census."""

    NAICS2017: str
    NAICS2017_LABEL: str
    RCPTOT: str
    ESTAB: str
    EMP: str
    us: str


# ═══════════════════════════════════════════════════════════════════
# Dataclasses — validated internal models
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class IndustryRecord:
    """A single industry row from CBP or Economic Census."""

    naics_code: str
    naics_label: str
    establishments: int
    employees: int
    annual_payroll: int
    year: int
    geo_level: str
    geo_code: str


@dataclass(frozen=True, slots=True)
class FirmRecord:
    """A single firm-level row from SUSB."""

    naics_code: str
    naics_label: str
    firms: int
    establishments: int
    employees: int
    annual_payroll: int
    year: int


@dataclass(frozen=True, slots=True)
class CensusResponse:
    """Standard return type for every Census client call."""

    dataset: str
    year: int
    records: tuple[IndustryRecord, ...] | tuple[FirmRecord, ...]
    raw_headers: tuple[str, ...]
    cached: bool = False
    cache_age_seconds: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# Response parsing
# ═══════════════════════════════════════════════════════════════════


def _safe_int(value: str) -> int:
    """Parse a Census numeric field, treating sentinel values as 0."""
    if value in _CENSUS_MISSING:
        return 0
    try:
        cleaned = value.replace(",", "")
        return int(float(cleaned))
    except (ValueError, TypeError):
        return 0


def _rows_to_dicts(
    raw: list[list[str]],
) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    """Convert Census array-of-arrays into header tuple + list of dicts."""
    if len(raw) < 1:
        return (), []
    headers = tuple(raw[0])
    rows = [{headers[i]: cell for i, cell in enumerate(row)} for row in raw[1:]]
    return headers, rows


def _geo_from_row(row: dict[str, str]) -> tuple[str, str]:
    """Extract geography level and code from a Census row dict."""
    if "county" in row and "state" in row:
        return "county", f"{row['state']}{row['county']}"
    if "state" in row:
        return "state", row["state"]
    if "us" in row:
        return "us", row["us"]
    if "metropolitan statistical area/micropolitan statistical area" in row:
        return "msa", row["metropolitan statistical area/micropolitan statistical area"]
    return "unknown", ""


def _parse_industry_rows(
    rows: list[dict[str, str]],
    year: int,
) -> tuple[IndustryRecord, ...]:
    """Parse dicts into IndustryRecord tuples, skipping empty rows."""
    records: list[IndustryRecord] = []
    for row in rows:
        naics = row.get("NAICS2017", "")
        if not naics:
            continue
        geo_level, geo_code = _geo_from_row(row)
        records.append(
            IndustryRecord(
                naics_code=naics,
                naics_label=row.get("NAICS2017_LABEL", ""),
                establishments=_safe_int(row.get("ESTAB", "0")),
                employees=_safe_int(row.get("EMP", "0")),
                annual_payroll=_safe_int(row.get("PAYANN", "0")),
                year=year,
                geo_level=geo_level,
                geo_code=geo_code,
            )
        )
    return tuple(records)


def _parse_firm_rows(
    rows: list[dict[str, str]],
    year: int,
) -> tuple[FirmRecord, ...]:
    """Parse dicts into FirmRecord tuples, skipping empty rows."""
    records: list[FirmRecord] = []
    for row in rows:
        naics = row.get("NAICS2017", "")
        if not naics:
            continue
        records.append(
            FirmRecord(
                naics_code=naics,
                naics_label=row.get("NAICS2017_LABEL", ""),
                firms=_safe_int(row.get("FIRM", "0")),
                establishments=_safe_int(row.get("ESTAB", "0")),
                employees=_safe_int(row.get("EMP", "0")),
                annual_payroll=_safe_int(row.get("PAYANN", "0")),
                year=year,
            )
        )
    return tuple(records)


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
        return self._dir / f"census_{key}.json"

    def get(self, params: str) -> tuple[list[list[str]], float] | None:
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
            data: list[list[str]] = raw.get("_data", [])
            return data, age
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            path.unlink(missing_ok=True)
            return None

    def put(self, params: str, data: list[list[str]]) -> None:
        path = self._path(self._key(params))
        payload: dict[str, Any] = {"_ts": time.time(), "_data": data}
        path.write_text(json.dumps(payload, indent=2))

    def clear(self) -> int:
        count = 0
        for f in self._dir.glob("census_*.json"):
            f.unlink()
            count += 1
        return count


# ═══════════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════════

_BASE = "https://api.census.gov/data"


class CensusClientError(RuntimeError):
    """Raised on Census API errors or client-side validation failures."""


class CensusClient:
    """Typed client for US Census Bureau data APIs.

    Usage::

        client = CensusClient(api_key="your-key")
        resp = client.get_cbp(2021, naics="5112")
        for rec in resp.records:
            print(rec.naics_code, rec.naics_label, rec.establishments)
    """

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: Path | None = None,
        cache_ttl: int = 604800,
        timeout: float = 30.0,
    ) -> None:
        self._key = api_key
        self._http = httpx.Client(timeout=timeout, follow_redirects=True)
        default_cache = Path.home() / ".strata" / "cache" / "census"
        self._cache = _DiskCache(cache_dir or default_cache, cache_ttl)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> CensusClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ── internal helpers ─────────────────────────────────────────

    def _cache_key(self, url: str, params: dict[str, str]) -> str:
        parts = [url, json.dumps(params, sort_keys=True)]
        return "|".join(parts)

    def _request(self, url: str, params: dict[str, str]) -> list[list[str]]:
        ck = self._cache_key(url, params)
        cached = self._cache.get(ck)
        if cached is not None:
            data, _age = cached
            return data

        if self._key:
            params["key"] = self._key

        http_resp = self._http.get(url, params=params)

        if http_resp.status_code == 204:
            raise CensusClientError("Census API returned no data (HTTP 204)")
        if http_resp.status_code != 200:
            raise CensusClientError(
                f"Census API HTTP {http_resp.status_code}: {http_resp.text[:500]}"
            )

        try:
            parsed: object = http_resp.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise CensusClientError(
                f"Census API returned invalid JSON: {http_resp.text[:200]}"
            ) from exc

        if not isinstance(parsed, list):
            raise CensusClientError("Census API returned unexpected response shape")

        raw = cast(list[list[str]], parsed)
        if len(raw) < 1:
            raise CensusClientError("Census API returned empty response")

        # Cache without the API key in params
        cache_params = {k: v for k, v in params.items() if k != "key"}
        ck_clean = self._cache_key(url, cache_params)
        self._cache.put(ck_clean, raw)

        return raw

    def _request_cached(
        self, url: str, params: dict[str, str]
    ) -> tuple[list[list[str]], bool, float]:
        """Like _request but returns cache metadata alongside data."""
        cache_params = {k: v for k, v in params.items() if k != "key"}
        ck = self._cache_key(url, cache_params)
        cached = self._cache.get(ck)
        if cached is not None:
            data, age = cached
            return data, True, age

        raw = self._request(url, params)
        return raw, False, 0.0

    def _build_url(self, dataset: str, year: int) -> str:
        return f"{_BASE}/{year}/{dataset}"

    def _build_params(
        self,
        variables: tuple[str, ...],
        geo_for: str,
        geo_in: str | None = None,
        predicates: dict[str, str] | None = None,
    ) -> dict[str, str]:
        params: dict[str, str] = {
            "get": ",".join(variables),
            "for": geo_for,
        }
        if geo_in is not None:
            params["in"] = geo_in
        if predicates:
            for k, v in predicates.items():
                params[k] = v
        return params

    # ── CBP queries ──────────────────────────────────────────────

    def get_cbp(
        self,
        year: int,
        naics: str | None = None,
        geo: str = "us:*",
        variables: tuple[str, ...] = (
            "NAICS2017",
            "NAICS2017_LABEL",
            "ESTAB",
            "EMP",
            "PAYANN",
        ),
    ) -> CensusResponse:
        """Query County Business Patterns for a given year.

        Returns establishment counts, employees, and payroll by NAICS
        industry at the specified geography level.
        """
        predicates: dict[str, str] | None = None
        if naics is not None:
            predicates = {"NAICS2017": naics}

        url = self._build_url(CensusDataset.CBP, year)
        params = self._build_params(variables, geo, predicates=predicates)
        raw, is_cached, age = self._request_cached(url, params)

        headers, rows = _rows_to_dicts(raw)
        records = _parse_industry_rows(rows, year)

        return CensusResponse(
            dataset=CensusDataset.CBP,
            year=year,
            records=records,
            raw_headers=headers,
            cached=is_cached,
            cache_age_seconds=round(age, 1),
        )

    def get_cbp_by_state(
        self,
        year: int,
        naics: str | None = None,
    ) -> CensusResponse:
        """Query CBP broken out by state."""
        return self.get_cbp(year, naics=naics, geo=CensusGeoLevel.STATE)

    def get_cbp_by_county(
        self,
        year: int,
        state_fips: str,
        naics: str | None = None,
    ) -> CensusResponse:
        """Query CBP for all counties within a state."""
        predicates: dict[str, str] | None = None
        if naics is not None:
            predicates = {"NAICS2017": naics}

        url = self._build_url(CensusDataset.CBP, year)
        params = self._build_params(
            ("NAICS2017", "NAICS2017_LABEL", "ESTAB", "EMP", "PAYANN"),
            "county:*",
            geo_in=f"state:{state_fips}",
            predicates=predicates,
        )
        raw, is_cached, age = self._request_cached(url, params)

        headers, rows = _rows_to_dicts(raw)
        records = _parse_industry_rows(rows, year)

        return CensusResponse(
            dataset=CensusDataset.CBP,
            year=year,
            records=records,
            raw_headers=headers,
            cached=is_cached,
            cache_age_seconds=round(age, 1),
        )

    # ── SUSB queries ─────────────────────────────────────────────

    def get_susb(
        self,
        year: int,
        naics: str | None = None,
    ) -> CensusResponse:
        """Query Statistics of US Businesses for firm-level data.

        Returns firm counts, establishments, employees, and payroll by
        NAICS industry at the national level.
        """
        variables = (
            "NAICS2017",
            "NAICS2017_LABEL",
            "FIRM",
            "ESTAB",
            "EMP",
            "PAYANN",
        )
        predicates: dict[str, str] | None = None
        if naics is not None:
            predicates = {"NAICS2017": naics}

        url = self._build_url(CensusDataset.SUSB, year)
        params = self._build_params(variables, CensusGeoLevel.US, predicates=predicates)
        raw, is_cached, age = self._request_cached(url, params)

        headers, rows = _rows_to_dicts(raw)
        records = _parse_firm_rows(rows, year)

        return CensusResponse(
            dataset=CensusDataset.SUSB,
            year=year,
            records=records,
            raw_headers=headers,
            cached=is_cached,
            cache_age_seconds=round(age, 1),
        )

    # ── Generic query (power users) ─────────────────────────────

    def query(
        self,
        dataset: str,
        year: int,
        variables: tuple[str, ...],
        geo_for: str = "us:*",
        geo_in: str | None = None,
        predicates: dict[str, str] | None = None,
    ) -> CensusResponse:
        """Generic query against any Census dataset.

        Returns IndustryRecord tuples (NAICS-keyed) for arbitrary
        variable selections. For SUSB firm-level queries, prefer
        ``get_susb()`` which returns FirmRecord tuples.
        """
        url = self._build_url(dataset, year)
        params = self._build_params(variables, geo_for, geo_in, predicates)
        raw, is_cached, age = self._request_cached(url, params)

        headers, rows = _rows_to_dicts(raw)
        records = _parse_industry_rows(rows, year)

        return CensusResponse(
            dataset=dataset,
            year=year,
            records=records,
            raw_headers=headers,
            cached=is_cached,
            cache_age_seconds=round(age, 1),
        )

    # ── Cache management ─────────────────────────────────────────

    def clear_cache(self) -> int:
        """Remove all cached Census responses. Returns count deleted."""
        return self._cache.clear()


# ═══════════════════════════════════════════════════════════════════
# Strata format converters
# ═══════════════════════════════════════════════════════════════════


def _snapshot_hash(
    dataset: str,
    year: int,
    naics_code: str,
    geo_level: str,
    value_field: str,
    value: int,
) -> str:
    """Content-hash a Census data point for source pinning (Q5)."""
    content = json.dumps(
        {
            "dataset": dataset,
            "year": year,
            "naics_code": naics_code,
            "geo_level": geo_level,
            "value_field": value_field,
            "value": value,
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()


def _pick_value(record: IndustryRecord, value_field: str) -> int:
    """Extract the requested numeric field from an IndustryRecord."""
    field_map: dict[str, int] = {
        "establishments": record.establishments,
        "employees": record.employees,
        "annual_payroll": record.annual_payroll,
    }
    if value_field not in field_map:
        valid = ", ".join(sorted(field_map))
        raise CensusClientError(f"Unknown value_field {value_field!r}; expected one of: {valid}")
    return field_map[value_field]


def industry_to_primitive_yaml(
    record: IndustryRecord,
    *,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    source_url: str,
    unit_kind: str = "stock",
    unit_dimension: str = "organizations",
    value_field: str = "establishments",
    geo_codes: tuple[str, ...] = ("US",),
    geo_level: str = "country",
    geo_perspective: str = "supply",
    distribution_shape: str = "normal",
    delivery_mode: str = "n/a",
) -> dict[str, Any]:
    """Convert a Census IndustryRecord to a Strata AtomicPrimitive YAML dict.

    Returns a dict ready for ``yaml.dump()`` that conforms to the
    AtomicPrimitive schema (models/primitive.py).
    """
    value = _pick_value(record, value_field)
    source_slug = f"census-cbp-{record.naics_code.lower()}-{record.year}"
    sha = _snapshot_hash(
        "cbp", record.year, record.naics_code, record.geo_level, value_field, value
    )

    unit: dict[str, str] = {"kind": unit_kind, "dimension": unit_dimension}
    if unit_kind == "flow" and value_field == "annual_payroll":
        unit["currency"] = "USD"
        unit["denominator"] = "year"

    return {
        "kind": "atomic_primitive",
        "slug": primitive_slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": name,
        "description": description,
        "value": value,
        "unit": unit,
        "as_of": date(record.year, 12, 31).isoformat(),
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


def industry_to_source_yaml(
    record: IndustryRecord,
    *,
    source_url: str,
    description: str = "",
) -> dict[str, Any]:
    """Convert a Census IndustryRecord to a Strata source_registry YAML dict."""
    source_slug = f"census-cbp-{record.naics_code.lower()}-{record.year}"
    sha = _snapshot_hash(
        "cbp",
        record.year,
        record.naics_code,
        record.geo_level,
        "establishments",
        record.establishments,
    )

    return {
        "kind": "source_registry",
        "slug": source_slug,
        "tier": "regulator",
        "url": source_url,
        "accessed": date.today().isoformat(),
        "snapshot_sha256": sha,
        "description": (
            description
            or f"Census CBP NAICS {record.naics_code} ({record.naics_label}), {record.year} data."
        ),
    }


def firm_to_primitive_yaml(
    record: FirmRecord,
    *,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    source_url: str,
    unit_kind: str = "stock",
    unit_dimension: str = "organizations",
    value_field: str = "firms",
    geo_codes: tuple[str, ...] = ("US",),
    geo_level: str = "country",
    geo_perspective: str = "supply",
    distribution_shape: str = "normal",
    delivery_mode: str = "n/a",
) -> dict[str, Any]:
    """Convert a Census FirmRecord to a Strata AtomicPrimitive YAML dict."""
    field_map: dict[str, int] = {
        "firms": record.firms,
        "establishments": record.establishments,
        "employees": record.employees,
        "annual_payroll": record.annual_payroll,
    }
    if value_field not in field_map:
        valid = ", ".join(sorted(field_map))
        raise CensusClientError(f"Unknown value_field {value_field!r}; expected one of: {valid}")
    value = field_map[value_field]

    source_slug = f"census-susb-{record.naics_code.lower()}-{record.year}"
    sha = _snapshot_hash("susb", record.year, record.naics_code, "us", value_field, value)

    unit: dict[str, str] = {"kind": unit_kind, "dimension": unit_dimension}
    if unit_kind == "flow" and value_field == "annual_payroll":
        unit["currency"] = "USD"
        unit["denominator"] = "year"

    return {
        "kind": "atomic_primitive",
        "slug": primitive_slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": name,
        "description": description,
        "value": value,
        "unit": unit,
        "as_of": date(record.year, 12, 31).isoformat(),
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


def firm_to_source_yaml(
    record: FirmRecord,
    *,
    source_url: str,
    description: str = "",
) -> dict[str, Any]:
    """Convert a Census FirmRecord to a Strata source_registry YAML dict."""
    source_slug = f"census-susb-{record.naics_code.lower()}-{record.year}"
    sha = _snapshot_hash("susb", record.year, record.naics_code, "us", "firms", record.firms)

    return {
        "kind": "source_registry",
        "slug": source_slug,
        "tier": "regulator",
        "url": source_url,
        "accessed": date.today().isoformat(),
        "snapshot_sha256": sha,
        "description": (
            description
            or f"Census SUSB NAICS {record.naics_code} ({record.naics_label}), {record.year} data."
        ),
    }
