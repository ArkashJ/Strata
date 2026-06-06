"""Tests for the bottoms-up vs tops-down convergence cross-check (MV2).

Convergence is pure synthesis of already-sourced scenario values — it must appear
only when ≥2 independent method families sized the concept, must never fabricate a
second method, and must refuse to compare values across mismatched units.
"""

from __future__ import annotations

from pathlib import Path

from strata.evaluator.engine import size_concept
from strata.loader import load_data_dir
from strata.registry import Registry

_DATA = Path(__file__).resolve().parents[2] / "data"


def _reg() -> Registry:
    return Registry.from_loaded(load_data_dir(_DATA))


def test_multi_family_concept_has_convergence() -> None:
    reg = _reg()
    tam = size_concept(reg, "doc-gen-pc-insurance")
    assert len(tam.method_families_used) >= 2
    conv = tam.convergence
    assert conv is not None
    assert conv.low_family != conv.high_family
    assert conv.low_value <= conv.high_value
    assert conv.ratio >= 1.0
    # The ratio is exactly high/low of the family medians — pure synthesis.
    assert conv.ratio == conv.high_value / conv.low_value


def test_single_method_concept_has_no_convergence() -> None:
    """A concept sized by one method family must not manufacture a second."""
    # PR5's framework expansion gave software-eng-productivity a second
    # applicable family; accrual-ai-tax-software remains genuinely single-family,
    # which is what this invariant is testing (no fabricated second method).
    reg = _reg()
    tam = size_concept(reg, "accrual-ai-tax-software")
    assert len(tam.method_families_used) == 1
    assert tam.convergence is None
