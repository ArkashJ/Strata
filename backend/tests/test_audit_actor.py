"""PR 1 / U5 — the Principal threads into the write paths.

An authenticated build attributes its persisted ``tam_outputs`` row to the
caller (``org_id`` + ``created_by``) and writes a strict-RLS-scoped audit row; an
anonymous build keeps writing a NULL-org GLOBAL permalink (byte-identical pre-PR
behaviour) and its ``/tam/<hash>`` permalink still resolves.

Requires a live Postgres migrated to head (the dual-purpose / strict RLS policies
are the thing under test); skipped when PG is unreachable so keyless CI stays
green. The Clerk verifier is stubbed — the bridge itself is unit-tested in
``test_auth_clerk_bridge`` / ``test_clerk_auth``.
"""

from __future__ import annotations

import socket
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api import auth
from strata.api.app import create_app
from strata.api.clerk_auth import ClerkClaims
from strata.config import settings

_CONCEPT = "ai-legal-assistants-us"
_COST_SLUG = "ai-legal-assistant-acv-per-seat-2024"
_USD_INTENSIVE = {"kind": "intensive", "dimension": "currency", "currency": "USD"}

_USER = "user_u5"
_ORG = f"clerk_user:{_USER}"


def _pg_reachable() -> bool:
    dsn = str(settings.database_url)
    try:
        hostport = dsn.split("@", 1)[1].split("/", 1)[0]
        host, _, port = hostport.partition(":")
        with socket.create_connection((host, int(port or 5432)), timeout=1.0):
            return True
    except (OSError, IndexError, ValueError):
        return False


pytestmark = pytest.mark.skipif(not _pg_reachable(), reason="no Postgres reachable")


def _asyncpg_dsn() -> str:
    return str(settings.database_url).replace("+asyncpg", "")


async def _connect() -> Any:
    import asyncpg

    return await asyncpg.connect(_asyncpg_dsn())


async def _require_008(conn: Any) -> None:
    has_col = await conn.fetchval(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'tam_outputs' AND column_name = 'org_id'"
    )
    if not has_col:
        pytest.skip("migration 008 not applied (run alembic upgrade head)")


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def stub_clerk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make a ``Bearer`` token resolve to our test user, keyless reads anonymous."""
    monkeypatch.setattr(
        auth, "verify_clerk_jwt", lambda _t: ClerkClaims(sub=_USER, org_id=None, raw={})
    )


@pytest.mark.asyncio
async def test_authenticated_build_attributes_org_and_actor(
    client: AsyncClient, stub_clerk: None
) -> None:
    """Authed build → tam row org_id=principal.org_id, created_by=user_id; the
    audit row carries the same org_id (strict-RLS-scoped)."""
    conn = await _connect()
    try:
        await _require_008(conn)
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", _ORG)
            await conn.execute("DELETE FROM tam_outputs WHERE org_id = $1", _ORG)
            await conn.execute("DELETE FROM audit_events WHERE org_id = $1", _ORG)

        built = (
            await client.get(f"/build/{_CONCEPT}", headers={"Authorization": "Bearer good.token"})
        ).json()
        state_hash = built["state_hash"]

        # The tenant row is visible only under the tenant's org scope (RLS).
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", _ORG)
            row = await conn.fetchrow(
                "SELECT org_id, created_by FROM tam_outputs WHERE state_hash = $1 AND org_id = $2",
                state_hash,
                _ORG,
            )
        assert row is not None, "authed build must persist a tenant-scoped tam row"
        assert row["org_id"] == _ORG
        assert row["created_by"] == _USER

        # An authed recompute writes a strict-RLS audit row under the same org.
        recomputed = (
            await client.post(
                "/build/recompute",
                headers={"Authorization": "Bearer good.token"},
                json={
                    "concept_slug": _CONCEPT,
                    "primitive_overrides": {_COST_SLUG: {"value": 4321.0, "unit": _USD_INTENSIVE}},
                },
            )
        ).json()
        assert recomputed["state_hash"]

        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", _ORG)
            audit_orgs = {
                r["org_id"]
                for r in await conn.fetch(
                    "SELECT org_id FROM audit_events WHERE org_id = $1 AND action = 'recompute'",
                    _ORG,
                )
            }
        assert audit_orgs == {_ORG}, "authed recompute must write an org-scoped audit row"
    finally:
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", _ORG)
            await conn.execute("DELETE FROM tam_outputs WHERE org_id = $1", _ORG)
            await conn.execute("DELETE FROM audit_events WHERE org_id = $1", _ORG)
        await conn.close()


@pytest.mark.asyncio
async def test_anonymous_build_is_global_and_permalink_resolves(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anonymous build → tam row org_id IS NULL (global permalink, unchanged) and
    GET /tam/<hash> still resolves; no tenant attribution leaks in."""
    monkeypatch.setattr(settings, "require_auth", False)
    conn = await _connect()
    try:
        await _require_008(conn)

        # No Authorization header → anonymous principal (org_id='public' → NULL row).
        built = (await client.get(f"/build/{_CONCEPT}")).json()
        state_hash = built["state_hash"]

        # Permalink resolves (the route reads NULL-org rows under no scope).
        resp = await client.get(f"/tam/{state_hash}")
        assert resp.status_code == 200
        assert resp.json()["state_hash"] == state_hash

        # The persisted row is a global NULL-org permalink (no scope set → RLS shows
        # only NULL-org rows), with no created_by attribution.
        row = await conn.fetchrow(
            "SELECT org_id, created_by FROM tam_outputs WHERE state_hash = $1",
            state_hash,
        )
        assert row is not None, "anonymous build must persist a global permalink row"
        assert row["org_id"] is None, "anonymous build must stay org_id IS NULL"
        assert row["created_by"] is None
    finally:
        await conn.execute("DELETE FROM tam_outputs WHERE state_hash = $1", state_hash)
        await conn.close()
