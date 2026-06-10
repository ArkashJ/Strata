"""SEC EDGAR XBRL client.

Typed wrappers for all five EDGAR data endpoints with disk caching
and conversion to Strata AtomicPrimitive / Source YAML format.

API reference: https://www.sec.gov/edgar/sec-api-documentation
No API key required.  User-Agent header is mandatory (SEC policy).
Rate limit: 10 requests/second (SEC enforced).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, TypedDict, cast

import httpx

# ═══════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════


class EDGARTaxonomy(StrEnum):
    US_GAAP = "us-gaap"
    DEI = "dei"
    IFRS = "ifrs-full"


class EDGARFormType(StrEnum):
    FORM_10K = "10-K"
    FORM_10Q = "10-Q"
    FORM_8K = "8-K"
    FORM_20F = "20-F"
    FORM_S1 = "S-1"


class EDGARPeriodType(StrEnum):
    ANNUAL = "CY"
    QUARTERLY = "Q"
    INSTANTANEOUS = "I"


# ═══════════════════════════════════════════════════════════════════
# TypedDicts — raw EDGAR JSON response shapes
# ═══════════════════════════════════════════════════════════════════


class FactRaw(TypedDict, total=False):
    val: int | float
    accn: str
    fy: int
    fp: str
    form: str
    filed: str
    frame: str
    start: str
    end: str


class CompanyTickerRaw(TypedDict):
    cik_str: int
    ticker: str
    title: str


class FilingRaw(TypedDict, total=False):
    accessionNumber: str
    filingDate: str
    reportDate: str
    form: str
    primaryDocument: str
    primaryDocDescription: str
    acceptanceDateTime: str
    act: str
    fileNumber: str
    filmNumber: str
    items: str
    size: int
    isXBRL: int
    isInlineXBRL: int


class RecentFilingsRaw(TypedDict, total=False):
    accessionNumber: list[str]
    filingDate: list[str]
    reportDate: list[str]
    form: list[str]
    primaryDocument: list[str]


class SubmissionsRaw(TypedDict, total=False):
    cik: str
    entityType: str
    sic: str
    sicDescription: str
    name: str
    tickers: list[str]
    exchanges: list[str]
    fiscalYearEnd: str
    filings: dict[str, Any]


class ConceptUnitsRaw(TypedDict, total=False):
    """Maps unit label (e.g. "USD", "shares") to list of FactRaw."""

    USD: list[FactRaw]
    shares: list[FactRaw]


class CompanyConceptRaw(TypedDict, total=False):
    cik: int
    taxonomy: str
    tag: str
    label: str
    description: str
    entityName: str
    units: dict[str, list[FactRaw]]


class FrameDataRaw(TypedDict, total=False):
    cik: int
    entityName: str
    loc: str
    end: str
    val: int | float
    accn: str
    form: str
    filed: str
    frame: str


class FrameResponseRaw(TypedDict, total=False):
    taxonomy: str
    tag: str
    ccp: str
    uom: str
    label: str
    description: str
    pts: int
    data: list[FrameDataRaw]


# ═══════════════════════════════════════════════════════════════════
# Dataclasses — validated internal models
# ═══════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class Fact:
    value: float
    form: str
    filed: str
    frame: str
    fiscal_year: int | None = None
    fiscal_period: str | None = None
    # The fact's own reporting period. fy/fp describe the FILING, so a FY2025
    # 10-K stamps fy=2025 on its FY2023/24/25 revenue comparatives — only
    # start/end identify which year a comparative actually covers.
    start: str = ""
    end: str = ""


@dataclass(frozen=True, slots=True)
class CompanyConcept:
    cik: str
    entity_name: str
    taxonomy: str
    tag: str
    label: str
    description: str
    units: dict[str, tuple[Fact, ...]]


# ── Period-aware annual fact selection ──────────────────────────────
# Shared with strata.sizing.revenue_lookup. `_pick_fact` (below, used by the
# YAML converters) still uses the older fy/frame heuristic — kept unchanged in
# this pass; only callers that opt into these helpers get period-aware selection.

# An annual XBRL frame is "CYnnnn" with no quarter suffix (e.g. CY2024); a
# quarterly frame carries a Q (CY2024Q1I). Annual is what a TAM cares about.
_ANNUAL_FRAME = re.compile(r"^CY\d{4}$")
# A fiscal year is ~365 days; this window admits 52/53-week fiscal calendars
# while excluding quarterly and multi-year durations.
_ANNUAL_DAYS = (330, 400)


def _is_annual(fact: Fact) -> bool:
    """Annual-duration test. When the fact carries its own period (start/end),
    trust THAT — fy/fp/form describe the filing, and a 10-K holds quarterly
    comparatives too. Frame/form is only a fallback for period-less facts."""
    if fact.start and fact.end:
        try:
            days = (date.fromisoformat(fact.end) - date.fromisoformat(fact.start)).days
        except ValueError:
            return bool(fact.frame and _ANNUAL_FRAME.match(fact.frame))
        return _ANNUAL_DAYS[0] <= days <= _ANNUAL_DAYS[1]
    return bool((fact.frame and _ANNUAL_FRAME.match(fact.frame)) or fact.form == "10-K")


def fiscal_year_from_end(fact: Fact) -> int | None:
    """Displayed fiscal year comes from the fact's own period end — never from
    ``fy``, which is the filing's year and mislabels comparatives."""
    if fact.end:
        try:
            return date.fromisoformat(fact.end).year
        except ValueError:
            return None
    return None


