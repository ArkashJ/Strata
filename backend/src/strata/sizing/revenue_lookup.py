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

from dataclasses import dataclass

from ..connectors.edgar import (
    EDGARClient,
    EDGARClientError,
    Fact,
    fact_recency,
    fiscal_year_from_end,
    latest_annual_fact,
)
from .sense_check import REVENUE_NOTE_FILING_TOTAL_CO, Player

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


def to_player(name: str, share: float, resolved: ResolvedRevenue) -> Player:
    """The ONE way an EDGAR figure becomes a sense-check player: always sourced,
    always carrying the total-company marker so the engine emits the caveat —
    a sourced-but-total figure is never an unmarked sourced line."""
    return Player(
        name=name,
        revenue=resolved.revenue,
        market_share=share,
        revenue_sourced=True,
        revenue_note=REVENUE_NOTE_FILING_TOTAL_CO,
    )


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
        tried = ", ".join(_REVENUE_CONCEPTS)
        miss_msg = (
            f"no usable annual revenue concept on file for {ticker!r} (CIK {cik}); "
            f"tried us-gaap tags: {tried}"
        )
        # ONE companyfacts request replaces up to 5 per-tag companyconcept calls.
        try:
            resp = c.get_company_facts(cik)
        except EDGARClientError as exc:
            raise RevenueLookupError(miss_msg) from exc
        by_tag = resp.concepts or {}
        # Gather the latest annual fact from EVERY revenue concept, then pick the
        # globally most-recent. Filers migrate tags over time (older "Revenues" →
        # ASC 606 "RevenueFromContract…"), so stopping at the first non-empty tag
        # can return a stale year — take the newest across all of them.
        candidates: list[tuple[Fact, str, str]] = []  # (fact, concept_tag, entity_name)
        for concept_tag in _REVENUE_CONCEPTS:
            concept = by_tag.get(concept_tag)
            if concept is None:
                continue
            fact = latest_annual_fact(concept.units.get("USD", ()))
            if fact is not None:
                candidates.append((fact, concept_tag, concept.entity_name))
        if not candidates:
            raise RevenueLookupError(miss_msg)
        fact, concept_tag, entity_name = max(candidates, key=lambda c: fact_recency(c[0]))
        return ResolvedRevenue(
            ticker=ticker.upper(),
            cik=cik,
            entity_name=entity_name,
            revenue=fact.value,
            fiscal_year=fiscal_year_from_end(fact),
            concept=concept_tag,
            source_url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}",
        )
    finally:
        if own:
            c.close()
