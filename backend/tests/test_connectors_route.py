"""Tests for the read-only /connectors catalog route (connector-explorer).

The route must list the capability registry, report a REAL primitives_in_bank
count from the data bank (never synthesized), and keep its host-map invariant:
a connector present in _CONNECTOR_HOSTS has data in reg.atomic; kalshi is absent
because its primitives are quarantined to reg.signals (Q20).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api.app import create_app
from strata.api.routes.connectors import _CONNECTOR_HOSTS


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:  # type: ignore[misc]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_lists_connectors_with_capabilities(client: AsyncClient) -> None:
    rows = (await client.get("/connectors")).json()
    assert len(rows) > 10
    for r in rows:
        assert r["method_count"] >= 1
        assert len(r["capabilities"]) == r["method_count"]


async def test_producing_connectors_have_real_samples(client: AsyncClient) -> None:
    rows = (await client.get("/connectors")).json()
    producing = [r for r in rows if r["primitives_in_bank"] > 0]
    assert producing, "at least one connector should have ingested bank data"
    for r in producing:
        # A real count carries a real sample slug + source url — never synthesized.
        assert r["sample_primitive_slug"]
        assert r["sample_source_url"]


async def test_capability_only_connectors_show_zero_without_sample(client: AsyncClient) -> None:
    rows = (await client.get("/connectors")).json()
    empty = [r for r in rows if r["primitives_in_bank"] == 0]
    assert empty, "some connectors are wired but not yet ingested"
    for r in empty:
        assert r["sample_primitive_slug"] is None


async def test_sample_is_deterministic(client: AsyncClient) -> None:
    first = (await client.get("/connectors")).json()
    second = (await client.get("/connectors")).json()
    assert [r["sample_primitive_slug"] for r in first] == [
        r["sample_primitive_slug"] for r in second
    ]


async def test_kalshi_absent_from_host_map() -> None:
    """Kalshi data is quarantined to reg.signals (Q20), so it must not be mapped
    as an atomic-bank producer — the map invariant is presence == has reg.atomic data."""
    assert "kalshi" not in _CONNECTOR_HOSTS


async def test_github_is_honest_zero(client: AsyncClient) -> None:
    """github is deliberately NOT host-mapped (PR 0): the only primitives citing
    github.com are hand-authored analyst/community-modeled figures, not
    github-connector ingests. Mapping it would attribute those citations as a fake
    ingest count. github stays in the catalog with primitives_in_bank == 0 even
    though primitives DO cite github.com — that gap is the honest-zero, not an
    oversight, so guard against a silent map-back regression."""
    assert "github" not in _CONNECTOR_HOSTS
    rows = (await client.get("/connectors")).json()
    gh = next((r for r in rows if r["connector"] == "github"), None)
    assert gh is not None, "github should still be listed in the connector catalog"
    assert gh["primitives_in_bank"] == 0


async def test_usda_nass_is_mapped(client: AsyncClient) -> None:
    """usda_nass is a real ingest (PR 0): host-mapped, so its citing primitives
    are attributed. Guards the positive side of the same host-map invariant."""
    assert "usda_nass" in _CONNECTOR_HOSTS
    rows = (await client.get("/connectors")).json()
    nass = next((r for r in rows if r["connector"] == "usda_nass"), None)
    assert nass is not None
    assert nass["primitives_in_bank"] > 0