def fact_recency(fact: Fact) -> tuple[str, str]:
    """Sort key: latest period end wins; filed date breaks ties (an amended
    re-filing of the same period supersedes the original). ISO date strings
    compare correctly as text; a missing end sorts before any real date."""
    return (fact.end, fact.filed)


def latest_annual_fact(facts: Iterable[Fact]) -> Fact | None:
    """The most recent annual fact, selected by the fact's own period end. A
    FY2025 10-K carries FY2023/24/25 comparatives all stamped fy=2025 with one
    filed date, so fy/filed cannot distinguish them — only ``end`` can."""
    usable = [f for f in facts if f.value]
    if not usable:
        return None
    annual = [f for f in usable if _is_annual(f)]
    pool = annual or usable
    return max(pool, key=fact_recency)


@dataclass(frozen=True, slots=True)
class CompanyInfo:
    cik: str
    name: str
    ticker: str
    exchange: str
    sic: str
    sic_description: str
    fiscal_year_end: str


@dataclass(frozen=True, slots=True)
class Filing:
    accession_number: str
    filing_date: str
    report_date: str
    form: str
    primary_document: str


@dataclass(frozen=True, slots=True)
class FrameEntry:
    cik: int
    entity_name: str
    value: float
    form: str
    filed: str
    frame: str


@dataclass(frozen=True, slots=True)
class Statements:
    """A small set of headline financial-statement figures for one company.

    Each value is the latest annual (10-K) figure available for the concept,
    or None when the company does not report that tag.
    """

    cik: str
    entity_name: str
    fiscal_year: int | None
    revenue: float | None
    net_income: float | None
    assets: float | None
    liabilities: float | None
    stockholders_equity: float | None
    shares_outstanding: float | None


@dataclass(frozen=True, slots=True)
class EDGARResponse:
    """Standard return type for every EDGAR client call."""

    kind: str
    company_info: CompanyInfo | None = None
    filings: tuple[Filing, ...] = ()
    concept: CompanyConcept | None = None
    frame_entries: tuple[FrameEntry, ...] = ()
    tickers: tuple[tuple[int, str, str], ...] = ()
    concepts: dict[str, CompanyConcept] | None = None
    statements: Statements | None = None
    cached: bool = False
    cache_age_seconds: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# Response parsing
# ═══════════════════════════════════════════════════════════════════


def _parse_fact(raw: dict[str, Any]) -> Fact:
    val = raw.get("val", 0)
    return Fact(
        value=float(val) if val is not None else 0.0,
        form=str(raw.get("form", "")),
        filed=str(raw.get("filed", "")),
        frame=str(raw.get("frame", "")),
        # SEC XBRL facts often carry "fy"/"fp" present-but-null; guard on the
        # value, not just key presence, or int(None)/str(None) corrupts the Fact.
        fiscal_year=int(raw["fy"]) if raw.get("fy") is not None else None,
        fiscal_period=str(raw["fp"]) if raw.get("fp") is not None else None,
        start=str(raw.get("start", "") or ""),
        end=str(raw.get("end", "") or ""),
    )


def _parse_company_info(raw: dict[str, Any]) -> CompanyInfo:
    tickers: list[str] = raw.get("tickers", [])
    exchanges: list[str] = raw.get("exchanges", [])
    return CompanyInfo(
        cik=str(raw.get("cik", "")),
        name=str(raw.get("name", "")),
        ticker=tickers[0] if tickers else "",
        exchange=exchanges[0] if exchanges else "",
        sic=str(raw.get("sic", "")),
        sic_description=str(raw.get("sicDescription", "")),
        fiscal_year_end=str(raw.get("fiscalYearEnd", "")),
    )


