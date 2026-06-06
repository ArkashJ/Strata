"""Strata Live Track C: audit events writer + GET /audit feed.

Exercises a real Postgres session. PR 1 (migration 008) put a STRICT closed RLS
policy on ``audit_events`` (org-scoped, fails closed when ``app.org_id`` is
unset), so writes and reads must now run under an ``org_session_scope`` — a
plain unscoped insert of a NULL-org row is rejected by design. Skipped when no
database is reachable so CI without PG stays green.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from strata.api.app import create_app
from strata.db.audit import list_audit_events, record_audit
from strata.db.engine import SessionLocal, org_session_scope

_ORG = "clerk_user:audit-test"


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
    # Writes run under the tenant's org scope so the strict RLS WITH CHECK passes.
    async with org_session_scope(_ORG) as session:
        await record_audit(
            session, actor="u1", action="resolve", target=f"first-{tag}", org_id=_ORG
        )
    async with org_session_scope(_ORG) as session:
        await record_audit(
            session, actor="u1", action="recompute", target=f"second-{tag}", org_id=_ORG
        )

    # Direct reader under the same org scope: newest first, only this org's rows.
    async with org_session_scope(_ORG) as session:
        events = await list_audit_events(session, limit=50)
    targets = [e.target for e in events]
    assert f"second-{tag}" in targets
    assert f"first-{tag}" in targets
    assert targets.index(f"second-{tag}") < targets.index(f"first-{tag}")
    assert all(e.org_id == _ORG for e in events), "strict RLS should scope the read to this org"

    # The route still answers (graceful degrade for anonymous, full feed for keyed
    # callers); it reads via an unscoped session so under strict RLS it returns an
    # honest empty/global window rather than another tenant's rows. We assert it
    # never hard-errors — the per-tenant feed lands on /me/audit (U7).
    from strata.api.auth import _KEY_STORE, hash_key, register_key

    anon = await client.get("/audit?limit=50")
    assert anon.status_code == 200
    register_key("audit-key", "org-ops")
    try:
        resp = await client.get("/audit?limit=50", headers={"X-API-Key": "audit-key"})
        assert resp.status_code == 200
    finally:
        _KEY_STORE.pop(hash_key("audit-key"), None)
