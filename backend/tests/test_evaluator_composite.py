"""SP-1: composites are first-class in TAM math.

A composite (same-unit set op, Q3) can be bound to a framework input; the
evaluator computes the set op (union → sum of members) before the framework's
unit-crossing multiply. These tests pin that behaviour against the seeded
``ai-coding-assistants-us`` (composite-backed persona) and
``ai-legal-assistants-us`` (single-primitive persona) concepts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from strata.evaluator import size_concept
from strata.loader import load_data_dir
from strata.models import BannerKind
from strata.registry import Registry

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# Census CBP 2022 employee counts the composite unions (regulator-sourced).
_SOFTWARE_PUBLISHERS = 874_707  # NAICS 5112
_COMPUTER_SYSTEMS = 2_126_573  # NAICS 5415
_LEGAL_SERVICES = 1_183_593  # NAICS 5411


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_loaded(load_data_dir(DATA_DIR))


def test_composite_union_feeds_framework(registry: Registry) -> None:
    """persona_pool binds to a composite; the evaluator sums the union before
    the per-seat multiply: (5112 + 5415 employees) x $300/seat."""
    tam = size_concept(registry, "ai-coding-assistants-us")
    sc = tam.scenarios[0]
    persona = next(iu for iu in sc.inputs_used if iu.role_name == "persona_pool")
    assert persona.primitive_slug == "us-software-engineering-workforce"
    assert persona.value == _SOFTWARE_PUBLISHERS + _COMPUTER_SYSTEMS
    assert sc.value == pytest.approx((_SOFTWARE_PUBLISHERS + _COMPUTER_SYSTEMS) * 300.0)


def test_real_union_not_flagged_modeled(registry: Registry) -> None:
    """The composite unions REAL Census data, so uses_modeled_composites stays
    False — honesty: only the per-seat multiplier is community-modeled."""
    tam = size_concept(registry, "ai-coding-assistants-us")
    assert tam.uses_modeled_composites is False


def test_community_modeled_input_emits_modeled_banner(registry: Registry) -> None:
    """A community-modeled multiplier must surface a MODELED banner for export."""
    tam = size_concept(registry, "ai-coding-assistants-us")
    kinds = {b.kind for sc in tam.scenarios for b in sc.banners}
    assert BannerKind.MODELED in kinds


def test_legal_single_primitive_persona(registry: Registry) -> None:
    """Legal persona is a single real atomic (5411 employees) × $800/seat."""
    tam = size_concept(registry, "ai-legal-assistants-us")
    sc = tam.scenarios[0]
    assert sc.value == pytest.approx(_LEGAL_SERVICES * 800.0)
