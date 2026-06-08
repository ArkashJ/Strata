"""MCP trace-capture (Direction 1) — the server-side tool-call tracer.

Non-DB tests (the gate is off by default, capture never breaks a call, the
reasoning tool's no-tenant refusal) run anywhere.  The capture/RLS/retention
paths need a live Postgres migrated to head; skipped when PG is unreachable,
mirroring the sourcing-gap + feedback suites exactly.

Acceptance criteria covered:
  AC-1.4  record_session_reasoning stitches reasoning onto a session row;
          refuses no_tenant over stdio (no principal).
  AC-1.5  off-by-default (no rows when trace_capture_enabled=False);
          a raising trace write NEVER breaks the tool call.
  AC-1.6  org-scoped RLS isolation; admin_session_scope sees every org.
"""

from __future__ import annotations

import socket
from typing import Any

import pytest

from strata.api.auth import Principal
from strata.config import settings
from strata.models.trace import TraceStatus

_TENANT_A = "clerk_user:trace_a"
_TENANT_B = "clerk_user:trace_b"
_ADMIN_ORG = "clerk_org:strata-ops"


# --------------------------------------------------------------------------- #
# Reasoning tool gate — no DB (AC-1.4).                                        #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_reasoning_no_tenant_over_stdio() -> None:
    """Over stdio there is no principal → the [WRITE] tool refuses honestly,
    exactly like report_sourcing_gap (the two guards are kept identical)."""
    from strata.mcp.trace_tools import record_session_reasoning

    out = await record_session_reasoning(
        None,  # type: ignore[arg-type]
        payload={"session_id": "s1", "reasoning": "did a thing"},
    )
    assert out["error"] == "no_tenant"


@pytest.mark.asyncio
async def test_reasoning_rejects_empty_and_bad_outcome(monkeypatch: pytest.MonkeyPatch) -> None:
    """With a principal set, the tool validates its payload before any DB work."""
    from strata.mcp import context
    from strata.mcp.trace_tools import record_session_reasoning

    token = context.current_principal.set(Principal(org_id=_TENANT_A, key_id="k", scopes=("*",)))
    try:
        empty = await record_session_reasoning(
            None,  # type: ignore[arg-type]
            payload={"session_id": "s1", "reasoning": "   "},
        )
        assert empty["error"] == "empty_reasoning"

        bad = await record_session_reasoning(
            None,  # type: ignore[arg-type]
            payload={"session_id": "s1", "reasoning": "ok", "outcome": "not-a-valid-tag"},
        )
        assert bad["error"] == "invalid_outcome"

        # No session_id and no active trace session → honest no_session error.
        no_sess = await record_session_reasoning(
            None,  # type: ignore[arg-type]
            payload={"reasoning": "ok"},
        )
        assert no_sess["error"] == "no_session"
    finally:
        context.current_principal.reset(token)


# --------------------------------------------------------------------------- #
# Off-by-default + never-breaks-the-call — no DB (AC-1.5).                     #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_capture_off_by_default_writes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """When trace_capture_enabled is False, _trace_call returns before importing
    or touching the DB — record_trace_safe must never even be reached."""
    from strata.mcp import server

    monkeypatch.setattr(settings, "trace_capture_enabled", False)

    reached = False

    async def _boom(**_kwargs: Any) -> None:
        nonlocal reached
        reached = True

    # Patch the underlying writer; the gate should short-circuit before it.
    monkeypatch.setattr("strata.db.traces.record_trace_safe", _boom)

    await server._trace_call("whoami", {}, "ok", {"ok": True}, 3)  # pyright: ignore[reportPrivateUsage]
    assert reached is False, "gate off → the trace writer must not be invoked"


@pytest.mark.asyncio
async def test_capture_failure_never_breaks_the_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-1.5: a trace write that raises is swallowed by _trace_call's bare
    except — it must not propagate.  We drive _trace_call directly (the server's
    _call_tool awaits it after returning the real result) and assert it returns
    None cleanly even though the writer raised."""
    from strata.mcp import context, server

    monkeypatch.setattr(settings, "trace_capture_enabled", True)

    async def _raise(**_kwargs: Any) -> None:
        raise RuntimeError("simulated trace-write failure")

    monkeypatch.setattr("strata.db.traces.record_trace_safe", _raise)

    ptok = context.current_principal.set(Principal(org_id=_TENANT_A, key_id="k", scopes=("*",)))
    try:
        # If the exception leaked, this await would raise; it must not.
        result = await server._trace_call(  # pyright: ignore[reportPrivateUsage]
            "whoami", {}, "ok", {"ok": True}, 3
        )
        assert result is None
    finally:
        context.current_principal.reset(ptok)


