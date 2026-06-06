"""Test that InputUsed carries value/name/unit enrichment fields."""

from __future__ import annotations

from pathlib import Path

import pytest

from strata.evaluator import size_concept
from strata.loader import load_data_dir
from strata.registry import Registry

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

ENRICHMENT_CONCEPTS = [
    "doc-gen-pc-insurance",
    "software-eng-productivity",
    "gtm-ops-tooling-na",
    "midmarket-saas-spend-na",
    "payments-throughput-pc-insurance",
    "workplace-suite-consolidation",
]


@pytest.fixture(scope="module")
def registry() -> Registry:
    records = load_data_dir(DATA_DIR)
    return Registry.from_loaded(records)


def test_all_inputs_enriched(registry: Registry) -> None:
    """Every InputUsed on every scenario must carry value, name, and unit."""
    for slug in ENRICHMENT_CONCEPTS:
        result = size_concept(registry, slug)
        for scenario in result.scenarios:
            for inp in scenario.inputs_used:
                assert inp.value is not None, (
                    f"{slug} / {scenario.framework}: primitive {inp.primitive_slug!r} missing value"
                )
                assert inp.name is not None, (
                    f"{slug} / {scenario.framework}: primitive {inp.primitive_slug!r} missing name"
                )
                assert inp.unit is not None, (
                    f"{slug} / {scenario.framework}: primitive {inp.primitive_slug!r} missing unit"
                )
                assert isinstance(inp.value, float), (
                    f"{slug}: inp.value is {type(inp.value)}, expected float"
                )
                assert len(inp.name) > 0, f"{slug}: inp.name is empty for {inp.primitive_slug!r}"


def test_concept_name_populated(registry: Registry) -> None:
    result = size_concept(registry, "doc-gen-pc-insurance")
    assert result.target.concept_name == "P&C insurance document generation"


def test_concept_name_populated_all(registry: Registry) -> None:
    """concept_name must be non-empty for every concept."""
    for slug in ENRICHMENT_CONCEPTS:
        result = size_concept(registry, slug)
        assert result.target.concept_name is not None, f"concept_name is None for {slug}"
        assert len(result.target.concept_name) > 0, f"concept_name is empty for {slug}"


def test_inputs_used_primitive_slug_matches_registry(registry: Registry) -> None:
    """Every primitive_slug in inputs_used must be resolvable in the registry."""
    for slug in ENRICHMENT_CONCEPTS:
        result = size_concept(registry, slug)
        for scenario in result.scenarios:
            for inp in scenario.inputs_used:
                prim = registry.primitive(inp.primitive_slug)
                assert prim is not None, f"primitive {inp.primitive_slug!r} not found in registry"


def test_inputs_used_snapshot_sha256_pinned(registry: Registry) -> None:
    """Every InputUsed must carry a valid 64-char snapshot_sha256."""
    for slug in ENRICHMENT_CONCEPTS:
        result = size_concept(registry, slug)
        for scenario in result.scenarios:
            for inp in scenario.inputs_used:
                assert len(inp.snapshot_sha256) == 64, (
                    f"{slug}: snapshot_sha256 wrong length for {inp.primitive_slug!r}"
                )
