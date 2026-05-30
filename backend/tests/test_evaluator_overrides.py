"""Strata Live Track A: override-aware evaluation.

The evaluator gains an optional ``EvalOverrides`` that either (a) substitutes a
transient what-if scalar for a primitive's sourced value — banner +
``uses_synthetic_primitives`` — or (b) re-points a framework input to a
different existing primitive (schema-pure, no banner). The registry is never
mutated. These tests pin that behaviour against the seeded
``ai-legal-assistants-us`` concept (persona 5411 employees × $800/seat).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from strata.evaluator import size_concept
from strata.evaluator.engine import EvalOverrides, OverrideValue
from strata.loader import load_data_dir
from strata.models import BannerKind, Unit, UnitDimension, UnitKind
from strata.registry import Registry

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

_LEGAL_SERVICES = 1_183_593  # NAICS 5411 employees (census-cbp-5411-employees-2022)
_LEGAL_ACV = 800.0  # ai-legal-assistant-acv-per-seat-2024
_CONCEPT = "ai-legal-assistants-us"
_FRAMEWORK = "bottoms-up-cost-efficiency"
_COST_INPUT = "cost_per_persona"
_COST_SLUG = "ai-legal-assistant-acv-per-seat-2024"
_ALT_COST_SLUG = "ai-coding-assistant-acv-per-engineer-2024"  # $300, compatible unit

# unit_signature on cost_per_persona: intensive / currency / USD
_COST_UNIT = Unit(kind=UnitKind.INTENSIVE, dimension=UnitDimension.CURRENCY, currency="USD")


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_loaded(load_data_dir(DATA_DIR))


def test_default_none_unchanged(registry: Registry) -> None:
    """overrides=None reproduces the baseline exactly."""
    base = size_concept(registry, _CONCEPT)
    same = size_concept(registry, _CONCEPT, overrides=None)
    assert same.state_hash == base.state_hash
    assert same.scenarios[0].value == base.scenarios[0].value


def test_scalar_override_changes_value(registry: Registry) -> None:
    """A what-if scalar substitutes the primitive's value at evaluation time."""
    base = size_concept(registry, _CONCEPT)
    assert base.scenarios[0].value == pytest.approx(_LEGAL_SERVICES * _LEGAL_ACV)

    ov = EvalOverrides(
        primitive_overrides={_COST_SLUG: OverrideValue(value=1000.0, unit=_COST_UNIT)},
    )
    out = size_concept(registry, _CONCEPT, overrides=ov)
    assert out.scenarios[0].value == pytest.approx(_LEGAL_SERVICES * 1000.0)
    # Registry untouched.
    assert registry.atomic[_COST_SLUG].value == _LEGAL_ACV


def test_scalar_override_banner_and_synthetic_flag(registry: Registry) -> None:
    ov = EvalOverrides(
        primitive_overrides={_COST_SLUG: OverrideValue(value=1000.0, unit=_COST_UNIT)},
    )
    out = size_concept(registry, _CONCEPT, overrides=ov)
    sc = out.scenarios[0]
    kinds = {b.kind for b in sc.banners}
    assert BannerKind.USER_OVERRIDE in kinds
    assert sc.uses_synthetic_primitives is True
    assert out.uses_synthetic_primitives is True


def test_scalar_override_new_state_hash(registry: Registry) -> None:
    base = size_concept(registry, _CONCEPT)
    ov = EvalOverrides(
        primitive_overrides={_COST_SLUG: OverrideValue(value=1000.0, unit=_COST_UNIT)},
    )
    out = size_concept(registry, _CONCEPT, overrides=ov)
    assert out.state_hash != base.state_hash


def test_framework_assumption_swap_no_banner(registry: Registry) -> None:
    """Re-pointing cost_per_persona to a different existing primitive recomputes
    with no user_override banner (schema-pure)."""
    base = size_concept(registry, _CONCEPT)
    ov = EvalOverrides(
        framework_assumptions={_FRAMEWORK: {_COST_INPUT: _ALT_COST_SLUG}},
    )
    out = size_concept(registry, _CONCEPT, overrides=ov)
    assert out.scenarios[0].value == pytest.approx(_LEGAL_SERVICES * 300.0)
    assert out.state_hash != base.state_hash
    kinds = {b.kind for sc in out.scenarios for b in sc.banners}
    assert BannerKind.USER_OVERRIDE not in kinds
    # Swap to an existing primitive is not synthetic.
    assert out.uses_synthetic_primitives is False
    sc = out.scenarios[0]
    cost = next(iu for iu in sc.inputs_used if iu.role_name == _COST_INPUT)
    assert cost.primitive_slug == _ALT_COST_SLUG


def test_framework_assumption_unknown_primitive_raises(registry: Registry) -> None:
    ov = EvalOverrides(
        framework_assumptions={_FRAMEWORK: {_COST_INPUT: "does-not-exist"}},
    )
    with pytest.raises(ValueError, match="does-not-exist"):
        size_concept(registry, _CONCEPT, overrides=ov)
