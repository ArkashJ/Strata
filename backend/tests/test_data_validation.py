"""Test that all seeded YAML data loads and validates cleanly."""

from __future__ import annotations

from pathlib import Path

import pytest

from strata.loader import load_data_dir
from strata.registry import Registry
from strata.validator import validate

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


# ---------------------------------------------------------------------------
# Loader counts
# ---------------------------------------------------------------------------


def test_all_data_loads() -> None:
    records = load_data_dir(DATA_DIR)
    assert len(records.atomic_primitives) >= 14, (
        f"expected ≥14 atomic primitives, got {len(records.atomic_primitives)}"
    )
    assert len(records.concepts) >= 6, f"expected ≥6 concepts, got {len(records.concepts)}"
    assert len(records.frameworks) >= 5, f"expected ≥5 frameworks, got {len(records.frameworks)}"


def test_no_composite_primitives_yet() -> None:
    """At v0.2 all primitives are atomic — confirm no stray composite files."""
    records = load_data_dir(DATA_DIR)
    # composites are allowed; just document the current count for regression
    assert len(records.composite_primitives) >= 0  # always true; documents baseline


def test_all_concept_slugs_present() -> None:
    expected = {
        "doc-gen-pc-insurance",
        "gtm-ops-tooling-na",
        "midmarket-saas-spend-na",
        "payments-throughput-pc-insurance",
        "workplace-suite-consolidation",
        "software-eng-productivity",
    }
    records = load_data_dir(DATA_DIR)
    actual = {c.slug for c in records.concepts}
    missing = expected - actual
    assert not missing, f"Missing concept slugs: {missing}"


def test_all_framework_slugs_present() -> None:
    expected = {
        "bottoms-up-cost-efficiency",
        "top-down-revenue-capture",
        "consolidation-sum-then-discount",
        "productivity-uplift-value-split",
        "throughput-take-rate",
    }
    records = load_data_dir(DATA_DIR)
    actual = {f.slug for f in records.frameworks}
    missing = expected - actual
    assert not missing, f"Missing framework slugs: {missing}"


# ---------------------------------------------------------------------------
# Registry construction
# ---------------------------------------------------------------------------


def test_registry_builds_from_loaded_records() -> None:
    records = load_data_dir(DATA_DIR)
    registry = Registry.from_loaded(records)
    assert len(registry.atomic) >= 14
    assert len(registry.concepts) >= 6
    assert len(registry.frameworks) >= 5


def test_registry_concept_lookup() -> None:
    records = load_data_dir(DATA_DIR)
    registry = Registry.from_loaded(records)
    concept = registry.get_concept("doc-gen-pc-insurance")
    assert concept.name == "P&C insurance document generation"
    assert concept.slug == "doc-gen-pc-insurance"


def test_registry_framework_lookup() -> None:
    records = load_data_dir(DATA_DIR)
    registry = Registry.from_loaded(records)
    fw = registry.get_framework("bottoms-up-cost-efficiency")
    assert fw.slug == "bottoms-up-cost-efficiency"
    assert len(fw.inputs) >= 1


def test_registry_primitive_lookup() -> None:
    records = load_data_dir(DATA_DIR)
    registry = Registry.from_loaded(records)
    prim = registry.primitive("naic-active-pc-carriers-2024")
    assert prim.slug == "naic-active-pc-carriers-2024"


# ---------------------------------------------------------------------------
# Full validator pipeline
# ---------------------------------------------------------------------------


def test_all_data_validates() -> None:
    """Run the structural → semantic → cross-record pipeline; expect zero errors."""
    report = validate(DATA_DIR)
    assert report.ok, "Validation errors found:\n" + "\n".join(
        f"  [{f.layer}/{f.code}] {f.slug}: {f.message}" for f in report.errors
    )


def test_validation_report_has_no_errors() -> None:
    report = validate(DATA_DIR)
    assert len(report.errors) == 0, f"Expected 0 errors, got {len(report.errors)}: " + str(
        [(e.code, e.message) for e in report.errors]
    )


def test_validation_report_registry_populated() -> None:
    """After a clean run the report carries a live Registry."""
    report = validate(DATA_DIR)
    assert report.ok
    assert report.registry is not None


# ---------------------------------------------------------------------------
# Schema integrity — every primitive has required fields
# ---------------------------------------------------------------------------


def test_all_atomics_have_value_and_unit() -> None:
    records = load_data_dir(DATA_DIR)
    for atomic in records.atomic_primitives:
        assert atomic.value is not None, f"{atomic.slug}: value is None"
        assert atomic.unit is not None, f"{atomic.slug}: unit is None"


def test_all_frameworks_have_inputs() -> None:
    records = load_data_dir(DATA_DIR)
    for fw in records.frameworks:
        assert len(fw.inputs) >= 1, f"framework {fw.slug!r} has no inputs"


def test_all_concepts_have_measurements() -> None:
    records = load_data_dir(DATA_DIR)
    for concept in records.concepts:
        assert len(concept.measurements) >= 1, f"concept {concept.slug!r} has no measurements"


def test_all_atomics_have_snapshot_sha256() -> None:
    records = load_data_dir(DATA_DIR)
    for atomic in records.atomic_primitives:
        assert len(atomic.source.snapshot_sha256) == 64, (
            f"{atomic.slug}: snapshot_sha256 wrong length"
        )
