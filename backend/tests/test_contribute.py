"""Wave 4 / AC4.3 — POST /contribute validates a proposed contribution."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api.app import create_app
from strata.api.routes.contribute import get_contribution_store

_GOOD_PRIM = {
    "kind": "atomic_primitive",
    "slug": "contrib-test-headcount-2024",
    "schema_version": 1,
    "concept_slug": "demo-ai-sales-ops-us",
    "name": "Contributed headcount",
    "description": "A proposed primitive.",
    "value": 123456,
    "unit": {"kind": "stock", "dimension": "people"},
    "as_of": "2024-12-31",
    "geo": {"level": "country", "codes": ["US"]},
    "geo_perspective": "supply",
    "distribution_shape": "normal",
    "delivery_mode": "n/a",
    "source": {
        "slug": "contrib-src",
        "tier": "regulator",
        "url": "https://www.bls.gov/x",
        "accessed": "2026-05-30",
        "snapshot_sha256": "a" * 64,
    },
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
async def test_contribute_accepts_valid_regulator(client: AsyncClient) -> None:
    r = await client.post("/contribute", json={"kind": "atomic_primitive", "payload": _GOOD_PRIM})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "accepted"
    assert body["contribution_id"] is not None


@pytest.mark.asyncio
async def test_contribute_rejects_malformed(client: AsyncClient) -> None:
    bad = {**_GOOD_PRIM, "value": "not-a-number", "unit": {}}
    r = await client.post("/contribute", json={"kind": "atomic_primitive", "payload": bad})
    body = r.json()
    assert body["status"] == "rejected"
    assert body["reasons"]  # has reasons


@pytest.mark.asyncio
async def test_contribute_low_tier_needs_review(client: AsyncClient) -> None:
    community = {
        **_GOOD_PRIM,
        "source": {**_GOOD_PRIM["source"], "tier": "community"},
    }
    r = await client.post("/contribute", json={"kind": "atomic_primitive", "payload": community})
    body = r.json()
    assert body["status"] == "needs_review"  # no auto-publish of low-tier
