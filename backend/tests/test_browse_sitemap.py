"""Wave 4 / AC4.1 — promoted TAMs surface in /browse (sitemap source)."""

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
async def test_sitemap_lists_promoted_tams(client: AsyncClient) -> None:
    # A freshly-built TAM is not promoted; /browse excludes it.
    built = (await client.get(f"/build/{_CONCEPT}")).json()
    assert built["is_promoted"] is False

    promoted = (await client.post(f"/build/{_CONCEPT}/promote")).json()
    assert promoted["is_promoted"] is True

    listing = (await client.get("/browse")).json()
    hashes = {t["state_hash"] for t in listing}
    assert promoted["state_hash"] in hashes
    assert all(t["is_promoted"] for t in listing)
    # The promoted TAM resolves at its permalink (SSR'd headline → crawlable).
    permalink = await client.get(f"/tam/{promoted['state_hash']}")
    assert permalink.status_code == 200
