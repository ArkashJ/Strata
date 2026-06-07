"""The 6-shapes + subframeworks taxonomy (2026-06-07 reframe).

Locks two things: (1) the seeded data really is 6 canonical lens shapes plus
subframeworks that each resolve to a same-lens canonical, and (2) the validator
gate fires on every way the invariant can break — so the "exactly one canonical
shape per lens" guarantee can't silently rot.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from strata.loader import load_data_dir
from strata.registry import Registry
from strata.validator.cross_record import cross_record_check

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

_TAXONOMY_CODE = "cross.framework_taxonomy"


def _taxonomy_issues(reg: Registry) -> list[str]:
    """Taxonomy-gate messages from the PUBLIC cross-record validator."""
    return [i.message for i in cross_record_check(reg) if i.code == _TAXONOMY_CODE]


# The six canonical lens shapes — one per AnalysisLens.
CANONICAL = {
    "cost-efficiency-full-displacement",
    "revenue-capture-full",
    "latent-demand-adoption-curve",
    "throughput-take-rate-with-share",
    "consolidation-net-of-bundling-discount",
    "productivity-uplift-full",
}


def _registry() -> Registry:
    return Registry.from_loaded(load_data_dir(DATA_DIR))


def test_six_canonical_shapes_one_per_lens() -> None:
    reg = _registry()
    canonical = {f.slug for f in reg.frameworks.values() if f.parent_lens_shape is None}
    assert canonical == CANONICAL, f"canonical set drifted: {canonical ^ CANONICAL}"

    lenses = {f.lens.value for f in reg.frameworks.values() if f.parent_lens_shape is None}
    assert len(lenses) == 6, f"expected one canonical per lens, got lenses {lenses}"
    assert len(canonical) == len(lenses), "two canonical shapes share a lens"


def test_every_subframework_resolves_to_same_lens_canonical() -> None:
    reg = _registry()
    for fw in reg.frameworks.values():
        if fw.parent_lens_shape is None:
            continue
        parent = reg.frameworks.get(fw.parent_lens_shape)
        assert parent is not None, f"{fw.slug} parent missing"
        assert parent.parent_lens_shape is None, f"{fw.slug} parent is not canonical"
        assert parent.lens == fw.lens, f"{fw.slug} parent is a different lens"
        assert fw.realism_modifiers, f"{fw.slug} subframework declares no realism_modifiers"


def test_seeded_data_has_no_taxonomy_errors() -> None:
    assert _taxonomy_issues(_registry()) == []


# --- CROSS-RECORD gate must FIRE on each registry-level violation -----------
#
# model_copy bypasses Pydantic validation, so it can stage a record that is
# locally legal but breaks a cross-record invariant — exactly what we want to
# feed the registry-level gate.


def _mutate(reg: Registry, slug: str, **updates: object) -> Registry:
    reg.frameworks[slug] = reg.frameworks[slug].model_copy(update=updates)
    return reg


def test_gate_fires_on_two_canonical_in_one_lens() -> None:
    reg = _registry()
    _mutate(
        reg, "cost-efficiency-bounded-displacement", parent_lens_shape=None, realism_modifiers=()
    )
    issues = _taxonomy_issues(reg)
    assert any("canonical shapes" in m for m in issues)


def test_gate_fires_on_zero_canonical_in_a_lens() -> None:
    # Remove a lens's only canonical while a subframework of it remains.
    reg = _registry()
    del reg.frameworks["cost-efficiency-full-displacement"]
    issues = _taxonomy_issues(reg)
    assert any("no canonical shape" in m for m in issues)


def test_gate_fires_on_unknown_parent() -> None:
    reg = _registry()
    _mutate(reg, "cost-efficiency-bounded-displacement", parent_lens_shape="does-not-exist")
    issues = _taxonomy_issues(reg)
    assert any("not a known framework" in m for m in issues)


def test_gate_fires_on_parent_chain() -> None:
    # A subframework pointing at ANOTHER subframework (of the same lens) — the
    # "no chains" rule the reframe exists to prevent.
    reg = _registry()
    _mutate(
        reg,
        "cost-efficiency-bounded-displacement",
        parent_lens_shape="cost-efficiency-adoption-gated",
    )
    issues = _taxonomy_issues(reg)
    assert any("no chains" in m for m in issues)


def test_gate_fires_on_cross_lens_parent() -> None:
    # A subframework pointing at a canonical of a DIFFERENT lens (its own lens
    # left intact) — the same-lens guarantee.
    reg = _registry()
    _mutate(reg, "cost-efficiency-bounded-displacement", parent_lens_shape="revenue-capture-full")
    issues = _taxonomy_issues(reg)
    assert any("different lens" in m for m in issues)


# --- LOCAL pair invariants are enforced on the MODEL (at construction) -------
#
# These can't even be constructed, so they never reach the registry. model_copy
# skips validation; model_validate runs it — so we validate a mutated dump.


def _framework_dump(slug: str) -> dict[str, object]:
    return _registry().frameworks[slug].model_dump(mode="json")


def test_model_rejects_canonical_with_modifier() -> None:
    from pydantic import ValidationError

    from strata.models import Framework

    d = _framework_dump("revenue-capture-full")  # canonical
    d["realism_modifiers"] = ["bounded"]
    with pytest.raises(ValidationError, match=r"must not.*realism_modifiers"):
        Framework.model_validate(d)


def test_model_rejects_subframework_without_modifier() -> None:
    from pydantic import ValidationError

    from strata.models import Framework

    d = _framework_dump("cost-efficiency-bounded-displacement")  # subframework
    d["realism_modifiers"] = []
    with pytest.raises(ValidationError, match="no realism_modifiers"):
        Framework.model_validate(d)


def test_model_rejects_self_parent() -> None:
    from pydantic import ValidationError

    from strata.models import Framework

    d = _framework_dump("cost-efficiency-bounded-displacement")
    d["parent_lens_shape"] = d["slug"]
    with pytest.raises(ValidationError, match="cannot be its own parent"):
        Framework.model_validate(d)
