"""Test all API endpoints against seeded data."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api.app import create_app

CONCEPT_SLUGS = [
    "doc-gen-pc-insurance",
    "gtm-ops-tooling-na",
    "midmarket-saas-spend-na",
    "payments-throughput-pc-insurance",
    "workplace-suite-consolidation",
    "software-eng-productivity",
]


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:  # type: ignore[misc]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


async def test_healthz(client: AsyncClient) -> None:
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Concepts
# ---------------------------------------------------------------------------


async def test_list_concepts(client: AsyncClient) -> None:
    r = await client.get("/c")
    assert r.status_code == 200
    concepts = r.json()
    assert isinstance(concepts, list)
    assert len(concepts) == 6
    slugs = {c["slug"] for c in concepts}
    for slug in CONCEPT_SLUGS:
        assert slug in slugs, f"concept {slug!r} missing from /c"


async def test_list_concepts_fields(client: AsyncClient) -> None:
    r = await client.get("/c")
    first = r.json()[0]
    assert "slug" in first
    assert "name" in first
    assert "definition" in first
    assert "primary_lens" in first
    assert "measurement_count" in first


async def test_get_concept_doc_gen(client: AsyncClient) -> None:
    r = await client.get("/c/doc-gen-pc-insurance")
    assert r.status_code == 200
    data = r.json()
    assert data["slug"] == "doc-gen-pc-insurance"
    assert data["name"] == "P&C insurance document generation"
    # measurements is a tuple of primitive slugs in the Concept model
    assert len(data["measurements"]) >= 1


async def test_get_concept_not_found(client: AsyncClient) -> None:
    r = await client.get("/c/nonexistent-concept-xyz")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


async def test_list_primitives(client: AsyncClient) -> None:
    r = await client.get("/p")
    assert r.status_code == 200
    primitives = r.json()
    assert isinstance(primitives, list)
    assert len(primitives) >= 14


async def test_list_primitives_fields(client: AsyncClient) -> None:
    r = await client.get("/p")
    first = r.json()[0]
    assert "slug" in first
    assert "name" in first
    assert "kind" in first
    assert "concept_slug" in first
    assert "unit_label" in first


async def test_get_primitive_detail(client: AsyncClient) -> None:
    r = await client.get("/p/naic-active-pc-carriers-2024")
    assert r.status_code == 200
    data = r.json()
    assert data["slug"] == "naic-active-pc-carriers-2024"
    assert data["kind"] == "atomic_primitive"


async def test_get_primitive_not_found(client: AsyncClient) -> None:
    r = await client.get("/p/nonexistent-primitive-xyz")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Frameworks
# ---------------------------------------------------------------------------


async def test_list_frameworks(client: AsyncClient) -> None:
    r = await client.get("/f")
    assert r.status_code == 200
    frameworks = r.json()
    assert isinstance(frameworks, list)
    assert len(frameworks) >= 5


async def test_list_frameworks_fields(client: AsyncClient) -> None:
    r = await client.get("/f")
    first = r.json()[0]
    assert "slug" in first
    assert "name" in first
    assert "method_family" in first
    assert "lens" in first
    assert "input_count" in first


async def test_get_framework_detail(client: AsyncClient) -> None:
    r = await client.get("/f/bottoms-up-cost-efficiency")
    assert r.status_code == 200
    data = r.json()
    assert data["slug"] == "bottoms-up-cost-efficiency"


async def test_get_framework_not_found(client: AsyncClient) -> None:
    r = await client.get("/f/nonexistent-framework-xyz")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Build — all concepts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("slug", CONCEPT_SLUGS)
async def test_build_concept(client: AsyncClient, slug: str) -> None:
    r = await client.get(f"/build/{slug}")
    assert r.status_code == 200, f"Build failed for {slug}: {r.text}"
    data = r.json()
    assert data["target"]["concept"] == slug
    assert data["target"]["concept_name"] is not None
    assert len(data["scenarios"]) >= 1
    assert data["scenarios"][0]["value"] > 0


async def test_build_enrichment_in_api(client: AsyncClient) -> None:
    """inputs_used in API response must carry value, name, and unit."""
    r = await client.get("/build/doc-gen-pc-insurance")
    assert r.status_code == 200
    data = r.json()
    for scenario in data["scenarios"]:
        for inp in scenario["inputs_used"]:
            assert inp.get("value") is not None, (
                f"API: inputs_used missing value for {inp.get('primitive_slug')}"
            )
            assert inp.get("name") is not None, (
                f"API: inputs_used missing name for {inp.get('primitive_slug')}"
            )
            assert inp.get("unit") is not None, (
                f"API: inputs_used missing unit for {inp.get('primitive_slug')}"
            )


async def test_build_concept_not_found(client: AsyncClient) -> None:
    r = await client.get("/build/nonexistent-concept-xyz")
    assert r.status_code == 422


async def test_build_response_has_state_hash(client: AsyncClient) -> None:
    r = await client.get("/build/doc-gen-pc-insurance")
    assert r.status_code == 200
    data = r.json()
    assert "state_hash" in data
    assert len(data["state_hash"]) == 64


# ---------------------------------------------------------------------------
# TAM frozen artifact
# ---------------------------------------------------------------------------


async def test_tam_not_found(client: AsyncClient) -> None:
    r = await client.get(
        "/tam/0000000000000000000000000000000000000000000000000000000000000000"
    )
    assert r.status_code == 404


async def test_tam_state_hash_deterministic_across_build_calls(
    client: AsyncClient,
) -> None:
    """Two /build calls for the same concept must emit the same state_hash."""
    r1 = await client.get("/build/doc-gen-pc-insurance")
    r2 = await client.get("/build/doc-gen-pc-insurance")
    assert r1.json()["state_hash"] == r2.json()["state_hash"]
