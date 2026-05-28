"""FDIC BankFind API client.

Typed wrappers for the FDIC BankFind API with disk caching
and conversion to Strata AtomicPrimitive / Source YAML format.

API reference: https://banks.data.fdic.gov/docs/
No authentication required. Rate limit: ~10 req/sec guideline.
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


class FDICFinancialField(StrEnum):
    """Common financial data fields from FDIC Call Reports."""

    ASSET = "ASSET"
    DEP = "DEP"
    NETINC = "NETINC"
    INTINC = "INTINC"
    NONII = "NONII"
    ROA = "ROA"
    ROE = "ROE"
    NITEFR = "NITEFR"
    EINTEXP = "EINTEXP"
    ELNATR = "ELNATR"
    EQ = "EQ"
    LNLSNET = "LNLSNET"
    SC = "SC"
    TRADE = "TRADE"
    FRETEFR = "FRETEFR"
    EEFFR = "EEFFR"


class FDICInstitutionField(StrEnum):
    """Common institution metadata fields."""

    CERTNUM = "CERTNUM"
    INSTNAME = "INSTNAME"
    CITY = "CITY"
    STNAME = "STNAME"
    ZIP = "ZIP"
    ASSET = "ASSET"
    DEP = "DEP"
    NETINC = "NETINC"
    ACTIVE = "ACTIVE"
    INSTCAT = "INSTCAT"
    SPECGRP = "SPECGRP"
    CHARTER_CLASS = "CHARTER_CLASS"
    REGAGENT = "REGAGENT"


class FDICSortOrder(StrEnum):
    """Sort direction for API queries."""

    ASC = "ASC"
    DESC = "DESC"


class FDICSpecialization(StrEnum):
    """Bank specialization groups."""

    COMMERCIAL = "Commercial Lending"
    SAVINGS = "Other Specialized < 1 Billion"
    SAVINGS_ASSOC = "All Other"


class FDICReportPeriod(StrEnum):
    """Common quarterly report dates (YYYYMMDD format)."""

    Q4_2023 = "20231231"
    Q3_2023 = "20230930"
    Q2_2023 = "20230630"
    Q1_2023 = "20230331"
    Q4_2022 = "20221231"
    Q3_2022 = "20220930"
    Q2_2022 = "20220630"
    Q1_2022 = "20220331"
    Q4_2021 = "20211231"
    Q4_2020 = "20201231"
    Q4_2019 = "20191231"
    Q4_2024 = "20241231"
    Q3_2024 = "20240930"
    Q2_2024 = "20240630"
    Q1_2024 = "20240331"


# ═══════════════════════════════════════════════════════════════════
# TypedDicts — raw FDIC JSON response shapes
# ═══════════════════════════════════════════════════════════════════


class FinancialRecordRaw(TypedDict, total=False):
    REPNM: str
    REPDTE: str
    CERT: str
    ASSET: str
    DEP: str
    NETINC: str
    INTINC: str
    NONII: str
    ROA: str
    ROE: str
    NITEFR: str
    EINTEXP: str
    ELNATR: str
    EQ: str
    LNLSNET: str
    SC: str
    STNAME: str
    CITY: str


class InstitutionRecordRaw(TypedDict, total=False):
    CERTNUM: str
    INSTNAME: str
    CITY: str
    STNAME: str
    ZIP: str
    ASSET: str
    DEP: str
    NETINC: str
    ACTIVE: str
    INSTCAT: str
    SPECGRP: str
    CHARTER_CLASS: str
    REGAGENT: str
    FED_RSSD: str


class FailureRecordRaw(TypedDict, total=False):
    CERT: str
    NAME: str
    CITY: str
    STATE: str
    FAILDATE: str
    SAVR: str
    FUND: str
    COST: str


class FDICApiResponseRaw(TypedDict, total=False):
    data: list[dict[str, Any]]
    totals: dict[str, int]
    meta: dict[str, Any]


# ═══════════════════════════════════════════════════════════════════
# Dataclasses — validated internal models
# ═══════════════════════════════════════════════════════════════════


def _safe_float(val: object) -> float | None:
    """Parse a value to float safely; FDIC fields are often string-encoded."""
    if val is None:
        return None
    try:
        result = float(val)  # type: ignore[arg-type]
        return result
    except (ValueError, TypeError):
        return None


def _safe_int(val: object) -> int | None:
    """Parse a value to int safely."""
    if val is None:
        return None
    try:
        return int(float(val))  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return None


@dataclass(frozen=True, slots=True)
class FinancialRecord:
    cert: int
    name: str
    report_date: str
    assets: float | None
    deposits: float | None
    net_income: float | None
    interest_income: float | None
    non_interest_income: float | None
    roa: float | None
    roe: float | None
    state: str
    city: str


@dataclass(frozen=True, slots=True)
class InstitutionRecord:
    cert: int
    name: str
    city: str
    state: str
    zip_code: str
    assets: float | None
    deposits: float | None
    active: bool
    specialization: str
    charter_class: str
    fed_rssd: int | None


@dataclass(frozen=True, slots=True)
class FailureRecord:
    cert: int
    name: str
    city: str
    state: str
    closing_date: str
    acquiring_institution: str
    fund: str
    estimated_loss: float | None


@dataclass(frozen=True, slots=True)
class BankSummary:
    period: str
    count: int
    total_assets: float | None
    total_deposits: float | None
    total_net_income: float | None


@dataclass(frozen=True, slots=True)
class LocationRecord:
    cert: int
    name: str
    address: str
    city: str
    state: str
    zip_code: str
    county: str


@dataclass(frozen=True, slots=True)
class HistoryRecord:
    cert: int
    name: str
    event_date: str
    event_type: str
    description: str


@dataclass(frozen=True, slots=True)
class FDICResponse:
    """Standard return type for every FDIC client call."""

    kind: str
    financials: tuple[FinancialRecord, ...] = ()
    institutions: tuple[InstitutionRecord, ...] = ()
    failures: tuple[FailureRecord, ...] = ()
    summaries: tuple[BankSummary, ...] = ()
    locations: tuple[LocationRecord, ...] = ()
    history: tuple[HistoryRecord, ...] = ()
    total: int = 0
    cached: bool = False
    cache_age_seconds: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# Response parsing
# ═══════════════════════════════════════════════════════════════════


def _parse_financial(raw: dict[str, Any]) -> FinancialRecord:
    data: dict[str, Any] = raw.get("data", raw)
    return FinancialRecord(
        cert=_safe_int(data.get("CERT")) or 0,
        name=str(data.get("REPNM", "")),
        report_date=str(data.get("REPDTE", "")),
        assets=_safe_float(data.get("ASSET")),
        deposits=_safe_float(data.get("DEP")),
        net_income=_safe_float(data.get("NETINC")),
        interest_income=_safe_float(data.get("INTINC")),
        non_interest_income=_safe_float(data.get("NONII")),
        roa=_safe_float(data.get("ROA")),
        roe=_safe_float(data.get("ROE")),
        state=str(data.get("STNAME", "")),
        city=str(data.get("CITY", "")),
    )


def _parse_institution(raw: dict[str, Any]) -> InstitutionRecord:
    data: dict[str, Any] = raw.get("data", raw)
    active_val = data.get("ACTIVE")
    active = str(active_val) == "1" if active_val is not None else False
    return InstitutionRecord(
        cert=_safe_int(data.get("CERTNUM")) or 0,
        name=str(data.get("INSTNAME", "")),
        city=str(data.get("CITY", "")),
        state=str(data.get("STNAME", "")),
        zip_code=str(data.get("ZIP", "")),
        assets=_safe_float(data.get("ASSET")),
        deposits=_safe_float(data.get("DEP")),
        active=active,
        specialization=str(data.get("SPECGRP", "")),
        charter_class=str(data.get("CHARTER_CLASS", "")),
        fed_rssd=_safe_int(data.get("FED_RSSD")),
    )


def _parse_failure(raw: dict[str, Any]) -> FailureRecord:
    data: dict[str, Any] = raw.get("data", raw)
    return FailureRecord(
        cert=_safe_int(data.get("CERT")) or 0,
        name=str(data.get("NAME", "")),
        city=str(data.get("CITY", "")),
        state=str(data.get("STATE", "")),
        closing_date=str(data.get("FAILDATE", "")),
        acquiring_institution=str(data.get("SAVR", "")),
        fund=str(data.get("FUND", "")),
        estimated_loss=_safe_float(data.get("COST")),
    )


def _parse_location(raw: dict[str, Any]) -> LocationRecord:
    data: dict[str, Any] = raw.get("data", raw)
    return LocationRecord(
        cert=_safe_int(data.get("CERT")) or 0,
        name=str(data.get("NAME", data.get("INSTNAME", ""))),
        address=str(data.get("ADDRESS", data.get("MAINOFF", ""))),
        city=str(data.get("CITY", "")),
        state=str(data.get("STALP", data.get("STNAME", ""))),
        zip_code=str(data.get("ZIP", "")),
        county=str(data.get("COUNTY", "")),
    )


def _parse_history(raw: dict[str, Any]) -> HistoryRecord:
    data: dict[str, Any] = raw.get("data", raw)
    return HistoryRecord(
        cert=_safe_int(data.get("CERT")) or 0,
        name=str(data.get("INSTNAME", "")),
        event_date=str(data.get("EFFDATE", data.get("PROCDATE", ""))),
        event_type=str(data.get("ACESSION", data.get("CHANGECODE", ""))),
        description=str(data.get("CHANGECODE_DESC", data.get("CLASS", ""))),
    )


def _extract_items(body: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    """Extract data items and total count from an FDIC API response."""
    data_list: list[dict[str, Any]] = body.get("data", [])
    meta: dict[str, Any] = body.get("meta", {})
    totals: dict[str, Any] = body.get("totals", {})
    total_count = int(meta.get("total", totals.get("count", len(data_list))))
    return data_list, total_count


def _parse_response(body: dict[str, Any], *, kind: str) -> FDICResponse:
    """Parse an FDIC API response dict into a typed FDICResponse."""
    items, total_count = _extract_items(body)

    financials: tuple[FinancialRecord, ...] = ()
    institutions: tuple[InstitutionRecord, ...] = ()
    failures: tuple[FailureRecord, ...] = ()
    locations: tuple[LocationRecord, ...] = ()
    history: tuple[HistoryRecord, ...] = ()

    if kind == "financials":
        financials = tuple(_parse_financial(i) for i in items)
    elif kind == "institutions":
        institutions = tuple(_parse_institution(i) for i in items)
    elif kind == "failures":
        failures = tuple(_parse_failure(i) for i in items)
    elif kind == "locations":
        locations = tuple(_parse_location(i) for i in items)
    elif kind == "history":
        history = tuple(_parse_history(i) for i in items)

    return FDICResponse(
        kind=kind,
        financials=financials,
        institutions=institutions,
        failures=failures,
        locations=locations,
        history=history,
        total=total_count,
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
        return self._dir / f"fdic_{key}.json"

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
        for f in self._dir.glob("fdic_*.json"):
            f.unlink()
            count += 1
        return count


# ═══════════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════════

_BASE = "https://banks.data.fdic.gov/api"


class FDICClientError(RuntimeError):
    """Raised on FDIC API errors or client-side validation failures."""


class FDICClient:
    """Typed client for the FDIC BankFind API.

    Usage::

        client = FDICClient()
        resp = client.get_financials("20231231")
        for f in resp.financials:
            print(f.name, f.assets)
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        cache_ttl: int = 86400,
        timeout: float = 30.0,
    ) -> None:
        self._http = httpx.Client(timeout=timeout)
        default_cache = Path.home() / ".strata" / "cache" / "fdic"
        self._cache = _DiskCache(cache_dir or default_cache, cache_ttl)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> FDICClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ── internal helpers ─────────────────────────────────────────

    def _cache_key(self, endpoint: str, params: dict[str, str]) -> str:
        parts = [endpoint, json.dumps(params, sort_keys=True)]
        return "|".join(parts)

    def _request(
        self,
        endpoint: str,
        params: dict[str, str],
        *,
        kind: str,
    ) -> FDICResponse:
        url = f"{_BASE}/{endpoint}"

        ck = self._cache_key(endpoint, params)
        cached = self._cache.get(ck)
        if cached is not None:
            data, age = cached
            resp = _parse_response(data, kind=kind)
            return replace(resp, cached=True, cache_age_seconds=round(age, 1))

        http_resp = self._http.get(url, params=params)
        http_resp.raise_for_status()

        body: Any = http_resp.json()
        if not isinstance(body, dict):
            raise FDICClientError(f"FDIC API returned unexpected type: {type(body).__name__}")

        body_dict = cast(dict[str, Any], body)

        # Check for API error messages
        error_msg = body_dict.get("error")
        if error_msg is not None:
            raise FDICClientError(f"FDIC API error: {error_msg}")

        self._cache.put(ck, body_dict)
        return _parse_response(body_dict, kind=kind)

    def _request_all_pages(
        self,
        endpoint: str,
        params: dict[str, str],
        *,
        kind: str,
        limit: int = 100,
    ) -> FDICResponse:
        """Fetch all pages and merge results."""
        params["limit"] = str(limit)
        params["offset"] = "0"

        first = self._request(endpoint, params, kind=kind)
        if first.total <= limit:
            return first

        all_financials = list(first.financials)
        all_institutions = list(first.institutions)
        all_failures = list(first.failures)
        all_locations = list(first.locations)
        all_history = list(first.history)

        fetched = limit
        while fetched < first.total:
            page_params = {**params, "offset": str(fetched)}
            resp = self._request(endpoint, page_params, kind=kind)
            all_financials.extend(resp.financials)
            all_institutions.extend(resp.institutions)
            all_failures.extend(resp.failures)
            all_locations.extend(resp.locations)
            all_history.extend(resp.history)

            fetched += limit
            # Break if we got fewer items than expected (API truncation)
            total_items = (
                len(resp.financials)
                + len(resp.institutions)
                + len(resp.failures)
                + len(resp.locations)
                + len(resp.history)
            )
            if total_items == 0:
                break

        return replace(
            first,
            financials=tuple(all_financials),
            institutions=tuple(all_institutions),
            failures=tuple(all_failures),
            locations=tuple(all_locations),
            history=tuple(all_history),
        )

    # ── financials ──────────────────────────────────────────────

    def get_financials(
        self,
        report_date: str,
        fields: list[str] | None = None,
        limit: int = 100,
        sort_by: str | None = None,
        sort_order: str = "DESC",
    ) -> FDICResponse:
        """Retrieve quarterly financial data for institutions.

        Args:
            report_date: Report date in YYYYMMDD format (e.g. "20231231").
            fields: Specific fields to return. None for default set.
            limit: Max results per page.
            sort_by: Field to sort by (e.g. "ASSET").
            sort_order: "ASC" or "DESC".
        """
        default_fields = [
            "CERT",
            "REPNM",
            "REPDTE",
            "ASSET",
            "DEP",
            "NETINC",
            "INTINC",
            "NONII",
            "ROA",
            "ROE",
            "STNAME",
            "CITY",
        ]
        params: dict[str, str] = {
            "filters": f"REPDTE:{report_date}",
            "fields": ",".join(fields or default_fields),
            "limit": str(limit),
        }
        if sort_by is not None:
            params["sort_by"] = sort_by
            params["sort_order"] = sort_order
        return self._request("financials", params, kind="financials")

    # ── institutions ────────────────────────────────────────────

    def get_institution(self, cert: int) -> FDICResponse:
        """Retrieve details for a single institution by FDIC certificate number."""
        params: dict[str, str] = {
            "filters": f"CERTNUM:{cert}",
            "fields": ",".join(
                [
                    "CERTNUM",
                    "INSTNAME",
                    "CITY",
                    "STNAME",
                    "ZIP",
                    "ASSET",
                    "DEP",
                    "NETINC",
                    "ACTIVE",
                    "SPECGRP",
                    "CHARTER_CLASS",
                    "REGAGENT",
                    "FED_RSSD",
                ]
            ),
            "limit": "1",
        }
        return self._request("institutions", params, kind="institutions")

    def search_institutions(
        self,
        name: str,
        state: str | None = None,
        limit: int = 25,
    ) -> FDICResponse:
        """Search institutions by name, optionally filtered by state.

        Args:
            name: Free-text name search.
            state: State name filter (e.g. "California").
            limit: Max results.
        """
        params: dict[str, str] = {
            "search": name,
            "fields": ",".join(
                [
                    "CERTNUM",
                    "INSTNAME",
                    "CITY",
                    "STNAME",
                    "ZIP",
                    "ASSET",
                    "DEP",
                    "ACTIVE",
                    "SPECGRP",
                    "CHARTER_CLASS",
                ]
            ),
            "limit": str(limit),
        }
        if state is not None:
            params["filters"] = f"STNAME:{state}"
        return self._request("institutions", params, kind="institutions")

    def get_active_institutions(
        self,
        state: str | None = None,
        limit: int = 100,
    ) -> FDICResponse:
        """Retrieve all active banking institutions, optionally by state.

        Args:
            state: State name filter (e.g. "California").
            limit: Max results per page.
        """
        filters = "ACTIVE:1"
        if state is not None:
            filters += f" AND STNAME:{state}"
        params: dict[str, str] = {
            "filters": filters,
            "fields": ",".join(
                [
                    "CERTNUM",
                    "INSTNAME",
                    "CITY",
                    "STNAME",
                    "ZIP",
                    "ASSET",
                    "DEP",
                    "ACTIVE",
                    "SPECGRP",
                    "CHARTER_CLASS",
                ]
            ),
            "limit": str(limit),
            "sort_by": "ASSET",
            "sort_order": "DESC",
        }
        return self._request("institutions", params, kind="institutions")

    # ── failures ────────────────────────────────────────────────

    def get_failures(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> FDICResponse:
        """Retrieve bank failure records.

        Args:
            start_date: Start date filter (YYYYMMDD).
            end_date: End date filter (YYYYMMDD).
            limit: Max results.
        """
        params: dict[str, str] = {
            "fields": "CERT,NAME,CITY,STATE,FAILDATE,SAVR,FUND,COST",
            "limit": str(limit),
            "sort_by": "FAILDATE",
            "sort_order": "DESC",
        }
        filters: list[str] = []
        if start_date is not None:
            filters.append(f"FAILDATE:['{start_date}' TO *]")
        if end_date is not None:
            filters.append(f"FAILDATE:[* TO '{end_date}']")
        if filters:
            params["filters"] = " AND ".join(filters)
        return self._request("failures", params, kind="failures")

    def get_failure_count(
        self,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> int:
        """Return the count of bank failures in a date range.

        Args:
            start_year: Start year (inclusive).
            end_year: End year (inclusive).
        """
        params: dict[str, str] = {
            "fields": "CERT",
            "limit": "1",
        }
        filters: list[str] = []
        if start_year is not None:
            filters.append(f"FAILDATE:['{start_year}0101' TO *]")
        if end_year is not None:
            filters.append(f"FAILDATE:[* TO '{end_year}1231']")
        if filters:
            params["filters"] = " AND ".join(filters)
        resp = self._request("failures", params, kind="failures")
        return resp.total

    # ── largest / aggregate queries ─────────────────────────────

    def get_largest_banks(
        self,
        report_date: str,
        limit: int = 25,
    ) -> FDICResponse:
        """Retrieve the largest banks by total assets for a report period.

        Args:
            report_date: Report date in YYYYMMDD format.
            limit: Number of banks to return.
        """
        params: dict[str, str] = {
            "filters": f"REPDTE:{report_date}",
            "fields": ",".join(
                [
                    "CERT",
                    "REPNM",
                    "REPDTE",
                    "ASSET",
                    "DEP",
                    "NETINC",
                    "INTINC",
                    "NONII",
                    "ROA",
                    "ROE",
                    "STNAME",
                    "CITY",
                ]
            ),
            "sort_by": "ASSET",
            "sort_order": "DESC",
            "limit": str(limit),
        }
        return self._request("financials", params, kind="financials")

    def get_total_assets(self, report_date: str) -> float | None:
        """Return total industry assets (in $thousands) for a report period.

        Uses the FDIC summary endpoint with aggregation.
        """
        params: dict[str, str] = {
            "filters": f"REPDTE:{report_date}",
            "fields": "ASSET",
            "agg_by": "REPDTE",
            "agg_sum_fields": "ASSET",
            "limit": "1",
        }
        resp = self._request("financials", params, kind="financials")
        if resp.financials:
            return resp.financials[0].assets
        return None

    def get_total_deposits(self, report_date: str) -> float | None:
        """Return total industry deposits (in $thousands) for a report period.

        Uses the FDIC summary endpoint with aggregation.
        """
        params: dict[str, str] = {
            "filters": f"REPDTE:{report_date}",
            "fields": "DEP",
            "agg_by": "REPDTE",
            "agg_sum_fields": "DEP",
            "limit": "1",
        }
        resp = self._request("financials", params, kind="financials")
        if resp.financials:
            return resp.financials[0].deposits
        return None

    # ── state / industry summary ────────────────────────────────

    def get_state_summary(
        self,
        state: str,
        report_date: str,
    ) -> FDICResponse:
        """Retrieve financial summary for all banks in a state.

        Args:
            state: State name (e.g. "California").
            report_date: Report date in YYYYMMDD format.
        """
        params: dict[str, str] = {
            "filters": f"REPDTE:{report_date} AND STNAME:{state}",
            "fields": ",".join(
                [
                    "CERT",
                    "REPNM",
                    "REPDTE",
                    "ASSET",
                    "DEP",
                    "NETINC",
                    "ROA",
                    "ROE",
                    "STNAME",
                    "CITY",
                ]
            ),
            "sort_by": "ASSET",
            "sort_order": "DESC",
            "limit": "100",
        }
        return self._request_all_pages("financials", params, kind="financials", limit=100)

    def get_industry_summary(self, report_date: str) -> BankSummary:
        """Return aggregate industry summary for a report period.

        Fetches institution count and aggregate financial figures.
        """
        # Get count of active institutions
        inst_params: dict[str, str] = {
            "filters": "ACTIVE:1",
            "fields": "CERTNUM",
            "limit": "1",
        }
        inst_resp = self._request("institutions", inst_params, kind="institutions")
        count = inst_resp.total

        total_assets = self.get_total_assets(report_date)
        total_deposits = self.get_total_deposits(report_date)

        # Get total net income via aggregation
        ni_params: dict[str, str] = {
            "filters": f"REPDTE:{report_date}",
            "fields": "NETINC",
            "agg_by": "REPDTE",
            "agg_sum_fields": "NETINC",
            "limit": "1",
        }
        ni_resp = self._request("financials", ni_params, kind="financials")
        total_ni = ni_resp.financials[0].net_income if ni_resp.financials else None

        return BankSummary(
            period=report_date,
            count=count,
            total_assets=total_assets,
            total_deposits=total_deposits,
            total_net_income=total_ni,
        )

    def get_historical_summary(
        self,
        start_year: int,
        end_year: int,
    ) -> FDICResponse:
        """Retrieve historical aggregate data via the summary endpoint.

        Args:
            start_year: Start year (inclusive).
            end_year: End year (inclusive).
        """
        # Build year-end date filters
        dates = [f"{y}1231" for y in range(start_year, end_year + 1)]
        date_filter = " OR ".join(f"REPDTE:{d}" for d in dates)
        params: dict[str, str] = {
            "filters": date_filter,
            "fields": "YEAR,DEP,ASSET,NETINC",
            "agg_by": "YEAR",
            "agg_term_fields": "YEAR",
            "agg_sum_fields": "ASSET,DEP,NETINC",
            "limit": str(len(dates)),
        }
        return self._request("summary", params, kind="financials")

    # ── single-bank time series ─────────────────────────────────

    def get_bank_financials(
        self,
        cert: int,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> FDICResponse:
        """Retrieve financial time series for a single institution.

        Args:
            cert: FDIC certificate number.
            start_date: Start report date (YYYYMMDD). None for all.
            end_date: End report date (YYYYMMDD). None for all.
        """
        filters = [f"CERT:{cert}"]
        if start_date is not None:
            filters.append(f"REPDTE:['{start_date}' TO *]")
        if end_date is not None:
            filters.append(f"REPDTE:[* TO '{end_date}']")

        params: dict[str, str] = {
            "filters": " AND ".join(filters),
            "fields": ",".join(
                [
                    "CERT",
                    "REPNM",
                    "REPDTE",
                    "ASSET",
                    "DEP",
                    "NETINC",
                    "INTINC",
                    "NONII",
                    "ROA",
                    "ROE",
                    "STNAME",
                    "CITY",
                ]
            ),
            "sort_by": "REPDTE",
            "sort_order": "DESC",
            "limit": "100",
        }
        return self._request_all_pages("financials", params, kind="financials", limit=100)

    # ── locations ───────────────────────────────────────────────

    def get_locations(self, cert: int) -> FDICResponse:
        """Retrieve branch locations for an institution.

        Args:
            cert: FDIC certificate number.
        """
        params: dict[str, str] = {
            "filters": f"CERT:{cert}",
            "fields": "CERT,NAME,ADDRESS,CITY,STALP,ZIP,COUNTY",
            "limit": "500",
        }
        return self._request_all_pages("locations", params, kind="locations", limit=500)

    # ── history ─────────────────────────────────────────────────

    def get_history(self, cert: int) -> FDICResponse:
        """Retrieve structure change history for an institution.

        Args:
            cert: FDIC certificate number.
        """
        params: dict[str, str] = {
            "filters": f"CERT:{cert}",
            "fields": "CERT,INSTNAME,EFFDATE,CHANGECODE,CHANGECODE_DESC,CLASS",
            "limit": "100",
        }
        return self._request_all_pages("history", params, kind="history", limit=100)

    # ── cache management ────────────────────────────────────────

    def clear_cache(self) -> int:
        """Remove all cached FDIC responses. Returns count deleted."""
        return self._cache.clear()


# ═══════════════════════════════════════════════════════════════════
# Strata format converters
# ═══════════════════════════════════════════════════════════════════


def _snapshot_hash(
    cert: int,
    field: str,
    report_date: str,
    value: float | None,
) -> str:
    """Content-hash a data point for source pinning (Q5)."""
    content = json.dumps(
        {
            "cert": cert,
            "field": field,
            "report_date": report_date,
            "value": value,
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()


def financial_to_primitive_yaml(
    record: FinancialRecord,
    *,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    field: str = "ASSET",
    source_url: str = "https://banks.data.fdic.gov/",
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
    """Convert an FDIC FinancialRecord to a Strata AtomicPrimitive YAML dict.

    Returns a dict ready for ``yaml.dump()`` that conforms to the
    AtomicPrimitive schema (models/primitive.py).
    """
    # Map field names to record attributes
    field_map: dict[str, float | None] = {
        "ASSET": record.assets,
        "DEP": record.deposits,
        "NETINC": record.net_income,
        "INTINC": record.interest_income,
        "NONII": record.non_interest_income,
        "ROA": record.roa,
        "ROE": record.roe,
    }
    value = field_map.get(field)

    # Format report date for as_of
    rd = record.report_date
    as_of = f"{rd[:4]}-{rd[4:6]}-{rd[6:8]}" if len(rd) == 8 else rd

    source_slug = f"fdic-{record.cert}-{field.lower()}-{record.report_date}"
    sha = _snapshot_hash(record.cert, field, record.report_date, value)

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
        "value": value,
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


def financial_to_source_yaml(
    record: FinancialRecord,
    *,
    field: str = "ASSET",
    source_url: str = "https://banks.data.fdic.gov/",
    description: str = "",
) -> dict[str, Any]:
    """Convert an FDIC FinancialRecord to a Strata source_registry YAML dict."""
    field_map: dict[str, float | None] = {
        "ASSET": record.assets,
        "DEP": record.deposits,
        "NETINC": record.net_income,
        "INTINC": record.interest_income,
        "NONII": record.non_interest_income,
        "ROA": record.roa,
        "ROE": record.roe,
    }
    value = field_map.get(field)

    source_slug = f"fdic-{record.cert}-{field.lower()}-{record.report_date}"
    sha = _snapshot_hash(record.cert, field, record.report_date, value)

    return {
        "kind": "source_registry",
        "slug": source_slug,
        "tier": "regulator",
        "url": source_url,
        "accessed": date.today().isoformat(),
        "snapshot_sha256": sha,
        "description": description
        or (
            f"FDIC {field} for {record.name} (cert {record.cert}), "
            f"report date {record.report_date}."
        ),
    }


def institution_count_to_primitive_yaml(
    count: int,
    *,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    source_url: str = "https://banks.data.fdic.gov/",
    state: str | None = None,
    as_of: str | None = None,
    geo_codes: tuple[str, ...] = ("US",),
    geo_level: str = "country",
    geo_perspective: str = "supply",
) -> dict[str, Any]:
    """Convert an FDIC institution count to a Strata AtomicPrimitive YAML dict.

    Useful for converting the total number of active banks (national or
    per-state) into a primitive for market-sizing frameworks.
    """
    today = date.today().isoformat()
    source_slug = "fdic-institution-count"
    if state is not None:
        source_slug += f"-{state.lower().replace(' ', '-')}"

    sha_content = json.dumps(
        {"count": count, "state": state, "as_of": as_of or today},
        sort_keys=True,
    )
    sha = hashlib.sha256(sha_content.encode()).hexdigest()

    return {
        "kind": "atomic_primitive",
        "slug": primitive_slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": name,
        "description": description,
        "value": count,
        "unit": {"kind": "stock", "dimension": "count"},
        "as_of": as_of or today,
        "geo": {"level": geo_level, "codes": list(geo_codes)},
        "geo_perspective": geo_perspective,
        "distribution_shape": "point",
        "delivery_mode": "n/a",
        "source": {
            "slug": source_slug,
            "tier": "regulator",
            "url": source_url,
            "accessed": today,
            "snapshot_sha256": sha,
        },
    }


def capabilities() -> list[CapabilitySpec]:
    """Methods exposed to the LLM router (spec §5)."""
    from ._capability import CapabilityArg, CapabilitySpec

    return [
        CapabilitySpec(
            connector="fdic",
            method="get_total_assets",
            description="Total US banking system assets for a report period.",
            returns="atomic primitive, unit=currency USD, tier=regulator",
            args=[
                CapabilityArg(
                    name="report_date",
                    type="str",
                    description="Quarter end YYYYMMDD",
                    example="20241231",
                ),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="fdic",
            method="get_total_deposits",
            description="Total US banking system deposits for a report period.",
            returns="atomic primitive, unit=currency USD, tier=regulator",
            args=[
                CapabilityArg(
                    name="report_date",
                    type="str",
                    description="Quarter end YYYYMMDD",
                    example="20241231",
                ),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="fdic",
            method="get_industry_summary",
            description=("Bank count, total assets, total deposits, total income for a quarter."),
            returns="atomic primitive bundle, tier=regulator",
            args=[
                CapabilityArg(
                    name="report_date",
                    type="str",
                    description="Quarter end YYYYMMDD",
                    example="20241231",
                ),
            ],
            source_tier="regulator",
        ),
    ]


from ._capability import CapabilitySpec as CapabilitySpec  # noqa: E402