@pytest.mark.asyncio
async def test_call_tool_returns_result_when_trace_write_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end AC-1.5: dispatch a real tool through the server's _call_tool
    with capture ON but the trace writer rigged to raise — the call STILL returns
    its normal CallToolResult.  This proves capture failure cannot break dispatch."""
    from pathlib import Path

    import mcp.types as types

    from strata.loader import load_data_dir
    from strata.mcp import context
    from strata.mcp.server import build_server
    from strata.registry import Registry

    monkeypatch.setattr(settings, "trace_capture_enabled", True)

    async def _raise(**_kwargs: Any) -> None:
        raise RuntimeError("simulated trace-write failure")

    monkeypatch.setattr("strata.db.traces.record_trace_safe", _raise)

    data = Path(__file__).resolve().parents[2] / "data"
    reg = Registry.from_loaded(load_data_dir(data))
    server = build_server(lambda: reg)

    # Reach the registered tools/call handler (the SDK stores it on the server).
    handler = server.request_handlers[types.CallToolRequest]
    req = types.CallToolRequest(
        method="tools/call",
        params=types.CallToolRequestParams(name="list_frameworks", arguments={}),
    )

    ptok = context.current_principal.set(Principal(org_id=_TENANT_A, key_id="k", scopes=("*",)))
    try:
        resp = await handler(req)
    finally:
        context.current_principal.reset(ptok)

    # The dispatch succeeded and returned a real result despite the raising tracer.
    assert isinstance(resp.root, types.CallToolResult)
    assert resp.root.isError is False


# --------------------------------------------------------------------------- #
# DB-backed: capture writes rows, RLS isolation, retention, truncation.       #
# --------------------------------------------------------------------------- #


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
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'tool_traces'"
        )
        if not has:
            return
        for org in (_TENANT_A, _TENANT_B):
            async with conn.transaction():
                await conn.execute("SELECT set_config('app.org_id', $1, true)", org)
                await conn.execute("DELETE FROM tool_traces WHERE org_id = $1", org)
                await conn.execute("DELETE FROM trace_sessions WHERE org_id = $1", org)
    finally:
        await conn.close()


@pytest.fixture
async def _clean() -> Any:  # pyright: ignore[reportUnusedFunction]
    await _cleanup()
    yield
    await _cleanup()
    from strata.db.engine import engine

    await engine.dispose()


@_PG
@pytest.mark.asyncio
async def test_capture_writes_one_row_per_call_and_bumps_count(_clean: None) -> None:
    """Each dispatched call writes one tool_traces row (correct tool/status/hash)
    and the trace_sessions row's call_count increments."""
    from strata.db.engine import org_session_scope
    from strata.db.traces import get_session_calls, list_sessions, record_trace_safe

    await record_trace_safe(
        org_id=_TENANT_A,
        session_id="cap-sess",
        tool="whoami",
        args={},
        result={"ok": True},
        status=TraceStatus.OK,
        duration_ms=3,
    )
    await record_trace_safe(
        org_id=_TENANT_A,
        session_id="cap-sess",
        tool="list_frameworks",
        args={},
        result={"count": 25},
        status=TraceStatus.OK,
        duration_ms=7,
    )

    async with org_session_scope(_TENANT_A) as s:
        sessions = await list_sessions(s)
        assert len(sessions) == 1
        assert sessions[0].session_id == "cap-sess"
        assert sessions[0].call_count == 2  # bumped once per call

        calls = await get_session_calls(s, session_id="cap-sess")
        assert [c.tool for c in calls] == ["whoami", "list_frameworks"]
        assert [c.seq for c in calls] == [1, 2]
        for c in calls:
            assert c.status is TraceStatus.OK
            assert c.result_sha256, "every captured call carries a non-empty result hash"
            assert len(c.result_sha256) == 64


