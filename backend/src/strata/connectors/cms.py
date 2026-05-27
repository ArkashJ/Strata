"""CMS (Centers for Medicare & Medicaid Services) Open Data API client.

Typed wrappers for CMS public datasets with disk caching
and conversion to Strata AtomicPrimitive / Source YAML format.

API reference: https://data.cms.gov
No authentication required for public datasets.
Data updates infrequently (quarterly/annually).
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


class CMSDataset(StrEnum):
    """Key CMS dataset identifiers (URL path segments or UUIDs)."""

    MEDICARE_ENROLLMENT = "medicare-total-enrollment"
    MEDICARE_SPENDING = "medicare-spending-by-state"
    PART_D_SPENDING = "medicare-part-d-spending-by-drug"
    PART_D_PRESCRIBERS = "medicare-part-d-prescribers-by-provider"
    HOSPITAL_GENERAL = "hospital-general-information"
    HOSPITAL_READMISSIONS = "hospital-readmissions-reduction-program"
    HOSPITAL_MORTALITY = "hospital-mortality"
    PHYSICIAN_COMPARE = "physician-compare-national-downloadable-file"
    NURSING_HOMES = "nursing-homes-including-rehab-services"
    NATIONAL_HEALTH_EXPENDITURE = "national-health-expenditure-data"
    MEDICAID_ENROLLMENT = "medicaid-enrollment"
    HOME_HEALTH = "home-health-care-agencies"
    HOSPICE = "hospice-providers"
    DIALYSIS = "dialysis-facility-compare"


class CMSState(StrEnum):
    """US state and territory FIPS postal codes."""

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
    PR = "PR"


class CMSMetric(StrEnum):
    """Common metric types returned by CMS datasets."""

    TOTAL_SPENDING = "total_spending"
    PER_CAPITA_SPENDING = "per_capita_spending"
    BENEFICIARIES = "beneficiaries"
    CLAIMS = "claims"
    PROVIDERS = "providers"
    AVERAGE_COST = "average_cost"


# ═══════════════════════════════════════════════════════════════════
# TypedDicts — raw CMS JSON response shapes
# ═══════════════════════════════════════════════════════════════════


class EnrollmentRecordRaw(TypedDict, total=False):
    """Raw fields from Medicare enrollment datasets."""

    year: str
    state: str
    state_name: str
    total_enrollment: str
    original_medicare_enrollment: str
    medicare_advantage_enrollment: str
    part_a_enrollment: str
    part_b_enrollment: str
    part_d_enrollment: str
    aged_enrollment: str
    disabled_enrollment: str


class SpendingRecordRaw(TypedDict, total=False):
    """Raw fields from Medicare spending datasets."""

    year: str
    state: str
    state_name: str
    total_spending: str
    per_capita_spending: str
    beneficiaries: str
    total_claims: str
    hospital_spending: str
    physician_spending: str
    outpatient_spending: str
    snf_spending: str
    home_health_spending: str
    hospice_spending: str


class ProviderRecordRaw(TypedDict, total=False):
    """Raw fields from provider/physician datasets."""

    npi: str
    last_name: str
    first_name: str
    city: str
    state: str
    specialty: str
    total_claims: str
    total_services: str
    total_beneficiaries: str
    total_submitted_charges: str
    total_allowed_amount: str
    total_payment_amount: str


class DrugSpendingRecordRaw(TypedDict, total=False):
    """Raw fields from Part D drug spending datasets."""

    drug_name: str
    generic_name: str
    year: str
    total_spending: str
    total_claims: str
    total_beneficiaries: str
    average_cost_per_claim: str
    total_annual_spending_per_user: str
    unit_count: str


class NHERecordRaw(TypedDict, total=False):
    """Raw fields from National Health Expenditure datasets."""

    year: str
    category: str
    amount: str
    per_capita: str
    percent_gdp: str
    annual_growth_rate: str


class HospitalRecordRaw(TypedDict, total=False):
    """Raw fields from Hospital General Information datasets."""

    facility_id: str
    facility_name: str
    address: str
    city: str
    state: str
    zip_code: str
    hospital_type: str
    hospital_ownership: str
    overall_rating: str
    emergency_services: str
    meets_criteria_for_promoting_interoperability: str


# ═══════════════════════════════════════════════════════════════════
# Dataclasses — validated internal models
# ═══════════════════════════════════════════════════════════════════


def _safe_float(raw: object) -> float | None:
    """Parse a string/numeric value to float, returning None on failure."""
    if raw is None:
        return None
    try:
        val = float(str(raw).replace(",", "").replace("$", "").strip())
        return val
    except (ValueError, TypeError):
        return None


def _safe_int(raw: object) -> int | None:
    """Parse a string/numeric value to int, returning None on failure."""
    if raw is None:
        return None
    try:
        return int(float(str(raw).replace(",", "").strip()))
    except (ValueError, TypeError):
        return None


@dataclass(frozen=True, slots=True)
class EnrollmentRecord:
    """Medicare enrollment data for a state and year."""

    year: int
    state: str
    total_enrollment: int | None
    part_a: int | None
    part_b: int | None
    part_d: int | None
    medicare_advantage: int | None
    original_medicare: int | None


@dataclass(frozen=True, slots=True)
class SpendingRecord:
    """Medicare spending data for a state and year."""

    year: int
    state: str
    total_spending: float | None
    per_capita: float | None
    beneficiaries: int | None
    claims: int | None
    hospital_spending: float | None
    physician_spending: float | None


@dataclass(frozen=True, slots=True)
class ProviderRecord:
    """Provider/physician data from CMS."""

    npi: str
    name: str
    city: str
    state: str
    specialty: str
    total_claims: int | None
    total_services: int | None
    total_beneficiaries: int | None
    total_submitted: float | None
    total_allowed: float | None
    total_payment: float | None


@dataclass(frozen=True, slots=True)
class DrugSpendingRecord:
    """Part D drug spending data."""

    drug_name: str
    generic_name: str
    year: int
    total_spending: float | None
    total_claims: int | None
    total_beneficiaries: int | None
    avg_cost_per_claim: float | None


@dataclass(frozen=True, slots=True)
class NationalHealthExpenditure:
    """National Health Expenditure data point."""

    year: int
    category: str
    amount: float | None
    per_capita: float | None
    percent_gdp: float | None


@dataclass(frozen=True, slots=True)
class HospitalRecord:
    """Hospital general information."""

    facility_id: str
    facility_name: str
    city: str
    state: str
    hospital_type: str
    hospital_ownership: str
    overall_rating: str
    emergency_services: bool


@dataclass(frozen=True, slots=True)
class CMSResponse:
    """Standard return type for every CMS client call."""

    kind: str
    enrollments: tuple[EnrollmentRecord, ...] = ()
    spending: tuple[SpendingRecord, ...] = ()
    providers: tuple[ProviderRecord, ...] = ()
    drug_spending: tuple[DrugSpendingRecord, ...] = ()
    nhe: tuple[NationalHealthExpenditure, ...] = ()
    hospitals: tuple[HospitalRecord, ...] = ()
    total: int = 0
    cached: bool = False
    cache_age_seconds: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# Response parsing
# ═══════════════════════════════════════════════════════════════════


def _parse_enrollment(raw: dict[str, Any]) -> EnrollmentRecord:
    year_val = _safe_int(raw.get("year") or raw.get("Year") or raw.get("YEAR"))
    return EnrollmentRecord(
        year=year_val or 0,
        state=str(raw.get("state") or raw.get("State") or raw.get("STATE") or ""),
        total_enrollment=_safe_int(
            raw.get("total_enrollment")
            or raw.get("Total_Enrollment")
            or raw.get("total_medicare_enrollment")
        ),
        part_a=_safe_int(raw.get("part_a_enrollment") or raw.get("Part_A_Enrollment")),
        part_b=_safe_int(raw.get("part_b_enrollment") or raw.get("Part_B_Enrollment")),
        part_d=_safe_int(raw.get("part_d_enrollment") or raw.get("Part_D_Enrollment")),
        medicare_advantage=_safe_int(
            raw.get("medicare_advantage_enrollment")
            or raw.get("Medicare_Advantage_Enrollment")
            or raw.get("ma_enrollment")
        ),
        original_medicare=_safe_int(
            raw.get("original_medicare_enrollment") or raw.get("Original_Medicare_Enrollment")
        ),
    )


def _parse_spending(raw: dict[str, Any]) -> SpendingRecord:
    year_val = _safe_int(raw.get("year") or raw.get("Year") or raw.get("YEAR"))
    return SpendingRecord(
        year=year_val or 0,
        state=str(raw.get("state") or raw.get("State") or raw.get("STATE") or ""),
        total_spending=_safe_float(
            raw.get("total_spending") or raw.get("Total_Spending") or raw.get("total_actual_costs")
        ),
        per_capita=_safe_float(
            raw.get("per_capita_spending")
            or raw.get("Per_Capita_Spending")
            or raw.get("per_capita_actual_costs")
        ),
        beneficiaries=_safe_int(
            raw.get("beneficiaries") or raw.get("Beneficiaries") or raw.get("total_beneficiaries")
        ),
        claims=_safe_int(raw.get("total_claims") or raw.get("Total_Claims")),
        hospital_spending=_safe_float(raw.get("hospital_spending") or raw.get("Hospital_Spending")),
        physician_spending=_safe_float(
            raw.get("physician_spending") or raw.get("Physician_Spending")
        ),
    )


def _parse_provider(raw: dict[str, Any]) -> ProviderRecord:
    first = str(raw.get("first_name") or raw.get("First_Name") or "")
    last = str(raw.get("last_name") or raw.get("Last_Name") or "")
    name = (
        f"{first} {last}".strip()
        if (first or last)
        else str(raw.get("provider_name") or raw.get("Provider_Name") or "")
    )
    return ProviderRecord(
        npi=str(raw.get("npi") or raw.get("NPI") or ""),
        name=name,
        city=str(raw.get("city") or raw.get("City") or raw.get("CITY") or ""),
        state=str(raw.get("state") or raw.get("State") or raw.get("STATE") or ""),
        specialty=str(
            raw.get("specialty") or raw.get("Specialty") or raw.get("provider_type") or ""
        ),
        total_claims=_safe_int(
            raw.get("total_claims") or raw.get("Total_Claims") or raw.get("number_of_services")
        ),
        total_services=_safe_int(
            raw.get("total_services") or raw.get("Total_Services") or raw.get("number_of_services")
        ),
        total_beneficiaries=_safe_int(
            raw.get("total_beneficiaries")
            or raw.get("Total_Beneficiaries")
            or raw.get("number_of_medicare_beneficiaries")
        ),
        total_submitted=_safe_float(
            raw.get("total_submitted_charges")
            or raw.get("Total_Submitted_Charges")
            or raw.get("total_submitted_chrg_amt")
        ),
        total_allowed=_safe_float(
            raw.get("total_allowed_amount")
            or raw.get("Total_Allowed_Amount")
            or raw.get("total_medicare_allowed_amt")
        ),
        total_payment=_safe_float(
            raw.get("total_payment_amount")
            or raw.get("Total_Payment_Amount")
            or raw.get("total_medicare_payment_amt")
        ),
    )


def _parse_drug_spending(raw: dict[str, Any]) -> DrugSpendingRecord:
    year_val = _safe_int(raw.get("year") or raw.get("Year") or raw.get("YEAR"))
    return DrugSpendingRecord(
        drug_name=str(raw.get("drug_name") or raw.get("Drug_Name") or raw.get("brand_name") or ""),
        generic_name=str(
            raw.get("generic_name") or raw.get("Generic_Name") or raw.get("gnrc_name") or ""
        ),
        year=year_val or 0,
        total_spending=_safe_float(
            raw.get("total_spending") or raw.get("Total_Spending") or raw.get("total_drug_cost")
        ),
        total_claims=_safe_int(
            raw.get("total_claims") or raw.get("Total_Claims") or raw.get("total_claim_count")
        ),
        total_beneficiaries=_safe_int(
            raw.get("total_beneficiaries")
            or raw.get("Total_Beneficiaries")
            or raw.get("bene_count")
        ),
        avg_cost_per_claim=_safe_float(
            raw.get("average_cost_per_claim")
            or raw.get("Average_Cost_Per_Claim")
            or raw.get("avg_cost_per_claim")
        ),
    )


def _parse_nhe(raw: dict[str, Any]) -> NationalHealthExpenditure:
    year_val = _safe_int(raw.get("year") or raw.get("Year") or raw.get("YEAR"))
    return NationalHealthExpenditure(
        year=year_val or 0,
        category=str(raw.get("category") or raw.get("Category") or raw.get("type") or ""),
        amount=_safe_float(raw.get("amount") or raw.get("Amount") or raw.get("expenditure")),
        per_capita=_safe_float(
            raw.get("per_capita") or raw.get("Per_Capita") or raw.get("per_capita_amount")
        ),
        percent_gdp=_safe_float(
            raw.get("percent_gdp") or raw.get("Percent_GDP") or raw.get("pct_of_gdp")
        ),
    )


def _parse_hospital(raw: dict[str, Any]) -> HospitalRecord:
    emergency_raw = str(raw.get("emergency_services") or raw.get("Emergency_Services") or "No")
    return HospitalRecord(
        facility_id=str(raw.get("facility_id") or raw.get("Facility_ID") or ""),
        facility_name=str(raw.get("facility_name") or raw.get("Facility_Name") or ""),
        city=str(raw.get("city") or raw.get("City") or ""),
        state=str(raw.get("state") or raw.get("State") or ""),
        hospital_type=str(raw.get("hospital_type") or raw.get("Hospital_Type") or ""),
        hospital_ownership=str(
            raw.get("hospital_ownership") or raw.get("Hospital_Ownership") or ""
        ),
        overall_rating=str(raw.get("overall_rating") or raw.get("Overall_Rating") or ""),
        emergency_services=emergency_raw.lower() in ("yes", "true", "1", "y"),
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
        return self._dir / f"cms_{key}.json"

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
        for f in self._dir.glob("cms_*.json"):
            f.unlink()
            count += 1
        return count


# ═══════════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════════

_BASE = "https://data.cms.gov/data-api/v1/dataset"
_PROVIDER_BASE = "https://data.cms.gov/provider-data/api/1/datastore/sql"


class CMSClientError(RuntimeError):
    """Raised on CMS API errors or client-side validation failures."""


class CMSClient:
    """Typed client for the CMS Open Data API.

    Usage::

        client = CMSClient()
        resp = client.get_enrollment(year=2022, state="CA")
        for e in resp.enrollments:
            print(e.year, e.state, e.total_enrollment)
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        cache_ttl: int = 604800,
        timeout: float = 30.0,
    ) -> None:
        self._http = httpx.Client(timeout=timeout)
        default_cache = Path.home() / ".strata" / "cache" / "cms"
        self._cache = _DiskCache(cache_dir or default_cache, cache_ttl)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> CMSClient:
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
        params: dict[str, str] | None = None,
        *,
        kind: str,
    ) -> CMSResponse:
        """Execute a CMS API request with caching and parsing."""
        request_params = params or {}
        ck = self._cache_key(url, request_params)
        cached = self._cache.get(ck)
        if cached is not None:
            data, age = cached
            return self._parse_list_response(data, kind=kind, cached=True, age=age)

        http_resp = self._http.get(url, params=request_params if request_params else None)
        http_resp.raise_for_status()

        body: Any = http_resp.json()

        if isinstance(body, dict):
            body_dict = cast(dict[str, Any], body)
            # Some CMS endpoints wrap data in a "data" key
            if "data" in body_dict:
                raw_data: Any = body_dict["data"]
                if isinstance(raw_data, list):
                    body = cast(list[Any], raw_data)
                else:
                    raise CMSClientError(
                        f"CMS API 'data' field is not a list: {type(raw_data).__name__}"
                    )
            elif "error" in body_dict or "message" in body_dict:
                msg = str(body_dict.get("error") or body_dict.get("message", ""))
                raise CMSClientError(f"CMS API error: {msg}")
            else:
                # Single-object response — wrap in a list
                body = [body_dict]

        if not isinstance(body, list):
            raise CMSClientError(f"CMS API returned unexpected type: {type(body).__name__}")

        raw = cast(list[Any], body)
        self._cache.put(ck, raw)
        return self._parse_list_response(raw, kind=kind)

    def _parse_list_response(
        self,
        data: list[Any],
        *,
        kind: str,
        cached: bool = False,
        age: float = 0.0,
    ) -> CMSResponse:
        """Parse a list of JSON objects into typed CMSResponse."""
        enrollments: tuple[EnrollmentRecord, ...] = ()
        spending_records: tuple[SpendingRecord, ...] = ()
        providers: tuple[ProviderRecord, ...] = ()
        drug_spending_records: tuple[DrugSpendingRecord, ...] = ()
        nhe_records: tuple[NationalHealthExpenditure, ...] = ()
        hospitals: tuple[HospitalRecord, ...] = ()

        records: list[dict[str, Any]] = [
            cast(dict[str, Any], r) for r in data if isinstance(r, dict)
        ]

        if kind == "enrollment":
            enrollments = tuple(_parse_enrollment(r) for r in records)
        elif kind == "spending":
            spending_records = tuple(_parse_spending(r) for r in records)
        elif kind == "provider":
            providers = tuple(_parse_provider(r) for r in records)
        elif kind == "drug_spending":
            drug_spending_records = tuple(_parse_drug_spending(r) for r in records)
        elif kind == "nhe":
            nhe_records = tuple(_parse_nhe(r) for r in records)
        elif kind == "hospital":
            hospitals = tuple(_parse_hospital(r) for r in records)

        return CMSResponse(
            kind=kind,
            enrollments=enrollments,
            spending=spending_records,
            providers=providers,
            drug_spending=drug_spending_records,
            nhe=nhe_records,
            hospitals=hospitals,
            total=len(records),
            cached=cached,
            cache_age_seconds=round(age, 1),
        )

    def _dataset_url(self, dataset: str | CMSDataset) -> str:
        """Build the full URL for a CMS dataset."""
        return f"{_BASE}/{dataset}/data"

    def _build_filters(
        self,
        *,
        year: int | None = None,
        state: str | CMSState | None = None,
        extra: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Build query parameter filters for CMS API requests."""
        params: dict[str, str] = {}
        if year is not None:
            params["filter[year]"] = str(year)
        if state is not None:
            params["filter[state]"] = str(state)
        if extra:
            params.update(extra)
        return params

    # ── enrollment endpoints ────────────────────────────────────

    def get_enrollment(
        self,
        year: int | None = None,
        state: str | CMSState | None = None,
        limit: int = 500,
    ) -> CMSResponse:
        """Retrieve Medicare enrollment data.

        Args:
            year: Filter by year (e.g. 2022).
            state: Filter by state code (e.g. "CA").
            limit: Maximum records to return.
        """
        url = self._dataset_url(CMSDataset.MEDICARE_ENROLLMENT)
        params = self._build_filters(year=year, state=state)
        params["size"] = str(limit)
        return self._request(url, params, kind="enrollment")

    def get_enrollment_trends(
        self,
        start_year: int,
        end_year: int,
        state: str | CMSState | None = None,
    ) -> CMSResponse:
        """Retrieve enrollment data across a range of years.

        Args:
            start_year: First year (inclusive).
            end_year: Last year (inclusive).
            state: Optional state code filter.
        """
        # CMS API does not support range queries; fetch each year and merge
        all_enrollments: list[EnrollmentRecord] = []
        cached_any = False
        max_age = 0.0

        for yr in range(start_year, end_year + 1):
            resp = self.get_enrollment(year=yr, state=state)
            all_enrollments.extend(resp.enrollments)
            if resp.cached:
                cached_any = True
                max_age = max(max_age, resp.cache_age_seconds)

        return CMSResponse(
            kind="enrollment",
            enrollments=tuple(all_enrollments),
            total=len(all_enrollments),
            cached=cached_any,
            cache_age_seconds=round(max_age, 1),
        )

    # ── spending endpoints ──────────────────────────────────────

    def get_spending(
        self,
        year: int | None = None,
        state: str | CMSState | None = None,
        limit: int = 500,
    ) -> CMSResponse:
        """Retrieve Medicare spending data by state.

        Args:
            year: Filter by year.
            state: Filter by state code.
            limit: Maximum records to return.
        """
        url = self._dataset_url(CMSDataset.MEDICARE_SPENDING)
        params = self._build_filters(year=year, state=state)
        params["size"] = str(limit)
        return self._request(url, params, kind="spending")

    def get_spending_trends(
        self,
        start_year: int,
        end_year: int,
        state: str | CMSState | None = None,
    ) -> CMSResponse:
        """Retrieve spending data across a range of years.

        Args:
            start_year: First year (inclusive).
            end_year: Last year (inclusive).
            state: Optional state code filter.
        """
        all_spending: list[SpendingRecord] = []
        cached_any = False
        max_age = 0.0

        for yr in range(start_year, end_year + 1):
            resp = self.get_spending(year=yr, state=state)
            all_spending.extend(resp.spending)
            if resp.cached:
                cached_any = True
                max_age = max(max_age, resp.cache_age_seconds)

        return CMSResponse(
            kind="spending",
            spending=tuple(all_spending),
            total=len(all_spending),
            cached=cached_any,
            cache_age_seconds=round(max_age, 1),
        )

    def get_per_capita_spending(
        self,
        year: int | None = None,
        state: str | CMSState | None = None,
    ) -> CMSResponse:
        """Retrieve per-capita Medicare spending.

        Convenience wrapper around get_spending that returns
        the same response (per_capita field is always populated).
        """
        return self.get_spending(year=year, state=state)

    # ── drug spending endpoints ─────────────────────────────────

    def get_drug_spending(
        self,
        year: int | None = None,
        limit: int = 100,
    ) -> CMSResponse:
        """Retrieve Part D drug spending data.

        Args:
            year: Filter by year.
            limit: Maximum records to return.
        """
        url = self._dataset_url(CMSDataset.PART_D_SPENDING)
        params: dict[str, str] = {"size": str(limit)}
        if year is not None:
            params["filter[year]"] = str(year)
        return self._request(url, params, kind="drug_spending")

    def get_top_drugs(
        self,
        year: int | None = None,
        limit: int = 25,
    ) -> CMSResponse:
        """Retrieve the highest-cost Part D drugs.

        Args:
            year: Filter by year.
            limit: Number of top drugs to return.
        """
        url = self._dataset_url(CMSDataset.PART_D_SPENDING)
        params: dict[str, str] = {
            "size": str(limit),
            "sort": "total_spending",
        }
        if year is not None:
            params["filter[year]"] = str(year)
        return self._request(url, params, kind="drug_spending")

    # ── provider endpoints ──────────────────────────────────────

    def get_providers(
        self,
        state: str | CMSState | None = None,
        specialty: str | None = None,
        limit: int = 100,
    ) -> CMSResponse:
        """Retrieve provider/physician data.

        Args:
            state: Filter by state code.
            specialty: Filter by specialty description.
            limit: Maximum records to return.
        """
        url = self._dataset_url(CMSDataset.PHYSICIAN_COMPARE)
        params: dict[str, str] = {"size": str(limit)}
        if state is not None:
            params["filter[state]"] = str(state)
        if specialty is not None:
            params["filter[specialty]"] = specialty
        return self._request(url, params, kind="provider")

    def get_part_d_prescribers(
        self,
        state: str | CMSState | None = None,
        year: int | None = None,
        limit: int = 100,
    ) -> CMSResponse:
        """Retrieve Part D prescriber-level data.

        Args:
            state: Filter by state code.
            year: Filter by year.
            limit: Maximum records to return.
        """
        url = self._dataset_url(CMSDataset.PART_D_PRESCRIBERS)
        params = self._build_filters(year=year, state=state)
        params["size"] = str(limit)
        return self._request(url, params, kind="provider")

    # ── hospital endpoints ──────────────────────────────────────

    def get_hospital_info(
        self,
        state: str | CMSState | None = None,
        limit: int = 100,
    ) -> CMSResponse:
        """Retrieve hospital general information.

        Args:
            state: Filter by state code.
            limit: Maximum records to return.
        """
        url = self._dataset_url(CMSDataset.HOSPITAL_GENERAL)
        params: dict[str, str] = {"size": str(limit)}
        if state is not None:
            params["filter[state]"] = str(state)
        return self._request(url, params, kind="hospital")

    def get_readmission_rates(
        self,
        state: str | CMSState | None = None,
        limit: int = 100,
    ) -> CMSResponse:
        """Retrieve hospital readmission reduction program data.

        Args:
            state: Filter by state code.
            limit: Maximum records to return.
        """
        url = self._dataset_url(CMSDataset.HOSPITAL_READMISSIONS)
        params: dict[str, str] = {"size": str(limit)}
        if state is not None:
            params["filter[state]"] = str(state)
        return self._request(url, params, kind="hospital")

    # ── national health expenditure ─────────────────────────────

    def get_national_health_expenditure(
        self,
        year: int | None = None,
        limit: int = 500,
    ) -> CMSResponse:
        """Retrieve National Health Expenditure data.

        Args:
            year: Filter by year.
            limit: Maximum records to return.
        """
        url = self._dataset_url(CMSDataset.NATIONAL_HEALTH_EXPENDITURE)
        params: dict[str, str] = {"size": str(limit)}
        if year is not None:
            params["filter[year]"] = str(year)
        return self._request(url, params, kind="nhe")

    def get_nhe_trends(
        self,
        start_year: int,
        end_year: int,
    ) -> CMSResponse:
        """Retrieve NHE data across a range of years.

        Args:
            start_year: First year (inclusive).
            end_year: Last year (inclusive).
        """
        all_nhe: list[NationalHealthExpenditure] = []
        cached_any = False
        max_age = 0.0

        for yr in range(start_year, end_year + 1):
            resp = self.get_national_health_expenditure(year=yr)
            all_nhe.extend(resp.nhe)
            if resp.cached:
                cached_any = True
                max_age = max(max_age, resp.cache_age_seconds)

        return CMSResponse(
            kind="nhe",
            nhe=tuple(all_nhe),
            total=len(all_nhe),
            cached=cached_any,
            cache_age_seconds=round(max_age, 1),
        )

    # ── medicaid ────────────────────────────────────────────────

    def get_medicaid_enrollment(
        self,
        year: int | None = None,
        state: str | CMSState | None = None,
        limit: int = 500,
    ) -> CMSResponse:
        """Retrieve Medicaid enrollment data.

        Args:
            year: Filter by year.
            state: Filter by state code.
            limit: Maximum records to return.
        """
        url = self._dataset_url(CMSDataset.MEDICAID_ENROLLMENT)
        params = self._build_filters(year=year, state=state)
        params["size"] = str(limit)
        return self._request(url, params, kind="enrollment")

    # ── dataset catalog ─────────────────────────────────────────

    def get_dataset_catalog(self) -> CMSResponse:
        """List available CMS datasets from the data.json catalog.

        Returns an empty CMSResponse with total set to the number
        of datasets found. The raw catalog is cached for inspection.
        """
        url = "https://data.cms.gov/data.json"
        ck = self._cache_key(url, {})
        cached = self._cache.get(ck)
        if cached is not None:
            data, age = cached
            return CMSResponse(
                kind="catalog",
                total=len(data),
                cached=True,
                cache_age_seconds=round(age, 1),
            )

        http_resp = self._http.get(url)
        http_resp.raise_for_status()
        body: Any = http_resp.json()

        datasets: list[Any] = []
        if isinstance(body, dict):
            body_dict = cast(dict[str, Any], body)
            raw_ds: Any = body_dict.get("dataset", [])
            datasets = cast(list[Any], raw_ds) if isinstance(raw_ds, list) else []
        elif isinstance(body, list):
            datasets = cast(list[Any], body)

        self._cache.put(ck, datasets)
        return CMSResponse(
            kind="catalog",
            total=len(datasets),
        )

    # ── cache management ────────────────────────────────────────

    def clear_cache(self) -> int:
        """Remove all cached CMS responses. Returns count deleted."""
        return self._cache.clear()


# ═══════════════════════════════════════════════════════════════════
# Strata format converters
# ═══════════════════════════════════════════════════════════════════


def _snapshot_hash(fields: dict[str, Any]) -> str:
    """Content-hash a data point for source pinning (Q5)."""
    content = json.dumps(fields, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()


def enrollment_to_primitive_yaml(
    record: EnrollmentRecord,
    *,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    source_url: str,
    geo_codes: tuple[str, ...] = ("US",),
    geo_level: str = "state",
    geo_perspective: str = "supply",
    unit_kind: str = "stock",
    unit_dimension: str = "people",
    distribution_shape: str = "normal",
    delivery_mode: str = "n/a",
) -> dict[str, Any]:
    """Convert a CMS enrollment record to a Strata AtomicPrimitive YAML dict.

    Returns a dict ready for ``yaml.dump()`` that conforms to the
    AtomicPrimitive schema (models/primitive.py).
    """
    sha = _snapshot_hash(
        {
            "dataset": "medicare_enrollment",
            "year": record.year,
            "state": record.state,
            "total_enrollment": record.total_enrollment,
        }
    )
    source_slug = f"cms-enrollment-{record.state.lower()}-{record.year}"

    geo_code_list: list[str] = list(geo_codes)
    if record.state and record.state not in geo_code_list:
        geo_code_list = [record.state]

    return {
        "kind": "atomic_primitive",
        "slug": primitive_slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": name,
        "description": description,
        "value": record.total_enrollment,
        "unit": {"kind": unit_kind, "dimension": unit_dimension},
        "as_of": f"{record.year}-12-31",
        "geo": {"level": geo_level, "codes": geo_code_list},
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


def spending_to_primitive_yaml(
    record: SpendingRecord,
    *,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    source_url: str,
    value_field: str = "total_spending",
    geo_codes: tuple[str, ...] = ("US",),
    geo_level: str = "state",
    geo_perspective: str = "supply",
    unit_kind: str = "stock",
    unit_dimension: str = "currency",
    unit_currency: str = "USD",
    unit_denominator: str | None = None,
    distribution_shape: str = "normal",
    delivery_mode: str = "n/a",
) -> dict[str, Any]:
    """Convert a CMS spending record to a Strata AtomicPrimitive YAML dict.

    Args:
        value_field: Which field to use as the primitive value.
            One of "total_spending", "per_capita", "beneficiaries", "claims".
    """
    value_map: dict[str, Any] = {
        "total_spending": record.total_spending,
        "per_capita": record.per_capita,
        "beneficiaries": record.beneficiaries,
        "claims": record.claims,
    }
    value = value_map.get(value_field, record.total_spending)

    sha = _snapshot_hash(
        {
            "dataset": "medicare_spending",
            "year": record.year,
            "state": record.state,
            "field": value_field,
            "value": value,
        }
    )
    source_slug = f"cms-spending-{record.state.lower()}-{value_field}-{record.year}"

    geo_code_list: list[str] = list(geo_codes)
    if record.state and record.state not in geo_code_list:
        geo_code_list = [record.state]

    unit: dict[str, str] = {"kind": unit_kind, "dimension": unit_dimension}
    if unit_currency:
        unit["currency"] = unit_currency
    if unit_denominator:
        unit["denominator"] = unit_denominator

    return {
        "kind": "atomic_primitive",
        "slug": primitive_slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": name,
        "description": description,
        "value": value,
        "unit": unit,
        "as_of": f"{record.year}-12-31",
        "geo": {"level": geo_level, "codes": geo_code_list},
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


def cms_to_source_yaml(
    *,
    dataset: str | CMSDataset,
    state: str = "",
    year: int | None = None,
    source_url: str,
    description: str = "",
    snapshot_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert CMS data to a Strata source_registry YAML dict.

    Generic converter that works for any CMS dataset.
    """
    slug_parts = [f"cms-{str(dataset).replace('_', '-').lower()}"]
    if state:
        slug_parts.append(state.lower())
    if year is not None:
        slug_parts.append(str(year))
    source_slug = "-".join(slug_parts)

    sha = _snapshot_hash(snapshot_fields or {"dataset": str(dataset), "year": year, "state": state})

    return {
        "kind": "source_registry",
        "slug": source_slug,
        "tier": "regulator",
        "url": source_url,
        "accessed": date.today().isoformat(),
        "snapshot_sha256": sha,
        "description": description
        or f"CMS {dataset} data{f' for {state}' if state else ''}{f', {year}' if year else ''}.",
    }
