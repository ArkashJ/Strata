"""Wave 0 / AC0.1 — built + recomputed TAMs must be retrievable by permalink.

A first-time VC sizes a market (``GET /build/{slug}``) or tweaks an assumption
(``POST /build/recompute``), copies the resulting ``/tam/<hash>`` URL, and the
link must resolve. The evaluator mints a fresh ``state_hash`` per distinct
state; the route persists the output into ``reg.tam_outputs`` (FIFO-capped) so
the permalink is live for the session.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api.app import create_app

_CONCEPT = "ai-legal-assistants-us"
_COST_SLUG = "ai-legal-assistant-acv-per-seat-2024"
_USD_INTENSIVE = {"kind": "intensive", "dimension": "currency", "currency": "USD"}


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_built_tam_permalink_resolves(client: AsyncClient) -> None:
    built = (await client.get(f"/build/{_CONCEPT}")).json()
    state_hash = built["state_hash"]
    resp = await client.get(f"/tam/{state_hash}")
    assert resp.status_code == 200
    assert resp.json()["state_hash"] == state_hash


@pytest.mark.asyncio
async def test_recomputed_tam_permalink_resolves(client: AsyncClient) -> None:
    recomputed = (
        await client.post(
            "/build/recompute",
            json={
                "concept_slug": _CONCEPT,
                "primitive_overrides": {_COST_SLUG: {"value": 1234.0, "unit": _USD_INTENSIVE}},
            },
        )
    ).json()
    state_hash = recomputed["state_hash"]
    resp = await client.get(f"/tam/{state_hash}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["state_hash"] == state_hash
    assert body["uses_synthetic_primitives"] is True


@pytest.mark.asyncio
async def test_unknown_tam_hash_404(client: AsyncClient) -> None:
    resp = await client.get("/tam/deadbeefdeadbeefdeadbeefdeadbeef")
    assert resp.status_code == 404