def _parse_filings(raw: dict[str, Any]) -> tuple[Filing, ...]:
    filings_block: dict[str, Any] = raw.get("filings", {})
    recent: dict[str, Any] = filings_block.get("recent", {})

    accession_numbers: list[str] = recent.get("accessionNumber", [])
    filing_dates: list[str] = recent.get("filingDate", [])
    report_dates: list[str] = recent.get("reportDate", [])
    forms: list[str] = recent.get("form", [])
    primary_docs: list[str] = recent.get("primaryDocument", [])

    count = len(accession_numbers)
    filings: list[Filing] = []
    for i in range(count):
        filings.append(
            Filing(
                accession_number=accession_numbers[i] if i < len(accession_numbers) else "",
                filing_date=filing_dates[i] if i < len(filing_dates) else "",
                report_date=report_dates[i] if i < len(report_dates) else "",
                form=forms[i] if i < len(forms) else "",
                primary_document=primary_docs[i] if i < len(primary_docs) else "",
            )
        )
    return tuple(filings)


def _parse_company_concept(raw: dict[str, Any]) -> CompanyConcept:
    units_raw: dict[str, list[dict[str, Any]]] = raw.get("units", {})
    units: dict[str, tuple[Fact, ...]] = {}
    for unit_label, facts_list in units_raw.items():
        units[unit_label] = tuple(_parse_fact(f) for f in facts_list)
    return CompanyConcept(
        cik=str(raw.get("cik", "")),
        entity_name=str(raw.get("entityName", "")),
        taxonomy=str(raw.get("taxonomy", "")),
        tag=str(raw.get("tag", "")),
        label=str(raw.get("label", "")),
        description=str(raw.get("description", "")),
        units=units,
    )


def _parse_frame_entries(raw: dict[str, Any]) -> tuple[FrameEntry, ...]:
    data: list[dict[str, Any]] = raw.get("data", [])
    return tuple(
        FrameEntry(
            cik=int(entry.get("cik", 0)),
            entity_name=str(entry.get("entityName", "")),
            value=float(entry.get("val", 0)),
            form=str(entry.get("form", "")),
            filed=str(entry.get("filed", "")),
            frame=str(entry.get("frame", "")),
        )
        for entry in data
    )


def _parse_tickers(raw: dict[str, Any]) -> tuple[tuple[int, str, str], ...]:
    entries: list[tuple[int, str, str]] = []
    for _idx in raw:
        item: object = raw[_idx]
        if isinstance(item, dict):
            d: dict[str, Any] = cast(dict[str, Any], item)
            entries.append(
                (
                    int(d.get("cik_str", 0)),
                    str(d.get("ticker", "")),
                    str(d.get("title", "")),
                )
            )
    return tuple(entries)


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
        return self._dir / f"edgar_{key}.json"

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
        path.write_text(json.dumps(payload))

    def clear(self) -> int:
        count = 0
        for f in self._dir.glob("edgar_*.json"):
            f.unlink()
            count += 1
        return count


# ═══════════════════════════════════════════════════════════════════
# Client
# ═══════════════════════════════════════════════════════════════════

_BASE = "https://data.sec.gov"
_USER_AGENT = "Strata/0.2 (arkash@benmore.tech)"


class EDGARClientError(RuntimeError):
    """Raised on EDGAR API errors or client-side validation failures."""


