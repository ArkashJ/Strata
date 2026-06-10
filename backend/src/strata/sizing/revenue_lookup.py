"""EDGAR-backed revenue lookup for the sense-check (public-company revenue).

Resolves a US-listed company's latest annual revenue from SEC EDGAR XBRL
(regulator-tier, redistributable) so the sense-check can use a SOURCED revenue
figure instead of an analyst estimate — closing the "private revenue is itself a
guess" critique for any public player.

Scope, stated honestly:
* **EDGAR** is the revenue source: free, regulator-tier, US-listed companies only.
* The figure is **TOTAL company revenue**, not in-market revenue — the caller must
  confirm they coincide or substitute a segment figure (the CLI/MCP surfaces say so).
* **yfinance** (the other already-wired finance connector) exposes *quotes*, not
  revenue, so it is not used here.
* **Private companies** have no public filing — they stay analyst estimates, or
  come from a session-side licensed source (e.g. a Capital IQ / S&P MCP) that is
  NEVER committed to the open bank (licensing + tier).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from ..connectors.edgar import CompanyConcept, EDGARClient, EDGARClientError, Fact

# us-gaap revenue concepts, in preference order (older filers use Revenues; newer
# ASC 606 filers report the RevenueFromContractWithCustomer tags; some report
# the older SalesRevenue tags).
_REVENUE_CONCEPTS = (
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
    "SalesRevenueServicesNet",
)
# An annual XBRL frame is "CYnnnn" with no quarter suffix (e.g. CY2024); a
# quarterly frame carries a Q (CY2024Q1I). Annual is what a TAM cares about.
_ANNUAL_FRAME = re.compile(r"^CY\d{4}$")
# A fiscal year is ~365 days; this window admits 52/53-week fiscal calendars
# while excluding quarterly and multi-year durations.
_ANNUAL_DAYS = (330, 400)


class RevenueLookupError(RuntimeError):
    """Ticker not found, or no usable annual revenue concept on file."""


@dataclass(frozen=True, slots=True)
class ResolvedRevenue:
    ticker: str
    cik: str
    entity_name: str
    revenue: float
    fiscal_year: int | None
    concept: str
    source_url: str


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


def _fiscal_year_from_end(fact: Fact) -> int | None:
    """Displayed fiscal year comes from the fact's own period end — never from
    ``fy``, which is the filing's year and mislabels comparatives."""
    if fact.end:
        try:
            return date.fromisoformat(fact.end).year
        except ValueError:
            return None
    return None


def _fact_recency(fact: Fact) -> tuple[str, str]:
    """Sort key: latest period end wins; filed date breaks ties (an amended
    re-filing of the same period supersedes the original). ISO date strings
    compare correctly as text; a missing end sorts before any real date."""
    return (fact.end, fact.filed)


def _latest_annual(concept: CompanyConcept) -> Fact | None:
    """The most recent annual revenue fact, selected by the fact's own period
    end. A FY2025 10-K carries FY2023/24/25 comparatives all stamped fy=2025
    with one filed date, so fy/filed cannot distinguish them — only ``end`` can."""
    facts = [f for f in concept.units.get("USD", ()) if f.value]
    if not facts:
        return None
    annual = [f for f in facts if _is_annual(f)]
    pool = annual or facts
    return max(pool, key=_fact_recency)


def resolve_revenue(ticker: str, *, client: EDGARClient | None = None) -> ResolvedRevenue:
    """Latest annual revenue for a US-listed ``ticker`` from SEC EDGAR XBRL.

    The figure is the company's TOTAL revenue (whole company, not a market
    segment) — the caller owns confirming it equals in-market revenue.

    Makes live HTTP calls (caller decides when — never on an offline path). Pass
    ``client`` to inject a configured/fake client (tests do this to stay offline).
    Raises :class:`RevenueLookupError` on a miss — never returns a fabricated value.
    """
    own = client is None
    c = client or EDGARClient()
    try:
        cik = c.resolve_ticker(ticker)
        if cik is None:
            raise RevenueLookupError(
                f"ticker {ticker!r} not found in the SEC company list (US-listed filers only)"
            )
        # Gather the latest annual fact from EVERY revenue concept, then pick the
        # globally most-recent. Filers migrate tags over time (older "Revenues" →
        # ASC 606 "RevenueFromContract…"), so stopping at the first non-empty tag
        # can return a stale year — take the newest across all of them.
        last_err: Exception | None = None
        candidates: list[tuple[Fact, str, str]] = []  # (fact, concept_tag, entity_name)
        for concept_tag in _REVENUE_CONCEPTS:
            try:
                resp = c.get_company_concept(cik, concept=concept_tag)
            except EDGARClientError as exc:
                last_err = exc
                continue
            if resp.concept is None:
                continue
            fact = _latest_annual(resp.concept)
            if fact is not None:
                candidates.append((fact, concept_tag, resp.concept.entity_name))
        if not candidates:
            tried = ", ".join(_REVENUE_CONCEPTS)
            msg = (
                f"no usable annual revenue concept on file for {ticker!r} (CIK {cik}); "
                f"tried us-gaap tags: {tried}"
            )
            raise RevenueLookupError(msg) from last_err
        fact, concept_tag, entity_name = max(candidates, key=lambda c: _fact_recency(c[0]))
        return ResolvedRevenue(
            ticker=ticker.upper(),
            cik=cik,
            entity_name=entity_name,
            revenue=fact.value,
            fiscal_year=_fiscal_year_from_end(fact),
            concept=concept_tag,
            source_url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}",
        )
    finally:
        if own:
            c.close()