@_PG
@pytest.mark.asyncio
async def test_error_status_is_captured(_clean: None) -> None:
    """An errored tool call is recorded with status=error + its error_code."""
    from strata.db.engine import org_session_scope
    from strata.db.traces import get_session_calls, record_trace_safe

    await record_trace_safe(
        org_id=_TENANT_A,
        session_id="err-sess",
        tool="get_primitive",
        args={"slug": "nope"},
        result={"error": "not_found"},
        status=TraceStatus.ERROR,
        duration_ms=2,
        error_code="NOT_FOUND",
    )
    async with org_session_scope(_TENANT_A) as s:
        calls = await get_session_calls(s, session_id="err-sess")
        assert len(calls) == 1
        assert calls[0].status is TraceStatus.ERROR
        assert calls[0].error_code == "NOT_FOUND"


@_PG
@pytest.mark.asyncio
async def test_traces_are_org_isolated_admin_sees_all(_clean: None) -> None:
    """AC-1.6: a trace written under org A is invisible to org B; an admin
    session (app.is_admin GUC) sees both.  Mirrors the sourcing-gap RLS test."""
    from strata.db.engine import admin_session_scope, org_session_scope
    from strata.db.traces import admin_list_sessions, list_sessions, record_trace_safe

    await record_trace_safe(
        org_id=_TENANT_A,
        session_id="A-only",
        tool="whoami",
        args={},
        result={"ok": True},
        status=TraceStatus.OK,
        duration_ms=1,
    )
    await record_trace_safe(
        org_id=_TENANT_B,
        session_id="B-only",
        tool="whoami",
        args={},
        result={"ok": True},
        status=TraceStatus.OK,
        duration_ms=1,
    )

    async with org_session_scope(_TENANT_A) as s:
        a_rows = await list_sessions(s)
        a_ids = {r.session_id for r in a_rows}
        assert a_ids == {"A-only"}
        assert "B-only" not in a_ids

    async with org_session_scope(_TENANT_B) as s:
        b_rows = await list_sessions(s)
        b_ids = {r.session_id for r in b_rows}
        assert b_ids == {"B-only"}
        assert "A-only" not in b_ids

    async with admin_session_scope("cli-admin") as s:
        admin_rows = await admin_list_sessions(s)
        admin_ids = {r.session_id for r in admin_rows}
        assert {"A-only", "B-only"} <= admin_ids


@_PG
@pytest.mark.asyncio
async def test_reasoning_stitches_onto_session(_clean: None) -> None:
    """AC-1.4: record_reasoning upserts the session row's reasoning + outcome;
    a second call updates the reasoning while the outcome coalesces (a late ok
    does not overwrite an early error)."""
    from strata.db.engine import org_session_scope
    from strata.db.traces import list_sessions, record_reasoning

    async with org_session_scope(_TENANT_A) as s:
        first = await record_reasoning(
            s,
            org_id=_TENANT_A,
            session_id="reason-sess",
            reasoning="initial plan",
            outcome="error",
        )
        assert first.reasoning == "initial plan"
        assert first.outcome == "error"

    async with org_session_scope(_TENANT_A) as s:
        second = await record_reasoning(
            s,
            org_id=_TENANT_A,
            session_id="reason-sess",
            reasoning="revised plan",
            outcome=None,  # coalesce: keep the earlier non-null outcome
        )
        assert second.reasoning == "revised plan"
        assert second.outcome == "error"

    async with org_session_scope(_TENANT_A) as s:
        rows = await list_sessions(s)
        match = [r for r in rows if r.session_id == "reason-sess"]
        assert len(match) == 1
        assert match[0].reasoning == "revised plan"
        assert match[0].outcome == "error"


