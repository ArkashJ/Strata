"""Test that every seeded concept produces a valid TAM output."""

from __future__ import annotations

from pathlib import Path

import pytest

from strata.evaluator import size_concept
from strata.loader import load_data_dir
from strata.registry import Registry

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

CONCEPT_SLUGS = [
    "doc-gen-pc-insurance",
    "gtm-ops-tooling-na",
    "midmarket-saas-spend-na",
    "payments-throughput-pc-insurance",
    "workplace-suite-consolidation",
    "software-eng-productivity",
]


@pytest.fixture(scope="module")
def registry() -> Registry:
    records = load_data_dir(DATA_DIR)
    return Registry.from_loaded(records)


@pytest.mark.parametrize("slug", CONCEPT_SLUGS)
def test_concept_evaluates(registry: Registry, slug: str) -> None:
    result = size_concept(registry, slug)

    # Target fields
    assert result.target.concept == slug
    assert result.target.concept_name is not None
    assert len(result.target.concept_name) > 0

    # At least one scenario
    assert len(result.scenarios) >= 1

    # Every scenario is well-formed
    for scenario in result.scenarios:
        assert scenario.value > 0, f"scenario value not positive for {slug}"
        assert scenario.unit.dimension.value == "currency", f"scenario unit not currency for {slug}"
        assert len(scenario.inputs_used) >= 1, f"no inputs_used for {slug}"


@pytest.mark.parametrize("slug", CONCEPT_SLUGS)
def test_concept_state_hash_is_deterministic(registry: Registry, slug: str) -> None:
    """Running size_concept twice for the same slug produces the same hash."""
    result_a = size_concept(registry, slug)
    result_b = size_concept(registry, slug)
    assert result_a.state_hash == result_b.state_hash


@pytest.mark.parametrize("slug", CONCEPT_SLUGS)
def test_concept_output_kind(registry: Registry, slug: str) -> None:
    result = size_concept(registry, slug)
    assert result.kind == "tam_output"


def test_all_six_concepts_are_seeded(registry: Registry) -> None:
    """Guard: confirms all six concept slugs exist in the registry."""
    for slug in CONCEPT_SLUGS:
        assert slug in registry.concepts, f"concept {slug!r} missing from registry"
