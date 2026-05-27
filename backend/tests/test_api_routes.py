"""Integration tests for the REST API routes."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api.app import create_app


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_healthz(client: AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_list_concepts(client: AsyncClient) -> None:
    resp = await client.get("/c")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["slug"] == "doc-gen-pc-insurance"


@pytest.mark.asyncio
async def test_get_concept(client: AsyncClient) -> None:
    resp = await client.get("/c/doc-gen-pc-insurance")
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == "doc-gen-pc-insurance"
    assert body["kind"] == "concept"


@pytest.mark.asyncio
async def test_get_concept_404(client: AsyncClient) -> None:
    resp = await client.get("/c/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_primitives(client: AsyncClient) -> None:
    resp = await client.get("/p")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 4


@pytest.mark.asyncio
async def test_get_primitive(client: AsyncClient) -> None:
    resp = await client.get("/p/naic-active-pc-carriers-2024")
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == "naic-active-pc-carriers-2024"


@pytest.mark.asyncio
async def test_get_primitive_404(client: AsyncClient) -> None:
    resp = await client.get("/p/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_frameworks(client: AsyncClient) -> None:
    resp = await client.get("/f")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_get_framework(client: AsyncClient) -> None:
    resp = await client.get("/f/bottoms-up-cost-efficiency")
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == "bottoms-up-cost-efficiency"


@pytest.mark.asyncio
async def test_get_framework_404(client: AsyncClient) -> None:
    resp = await client.get("/f/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_build_tam(client: AsyncClient) -> None:
    resp = await client.get("/build/doc-gen-pc-insurance")
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "tam_output"
    assert len(body["scenarios"]) >= 1
    assert body["target"]["concept"] == "doc-gen-pc-insurance"
    assert body["target"]["concept_name"] is not None
    # Verify InputUsed enrichment fields are present in the API response
    first_scenario = body["scenarios"][0]
    assert first_scenario["inputs_used"], "inputs_used is empty"
    first_input = first_scenario["inputs_used"][0]
    assert first_input["value"] is not None
    assert first_input["name"] is not None
    assert first_input["unit"] is not None


@pytest.mark.asyncio
async def test_build_tam_unknown_concept(client: AsyncClient) -> None:
    resp = await client.get("/build/nonexistent")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_tam_by_hash_404(client: AsyncClient) -> None:
    fake_hash = "a" * 64
    resp = await client.get(f"/tam/{fake_hash}")
    assert resp.status_code == 404