class EDGARClient:
    """Typed client for SEC EDGAR data endpoints.

    Usage::

        client = EDGARClient()
        resp = client.get_company_concept("0000320193", concept="Revenue")
        for fact in resp.concept.units["USD"]:
            print(fact.fiscal_year, fact.value)
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        cache_ttl: int = 86400,
        timeout: float = 30.0,
        user_agent: str = _USER_AGENT,
    ) -> None:
        self._http = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": user_agent,
                "Accept": "application/json",
            },
        )
        default_cache = Path.home() / ".strata" / "cache" / "edgar"
        self._cache = _DiskCache(cache_dir or default_cache, cache_ttl)
        # ticker → CIK map, parsed once per client so resolve_ticker is a dict
        # hit after the first call (the SEC list is ~12k rows re-scanned otherwise).
        self._cik_by_ticker: dict[str, str] | None = None

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> EDGARClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ── internal helpers ─────────────────────────────────────────

    @staticmethod
    def _pad_cik(cik: str | int) -> str:
        """Zero-pad CIK to 10 digits as required by EDGAR URLs."""
        return str(int(str(cik).lstrip("0") or "0")).zfill(10)

    def _cache_key(self, url: str) -> str:
        return url

    def _request(self, url: str, *, kind: str) -> dict[str, Any]:
        """Fetch URL with caching and rate limiting.

        Returns the raw parsed JSON dict. Rate-limits at 10 req/sec
        by sleeping 0.1s after each live HTTP request.
        """
        ck = self._cache_key(url)
        cached = self._cache.get(ck)
        if cached is not None:
            return cached[0]

        http_resp = self._http.get(url)
        time.sleep(0.1)

        if http_resp.status_code == 404:
            raise EDGARClientError(f"EDGAR 404: resource not found at {url}")
        http_resp.raise_for_status()

        raw: dict[str, Any] = http_resp.json()
        self._cache.put(ck, raw)
        return raw

    def _request_response(self, url: str, *, kind: str) -> tuple[dict[str, Any], bool, float]:
        """Like _request but returns (data, cached, cache_age_seconds)."""
        ck = self._cache_key(url)
        cached = self._cache.get(ck)
        if cached is not None:
            return cached[0], True, round(cached[1], 1)

        http_resp = self._http.get(url)
        time.sleep(0.1)

        if http_resp.status_code == 404:
            raise EDGARClientError(f"EDGAR 404: resource not found at {url}")
        http_resp.raise_for_status()

        raw: dict[str, Any] = http_resp.json()
        self._cache.put(ck, raw)
        return raw, False, 0.0

    # ── Endpoint 1: Company Submissions ─────────────────────────

    def get_submissions(self, cik: str | int) -> EDGARResponse:
        """Retrieve filing history and company metadata for a CIK."""
        padded = self._pad_cik(cik)
        url = f"{_BASE}/submissions/CIK{padded}.json"
        raw, was_cached, age = self._request_response(url, kind="submissions")

        company_info = _parse_company_info(raw)
        filings = _parse_filings(raw)

        return EDGARResponse(
            kind="submissions",
            company_info=company_info,
            filings=filings,
            cached=was_cached,
            cache_age_seconds=age,
        )

    # ── Endpoint 2: Company Facts ───────────────────────────────

    def get_company_facts(self, cik: str | int) -> EDGARResponse:
        """Retrieve ALL XBRL financial data for a company.

        Warning: response can be 10MB+ for large filers. The returned
        EDGARResponse.concept contains all facts across all concepts
        merged into a single CompanyConcept with tag="ALL".
        """
        padded = self._pad_cik(cik)
        url = f"{_BASE}/api/xbrl/companyfacts/CIK{padded}.json"
        raw, was_cached, age = self._request_response(url, kind="companyfacts")

        facts_raw: dict[str, Any] = raw.get("facts", {})

        cik_str = str(raw.get("cik", ""))
        entity_name = str(raw.get("entityName", ""))
        all_units: dict[str, list[Fact]] = {}
        # Per-tag accumulation alongside the merged view, so one companyfacts
        # request can answer per-concept questions (e.g. the revenue lookup)
        # without N companyconcept round-trips.
        per_tag_units: dict[str, dict[str, list[Fact]]] = {}
        per_tag_meta: dict[str, tuple[str, str, str]] = {}  # tag → (taxonomy, label, description)
        for taxonomy_name in facts_raw:
            taxonomy_data: object = facts_raw[taxonomy_name]
            if not isinstance(taxonomy_data, dict):
                continue
            taxonomy_dict: dict[str, Any] = cast(dict[str, Any], taxonomy_data)
            for concept_tag in taxonomy_dict:
                concept_data: object = taxonomy_dict[concept_tag]
                if not isinstance(concept_data, dict):
                    continue
                concept_dict: dict[str, Any] = cast(dict[str, Any], concept_data)
                units_block: dict[str, Any] = concept_dict.get("units", {})
                per_tag_meta.setdefault(
                    concept_tag,
                    (
                        str(taxonomy_name),
                        str(concept_dict.get("label") or ""),
                        str(concept_dict.get("description") or ""),
                    ),
                )
                tag_units = per_tag_units.setdefault(concept_tag, {})
                for unit_label in units_block:
                    fact_list: object = units_block[unit_label]
                    if not isinstance(fact_list, list):
                        continue
                    typed_list: list[dict[str, Any]] = cast(list[dict[str, Any]], fact_list)
                    parsed = [_parse_fact(f) for f in typed_list]
                    all_units.setdefault(unit_label, []).extend(parsed)
                    # A tag colliding across taxonomies merges its facts under
                    # one key (none collide in practice; us-gaap vs dei disjoint).
                    tag_units.setdefault(unit_label, []).extend(parsed)

        concept = CompanyConcept(
            cik=cik_str,
            entity_name=entity_name,
            taxonomy="all",
            tag="ALL",
            label="All XBRL facts",
            description="Aggregated company facts across all taxonomies",
            units={k: tuple(v) for k, v in all_units.items()},
        )
        concepts = {
            tag: CompanyConcept(
                cik=cik_str,
                entity_name=entity_name,
                taxonomy=per_tag_meta[tag][0],
                tag=tag,
                label=per_tag_meta[tag][1],
                description=per_tag_meta[tag][2],
                units={k: tuple(v) for k, v in units.items()},
            )
            for tag, units in per_tag_units.items()
        }

        return EDGARResponse(
            kind="companyfacts",
            concept=concept,
            concepts=concepts,
            cached=was_cached,
            cache_age_seconds=age,
        )

    # ── Endpoint 3: Company Concept ─────────────────────────────

    def get_company_concept(
        self,
        cik: str | int,
        taxonomy: str = "us-gaap",
        concept: str = "Revenue",
    ) -> EDGARResponse:
        """Retrieve a specific XBRL concept for a company."""
        padded = self._pad_cik(cik)
        url = f"{_BASE}/api/xbrl/companyconcept/CIK{padded}/{taxonomy}/{concept}.json"
        raw, was_cached, age = self._request_response(url, kind="companyconcept")

        parsed_concept = _parse_company_concept(raw)

        return EDGARResponse(
            kind="companyconcept",
            concept=parsed_concept,
            cached=was_cached,
            cache_age_seconds=age,
        )

    # ── Derived: batch concepts ─────────────────────────────────

    def get_concepts(
        self,
        cik: str | int,
        tags: tuple[str, ...],
        taxonomy: str = "us-gaap",
    ) -> EDGARResponse:
        """Fetch several XBRL concepts for one company in a single call.

        Missing tags (404) are skipped rather than raising.

        Args:
            cik: Company CIK.
            tags: XBRL concept tags to fetch.
            taxonomy: Taxonomy namespace.
        """
        out: dict[str, CompanyConcept] = {}
        for tag in tags:
            try:
                resp = self.get_company_concept(cik, taxonomy=taxonomy, concept=tag)
            except EDGARClientError:
                continue
            if resp.concept is not None:
                out[tag] = resp.concept
        return EDGARResponse(kind="concepts", concepts=out)

    def get_facts_by_concept(
        self,
        cik: str | int,
        tag: str,
        taxonomy: str = "us-gaap",
    ) -> EDGARResponse:
        """Alias for :meth:`get_company_concept` keyed by tag name.

        Args:
            cik: Company CIK.
            tag: XBRL concept tag (e.g. "Assets").
            taxonomy: Taxonomy namespace.
        """
        return self.get_company_concept(cik, taxonomy=taxonomy, concept=tag)

    def get_shares_outstanding(self, cik: str | int) -> EDGARResponse:
        """Retrieve common shares outstanding (dei taxonomy).

        Args:
            cik: Company CIK.
        """
        return self.get_company_concept(
            cik,
            taxonomy="dei",
            concept="EntityCommonStockSharesOutstanding",
        )

    def get_segment_revenue(self, cik: str | int) -> EDGARResponse:
        """Retrieve revenue-from-contracts facts (a proxy for segment revenue).

        Args:
            cik: Company CIK.
        """
        return self.get_company_concept(
            cik,
            taxonomy="us-gaap",
            concept="RevenueFromContractWithCustomerExcludingAssessedTax",
        )

    def get_financial_statements(
        self,
        cik: str | int,
        year: int | None = None,
    ) -> EDGARResponse:
        """Assemble a small set of headline financials for a company.

        Pulls revenue, net income, assets, liabilities, equity and shares
        outstanding and packs them into a :class:`Statements` object.

        Args:
            cik: Company CIK.
            year: Optional fiscal year to pin each figure to.
        """
        tag_map: dict[str, tuple[str, str]] = {
            "revenue": ("us-gaap", "Revenues"),
            "net_income": ("us-gaap", "NetIncomeLoss"),
            "assets": ("us-gaap", "Assets"),
            "liabilities": ("us-gaap", "Liabilities"),
            "stockholders_equity": ("us-gaap", "StockholdersEquity"),
            "shares_outstanding": ("dei", "EntityCommonStockSharesOutstanding"),
        }
        values: dict[str, float | None] = {}
        entity_name = ""
        fiscal_year: int | None = year
        for field, (taxonomy, tag) in tag_map.items():
            try:
                resp = self.get_company_concept(cik, taxonomy=taxonomy, concept=tag)
            except EDGARClientError:
                values[field] = None
                continue
            concept = resp.concept
            if concept is None:
                values[field] = None
                continue
            entity_name = entity_name or concept.entity_name
            unit = "shares" if field == "shares_outstanding" else "USD"
            try:
                fact = _pick_fact(concept, year=year, unit_filter=unit)
                values[field] = fact.value
                if fiscal_year is None and fact.fiscal_year is not None:
                    fiscal_year = fact.fiscal_year
            except EDGARClientError:
                values[field] = None

        statements = Statements(
            cik=self._pad_cik(cik),
            entity_name=entity_name,
            fiscal_year=fiscal_year,
            revenue=values.get("revenue"),
            net_income=values.get("net_income"),
            assets=values.get("assets"),
            liabilities=values.get("liabilities"),
            stockholders_equity=values.get("stockholders_equity"),
            shares_outstanding=values.get("shares_outstanding"),
        )
        return EDGARResponse(kind="statements", statements=statements)

    # ── Endpoint 4: XBRL Frames ────────────────────────────────

    def get_frames(
        self,
        taxonomy: str = "us-gaap",
        concept: str = "Revenue",
        unit: str = "USD",
        period: str = "CY2023",
    ) -> EDGARResponse:
        """Retrieve cross-company aggregation for a concept+period."""
        url = f"{_BASE}/api/xbrl/frames/{taxonomy}/{concept}/{unit}/{period}.json"
        raw, was_cached, age = self._request_response(url, kind="frames")

        frame_entries = _parse_frame_entries(raw)

        return EDGARResponse(
            kind="frames",
            frame_entries=frame_entries,
            cached=was_cached,
            cache_age_seconds=age,
        )

    # ── Derived: SIC industry rollups ───────────────────────────

    def peers_by_sic(
        self,
        sic: str,
        period: str = "CY2023",
        concept: str = "Revenues",
        max_lookups: int = 50,
    ) -> EDGARResponse:
        """Return frame entries restricted to filers in one SIC code.

        Pulls the cross-company frame for ``concept`` then filters to CIKs
        whose submissions report the requested SIC. Bounded by ``max_lookups``
        submission fetches (rate-limited at 10 req/s by the client).

        Args:
            sic: Standard Industrial Classification code (e.g. "2834").
            period: Frame period code (e.g. "CY2023").
            concept: XBRL concept tag to roll up.
            max_lookups: Cap on submission lookups (newest-frame-first).
        """
        frame_resp = self.get_frames(concept=concept, period=period)
        matched: list[FrameEntry] = []
        for entry in frame_resp.frame_entries[:max_lookups]:
            try:
                sub = self.get_submissions(entry.cik)
            except EDGARClientError:
                continue
            if sub.company_info is not None and sub.company_info.sic == str(sic):
                matched.append(entry)
        return EDGARResponse(kind="frames", frame_entries=tuple(matched))

    def get_industry_revenue(
        self,
        sic: str,
        period: str = "CY2023",
        max_lookups: int = 50,
    ) -> EDGARResponse:
        """Sum reported Revenues across filers in one SIC code for a period.

        Returns an EDGARResponse whose ``frame_entries`` are the SIC-matched
        filers; callers aggregate via :func:`frame_to_primitive_yaml`.

        Args:
            sic: SIC industry code.
            period: Frame period code.
            max_lookups: Cap on submission lookups.
        """
        return self.peers_by_sic(sic, period=period, concept="Revenues", max_lookups=max_lookups)

    # ── Endpoint 5: Company Tickers ─────────────────────────────

    def get_company_tickers(self) -> EDGARResponse:
        """Retrieve the full ticker-to-CIK mapping."""
        url = "https://www.sec.gov/files/company_tickers.json"
        raw, was_cached, age = self._request_response(url, kind="tickers")

        tickers = _parse_tickers(raw)

        return EDGARResponse(
            kind="tickers",
            tickers=tickers,
            cached=was_cached,
            cache_age_seconds=age,
        )

    # ── Convenience: ticker → CIK ──────────────────────────────

    def resolve_ticker(self, ticker: str) -> str | None:
        """Map a ticker symbol to its zero-padded CIK. Returns None if not found."""
        if self._cik_by_ticker is None:
            resp = self.get_company_tickers()
            mapping: dict[str, str] = {}
            for cik_int, tick, _name in resp.tickers:
                # setdefault keeps the FIRST entry per symbol — same winner as
                # the previous linear scan when the SEC list carries duplicates.
                mapping.setdefault(tick.upper(), str(cik_int).zfill(10))
            self._cik_by_ticker = mapping
        return self._cik_by_ticker.get(ticker.upper())

    # ── Cache management ─────────────────────────────────────────

    def clear_cache(self) -> int:
        """Remove all cached EDGAR responses. Returns count deleted."""
        return self._cache.clear()


# ═══════════════════════════════════════════════════════════════════
# Strata format converters
# ═══════════════════════════════════════════════════════════════════


def _pick_fact(
    concept: CompanyConcept,
    *,
    year: int | None = None,
    form_filter: str = "10-K",
    unit_filter: str = "USD",
) -> Fact:
    """Select the best fact from a CompanyConcept for a given year and form type."""
    facts = concept.units.get(unit_filter, ())
    if not facts:
        raise EDGARClientError(
            f"No facts with unit '{unit_filter}' for {concept.tag} (CIK {concept.cik})"
        )

    # Filter to requested form type
    filtered = [f for f in facts if f.form == form_filter]
    if not filtered:
        filtered = list(facts)

    # Filter to requested year (match frame like "CY2023" or fiscal_year)
    if year is not None:
        year_str = f"CY{year}"
        year_matched = [
            f for f in filtered if f.frame.startswith(year_str) or f.fiscal_year == year
        ]
        if year_matched:
            filtered = year_matched

    # Prefer annual frames (CYnnnn without Q suffix) over quarterly
    annual = [f for f in filtered if f.frame and not any(c in f.frame for c in "QI")]
    if annual:
        return annual[-1]

    if filtered:
        return filtered[-1]

    raise EDGARClientError(f"No matching fact for {concept.tag} year={year} form={form_filter}")


def _snapshot_hash(cik: str, concept_tag: str, period: str, value: float) -> str:
    """Content-hash a fact for source pinning (Q5)."""
    content = json.dumps(
        {
            "cik": cik,
            "concept": concept_tag,
            "period": period,
            "value": value,
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()


def _as_of_date(fact: Fact) -> str:
    """Derive an as_of date from the fact's filed date or frame."""
    if fact.filed:
        return fact.filed
    if fact.frame:
        # Parse "CY2023" → 2023-12-31, "CY2023Q1" → 2023-03-31
        frame = fact.frame
        if "Q4" in frame:
            return f"{frame[2:6]}-12-31"
        if "Q3" in frame:
            return f"{frame[2:6]}-09-30"
        if "Q2" in frame:
            return f"{frame[2:6]}-06-30"
        if "Q1" in frame:
            return f"{frame[2:6]}-03-31"
        if len(frame) >= 6:
            return f"{frame[2:6]}-12-31"
    if fact.fiscal_year is not None:
        return f"{fact.fiscal_year}-12-31"
    return date.today().isoformat()


