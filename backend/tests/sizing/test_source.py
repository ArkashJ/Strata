"""source_via_exa + guard integration (spec §5 step 3b, §6/F1, F2).

Analyst sourcing must (a) only persist a number the guard verifies is verbatim
on the fetched page, and (b) always land org-PRIVATE (never public off one hit).
"""

from __future__ import annotations

from strata.sizing.source import source_via_exa


def test_verified_value_is_sourced_private() -> None:
    def fetcher(_q: str) -> tuple[str, str]:
        return ("https://example.com/report", "The segment revenue reached $4.2B last year.")

    out = source_via_exa("revenue", "acme revenue", 4.2e9, fetcher=fetcher)
    assert out is not None
    assert out.tier == "analyst"
    assert out.visibility == "private"  # F2 — never public on one hit
    assert out.url == "https://example.com/report"
    assert out.snapshot_sha256


def test_hallucinated_value_is_rejected() -> None:
    def fetcher(_q: str) -> tuple[str, str]:
        return ("https://example.com", "Revenue was $3.9B for the period.")

    # LLM claims 4.2B but the page only supports 3.9B → not sourced.
    out = source_via_exa("revenue", "acme revenue", 4.2e9, fetcher=fetcher)
    assert out is None


def test_no_page_hit_returns_none() -> None:
    out = source_via_exa("revenue", "acme revenue", 4.2e9, fetcher=lambda _q: None)
    assert out is None


def test_two_sources_corroborate_but_still_private() -> None:
    def fetcher(_q: str) -> tuple[str, str]:
        return ("https://a.com", "Revenue is $4.2B per source one.")

    def second(_q: str) -> tuple[str, str]:
        return ("https://b.com", "An independent filing lists revenue of 4.2 billion.")

    out = source_via_exa("revenue", "acme", 4.2e9, fetcher=fetcher, second_fetcher=second)
    assert out is not None
    # Corroborated → guard verdict is public-eligible, but the SOURCED input is
    # still written private; public promotion is a separate gated step (F2).
    assert out.guard is not None
    assert out.guard.eligible_public is True
    assert out.visibility == "private"
