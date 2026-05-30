"""Wave 0 / AC0.6 + AC0.7 — the curated demo set is triangulated.

Each demo concept must (AC0.6) carry non-empty ``competing_concepts`` and ≥2
independently-sourced measurements of the same quantity that differ ≥10% (so the
``/c/<slug>`` disagreement bar renders >1 bar), and (AC0.7) build a TAM whose
``independence_score > 0`` because it spans ≥2 method families.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from strata.evaluator.engine import size_concept
from strata.loader import load_data_dir
from strata.registry import Registry

_DATA = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture(scope="module")
def registry() -> Registry:
    return Registry.from_loaded(load_data_dir(_DATA))


def _demo_slugs(registry: Registry) -> list[str]:
    return sorted(s for s in registry.concepts if s.startswith("demo-"))


def test_demo_set_has_at_least_five(registry: Registry) -> None:
    assert len(_demo_slugs(registry)) >= 5


def test_demo_concepts_are_triangulated(registry: Registry) -> None:
    """AC0.6 — non-empty competing_concepts + ≥2 same-quantity measurements ≥10% apart."""
    for slug in _demo_slugs(registry):
        concept = registry.concepts[slug]
        assert concept.competing_concepts, f"{slug}: competing_concepts must be non-empty"

        atoms = [registry.atomic[m] for m in concept.measurements if m in registry.atomic]
        # Bucket by unit dimension to find a same-quantity disagreement pair.
        by_dim: dict[str, list[float]] = {}
        for a in atoms:
            by_dim.setdefault(a.unit.dimension.value, []).append(a.value)
        spreads = [
            (max(v) - min(v)) / max(v) for v in by_dim.values() if len(v) >= 2 and max(v) > 0
        ]
        assert spreads, f"{slug}: needs ≥2 same-quantity measurements for a disagreement bar"
        assert max(spreads) >= 0.10, f"{slug}: same-quantity measurements differ <10%"

        # ≥2 independently-sourced measurements overall.
        tiers = {a.source.tier.value for a in atoms}
        assert len(atoms) >= 2 and len(tiers) >= 2, f"{slug}: needs ≥2 independent sources"


def test_demo_concepts_independence_positive(registry: Registry) -> None:
    """AC0.7 — a built TAM spans ≥2 method families (independence_score > 0)."""
    for slug in _demo_slugs(registry):
        tam = size_concept(registry, slug)
        assert len(set(tam.method_families_used)) >= 2, f"{slug}: <2 method families"
        assert tam.independence_score > 0, f"{slug}: independence_score must be > 0"
        assert len(tam.scenarios) >= 2, f"{slug}: needs ≥2 scenarios"
