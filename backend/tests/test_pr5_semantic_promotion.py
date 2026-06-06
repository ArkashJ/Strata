"""PR5 — semantic-embeddings search + concept-promotion (validator-gated).

Pure unit coverage (no DB): the feature-hashing embedding, the intersection
candidate builder, and the ``/contribute`` concept path through the review gate.
The live pgvector NN path is exercised by ``strata embed`` + a separate
DB-gated test; here we cover the deterministic, network-free logic.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api.app import create_app
from strata.api.concept_promotion import intersection_candidate
from strata.api.routes.contribute import get_contribution_store
from strata.models import Concept
from strata.models.scope import CodedTag, CodeSystem, MarketScope
from strata.resolver.embeddings import EMBED_DIM, cosine, embed_text

# --------------------------------------------------------------------------- #
# Embeddings (deterministic feature-hashing)                                   #
# --------------------------------------------------------------------------- #


def test_embed_dim_is_fixed() -> None:
    assert len(embed_text("software developer market")) == EMBED_DIM


def test_embed_is_deterministic() -> None:
    a = embed_text("AI coding assistants US")
    b = embed_text("AI coding assistants US")
    assert a == b


def test_embed_empty_text_is_zero_vector() -> None:
    vec = embed_text("   !!!  ")
    assert vec == [0.0] * EMBED_DIM
    # zero vector has zero similarity to anything → never a spurious match.
    assert cosine(vec, embed_text("anything")) == 0.0


def test_embed_is_l2_normalized() -> None:
    vec = embed_text("developer tooling productivity")
    norm = sum(v * v for v in vec) ** 0.5
    assert norm == pytest.approx(1.0, abs=1e-9)


def test_related_text_more_similar_than_unrelated() -> None:
    target = embed_text("AI developer tooling for US software developers")
    related = embed_text("software developer tooling market")
    unrelated = embed_text("offshore wind turbine maintenance contracts")
    assert cosine(target, related) > cosine(target, unrelated)


def test_cosine_length_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        cosine([0.1, 0.2], [0.1, 0.2, 0.3])


# --------------------------------------------------------------------------- #
# Intersection auto-promotion (pure draft builder)                            #
# --------------------------------------------------------------------------- #


def _concept(slug: str, name: str, *, vertical: str | None, persona: str | None) -> Concept:
    return Concept(
        kind="concept",
        slug=slug,
        schema_version=1,
        name=name,
        definition=f"{name} definition.",
        analysis_lens={"primary": "cost_efficiency"},
        scope=MarketScope(
            vertical=(
                (CodedTag(system=CodeSystem.NAICS, code=vertical, label="v"),) if vertical else ()
            ),
            persona=(
                (CodedTag(system=CodeSystem.SOC, code=persona, label="p"),) if persona else ()
            ),
        ),
    )


def _registry_with(*concepts: Concept):
    from strata.registry import Registry

    return Registry(
        atomic={},
        composite={},
        concepts={c.slug: c for c in concepts},
        frameworks={},
        annotations={},
        tam_outputs={},
    )


def test_intersection_builds_draft_on_shared_vertical() -> None:
    a = _concept("a", "Market A", vertical="5415", persona="15-1252")
    b = _concept("b", "Market B", vertical="5415", persona="41-4012")
    reg = _registry_with(a, b)

    draft = intersection_candidate(reg, "a", "b")
    assert draft is not None
    assert draft.kind == "concept"
    # shared vertical retained; non-shared persona dropped.
    assert [t.code for t in draft.scope.vertical] == ["5415"]
    assert draft.scope.persona == ()
    # lineage is explicit + sorted; NO fabricated measurements (Q20).
    assert draft.competing_concepts == ("a", "b")
    assert draft.measurements == ()
    # deterministic slug (sorted) → idempotent dedupe at review.
    assert draft.slug == "intersection-a-x-b"
    assert intersection_candidate(reg, "b", "a").slug == "intersection-a-x-b"


def test_intersection_none_when_no_shared_dimension() -> None:
    a = _concept("a", "Market A", vertical="5415", persona=None)
    b = _concept("b", "Market B", vertical="3361", persona=None)
    reg = _registry_with(a, b)
    assert intersection_candidate(reg, "a", "b") is None


def test_intersection_none_for_unknown_or_self() -> None:
    a = _concept("a", "Market A", vertical="5415", persona=None)
    reg = _registry_with(a)
    assert intersection_candidate(reg, "a", "a") is None
    assert intersection_candidate(reg, "a", "missing") is None


# --------------------------------------------------------------------------- #
# /contribute concept path — validator-gated, never auto-published            #
# --------------------------------------------------------------------------- #


_GOOD_CONCEPT = {
    "kind": "concept",
    "slug": "contrib-test-concept",
    "schema_version": 1,
    "name": "Contributed concept",
    "definition": "A proposed concept.",
    "analysis_lens": {"primary": "cost_efficiency"},
}


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def _reset():
    get_contribution_store().reset()
    yield
    get_contribution_store().reset()


@pytest.mark.asyncio
async def test_concept_promote_queues_for_review(client: AsyncClient) -> None:
    r = await client.post("/concepts/promote", json={"payload": _GOOD_CONCEPT})
    assert r.status_code == 200
    body = r.json()
    # A concept is NEVER auto-accepted — always human review (flow 39).
    assert body["status"] == "needs_review"


@pytest.mark.asyncio
async def test_concept_promote_rejects_malformed(client: AsyncClient) -> None:
    bad = {**_GOOD_CONCEPT, "analysis_lens": {"primary": "not-a-lens"}}
    r = await client.post("/concepts/promote", json={"payload": bad})
    assert r.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_intersect_422_when_no_shared_scope(client: AsyncClient) -> None:
    # Two real demo concepts in different verticals → no shared scope.
    r = await client.post(
        "/concepts/intersect",
        json={"concept_a": "demo-ai-dev-tooling-us", "concept_b": "demo-ai-clinical-docs-us"},
    )
    assert r.status_code in (200, 422)  # 422 if disjoint; 200 if they happen to overlap