def concept_to_primitive_yaml(
    concept: CompanyConcept,
    *,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    source_url: str,
    year: int | None = None,
    form_filter: str = "10-K",
    unit_filter: str = "USD",
    geo_codes: tuple[str, ...] = ("US",),
    geo_level: str = "country",
    geo_perspective: str = "supply",
    unit_kind: str = "flow",
    unit_dimension: str = "currency",
    unit_denominator: str | None = "per-year",
    unit_currency: str | None = "USD",
    distribution_shape: str = "normal",
    delivery_mode: str = "n/a",
) -> dict[str, Any]:
    """Convert an EDGAR CompanyConcept to a Strata AtomicPrimitive YAML dict.

    Returns a dict ready for ``yaml.dump()`` that conforms to the
    AtomicPrimitive schema (models/primitive.py).
    """
    fact = _pick_fact(concept, year=year, form_filter=form_filter, unit_filter=unit_filter)
    source_slug = f"edgar-{concept.cik}-{concept.tag.lower()}-{(fact.frame or 'latest').lower()}"
    sha = _snapshot_hash(concept.cik, concept.tag, fact.frame, fact.value)

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
        "value": fact.value,
        "unit": unit,
        "as_of": _as_of_date(fact),
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


def concept_to_source_yaml(
    concept: CompanyConcept,
    *,
    source_url: str,
    year: int,
    description: str = "",
) -> dict[str, Any]:
    """Convert an EDGAR CompanyConcept to a Strata source_registry YAML dict."""
    fact = _pick_fact(concept, year=year)
    source_slug = f"edgar-{concept.cik}-{concept.tag.lower()}-{str(fact.frame or year).lower()}"
    sha = _snapshot_hash(concept.cik, concept.tag, fact.frame, fact.value)

    return {
        "kind": "source_registry",
        "slug": source_slug,
        "tier": "regulator",
        "url": source_url,
        "accessed": date.today().isoformat(),
        "snapshot_sha256": sha,
        "description": description
        or f"SEC EDGAR {concept.tag} for CIK {concept.cik}, {year} data.",
    }


