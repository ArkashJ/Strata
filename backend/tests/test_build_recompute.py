"""Strata Live Track A: POST /build/recompute.

Override-aware recompute over the seeded ``ai-legal-assistants-us`` concept.
The route validates each what-if override's unit against the consuming
framework input signature (422 on mismatch), returns a fresh state_hash, and
marks overridden scenarios with a user_override banner.
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
async def test_recompute_scalar_override(client: AsyncClient) -> None:
    base = (await client.get(f"/build/{_CONCEPT}")).json()
    resp = await client.post(
        "/build/recompute",
        json={
            "concept_slug": _CONCEPT,
            "primitive_overrides": {_COST_SLUG: {"value": 1000.0, "unit": _USD_INTENSIVE}},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["state_hash"] != base["state_hash"]
    assert body["uses_synthetic_primitives"] is True
    kinds = {b["kind"] for sc in body["scenarios"] for b in sc["banners"]}
    assert "user_override" in kinds


@pytest.mark.asyncio
async def test_recompute_unit_mismatch_422(client: AsyncClient) -> None:
    resp = await client.post(
        "/build/recompute",
        json={
            "concept_slug": _CONCEPT,
            "primitive_overrides": {
                _COST_SLUG: {
                    "value": 1000.0,
                    "unit": {"kind": "stock", "dimension": "people"},
                }
            },
        },
    )
    assert resp.status_code == 422
    assert "unit" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_recompute_unknown_concept_404(client: AsyncClient) -> None:
    resp = await client.post(
        "/build/recompute",
        json={"concept_slug": "does-not-exist"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_recompute_unknown_swap_primitive_422(client: AsyncClient) -> None:
    # A framework_assumptions swap to a non-existent primitive raises ValueError
    # in the evaluator; the route must translate that to 422, not leak a 500.
    resp = await client.post(
        "/build/recompute",
        json={
            "concept_slug": _CONCEPT,
            "framework_assumptions": {
                "bottoms-up-cost-efficiency": {"cost_per_persona": "does-not-exist"}
            },
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_recompute_unconsumed_override_422(client: AsyncClient) -> None:
    # A what-if override on a slug no applicable framework input binds must be
    # rejected (not silently 200 + base TAM) — the inverse of an unknown swap.
    resp = await client.post(
        "/build/recompute",
        json={
            "concept_slug": _CONCEPT,
            "primitive_overrides": {
                "not-a-bound-input-slug": {"value": 1.0, "unit": _USD_INTENSIVE}
            },
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_recompute_framework_swap_no_banner(client: AsyncClient) -> None:
    resp = await client.post(
        "/build/recompute",
        json={
            "concept_slug": _CONCEPT,
            "framework_assumptions": {
                "bottoms-up-cost-efficiency": {
                    "cost_per_persona": "ai-coding-assistant-acv-per-engineer-2024"
                }
            },
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    kinds = {b["kind"] for sc in body["scenarios"] for b in sc["banners"]}
    assert "user_override" not in kinds
