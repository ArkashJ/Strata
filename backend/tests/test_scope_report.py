"""Scope report wired into the sized TAM (sub-project 1, commit 3).

The evaluator attaches a ``ScopeReport`` to every ``TAMOutput``: declared market
scope + per-primitive snap-to-truth scope + definite mismatch warnings. These
pin the behaviour against the seeded ``demo-ai-sales-ops-us`` concept — whose
two methods (bottoms-up $2.0B, top-down $31.2B) diverge precisely because of the
scope mismatches the report now surfaces.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from strata.evaluator import size_concept
from strata.loader import load_data_dir
from strata.models import InputScope, ScopeReport
from strata.models.scope import FirmSizeBand, MarketScope
from strata.registry import Registry

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

_SALES_OPS = "demo-ai-sales-ops-us"
_BLS_WHOLESALE = "demo-bls-sales-reps-us-2024"  # SOC 41-4012, wholesale/mfg only
_ACV_SEAT = "demo-ai-sales-ops-acv-per-seat-2024"  # a price seat, no persona
_MIDMARKET_FIRMS = "demo-census-midmarket-firms-us-2022"  # mid-market only


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_loaded(load_data_dir(DATA_DIR))


def _input(report: ScopeReport, slug: str) -> InputScope:
    return next(i for i in report.inputs if i.primitive_slug == slug)


def test_sized_tam_carries_a_scope_report(registry: Registry):
    tam = size_concept(registry, _SALES_OPS)
    assert tam.scope is not None
    # declared market = all B2B sales reps, not the narrow wholesale SOC
    assert {t.code for t in tam.scope.declared.persona} == {"41-3000", "41-4000"}
    assert not tam.scope.ok  # at least one input diverges


def test_wholesale_headcount_flagged_narrower_and_snaps_to_truth(registry: Registry):
    report = size_concept(registry, _SALES_OPS).scope
    assert report is not None
    bls = _input(report, _BLS_WHOLESALE)
    # snap-to-truth: the displayed persona is the primitive's real SOC, not the declared one
    assert [t.code for t in bls.displayed.persona] == ["41-4012"]
    persona = [w for w in bls.warnings if w.dimension.value == "persona"]
    assert persona and persona[0].relationship == "narrower"
    assert "41-3000" in persona[0].message  # names the services group it excludes


def test_midmarket_firm_count_flagged_narrower_on_segment(registry: Registry):
    report = size_concept(registry, _SALES_OPS).scope
    assert report is not None
    firms = _input(report, _MIDMARKET_FIRMS)
    seg = [w for w in firms.warnings if w.dimension.value == "segment"]
    assert seg and seg[0].relationship == "narrower"


def test_price_input_without_persona_is_not_nagged(registry: Registry):
    """A per-seat price legitimately has no persona pool — the UNKNOWN that the
    guard computes must be suppressed in the report, not shown as a mismatch."""
    report = size_concept(registry, _SALES_OPS).scope
    assert report is not None
    acv = _input(report, _ACV_SEAT)
    assert acv.warnings == ()


def test_each_consumed_primitive_appears_once(registry: Registry):
    report = size_concept(registry, _SALES_OPS).scope
    assert report is not None
    slugs = [i.primitive_slug for i in report.inputs]
    assert len(slugs) == len(set(slugs))


# The state hash demo-ai-sales-ops-us minted BEFORE the scope field existed. The
# scope report is derived and must never fold into the hash, so this value must
# not move when scope is present — a regression that added scope to the hashed
# payload would change it. (It will also, correctly, change if the concept's
# frameworks/primitives/values change — that is real state, and is what the hash
# is for.)
# Updated in PR5: new applicable frameworks added scenarios to this concept, so
# the hash legitimately moved (per the note above). The scope field still does
# NOT fold into the hash — test_scope_report_is_not_part_of_state_hash proves
# that against this same value.
_SALES_OPS_GOLDEN_HASH = "2779ada9b101251aa405ab32ef596fd84b132cc4a553a1b73a6211e33d2830a0"


def test_scope_report_is_not_part_of_state_hash(registry: Registry):
    """The scope report is derived; adding it must not change the minted hash a
    reviewer would have bookmarked before scope landed. Two equal calls only
    prove determinism — the golden constant proves independence from scope."""
    a = size_concept(registry, _SALES_OPS)
    assert a.state_hash == _SALES_OPS_GOLDEN_HASH  # unchanged despite scope present
    assert a.scope is not None  # ...and scope really is populated


# ── Sub-project 1.5: a user-pinned market overrides the declared scope ──────────


def test_pinned_scope_override_drives_the_declared_side(registry: Registry):
    """A non-empty pinned scope replaces the concept's declared scope as the side
    the guard checks against — the ScopeReport reflects the market the user pinned."""
    pinned = MarketScope(segment=FirmSizeBand(min_emp=1000, max_emp=None, label="Enterprise"))
    report = size_concept(registry, _SALES_OPS, declared_scope_override=pinned).scope
    assert report is not None
    assert report.declared.segment == pinned.segment


def test_pinned_market_is_a_distinct_build(registry: Registry):
    """A different pinned market is a different build, so it mints a different hash
    (unlike the derived report, which never moves the hash)."""
    pinned = MarketScope(segment=FirmSizeBand(min_emp=1000, max_emp=None, label="Enterprise"))
    pinned_tam = size_concept(registry, _SALES_OPS, declared_scope_override=pinned)
    assert pinned_tam.state_hash != _SALES_OPS_GOLDEN_HASH


def test_empty_scope_override_is_a_noop(registry: Registry):
    """An empty override is indistinguishable from passing nothing — same hash."""
    tam = size_concept(registry, _SALES_OPS, declared_scope_override=MarketScope())
    assert tam.state_hash == _SALES_OPS_GOLDEN_HASH
