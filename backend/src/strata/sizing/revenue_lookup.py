"""EDGAR-backed revenue lookup for the sense-check (public-company revenue).

Resolves a US-listed company's latest annual revenue from SEC EDGAR XBRL
(regulator-tier, redistributable) so the sense-check can use a SOURCED revenue
figure instead of an analyst estimate — closing the "private revenue is itself a
guess" critique for any public player.

Scope, stated honestly:
* **EDGAR** is the revenue source: free, regulator-tier, US-listed companies only.
* **yfinance** (the other already-wired finance connector) exposes *quotes*, not
  revenue, so it is not used here.
* **Private companies** have no public filing — they stay analyst estimates, or
  come from a session-side licensed source (e.g. a Capital IQ / S&P MCP) that is
  NEVER committed to the open bank (licensing + tier).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..connectors.edgar import CompanyConcept, EDGARClient, EDGARClientError, Fact

# us-gaap revenue concepts, in preference order (older filers use Revenues; newer
# ASC 606 filers report RevenueFromContractWithCustomerExcludingAssessedTax).
_REVENUE_CONCEPTS = ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax")
# An annual XBRL frame is "CYnnnn" with no quarter suffix (e.g. CY2024); a
# quarterly frame carries a Q (CY2024Q1I). Annual is what a TAM cares about.
_ANNUAL_FRAME = re.compile(r"^CY\d{4}$")


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


def _latest_annual(concept: CompanyConcept) -> Fact | None:
    """The most recent annual revenue fact: prefer 10-K / annual-framed facts,
    then take the latest fiscal year (filed-date as tiebreak)."""
    facts = concept.units.get("USD", ())
    if not facts:
        return None
    annual = [f for f in facts if (f.frame and _ANNUAL_FRAME.match(f.frame)) or f.form == "10-K"]
    pool = annual or list(facts)
    return max(pool, key=lambda f: (f.fiscal_year or 0, f.filed))


def resolve_revenue(ticker: str, *, client: EDGARClient | None = None) -> ResolvedRevenue:
    """Latest annual revenue for a US-listed ``ticker`` from SEC EDGAR XBRL.

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
            msg = f"no usable annual revenue concept on file for {ticker!r} (CIK {cik})"
            raise RevenueLookupError(msg) from last_err
        fact, concept_tag, entity_name = max(
            candidates, key=lambda c: (c[0].fiscal_year or 0, c[0].filed)
        )
        return ResolvedRevenue(
            ticker=ticker.upper(),
            cik=cik,
            entity_name=entity_name,
            revenue=fact.value,
            fiscal_year=fact.fiscal_year,
            concept=concept_tag,
            source_url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}",
        )
    finally:
        if own:
            c.close()
