"""Tests for EDGAR-backed revenue lookup (mocked client — no network)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from strata.connectors.edgar import CompanyConcept, Fact
from strata.sizing.revenue_lookup import RevenueLookupError, resolve_revenue


def _concept(facts: tuple[Fact, ...]) -> CompanyConcept:
    return CompanyConcept(
        cik="0000320193",
        entity_name="Salesforce, Inc.",
        taxonomy="us-gaap",
        tag="Revenues",
        label="Revenues",
        description="",
        units={"USD": facts},
    )


class _FakeClient:
    """Stands in for EDGARClient — no HTTP. ``concept_by_tag`` maps tag -> response."""

    def __init__(self, cik: str | None, concept_by_tag: dict[str, CompanyConcept | None]) -> None:
        self._cik = cik
        self._by_tag = concept_by_tag
        self.closed = False

    def resolve_ticker(self, ticker: str) -> str | None:
        _ = ticker
        return self._cik

    def get_company_concept(
        self, cik: str, taxonomy: str = "us-gaap", concept: str = "Revenues"
    ) -> SimpleNamespace:
        _ = (cik, taxonomy)
        return SimpleNamespace(concept=self._by_tag.get(concept))

    def close(self) -> None:
        self.closed = True


def test_resolve_picks_latest_annual_revenue() -> None:
    facts = (
        Fact(
            value=26_000_000_000,
            form="10-K",
            filed="2022-03-01",
            frame="CY2021",
            fiscal_year=2021,
            start="2021-01-01",
            end="2021-12-31",
        ),
        Fact(
            value=34_900_000_000,
            form="10-K",
            filed="2024-03-01",
            frame="CY2023",
            fiscal_year=2023,
            start="2023-01-01",
            end="2023-12-31",
        ),
        Fact(
            value=9_000_000_000,
            form="10-Q",
            filed="2024-06-01",
            frame="CY2024Q1",
            fiscal_year=2024,
            start="2024-01-01",
            end="2024-03-31",
        ),
    )
    client = _FakeClient("0000320193", {"Revenues": _concept(facts)})
    rr = resolve_revenue("CRM", client=client)
    assert rr.revenue == 34_900_000_000  # latest ANNUAL, not the later-period quarterly
    assert rr.fiscal_year == 2023
    assert rr.ticker == "CRM"
    assert rr.concept == "Revenues"
    assert "sec.gov" in rr.source_url


def test_comparative_facts_latest_period_end_wins() -> None:
    # The regression that mislabeled stale revenue as current: a FY2025 10-K
    # carries FY2023/24/25 revenue comparatives ALL stamped fy=2025 with one
    # filed date. Only the fact's own period end can tell them apart — the
    # latest end must win, and the displayed year must come from end, not fy.
    facts = (
        Fact(
            value=20_000_000_000,
            form="10-K",
            filed="2025-03-01",
            frame="",
            fiscal_year=2025,
            start="2022-02-01",
            end="2023-01-31",
        ),
        Fact(
            value=25_000_000_000,
            form="10-K",
            filed="2025-03-01",
            frame="",
            fiscal_year=2025,
            start="2023-02-01",
            end="2024-01-31",
        ),
        Fact(
            value=30_000_000_000,
            form="10-K",
            filed="2025-03-01",
            frame="",
            fiscal_year=2025,
            start="2024-02-01",
            end="2025-01-31",
        ),
    )
    client = _FakeClient("0000320193", {"Revenues": _concept(facts)})
    rr = resolve_revenue("CRM", client=client)
    assert rr.revenue == 30_000_000_000  # the latest period end, not the first fy=2025 fact
    assert rr.fiscal_year == 2025  # derived from end (2025-01-31), never from fy


def test_fiscal_year_label_comes_from_period_end_not_fy() -> None:
    # A FY2025-stamped comparative whose own period ends in Jan 2024 is FY2024.
    facts = (
        Fact(
            value=25_000_000_000,
            form="10-K",
            filed="2025-03-01",
            frame="",
            fiscal_year=2025,
            start="2023-02-01",
            end="2024-01-31",
        ),
    )
    client = _FakeClient("0000320193", {"Revenues": _concept(facts)})
    rr = resolve_revenue("CRM", client=client)
    assert rr.fiscal_year == 2024


def test_zero_or_null_value_facts_never_become_revenue() -> None:
    # A null val parses to 0.0 — it must be skipped, not returned as revenue 0.
    facts = (
        Fact(
            value=34_900_000_000,
            form="10-K",
            filed="2024-03-01",
            frame="",
            fiscal_year=2023,
            start="2023-02-01",
            end="2024-01-31",
        ),
        Fact(
            value=0.0,
            form="10-K",
            filed="2025-03-01",
            frame="",
            fiscal_year=2025,
            start="2024-02-01",
            end="2025-01-31",
        ),
    )
    client = _FakeClient("0000320193", {"Revenues": _concept(facts)})
    rr = resolve_revenue("CRM", client=client)
    assert rr.revenue == 34_900_000_000


def test_null_fy_fact_with_latest_end_still_wins() -> None:
    # fy is the filing's year, often null — a null-fy fact must not be demoted.
    facts = (
        Fact(
            value=26_000_000_000,
            form="10-K",
            filed="2024-03-01",
            frame="",
            fiscal_year=2023,
            start="2023-01-01",
            end="2023-12-31",
        ),
        Fact(
            value=34_900_000_000,
            form="10-K",
            filed="2025-03-01",
            frame="",
            fiscal_year=None,
            start="2024-01-01",
            end="2024-12-31",
        ),
    )
    client = _FakeClient("0000320193", {"Revenues": _concept(facts)})
    rr = resolve_revenue("CRM", client=client)
    assert rr.revenue == 34_900_000_000
    assert rr.fiscal_year == 2024


def test_resolve_falls_back_to_second_concept() -> None:
    facts = (
        Fact(
            value=5_000_000_000,
            form="10-K",
            filed="2024-03-01",
            frame="CY2023",
            fiscal_year=2023,
            start="2023-01-01",
            end="2023-12-31",
        ),
    )
    client = _FakeClient(
        "0000320193",
        {"Revenues": None, "RevenueFromContractWithCustomerExcludingAssessedTax": _concept(facts)},
    )
    rr = resolve_revenue("ABC", client=client)
    assert rr.revenue == 5_000_000_000
    assert rr.concept == "RevenueFromContractWithCustomerExcludingAssessedTax"


def test_picks_latest_year_across_concepts() -> None:
    # Old "Revenues" tag stops at FY2017; ASC 606 tag carries FY2023 → newer wins.
    old = (
        Fact(
            value=1_500_000_000,
            form="10-K",
            filed="2018-03-01",
            frame="CY2017",
            fiscal_year=2017,
            start="2017-01-01",
            end="2017-12-31",
        ),
    )
    new = (
        Fact(
            value=34_900_000_000,
            form="10-K",
            filed="2024-03-01",
            frame="CY2023",
            fiscal_year=2023,
            start="2023-01-01",
            end="2023-12-31",
        ),
    )
    client = _FakeClient(
        "0000320193",
        {
            "Revenues": _concept(old),
            "RevenueFromContractWithCustomerExcludingAssessedTax": _concept(new),
        },
    )
    rr = resolve_revenue("CRM", client=client)
    assert rr.revenue == 34_900_000_000
    assert rr.fiscal_year == 2023
    assert rr.concept == "RevenueFromContractWithCustomerExcludingAssessedTax"


def test_unknown_ticker_raises() -> None:
    with pytest.raises(RevenueLookupError):
        resolve_revenue("NOPE", client=_FakeClient(None, {}))


def test_no_revenue_concept_raises_and_names_tried_tags() -> None:
    with pytest.raises(RevenueLookupError) as exc_info:
        resolve_revenue("ABC", client=_FakeClient("0000320193", {"Revenues": None}))
    msg = str(exc_info.value)
    assert "Revenues" in msg
    assert "SalesRevenueNet" in msg
