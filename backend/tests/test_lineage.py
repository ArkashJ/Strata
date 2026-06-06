"""Tests for the read-only lineage DAG route (GET /lineage/{concept_slug}).

The endpoint walks concept → framework → bound primitive → composite inputs /
derives_from and returns a {nodes, edges} payload whose keys match the frontend's
LineageGraph builder. These tests pin: the composite-input expansion, the
cycle-guard, the depth cap, the 404, and the exact response shape.
"""

from __future__ import annotations

import dataclasses
from datetime import date
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api.app import create_app
from strata.api.routes.lineage import MAX_DEPTH, build_lineage
from strata.loader import load_data_dir
from strata.models import AtomicPrimitive, Concept, Unit
from strata.models.concept import ConceptAnalysisLens
from strata.models.geo import Geo, GeoLevel, GeoPerspective
from strata.models.source import SourceTier, StandardSource
from strata.models.unit import UnitDimension, UnitKind
from strata.registry import Registry

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _base_registry() -> Registry:
    return Registry.from_loaded(load_data_dir(_DATA_DIR))


# A concept whose declared scope binds a framework to a COMPOSITE persona_pool,
# whose two atomic members are themselves in the bank — the full DAG.
_COMPOSITE_CONCEPT = "ai-coding-assistants-us"
_COMPOSITE_SLUG = "us-software-engineering-workforce"
_COMPOSITE_MEMBERS = {
    "census-cbp-5112-employees-2022",
    "census-cbp-5415-employees-2022",
}


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:  # type: ignore[misc]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _ids(payload: dict[str, object]) -> set[str]:
    return {n["id"] for n in payload["nodes"]}  # type: ignore[index,union-attr]


async def test_composite_inputs_return_full_node_and_edge_set(client: AsyncClient) -> None:
    resp = await client.get(f"/lineage/{_COMPOSITE_CONCEPT}")
    assert resp.status_code == 200
    payload = resp.json()
    ids = _ids(payload)

    # Root concept node.
    assert "concept" in ids
    # The composite primitive node (bound as a framework input).
    assert f"p-{_COMPOSITE_SLUG}" in ids
    # Both atomic members of the composite are expanded as primitive nodes.
    for member in _COMPOSITE_MEMBERS:
        assert f"p-{member}" in ids, f"composite member {member} missing from lineage"

    # An edge from the composite to each of its members exists.
    edge_pairs = {(e["from"], e["to"]) for e in payload["edges"]}
    for member in _COMPOSITE_MEMBERS:
        assert (f"p-{_COMPOSITE_SLUG}", f"p-{member}") in edge_pairs


async def test_response_shape_matches_builder_keys(client: AsyncClient) -> None:
    """The frontend builder reads node.{id,label,kind,lens?,role?} and
    edge.{id,from,to,signals}. The payload must expose exactly those JSON keys."""
    payload = (await client.get(f"/lineage/{_COMPOSITE_CONCEPT}")).json()

    for node in payload["nodes"]:
        assert {"id", "label", "kind"} <= set(node.keys())
        assert node["kind"] in {"concept", "framework", "primitive"}

    for edge in payload["edges"]:
        # ``from`` (not ``from_``) is the client key — the alias must win.
        assert set(edge.keys()) == {"id", "from", "to", "signals"}
        assert "from_" not in edge
        assert isinstance(edge["signals"], list)

    # A framework node carries a lens; the concept→framework edge signals the lens.
    fw_nodes = [n for n in payload["nodes"] if n["kind"] == "framework"]
    assert fw_nodes, "expected at least one framework node"
    assert any(n.get("lens") for n in fw_nodes)


async def test_unknown_id_returns_404(client: AsyncClient) -> None:
    resp = await client.get("/lineage/does-not-exist-xyz")
    assert resp.status_code == 404


def _atomic(slug: str, derives_from: tuple[str, ...]) -> AtomicPrimitive:
    return AtomicPrimitive(
        kind="atomic_primitive",
        slug=slug,
        schema_version=1,
        concept_slug="cyc",
        name=f"primitive {slug}",
        description="test primitive",
        value=1.0,
        unit=Unit(kind=UnitKind.STOCK, dimension=UnitDimension.PEOPLE),
        as_of=date(2024, 1, 1),
        geo=Geo(level=GeoLevel.COUNTRY, codes=("US",)),
        geo_perspective=GeoPerspective.SUPPLY,
        source=StandardSource(
            tier=SourceTier.REGULATOR,
            slug=f"src-{slug}",
            url="https://example.gov/x",
            accessed=date(2024, 1, 1),
            snapshot_sha256="0" * 64,
        ),
        derives_from=derives_from,
    )