def frame_to_primitive_yaml(
    entries: tuple[FrameEntry, ...],
    *,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    source_url: str,
    aggregation: str = "sum",
    geo_codes: tuple[str, ...] = ("US",),
    geo_level: str = "country",
    geo_perspective: str = "supply",
    unit_kind: str = "flow",
    unit_dimension: str = "currency",
    unit_denominator: str | None = "per-year",
    unit_currency: str | None = "USD",
    distribution_shape: str = "normal",
    delivery_mode: str = "n/a",
) -> dict[str, Any]:
    """Convert EDGAR frame entries to a Strata AtomicPrimitive YAML dict.

    Aggregates across all companies in the frame using the specified method
    (sum, count, or mean).
    """
    if not entries:
        raise EDGARClientError("No frame entries to aggregate")

    values = [e.value for e in entries]
    if aggregation == "sum":
        agg_value = sum(values)
    elif aggregation == "count":
        agg_value = float(len(values))
    elif aggregation == "mean":
        agg_value = sum(values) / len(values)
    else:
        raise EDGARClientError(f"Unknown aggregation method: {aggregation}")

    frame_label = entries[0].frame if entries[0].frame else "unknown"
    sha = _snapshot_hash("frame", f"{aggregation}_{len(entries)}", frame_label, agg_value)
    source_slug = f"edgar-frame-{frame_label.lower()}-{aggregation}"

    unit: dict[str, str] = {"kind": unit_kind, "dimension": unit_dimension}
    if unit_denominator:
        unit["denominator"] = unit_denominator
    if unit_currency:
        unit["currency"] = unit_currency

    as_of = entries[0].filed if entries[0].filed else date.today().isoformat()

    return {
        "kind": "atomic_primitive",
        "slug": primitive_slug,
        "schema_version": 1,
        "concept_slug": concept_slug,
        "name": name,
        "description": description,
        "value": agg_value,
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


def capabilities() -> list[CapabilitySpec]:
    """Methods exposed to the LLM router (spec §5)."""
    from ._capability import CapabilityArg, CapabilitySpec

    return [
        CapabilitySpec(
            connector="edgar",
            method="get_company_concept",
            description=("XBRL facts for a US-listed company concept (revenue, assets, etc.)."),
            returns="atomic primitive, unit=currency USD, tier=regulator",
            args=[
                CapabilityArg(
                    name="cik",
                    type="str",
                    description="Company CIK (with leading zeros)",
                    example="0000320193",
                ),
                CapabilityArg(
                    name="taxonomy",
                    type="str",
                    description="Taxonomy (us-gaap)",
                    example="us-gaap",
                ),
                CapabilityArg(
                    name="concept",
                    type="str",
                    description="XBRL concept tag",
                    example="Revenues",
                ),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="edgar",
            method="get_frames",
            description=(
                "All filers' values for a single XBRL concept in a period (industry-wide rollup)."
            ),
            returns="atomic primitive list, unit=currency USD, tier=regulator",
            args=[
                CapabilityArg(
                    name="taxonomy", type="str", description="Taxonomy", example="us-gaap"
                ),
                CapabilityArg(
                    name="concept",
                    type="str",
                    description="Concept tag",
                    example="Revenues",
                ),
                CapabilityArg(name="unit", type="str", description="Unit code", example="USD"),
                CapabilityArg(
                    name="period",
                    type="str",
                    description="Period code, e.g. CY2023Q4I",
                    example="CY2023",
                ),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="edgar",
            method="get_shares_outstanding",
            description="Common shares outstanding for a US-listed company (dei taxonomy).",
            returns="atomic primitive, unit=count shares, tier=regulator",
            args=[
                CapabilityArg(
                    name="cik",
                    type="str",
                    description="Company CIK (with leading zeros)",
                    example="0000320193",
                ),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="edgar",
            method="get_segment_revenue",
            description="Revenue-from-contracts facts (segment-revenue proxy) for a company.",
            returns="atomic primitive, unit=currency USD, tier=regulator",
            args=[
                CapabilityArg(
                    name="cik",
                    type="str",
                    description="Company CIK (with leading zeros)",
                    example="0000320193",
                ),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="edgar",
            method="get_financial_statements",
            description="Headline financials (revenue/income/assets/equity/shares) for a company.",
            returns="atomic primitive bundle, tier=regulator",
            args=[
                CapabilityArg(
                    name="cik",
                    type="str",
                    description="Company CIK (with leading zeros)",
                    example="0000320193",
                ),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="edgar",
            method="get_industry_revenue",
            description="Sum of reported Revenues across filers in one SIC code (industry TAM).",
            returns="atomic primitive list, unit=currency USD, tier=regulator",
            args=[
                CapabilityArg(
                    name="sic", type="str", description="SIC industry code", example="2834"
                ),
                CapabilityArg(
                    name="period", type="str", description="Frame period", example="CY2023"
                ),
            ],
            source_tier="regulator",
        ),
        CapabilitySpec(
            connector="edgar",
            method="peers_by_sic",
            description="Filers' values for a concept restricted to one SIC code (peer set).",
            returns="atomic primitive list, unit=currency USD, tier=regulator",
            args=[
                CapabilityArg(
                    name="sic", type="str", description="SIC industry code", example="2834"
                ),
            ],
            source_tier="regulator",
        ),
    ]


from ._capability import CapabilitySpec as CapabilitySpec  # noqa: E402
