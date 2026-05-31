"""Adversarial test suite for the verbatim guard (spec §6 + F1).

The guard is the Q20 wall: it decides whether an LLM-extracted number is a
faithful, corroborated extraction of a real sourced figure (eligible to
persist) or a hallucination / mismatch (rejected). Two gates in series:

  GATE 1  semantic magnitude match + role-keyword locality
  GATE 2  corroboration (≥2 independent spans, or a 2nd source)

Verdicts: verbatim_corroborated | verbatim_single | semantic_mismatch | absent
Only ``verbatim_corroborated`` is eligible for PUBLIC persistence;
``verbatim_single`` persists org-private only.
"""

from __future__ import annotations

import pytest

from strata.sizing.guard import GuardVerdict, parse_magnitude, scan_magnitudes, verbatim_guard


# ── magnitude parsing: the normalize equivalence class ──────────────────────
@pytest.mark.parametrize(
    "surface,expected",
    [
        ("$4.2B", 4.2e9),
        ("4.2 billion", 4.2e9),
        ("4,200,000,000", 4.2e9),
        ("USD 4.2bn", 4.2e9),
        ("4.2bn", 4.2e9),
        ("$3.9B", 3.9e9),
        ("12 million", 12e6),
        ("$1.5 trillion", 1.5e12),
        ("250,000", 250_000.0),
        ("750K", 750_000.0),
    ],
)
def test_parse_magnitude_equivalence(surface: str, expected: float) -> None:
    got = parse_magnitude(surface)
    assert got is not None
    assert abs(got - expected) <= expected * 0.005


def test_parse_magnitude_rejects_non_numeric() -> None:
    assert parse_magnitude("the market is large") is None


def test_scan_magnitudes_finds_all_forms() -> None:
    text = "Revenue hit $4.2B in 2024, up from 3,100,000,000 the prior year."
    mags = scan_magnitudes(text)
    values = [m.value for m in mags]
    assert any(abs(v - 4.2e9) <= 4.2e9 * 0.005 for v in values)
    assert any(abs(v - 3.1e9) <= 3.1e9 * 0.005 for v in values)


# ── GATE 1: semantic magnitude match ────────────────────────────────────────
def test_format_equivalence_passes_gate1() -> None:
    # value as "$4.2B" must match a page that writes "4.2 billion"
    page = "Analysts peg annual revenue at 4.2 billion dollars for the segment."
    v = verbatim_guard(4.2e9, page, role_keywords=["revenue"])
    assert v.verdict in {"verbatim_single", "verbatim_corroborated"}
    assert v.matched_span is not None
    assert v.offset is not None


def test_comma_grouped_form_passes() -> None:
    page = "Total addressable revenue of $4,200,000,000 was reported."
    v = verbatim_guard(4.2e9, page, role_keywords=["revenue"])
    assert v.verdict in {"verbatim_single", "verbatim_corroborated"}


def test_usd_prefix_and_footnote_noise_passes() -> None:
    page = "The pool is USD 4.2bn[3] according to the filing's revenue line."
    v = verbatim_guard(4.2e9, page, role_keywords=["revenue"])
    assert v.verdict in {"verbatim_single", "verbatim_corroborated"}


def test_close_but_different_value_is_semantic_mismatch() -> None:
    # LLM claims 4.2B but the page only supports 3.9B → reject
    page = "Reported revenue was $3.9B for the fiscal year."
    v = verbatim_guard(4.2e9, page, role_keywords=["revenue"])
    assert v.verdict == "semantic_mismatch"


def test_value_absent_from_page_is_absent() -> None:
    page = "The company operates in a competitive landscape with many players."
    v = verbatim_guard(4.2e9, page, role_keywords=["revenue"])
    assert v.verdict == "absent"


def test_role_mismatch_is_rejected() -> None:
    # The magnitude appears, but only attached to "market cap", not the
    # requested "revenue" role → reject (folds into semantic_mismatch).
    page = "Its market cap reached $4.2B, while revenue stayed modest."
    v = verbatim_guard(4.2e9, page, role_keywords=["revenue"])
    assert v.verdict == "semantic_mismatch"


def test_no_role_keywords_skips_locality_check() -> None:
    page = "The figure $4.2B appears in the summary."
    v = verbatim_guard(4.2e9, page, role_keywords=None)
    assert v.verdict in {"verbatim_single", "verbatim_corroborated"}


# ── GATE 2: corroboration ───────────────────────────────────────────────────
def test_single_mention_is_verbatim_single_not_public() -> None:
    page = "The segment revenue is approximately $4.2B per the analyst note."
    v = verbatim_guard(4.2e9, page, role_keywords=["revenue"])
    assert v.verdict == "verbatim_single"
    assert v.corroborating_spans == []


def test_two_independent_spans_corroborate() -> None:
    page = (
        "Segment revenue is about $4.2B this year. "
        "Separately, the firm's revenue of 4,200,000,000 was confirmed in the 10-K."
    )
    v = verbatim_guard(4.2e9, page, role_keywords=["revenue"])
    assert v.verdict == "verbatim_corroborated"
    assert len(v.corroborating_spans) >= 1


def test_second_source_corroborates() -> None:
    page = "Revenue is $4.2B per the first source."
    second = "An independent report lists revenue of 4.2 billion."
    v = verbatim_guard(4.2e9, page, role_keywords=["revenue"], second_source_text=second)
    assert v.verdict == "verbatim_corroborated"
    assert len(v.corroborating_spans) >= 1


def test_corroboration_requires_role_match_too() -> None:
    # Second mention exists but only as market cap → does NOT corroborate revenue.
    page = (
        "Revenue is $4.2B per the note. The company's market cap also happens to be 4,200,000,000."
    )
    v = verbatim_guard(4.2e9, page, role_keywords=["revenue"])
    assert v.verdict == "verbatim_single"


# ── eligibility helpers ──────────────────────────────────────────────────────
def test_public_eligibility_only_for_corroborated() -> None:
    corroborated = GuardVerdict(
        verdict="verbatim_corroborated",
        value=4.2e9,
        matched_span="$4.2B",
        offset=0,
        unit_keyword="revenue",
        corroborating_spans=["4,200,000,000"],
    )
    single = GuardVerdict(
        verdict="verbatim_single",
        value=4.2e9,
        matched_span="$4.2B",
        offset=0,
        unit_keyword="revenue",
        corroborating_spans=[],
    )
    rejected = GuardVerdict(
        verdict="semantic_mismatch",
        value=None,
        matched_span=None,
        offset=None,
        unit_keyword=None,
        corroborating_spans=[],
    )
    assert corroborated.eligible_public is True
    assert corroborated.eligible_private is True
    assert single.eligible_public is False
    assert single.eligible_private is True
    assert rejected.eligible_public is False
    assert rejected.eligible_private is False
