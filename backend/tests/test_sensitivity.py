"""Wave 2 / AC2.3 — GET /build/{slug}/sensitivity feeds the tornado chart.

Each framework input is perturbed ±pct through the override-aware evaluator and
the resulting TAM-midpoint swing is reported; rows are sorted by |impact| so the
tornado chart's bars come pre-ordered.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api.app import create_app

_CONCEPT = "demo-ai-dev-tooling-us"


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_sensitivity_rows_sorted_by_impact(client: AsyncClient) -> None:
    resp = await client.get(f"/build/{_CONCEPT}/sensitivity")
    assert resp.status_code == 200
    body = resp.json()
    rows = body["inputs"]
    assert len(rows) >= 2, "expected several perturbable inputs"
    impacts = [r["impact"] for r in rows]
    assert impacts == sorted(impacts, reverse=True), "rows must be sorted by |impact| desc"
    for r in rows:
        assert r["low"] <= r["base"] <= r["high"] or r["high"] <= r["base"] <= r["low"]
        assert r["impact"] >= 0


@pytest.mark.asyncio
async def test_sensitivity_perturbation_moves_the_tam(client: AsyncClient) -> None:
    resp = await client.get(f"/build/{_CONCEPT}/sensitivity", params={"pct": 0.25})
    body = resp.json()
    # At least one input must actually swing the TAM (non-zero impact).
    assert any(r["impact"] > 0 for r in body["inputs"])
    assert body["pct"] == 0.25


@pytest.mark.asyncio
async def test_sensitivity_unknown_concept_404(client: AsyncClient) -> None:
    resp = await client.get("/build/does-not-exist/sensitivity")
    assert resp.status_code in (404, 422)
