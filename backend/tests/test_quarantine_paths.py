"""Registry-level quarantine invariant — enforced on BOTH load paths (#102).

The bug: ``Registry.from_db`` (the prod Postgres path) quarantined only
``prediction_market``, so community/social-tier primitives (reddit/twitter/
stack_exchange/github → tier ``community``) could feed ``reg.atomic`` in prod
while the YAML loader quarantined them. Quarantine must be a property of the
RECORD's tier (``NON_SIZING_TIERS``), identical on every path.

Invariant (parametrized so neither path can regress):

    reg.atomic ∩ {primitives whose source.tier ∈ NON_SIZING_TIERS} == ∅

A misfiled non-sizing primitive (under ``data/primitives/`` on the YAML path, or
seeded into the DB on the prod path) must be routed to ``reg.signals``, never to
``reg.atomic`` where the evaluator/frameworks could consume it (Q20).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import yaml

from strata.loader import load_data_dir
from strata.models import NON_SIZING_TIERS, AtomicPrimitive, SourceTier
from strata.registry import Registry

_REPO = Path(__file__).resolve().parents[2]
# A real, self-contained committed signal we clone and re-tier per tier.
_TEMPLATE = _REPO / "data" / "signals" / "kalshi-agi-by-2030-probability.yaml"


def test_non_sizing_tiers_is_the_shared_constant() -> None:
    # The constant is the single source of truth; both load paths import it.
    # community covers all social connectors (reddit/twitter/stack/github).
    assert SourceTier.PREDICTION_MARKET in NON_SIZING_TIERS
    assert SourceTier.COMMUNITY in NON_SIZING_TIERS
    # community-modeled is a sizing input (gated elsewhere), NOT quarantined.
    assert SourceTier.COMMUNITY_MODELED not in NON_SIZING_TIERS


def _primitive_with_tier(tier: SourceTier, slug: str) -> AtomicPrimitive:
    raw = yaml.safe_load(_TEMPLATE.read_text(encoding="utf-8"))
    raw["slug"] = slug
    raw["source"]["tier"] = tier.value
    return AtomicPrimitive.model_validate(raw)


def _registry_via_yaml(prim: AtomicPrimitive, tmp_path: Path) -> Registry:
    """Write the primitive MISFILED under data/primitives/ (not data/signals/)
    so only the tier check — not the directory — can quarantine it."""
    prims = tmp_path / "primitives"
    prims.mkdir(parents=True, exist_ok=True)
    (tmp_path / "signals").mkdir(parents=True, exist_ok=True)
    raw = prim.model_dump(mode="json")
    raw["kind"] = "atomic_primitive"
    (prims / f"{prim.slug}.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    return Registry.from_loaded(load_data_dir(tmp_path))


def _registry_via_db(prim: AtomicPrimitive, monkeypatch: pytest.MonkeyPatch) -> Registry:
    """Drive ``Registry.from_db`` with the primitive 'seeded' into the DB, by
    monkeypatching the four db loaders + SessionLocal — no real Postgres."""
    import strata.db.engine as engine_mod
    import strata.db.queries as queries_mod
    import strata.db.tams as tams_mod

    @asynccontextmanager
    async def _fake_session():  # test-local stand-in
        yield object()

    monkeypatch.setattr(engine_mod, "SessionLocal", _fake_session, raising=True)

    async def _prims(_session: object) -> list[AtomicPrimitive]:
        return [prim]

    async def _empty(_session: object) -> list[object]:
        return []

    monkeypatch.setattr(queries_mod, "load_primitives_from_db", _prims, raising=True)
    monkeypatch.setattr(queries_mod, "load_concepts_from_db", _empty, raising=True)
    monkeypatch.setattr(queries_mod, "load_frameworks_from_db", _empty, raising=True)
    monkeypatch.setattr(tams_mod, "load_promoted_tams_from_db", _empty, raising=True)

    import asyncio

    return asyncio.run(Registry.from_db())


@pytest.mark.parametrize("tier", sorted(NON_SIZING_TIERS, key=lambda t: t.value))
@pytest.mark.parametrize("path", ["yaml", "db"])
def test_non_sizing_tier_never_reaches_atomic(
    tier: SourceTier,
    path: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slug = f"synthetic-{tier.value.replace('_', '-')}-quarantine"
    prim = _primitive_with_tier(tier, slug)

    if path == "yaml":
        reg = _registry_via_yaml(prim, tmp_path)
    else:
        reg = _registry_via_db(prim, monkeypatch)

    # The load-bearing invariant on BOTH paths.
    leaked = {s for s, p in reg.atomic.items() if p.source.tier in NON_SIZING_TIERS}
    assert leaked == set(), f"[{path}] non-sizing tier leaked into reg.atomic: {leaked}"
    # And it must be quarantined, not dropped.
    assert slug in reg.signals, f"[{path}] {slug} was not routed to reg.signals"
    assert slug not in reg.atomic


def test_committed_bank_holds_invariant_on_yaml_path() -> None:
    # Belt-and-suspenders on the REAL committed data dir (no synthetic records).
    reg = Registry.from_loaded(load_data_dir(_REPO / "data"))
    leaked = {s for s, p in reg.atomic.items() if p.source.tier in NON_SIZING_TIERS}
    assert leaked == set(), f"committed data/primitives/ leaks non-sizing tiers: {leaked}"
