"""Adversarial tests for the scope guard (sub-project 1).

The guard is the wall that makes scope tags enforcing rather than decorative.
These cases mirror the real review failures: a wholesale/mfg-only headcount
under an "all B2B reps" market, a 2022 all-employees count under a "lawyers"
market, silent mid-market narrowing, and the NAICS/SOC hierarchy edge cases the
significant-prefix comparison must get right.
"""

from __future__ import annotations

from strata.models.scope import CodedTag, CodeSystem, FirmSizeBand, MarketScope, ScopeDimension
from strata.scope.guard import (  # type: ignore[attr-defined]
    Relationship,
    _covers,
    _sig,
    classify_scope,
)


def soc(code: str, label: str) -> CodedTag:
    return CodedTag(system=CodeSystem.SOC, code=code, label=label)


def naics(code: str, label: str) -> CodedTag:
    return CodedTag(system=CodeSystem.NAICS, code=code, label=label)


# ── significant-prefix hierarchy ─────────────────────────────────────────────


def test_sig_strips_separators_and_trailing_zeros():
    assert _sig("41-4012") == "414012"
    assert _sig("41-4000") == "414"
    assert _sig("5411") == "5411"
    assert _sig("541110") == "54111"


def test_covers_naics_ancestor():
    assert _covers(naics("5411", "Legal services"), naics("541110", "Offices of lawyers"))
    assert not _covers(naics("541110", "Offices of lawyers"), naics("5411", "Legal services"))


def test_covers_distinct_naics_siblings_disjoint():
    assert not _covers(naics("5411", "Legal"), naics("5415", "Computer systems design"))
    assert not _covers(naics("5415", "Computer systems design"), naics("5411", "Legal"))


def test_covers_soc_broad_group_contains_detailed():
    assert _covers(soc("41-4000", "Wholesale & mfg sales"), soc("41-4012", "Sales reps W&M"))
    assert not _covers(soc("41-4012", "Sales reps W&M"), soc("41-4000", "Wholesale & mfg sales"))


def test_covers_distinct_detailed_soc_disjoint():
    assert not _covers(soc("41-4012", "W&M"), soc("41-3091", "Services sales"))


def test_custom_codes_match_only_exactly():
    a = CodedTag(system=CodeSystem.CUSTOM, code="ai-coding", label="AI coding")
    b = CodedTag(system=CodeSystem.CUSTOM, code="ai-coding", label="AI coding (peers)")
    c = CodedTag(system=CodeSystem.CUSTOM, code="ai-legal", label="AI legal")
    assert _covers(a, b)
    assert not _covers(a, c)


# ── the headline review failure: wholesale/mfg under "all B2B reps" ──────────


def test_wholesale_only_headcount_is_narrower_than_all_b2b_reps():
    """The exact complaint: SOC 41-4012 (wholesale & mfg) sized as if it were all
    B2B sales reps (services 41-3000 + wholesale/mfg 41-4000)."""
    declared = MarketScope(
        persona=(
            soc("41-3000", "Sales reps, services"),
            soc("41-4000", "Sales reps, wholesale & manufacturing"),
        )
    )
    actual = MarketScope(persona=(soc("41-4012", "Sales reps, wholesale & mfg, exc. tech"),))

    match = classify_scope(declared, actual)
    assert not match.ok
    assert match.displayed == actual  # snap-to-truth
    persona = [w for w in match.warnings if w.dimension is ScopeDimension.PERSONA]
    assert len(persona) == 1
    assert persona[0].relationship is Relationship.NARROWER
    # names the services group it excludes entirely
    assert "41-3000" in persona[0].message
    assert "excludes" in persona[0].message.lower()


def test_all_naics_5411_employees_under_lawyers_only_persona():
    """1.18M all-NAICS-5411 employees displayed under a 'lawyers' reading: the
    vertical matches but the persona is broader than just lawyers."""
    declared = MarketScope(
        vertical=(naics("5411", "Legal services"),),
        persona=(soc("23-1011", "Lawyers"),),
    )
    actual = MarketScope(
        vertical=(naics("5411", "Legal services"),),
        # an all-employees headcount declares the whole legal-occupations group
        persona=(soc("23-0000", "Legal occupations"),),
    )
    match = classify_scope(declared, actual)
    persona = [w for w in match.warnings if w.dimension is ScopeDimension.PERSONA]
    assert persona and persona[0].relationship is Relationship.BROADER
    # vertical agrees exactly → no vertical warning
    assert not [w for w in match.warnings if w.dimension is ScopeDimension.VERTICAL]


# ── exact / clean ────────────────────────────────────────────────────────────


def test_exact_scope_has_no_warnings():
    scope = MarketScope(
        vertical=(naics("5411", "Legal services"),),
        persona=(soc("23-1011", "Lawyers"),),
        geo_demand=("US",),
    )
    match = classify_scope(scope, scope)
    assert match.ok
    assert match.warnings == ()


