"""Wave 3 - auth, rate-limit, metering, CORS, observability (AC3.1-AC3.5).

These exercise the ASGI surface directly (no Postgres). RLS (AC3.6) is a
migration-level test gated on a live DB.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api.app import create_app
from strata.api.auth import _KEY_STORE, register_key
from strata.api.metering import get_meter
from strata.api.ratelimit import get_limiter
from strata.config import settings
from tests.test_resolve import MOCK_PARSED
from tests.test_resolve import MOCK_PRIMITIVE_1 as MOCK_P1
from tests.test_resolve import MOCK_PRIMITIVE_2 as MOCK_P2


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_state():
    get_meter().reset()
    get_limiter().reset()
    initial_keys = set(_KEY_STORE)
    yield
    settings.require_auth = False
    for k in set(_KEY_STORE) - initial_keys:
        _KEY_STORE.pop(k, None)


def _mock_resolver(fn):
    """Mock the LLM fallback so /resolve returns fast + offline (status-only tests)."""
    fn = patch("strata.api.routes.resolve.search_primitive", side_effect=[MOCK_P1, MOCK_P2])(fn)
    fn = patch("strata.api.routes.resolve.parse_query", return_value=MOCK_PARSED)(fn)
    return fn


# ── AC3.1 auth ────────────────────────────────────────────────────────────


@_mock_resolver
@pytest.mark.asyncio
async def test_auth_required(_mp, _ms, client: AsyncClient) -> None:
    register_key("secret-key-1", "org-acme")
    settings.require_auth = True
    # Missing key → 401.
    r = await client.post("/resolve", json={"query": "test"})
    assert r.status_code == 401
    # Wrong key → 401.
    r = await client.post("/resolve", json={"query": "test"}, headers={"X-API-Key": "nope"})
    assert r.status_code == 401
    # Valid key → not 401 (the resolve stream returns 200).
    r = await client.post("/resolve", json={"query": "test"}, headers={"X-API-Key": "secret-key-1"})
    assert r.status_code == 200  # _reset_state fixture purges the registered key


# ── AC3.2 rate limit ──────────────────────────────────────────────────────


@_mock_resolver
@pytest.mark.asyncio
async def test_rate_limit_429(_mp, _ms, client: AsyncClient) -> None:
    get_limiter().capacity = 2.0
    get_limiter().refill_per_sec = 0.0  # no refill within the test window
    get_limiter().reset()
    codes = []
    for _ in range(4):
        r = await client.post("/resolve", json={"query": "x"})
        codes.append(r.status_code)
    assert 429 in codes
    blocked = await client.post("/resolve", json={"query": "x"})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    # Restore a sane limiter for other tests.
    get_limiter().capacity = float(settings.rate_limit_rpm)
    get_limiter().refill_per_sec = settings.rate_limit_rpm / 60.0


# ── AC3.3 metering ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_metering(client: AsyncClient) -> None:
    await client.get("/c")
    await client.get("/c")
    usage = (await client.get("/usage")).json()
    assert usage["org_id"] == "public"
    assert usage["total"] >= 2
    assert any("/c" in route for route in usage["by_route"])


# ── AC3.4 CORS ────────────────────────────────────────────────────────────


def test_cors_not_wildcard_prod(monkeypatch) -> None:
    monkeypatch.setattr(settings, "env", "prod")
    monkeypatch.setattr(settings, "cors_origins", ["*"])
    prod_app = create_app()
    cors = next(m for m in prod_app.user_middleware if "CORSMiddleware" in str(m.cls))
    assert cors.kwargs["allow_origins"] != ["*"]


def test_cors_explicit_origins_preserved(monkeypatch) -> None:
    monkeypatch.setattr(settings, "env", "prod")
    monkeypatch.setattr(settings, "cors_origins", ["https://strata.example"])
    prod_app = create_app()
    cors = next(m for m in prod_app.user_middleware if "CORSMiddleware" in str(m.cls))
    assert cors.kwargs["allow_origins"] == ["https://strata.example"]


# ── AC3.5 observability ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_request_id_header(client: AsyncClient) -> None:
    r = await client.get("/healthz")
    assert r.headers.get("X-Request-Id")
    assert len(r.headers["X-Request-Id"]) >= 16


@pytest.mark.asyncio
async def test_metrics_endpoint(client: AsyncClient) -> None:
    await client.get("/c")
    r = await client.get("/metrics")
    assert r.status_code == 200
    assert "strata_requests_total" in r.text
