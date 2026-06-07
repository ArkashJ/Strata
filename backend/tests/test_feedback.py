"""Phase F — assumption-flagging + feedback loop.

Covers the org-scoped DB layer (record/list/update), the REST surface
(POST/GET/PATCH /feedback + anonymous-401), the failed-query auto-capture on
/resolve, and the two MCP tools (submit_feedback / list_feedback).

The CRUD/RLS paths need a live Postgres migrated to head; skipped when PG is
unreachable so keyless CI stays green. The anonymous-401 checks and the MCP
no-tenant honesty checks do not need Postgres and always run.
"""

from __future__ import annotations

import socket

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api import auth
from strata.api.app import create_app
from strata.api.auth import Principal
from strata.api.clerk_auth import ClerkClaims
from strata.config import settings
from strata.db.feedback import list_feedback, record_feedback, update_feedback
from strata.models.feedback import FeedbackKind, FeedbackStatus, TargetType

_USER_A = "user_fb_a"
_USER_B = "user_fb_b"
_ORG_A = f"clerk_user:{_USER_A}"
_ORG_B = f"clerk_user:{_USER_B}"

_BEARER_A = {"Authorization": "Bearer token.a"}
_BEARER_B = {"Authorization": "Bearer token.b"}


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


async def _cleanup() -> None:
    import asyncpg

    conn = await asyncpg.connect(_asyncpg_dsn())
    try:
        has = await conn.fetchval(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'feedback_events'"
        )
        if not has:
            return
        for org in (_ORG_A, _ORG_B):
            async with conn.transaction():
                await conn.execute("SELECT set_config('app.org_id', $1, true)", org)
                await conn.execute("DELETE FROM feedback_events WHERE org_id = $1", org)
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
async def _clean():
    await _cleanup()
    yield
    await _cleanup()
    from strata.db.engine import engine

    await engine.dispose()


# --------------------------------------------------------------------------- #
# Anonymous → 401 on every verb (no Postgres needed).                         #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_anonymous_is_401_on_every_verb(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "require_auth", False)
    assert (await client.get("/feedback")).status_code == 401
    body = {"kind": "bad_assumption", "target_type": "tam", "body": "x"}
    assert (await client.post("/feedback", json=body)).status_code == 401
    assert (await client.patch("/feedback/1", json={"status": "resolved"})).status_code == 401


# --------------------------------------------------------------------------- #
# DB layer — record / list / update, org-scoped.                              #
# --------------------------------------------------------------------------- #


@_PG
@pytest.mark.asyncio
async def test_db_record_list_update_is_org_scoped(_clean: None) -> None:
    from strata.db.engine import org_session_scope

    async with org_session_scope(_ORG_A) as session:
        ev = await record_feedback(
            session,
            org_id=_ORG_A,
            user_id=_USER_A,
            kind=FeedbackKind.BAD_ASSUMPTION,
            target_type=TargetType.TAM,
            body="adoption rate looks aggressive",
            target_id="abc123",
            severity="warning",
            suggested_value={"adoption": 0.1},
        )
        fid = ev.id

    # A sees its own row; B sees none of A's (RLS isolation).
    async with org_session_scope(_ORG_A) as session:
        a_rows = await list_feedback(session)
        assert {r.id for r in a_rows} == {fid}
        assert a_rows[0].suggested_value == {"adoption": 0.1}
    async with org_session_scope(_ORG_B) as session:
        assert await list_feedback(session) == []

    # B cannot update A's row (invisible → None).
    async with org_session_scope(_ORG_B) as session:
        assert await update_feedback(session, fid, status=FeedbackStatus.RESOLVED) is None

    # A resolves its own row.
    async with org_session_scope(_ORG_A) as session:
        updated = await update_feedback(
            session, fid, status=FeedbackStatus.RESOLVED, resolution="fixed the source"
        )
        assert updated is not None
        assert updated.status is FeedbackStatus.RESOLVED
        assert updated.resolution == "fixed the source"


@_PG
@pytest.mark.asyncio
async def test_db_list_filters_by_status_and_target(_clean: None) -> None:
    from strata.db.engine import org_session_scope

    async with org_session_scope(_ORG_A) as session:
        await record_feedback(
            session,
            org_id=_ORG_A,
            user_id=_USER_A,
            kind=FeedbackKind.MISSING_DATA,
            target_type=TargetType.QUERY,
            body="no data for query",
        )
        await record_feedback(
            session,
            org_id=_ORG_A,
            user_id=_USER_A,
            kind=FeedbackKind.PRIMITIVE_CORRECTION,
            target_type=TargetType.PRIMITIVE,
            body="wrong value",
            status=FeedbackStatus.TRIAGED,
        )
    async with org_session_scope(_ORG_A) as session:
        open_rows = await list_feedback(session, status=FeedbackStatus.OPEN)
        assert {r.target_type for r in open_rows} == {TargetType.QUERY}
        prim_rows = await list_feedback(session, target_type=TargetType.PRIMITIVE)
        assert len(prim_rows) == 1
        assert prim_rows[0].status is FeedbackStatus.TRIAGED