def test_unconstrained_declared_dimension_is_not_a_violation():
    """User left persona open; the primitive's specific persona just informs the
    displayed tag — no warning."""
    declared = MarketScope(vertical=(naics("5411", "Legal services"),))
    actual = MarketScope(
        vertical=(naics("5411", "Legal services"),),
        persona=(soc("23-1011", "Lawyers"),),
    )
    match = classify_scope(declared, actual)
    assert match.ok


# ── disjoint / wrong market ──────────────────────────────────────────────────


def test_disjoint_vertical_is_wrong_market():
    declared = MarketScope(vertical=(naics("5411", "Legal services"),))
    actual = MarketScope(vertical=(naics("5415", "Computer systems design"),))
    match = classify_scope(declared, actual)
    vertical = [w for w in match.warnings if w.dimension is ScopeDimension.VERTICAL]
    assert vertical and vertical[0].relationship is Relationship.DISJOINT


# ── unverified (primitive declares no scope) ─────────────────────────────────


def test_primitive_without_scope_is_unverified():
    declared = MarketScope(persona=(soc("23-1011", "Lawyers"),))
    actual = MarketScope()  # legacy primitive, no scope backfilled
    match = classify_scope(declared, actual)
    persona = [w for w in match.warnings if w.dimension is ScopeDimension.PERSONA]
    assert persona and persona[0].relationship is Relationship.UNKNOWN


def test_two_empty_scopes_are_clean():
    match = classify_scope(MarketScope(), MarketScope())
    assert match.ok


# ── segment (the silent mid-market) ──────────────────────────────────────────


def test_unrestricted_headcount_is_broader_than_midmarket_band():
    """A sales-rep occupation count has no firm-size restriction, so claiming it
    sizes a mid-market-only market overcounts."""
    declared = MarketScope(segment=FirmSizeBand(min_emp=100, max_emp=999, label="Mid-market"))
    actual = MarketScope(segment=None)
    match = classify_scope(declared, actual)
    seg = [w for w in match.warnings if w.dimension is ScopeDimension.SEGMENT]
    assert seg and seg[0].relationship is Relationship.BROADER


def test_midmarket_inside_all_smb_to_enterprise_is_narrower():
    declared = MarketScope(segment=FirmSizeBand(min_emp=1, max_emp=10000, label="All employers"))
    actual = MarketScope(segment=FirmSizeBand(min_emp=100, max_emp=999, label="Mid-market"))
    match = classify_scope(declared, actual)
    seg = [w for w in match.warnings if w.dimension is ScopeDimension.SEGMENT]
    assert seg and seg[0].relationship is Relationship.NARROWER


def test_exact_segment_band_is_clean():
    band = FirmSizeBand(min_emp=100, max_emp=999, label="Mid-market")
    match = classify_scope(MarketScope(segment=band), MarketScope(segment=band))
    assert not [w for w in match.warnings if w.dimension is ScopeDimension.SEGMENT]


def test_non_overlapping_bands_are_disjoint():
    declared = MarketScope(segment=FirmSizeBand(min_emp=1, max_emp=99, label="SMB"))
    actual = MarketScope(segment=FirmSizeBand(min_emp=1000, max_emp=None, label="Enterprise"))
    match = classify_scope(declared, actual)
    seg = [w for w in match.warnings if w.dimension is ScopeDimension.SEGMENT]
    assert seg and seg[0].relationship is Relationship.DISJOINT


# ── geo ──────────────────────────────────────────────────────────────────────


def test_geo_exact_is_clean():
    scope = MarketScope(geo_demand=("US",))
    assert classify_scope(scope, scope).ok


def test_geo_narrower_when_actual_subset():
    declared = MarketScope(geo_demand=("US", "CA"))
    actual = MarketScope(geo_demand=("US",))
    match = classify_scope(declared, actual)
    geo = [w for w in match.warnings if w.dimension is ScopeDimension.GEO]
    assert geo and geo[0].relationship is Relationship.NARROWER


def test_geo_global_actual_is_broader():
    declared = MarketScope(geo_demand=("US",))
    actual = MarketScope(geo_demand=("global",))
    match = classify_scope(declared, actual)
    geo = [w for w in match.warnings if w.dimension is ScopeDimension.GEO]
    assert geo and geo[0].relationship is Relationship.BROADER


def test_geo_disjoint_regions():
    declared = MarketScope(geo_demand=("US",))
    actual = MarketScope(geo_demand=("DE",))
    match = classify_scope(declared, actual)
    geo = [w for w in match.warnings if w.dimension is ScopeDimension.GEO]
    assert geo and geo[0].relationship is Relationship.DISJOINT


def test_displayed_is_always_actual_even_when_clean():
    declared = MarketScope(vertical=(naics("5411", "Legal"),))
    actual = MarketScope(vertical=(naics("5411", "Legal"),), persona=(soc("23-1011", "Lawyers"),))
    assert classify_scope(declared, actual).displayed == actual
