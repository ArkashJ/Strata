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
_SALES_OPS_GOLDEN_HASH = "5bafcb37383d1e1352c68cd859f98584d40c3de7f7081cbb8a8902fbcd76abf3"


def test_scope_report_is_not_part_of_state_hash(registry: Registry):
    """The scope report is derived; adding it must not change the minted hash a
    reviewer would have bookmarked before scope landed. Two equal calls only
    prove determinism — the golden constant proves independence from scope."""
    a = size_concept(registry, _SALES_OPS)
    assert a.state_hash == _SALES_OPS_GOLDEN_HASH  # unchanged despite scope present
    assert a.scope is not None  # ...and scope really is populated