# --------------------------------------------------------------------------- #
# REST surface — POST / GET / PATCH.                                          #
# --------------------------------------------------------------------------- #


@_PG
@pytest.mark.asyncio
async def test_rest_submit_list_resolve(
    client: AsyncClient, stub_clerk: None, _clean: None
) -> None:
    created = await client.post(
        "/feedback",
        headers=_BEARER_A,
        json={
            "kind": "bad_assumption",
            "target_type": "tam",
            "body": "adoption looks aggressive",
            "target_id": "hash123",
        },
    )
    assert created.status_code == 201, created.text
    fid = created.json()["id"]
    assert created.json()["org_id"] == _ORG_A
    assert created.json()["status"] == "open"

    # A lists its own; B sees none.
    a_list = (await client.get("/feedback", headers=_BEARER_A)).json()
    assert {r["id"] for r in a_list} == {fid}
    assert (await client.get("/feedback", headers=_BEARER_B)).json() == []

    # status filter.
    triaged = await client.get("/feedback?status=triaged", headers=_BEARER_A)
    assert triaged.json() == []

    # B cannot resolve A's row (404 under B's scope).
    assert (
        await client.patch(f"/feedback/{fid}", headers=_BEARER_B, json={"status": "resolved"})
    ).status_code == 404

    # A resolves its own.
    patched = await client.patch(
        f"/feedback/{fid}",
        headers=_BEARER_A,
        json={"status": "resolved", "resolution": "fixed"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "resolved"


@_PG
@pytest.mark.asyncio
async def test_rest_bad_enum_is_422(client: AsyncClient, stub_clerk: None, _clean: None) -> None:
    r = await client.post(
        "/feedback",
        headers=_BEARER_A,
        json={"kind": "not_a_kind", "target_type": "tam", "body": "x"},
    )
    assert r.status_code == 422, r.text


# --------------------------------------------------------------------------- #
# Failed-query auto-capture on /resolve.                                      #
# --------------------------------------------------------------------------- #


@_PG
@pytest.mark.asyncio
async def test_failed_query_autocaptures_feedback(
    client: AsyncClient, stub_clerk: None, _clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A resolve dead-end records a failed_query flag under the caller's org."""
    monkeypatch.setenv("STRATA_OFFLINE", "1")
    # A novel, unmatched query with no live/fallback path → terminal "no data".
    r = await client.post(
        "/resolve",
        headers=_BEARER_A,
        json={"query": "wholly unrelated zylophone market 2099"},
    )
    assert r.status_code == 200, r.text
    # Drain the SSE stream so the route reaches its terminal branch.
    _ = r.text

    from strata.db.engine import org_session_scope

    async with org_session_scope(_ORG_A) as session:
        rows = await list_feedback(session)
    assert any(
        r.kind is FeedbackKind.FAILED_QUERY and r.target_type is TargetType.QUERY for r in rows
    ), "a failed resolve must auto-create a failed_query feedback row"


# --------------------------------------------------------------------------- #
# MCP tools — no-tenant honesty (no Postgres), + org-scoped write/read (PG).   #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_mcp_submit_feedback_refuses_without_tenant() -> None:
    """Over local stdio there is no principal → the flag is refused honestly,
    never attributed to a placeholder org."""
    from strata.mcp.feedback_tools import submit_feedback

    out = await submit_feedback(
        None,  # type: ignore[arg-type]
        payload={"kind": "general", "target_type": "query", "body": "x"},
    )
    assert out["error"] == "no_tenant"


@_PG
@pytest.mark.asyncio
async def test_mcp_submit_and_list_feedback_org_scoped(_clean: None) -> None:
    from strata.mcp import context
    from strata.mcp.feedback_tools import list_feedback as mcp_list
    from strata.mcp.feedback_tools import submit_feedback as mcp_submit

    principal = Principal(org_id=_ORG_A, key_id="key_a", scopes=("*",))
    token = context.current_principal.set(principal)
    try:
        out = await mcp_submit(
            None,  # type: ignore[arg-type]
            payload={
                "kind": "bad_assumption",
                "target_type": "primitive",
                "body": "the WTP primitive is stale",
                "target_id": "wtp-2021",
            },
        )
        assert out["submitted"] is True
        assert out["status"] == "open"

        listed = await mcp_list(None, status="open")  # type: ignore[arg-type]
        assert listed["org_id"] == _ORG_A
        assert listed["count"] == 1
        assert listed["feedback"][0]["target_id"] == "wtp-2021"
    finally:
        context.current_principal.reset(token)
