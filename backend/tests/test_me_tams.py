"""PR 1 / U7 — saved research + per-user history (``/me/tams``, ``/me/audit``).

The save path is the riskiest interaction with the dual-purpose RLS policy on
``tam_outputs`` (KTD-1/KTD-2): a tenant save must land on the ``(org_id,
state_hash)`` partial index WITHOUT touching the anonymous ``org_id IS NULL``
permalink row, and a second tenant must see none of the first's saves. The audit
feed is RLS-scoped to the caller's org so ``/me/audit`` returns only the caller's
events.

These exercises need a live Postgres migrated to head; skipped when PG is
unreachable so keyless CI stays green. The Clerk verifier is stubbed.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api import auth
from strata.api.app import create_app
from strata.api.clerk_auth import ClerkClaims
from strata.config import settings
from strata.db.audit import record_audit_safe
from strata.db.tams import persist_tam_safe
from strata.evaluator.engine import size_concept
from strata.loader import load_data_dir
from strata.models import TAMOutput
from strata.registry import Registry

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

_USER_A = "user_tams_a"
_USER_B = "user_tams_b"
_ORG_A = f"clerk_user:{_USER_A}"
_ORG_B = f"clerk_user:{_USER_B}"

_BEARER_A = {"Authorization": "Bearer token.a"}
_BEARER_B = {"Authorization": "Bearer token.b"}


def _a_tam() -> TAMOutput:
    """A real evaluator-produced TAM, used as the build the caller saves."""
    registry = Registry.from_loaded(load_data_dir(_DATA_DIR))
    return size_concept(registry, "demo-ai-sales-ops-us")


def _pg_reachable() -> bool:
    dsn = str(settings.database_url)
    try:
        hostport = dsn.split("@", 1)[1].split("/", 1)[0]
        host, _, port = hostport.partition(":")
        with socket.create_connection((host, int(port or 5432)), timeout=1.0):
            return True
    except (OSError, IndexError, ValueError):
        return False


_PG = pytest.mark.skipif(not _pg_reachable(), reason="no Postgres reachable")


def _asyncpg_dsn() -> str:
    return str(settings.database_url).replace("+asyncpg", "")


async def _cleanup(state_hash: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(_asyncpg_dsn())
    try:
        has = await conn.fetchval(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'tam_outputs'"
        )
        if not has:
            return
        # Both tables are FORCE ROW LEVEL SECURITY, so a DELETE only touches rows
        # the policy admits for the current scope. Delete the global permalink (no
        # scope) and each tenant's saves/audit under that tenant's scope.
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', '', true)")
            await conn.execute(
                "DELETE FROM tam_outputs WHERE state_hash = $1 AND org_id IS NULL", state_hash
            )
        for org in (_ORG_A, _ORG_B):
            async with conn.transaction():
                await conn.execute("SELECT set_config('app.org_id', $1, true)", org)
                await conn.execute(
                    "DELETE FROM tam_outputs WHERE state_hash = $1 AND org_id = $2",
                    state_hash,
                    org,
                )
                await conn.execute("DELETE FROM audit_events WHERE org_id = $1", org)
    finally:
        await conn.close()


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
    def _verify(token: str) -> ClerkClaims:
        if token == "token.a":
            return ClerkClaims(sub=_USER_A, org_id=None, raw={})
        return ClerkClaims(sub=_USER_B, org_id=None, raw={})

    monkeypatch.setattr(auth, "verify_clerk_jwt", _verify)


@pytest.fixture
async def seeded():
    """Seed a GLOBAL permalink (org_id IS NULL) for a real TAM, then clean both the
    permalink and any tenant saves afterwards."""
    tam = _a_tam()
    await _cleanup(tam.state_hash)
    await persist_tam_safe(tam, org_id=None)
    yield tam
    await _cleanup(tam.state_hash)
    from strata.db.engine import engine

    await engine.dispose()


async def _row_orgs(state_hash: str) -> list[tuple[str | None, bool]]:
    """All (org_id, is_saved) rows for a hash across both test orgs + the global
    permalink. ``tam_outputs`` is ``FORCE ROW LEVEL SECURITY``, so even the table
    owner only sees rows the dual-purpose policy admits for the current
    ``app.org_id`` — we read once per org scope and union the results."""
    import asyncpg

    conn = await asyncpg.connect(_asyncpg_dsn())
    seen: dict[tuple[str | None, bool], None] = {}
    try:
        for scope in (None, _ORG_A, _ORG_B):
            async with conn.transaction():
                await conn.execute("SELECT set_config('app.org_id', $1, true)", scope or "")
                rows = await conn.fetch(
                    "SELECT org_id, is_saved FROM tam_outputs WHERE state_hash = $1",
                    state_hash,
                )
                for r in rows:
                    seen[(r["org_id"], r["is_saved"])] = None
    finally:
        await conn.close()
    return list(seen)


# --------------------------------------------------------------------------- #
# Anonymous → 401 (no Postgres needed).                                        #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_anonymous_is_401(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "require_auth", False)
    assert (await client.post("/me/tams/save", json={"state_hash": "x"})).status_code == 401
    assert (await client.get("/me/tams")).status_code == 401
    assert (await client.get("/me/audit")).status_code == 401


# --------------------------------------------------------------------------- #
# Save → GET round-trip; second org sees nothing; permalink untouched.         #
# --------------------------------------------------------------------------- #


@_PG
@pytest.mark.asyncio
async def test_save_then_get_and_tenant_isolation(
    client: AsyncClient, stub_clerk: None, seeded: TAMOutput
) -> None:
    h = seeded.state_hash

    saved = await client.post(
        "/me/tams/save", headers=_BEARER_A, json={"state_hash": h, "title": "My memo"}
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["state_hash"] == h

    # A sees its saved row; B sees none of A's saves.
    a_list = (await client.get("/me/tams", headers=_BEARER_A)).json()
    assert {t["state_hash"] for t in a_list} == {h}
    b_list = (await client.get("/me/tams", headers=_BEARER_B)).json()
    assert b_list == []

    # The global permalink row was NOT turned into a save: there is still exactly
    # one org_id IS NULL row (is_saved false) plus the new tenant row for A.
    rows = await _row_orgs(h)
    assert (None, False) in rows
    assert (_ORG_A, True) in rows
    assert all(org != _ORG_B for org, _ in rows)


@_PG
@pytest.mark.asyncio
async def test_save_unknown_hash_is_404(
    client: AsyncClient, stub_clerk: None, seeded: TAMOutput
) -> None:
    r = await client.post("/me/tams/save", headers=_BEARER_A, json={"state_hash": "deadbeef" * 8})
    assert r.status_code == 404, r.text


# --------------------------------------------------------------------------- #
# /me/audit returns only the caller's events.                                  #
# --------------------------------------------------------------------------- #


@_PG
@pytest.mark.asyncio
async def test_me_audit_returns_only_callers_events(
    client: AsyncClient, stub_clerk: None, seeded: TAMOutput
) -> None:
    await record_audit_safe(
        _USER_A, "build", target="hash-a", meta={"market": "m-a"}, org_id=_ORG_A
    )
    await record_audit_safe(
        _USER_B, "build", target="hash-b", meta={"market": "m-b"}, org_id=_ORG_B
    )

    a_audit = (await client.get("/me/audit", headers=_BEARER_A)).json()
    assert {e["target"] for e in a_audit} == {"hash-a"}
    assert all(e["org_id"] == _ORG_A for e in a_audit)

    b_audit = (await client.get("/me/audit", headers=_BEARER_B)).json()
    assert {e["target"] for e in b_audit} == {"hash-b"}
