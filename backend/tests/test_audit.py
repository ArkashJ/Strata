"""Strata Live Track C: audit events writer + GET /audit feed.

Exercises a real Postgres session (the audit_events table created by migration
002). Skipped when no database is reachable so CI without PG stays green.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from strata.api.app import create_app
from strata.db.audit import list_audit_events, record_audit
from strata.db.engine import SessionLocal


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _db_available() -> bool:
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.mark.asyncio
async def test_audit_returns_rows_newest_first(client: AsyncClient) -> None:
    if not await _db_available():
        pytest.skip("no database reachable")

    tag = uuid.uuid4().hex
    async with SessionLocal() as session:
        await record_audit(session, actor="anon", action="resolve", target=f"first-{tag}")
        await record_audit(session, actor="anon", action="recompute", target=f"second-{tag}")

    # Direct reader: newest first.
    async with SessionLocal() as session:
        events = await list_audit_events(session, limit=50)
    targets = [e.target for e in events]
    assert f"second-{tag}" in targets
    assert f"first-{tag}" in targets
    assert targets.index(f"second-{tag}") < targets.index(f"first-{tag}")

    # Via the route — anonymous callers get a read-only capped public feed
    # (graceful degrade, P1.4) rather than a hard 401, so the dashboard trust
    # trail is populated in a keyless demo. Authenticated callers get the full feed.
    from strata.api.auth import _KEY_STORE, hash_key, register_key

    anon = await client.get("/audit?limit=50")
    assert anon.status_code == 200  # graceful degrade, not rejected
    register_key("audit-key", "org-ops")
    try:
        resp = await client.get("/audit?limit=50", headers={"X-API-Key": "audit-key"})
        assert resp.status_code == 200
    finally:
        _KEY_STORE.pop(hash_key("audit-key"), None)
    body = resp.json()
    route_targets = [e["target"] for e in body]
    assert route_targets.index(f"second-{tag}") < route_targets.index(f"first-{tag}")