def _cyclic_registry() -> Registry:
    """A registry where two atomics derive from each other (a→b→a) and a concept
    binds ``a`` via a framework — exercises the derives_from cycle-guard."""
    base = _base_registry()

    a = _atomic("cyc-a", derives_from=("cyc-b",))
    b = _atomic("cyc-b", derives_from=("cyc-a",))  # back-edge into a

    # Reuse a real framework but rebind a variant onto our cyclic concept so the
    # walk reaches the cyclic primitives. Easiest path: borrow an existing
    # applicable framework and point its persona_pool at cyc-a.
    fw = next(iter(base.frameworks.values()))
    # Clone with a new variant scoped to the cyclic concept (frozen models →
    # model_copy with an extended variants tuple).
    from strata.models.framework import FrameworkVariant

    first_input = fw.inputs[0].name
    new_variant = FrameworkVariant(scope="cyc", default_inputs={first_input: "cyc-a"})
    fw2 = fw.model_copy(
        update={
            "applicable_to": (*fw.applicable_to, "cyc"),
            "variants": (*fw.variants, new_variant),
        }
    )

    concept = Concept(
        kind="concept",
        slug="cyc",
        schema_version=1,
        name="Cyclic concept",
        definition="cyclic test concept",
        analysis_lens=ConceptAnalysisLens(primary=fw.lens),
    )

    return dataclasses.replace(
        base,
        atomic={**base.atomic, "cyc-a": a, "cyc-b": b},
        frameworks={**base.frameworks, fw.slug: fw2},
        concepts={**base.concepts, "cyc": concept},
    )


def test_cyclic_link_terminates() -> None:
    """A mutually-referential derives_from (cyc-a ↔ cyc-b) must terminate — the
    visited set stops the recursion instead of looping forever."""
    reg = _cyclic_registry()
    result = build_lineage(reg, "cyc")  # must return, not hang

    ids = {n.id for n in result.nodes}
    assert "p-cyc-a" in ids
    assert "p-cyc-b" in ids
    # The back-edge cyc-b → cyc-a is present, but cyc-a is not re-expanded: each
    # node appears exactly once (de-duplicated).
    assert len([n for n in result.nodes if n.id == "p-cyc-a"]) == 1
    assert len([n for n in result.nodes if n.id == "p-cyc-b"]) == 1


def _deep_chain_registry(length: int) -> Registry:
    """A linear derives_from chain p0 → p1 → ... → p{length} bound to a concept."""
    from strata.models.framework import FrameworkVariant

    base = _base_registry()

    chain: dict[str, AtomicPrimitive] = {}
    for i in range(length + 1):
        nxt = (f"deep-{i + 1}",) if i < length else ()
        chain[f"deep-{i}"] = _atomic(f"deep-{i}", derives_from=nxt)

    fw = next(iter(base.frameworks.values()))
    first_input = fw.inputs[0].name
    fw2 = fw.model_copy(
        update={
            "applicable_to": (*fw.applicable_to, "deep"),
            "variants": (
                *fw.variants,
                FrameworkVariant(scope="deep", default_inputs={first_input: "deep-0"}),
            ),
        }
    )
    concept = Concept(
        kind="concept",
        slug="deep",
        schema_version=1,
        name="Deep chain",
        definition="deep chain test concept",
        analysis_lens=ConceptAnalysisLens(primary=fw.lens),
    )
    return dataclasses.replace(
        base,
        atomic={**base.atomic, **chain},
        frameworks={**base.frameworks, fw.slug: fw2},
        concepts={**base.concepts, "deep": concept},
    )


def test_depth_cap_honored() -> None:
    """A chain longer than the depth cap stops expanding — nodes beyond the cap
    are not emitted, proving the walk is bounded."""
    reg = _deep_chain_registry(length=MAX_DEPTH + 5)
    result = build_lineage(reg, "deep")
    ids = {n.id for n in result.nodes}

    # The first primitive (bound as the framework input) is always present.
    assert "p-deep-0" in ids
    # The deepest links are never reached (the cap stopped the recursion).
    assert f"p-deep-{MAX_DEPTH + 5}" not in ids
    assert f"p-deep-{MAX_DEPTH + 4}" not in ids
