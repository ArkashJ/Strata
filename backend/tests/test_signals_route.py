"""Tests for the read-only /signals route (T1).

Signals are the prediction-market primitives quarantined to data/signals/ (Q20).
They must surface read-only, carry their source pin, and never leak into the
sizing surfaces (/p, frameworks, TAMs).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api.app import create_app
from strata.loader import load_data_dir
from strata.models.source import SourceTier
from strata.registry import Registry

_DATA = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:  # type: ignore[misc]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_list_signals_returns_prediction_market_rows(client: AsyncClient) -> None:
    r = await client.get("/signals")
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
    assert len(rows) > 0
    for row in rows:
        assert row["source_tier"] == "prediction_market"
        # The receipt: every signal carries a source URL + snapshot pin.
        assert row["source_url"]
        assert len(row["snapshot_sha256"]) == 64


async def test_signal_detail_round_trips(client: AsyncClient) -> None:
    slug = (await client.get("/signals")).json()[0]["slug"]
    r = await client.get(f"/signals/{slug}")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == slug
    assert body["kind"] == "atomic_primitive"
    assert body["source"]["tier"] == "prediction_market"


async def test_signal_detail_404_for_unknown(client: AsyncClient) -> None:
    r = await client.get("/signals/does-not-exist")
    assert r.status_code == 404


async def test_signals_never_leak_into_primitives(client: AsyncClient) -> None:
    """Quarantine invariant (Q20): no signal slug appears under /p."""
    signal_slugs = {row["slug"] for row in (await client.get("/signals")).json()}
    primitive_slugs = {row["slug"] for row in (await client.get("/p")).json()}
    assert signal_slugs.isdisjoint(primitive_slugs)


def test_registry_quarantines_signals_from_evaluable_primitives() -> None:
    """The load-bearing Q20 gate at the registry level: signals are a separate
    index from the atomic/composite primitives the evaluator can resolve, and
    every signal is prediction-market tier. A framework input slug can only ever
    bind against ``reg.atomic``/``reg.composite`` — never ``reg.signals`` — so
    disjoint keyspaces here are what actually keep a signal out of a TAM."""
    reg = Registry.from_loaded(load_data_dir(_DATA))
    assert reg.signals  # the 202 Kalshi signals are loaded
    assert reg.signals.keys().isdisjoint(reg.atomic.keys())
    assert reg.signals.keys().isdisjoint(reg.composite.keys())
    assert all(s.source.tier is SourceTier.PREDICTION_MARKET for s in reg.signals.values())