@_PG
@pytest.mark.asyncio
async def test_reasoning_tool_full_path_with_principal(_clean: None) -> None:
    """AC-1.4 end-to-end: with a principal set, the MCP tool opens an org scope
    and stitches the reasoning onto the session row."""
    from strata.db.engine import org_session_scope
    from strata.db.traces import list_sessions
    from strata.mcp import context
    from strata.mcp.trace_tools import record_session_reasoning

    token = context.current_principal.set(Principal(org_id=_TENANT_A, key_id="k", scopes=("*",)))
    try:
        out = await record_session_reasoning(
            None,  # type: ignore[arg-type]
            payload={
                "session_id": "tool-reason-sess",
                "reasoning": "sized the market top-down then cross-checked",
                "outcome": "ok",
            },
        )
        assert out["recorded"] is True
        assert out["session_id"] == "tool-reason-sess"
        assert out["outcome"] == "ok"
    finally:
        context.current_principal.reset(token)

    async with org_session_scope(_TENANT_A) as s:
        rows = await list_sessions(s)
        match = [r for r in rows if r.session_id == "tool-reason-sess"]
        assert len(match) == 1
        assert (match[0].reasoning or "").startswith("sized the market")


@_PG
@pytest.mark.asyncio
async def test_retention_prunes_oldest_sessions(
    _clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Writing more than trace_max_sessions sessions prunes the oldest, keeping
    only the N most-recently-active (FIFO cap, D3)."""
    from strata.db.engine import org_session_scope
    from strata.db.traces import list_sessions, record_trace_safe

    monkeypatch.setattr(settings, "trace_max_sessions", 2)

    # Three distinct sessions, written oldest-first.
    for i in range(3):
        await record_trace_safe(
            org_id=_TENANT_A,
            session_id=f"sess-{i}",
            tool="whoami",
            args={},
            result={"ok": True},
            status=TraceStatus.OK,
            duration_ms=1,
        )

    async with org_session_scope(_TENANT_A) as s:
        rows = await list_sessions(s)
        ids = {r.session_id for r in rows}
        # Only the 2 most-recent survive; the oldest (sess-0) was pruned.
        assert len(rows) == 2
        assert "sess-0" not in ids
        assert {"sess-1", "sess-2"} == ids


@_PG
@pytest.mark.asyncio
async def test_oversized_field_is_truncated_and_flagged(
    _clean: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A field exceeding trace_max_field_bytes is replaced with a sentinel and
    the *_truncated flag is set so 'traces show' is honest about the drop."""
    from strata.db.engine import org_session_scope
    from strata.db.traces import get_session_calls, record_trace_safe

    # Tiny cap so a modest args payload trips truncation.
    monkeypatch.setattr(settings, "trace_max_field_bytes", 1024)

    big_args = {"blob": "x" * 5000}  # well over 1 KB once JSON-encoded
    await record_trace_safe(
        org_id=_TENANT_A,
        session_id="trunc-sess",
        tool="whoami",
        args=big_args,
        result={"ok": True},
        status=TraceStatus.OK,
        duration_ms=1,
    )

    async with org_session_scope(_TENANT_A) as s:
        calls = await get_session_calls(s, session_id="trunc-sess")
        assert len(calls) == 1
        assert calls[0].args_truncated is True
        # The stored args are the sentinel, not the raw blob.
        assert calls[0].args.get("__truncated__") is True
        # The small result stayed intact.
        assert calls[0].result_truncated is False
