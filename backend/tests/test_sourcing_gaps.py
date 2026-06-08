"""Sourcing-gap queue (Pillar B1) — measure + rank the misses.

Non-DB tests (dedup-key normalization, the machine-readable resolve_market miss,
the tool gate envelopes) run anywhere. The CRUD/RLS paths (de-dup upsert, demand
ranking, cross-org admin) need a live Postgres at head; skipped when PG is
unreachable, like the feedback suite.
"""

from __future__ import annotations

import socket
from typing import Any

import pytest

from strata.api.auth import Principal
from strata.config import settings
from strata.db.sourcing_gaps import make_dedup_key
from strata.models.sourcing_gap import GapSource, GapStatus

_TENANT_A = "clerk_user:gap_a"
_TENANT_B = "clerk_user:gap_b"
_ADMIN_ORG = "clerk_org:strata-ops"


# --------------------------------------------------------------------------- #
# Dedup-key normalization — pure.                                             #
# --------------------------------------------------------------------------- #


def test_dedup_key_collapses_query_whitespace_and_case() -> None:
    a = make_dedup_key(query_text="  Market  Research   TOOLS ", resource_target=None)
    b = make_dedup_key(query_text="market research tools", resource_target=None)
    assert a == b == "query:market research tools"


def test_dedup_key_prefers_resource_target() -> None:
    # A named target wins so many phrasings of the same gap collapse to one row.
    k = make_dedup_key(query_text="whatever phrasing", resource_target="BLS:Displacement")
    assert k == "target:bls:displacement"


# --------------------------------------------------------------------------- #
# resolve_market miss is machine-readable (AC-B2.1) — pure.                    #
# --------------------------------------------------------------------------- #


def test_resolve_market_miss_is_flagged_unsourced() -> None:
    from pathlib import Path

    from strata.loader import load_data_dir
    from strata.mcp.tools import resolve_market
    from strata.registry import Registry

    reg = Registry.from_loaded(load_data_dir(Path(__file__).resolve().parents[2] / "data"))
    out = resolve_market(reg, query="zzqx nonexistent market xyzzy qwerty")
    assert out["matched"] is False
    assert out["unsourced"] is True
    assert out["independence_score"] == 0.0
    # It tells the agent exactly how to turn the miss into ranked demand.
    assert out["next_action"]["tool"] == "report_sourcing_gap"
    assert out["next_action"]["payload"]["source"] == "resolve_miss"


# --------------------------------------------------------------------------- #
# Tool gate envelopes — no DB.                                                #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_report_gap_no_tenant_over_stdio() -> None:
    from strata.mcp.sourcing_gap_tools import report_sourcing_gap

    out = await report_sourcing_gap(None, payload={"query_text": "x"})  # type: ignore[arg-type]
    assert out["error"] == "no_tenant"


@pytest.mark.asyncio
async def test_report_gap_requires_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    from strata.mcp import context
    from strata.mcp.sourcing_gap_tools import report_sourcing_gap

    token = context.current_principal.set(Principal(org_id=_TENANT_A, key_id="k", scopes=("*",)))
    try:
        out = await report_sourcing_gap(None, payload={})  # type: ignore[arg-type]
        assert out["error"] == "empty_gap"
    finally:
        context.current_principal.reset(token)


@pytest.mark.asyncio
async def test_list_gaps_scope_all_is_admin_only(monkeypatch: pytest.MonkeyPatch) -> None:
    from strata.mcp import context
    from strata.mcp.sourcing_gap_tools import list_sourcing_gaps

    monkeypatch.setattr(settings, "admin_orgs", _ADMIN_ORG)
    token = context.current_principal.set(Principal(org_id=_TENANT_A, key_id="k", scopes=("*",)))
    try:
        out = await list_sourcing_gaps(None, scope="all")  # type: ignore[arg-type]
        assert out["error"] == "forbidden"
    finally:
        context.current_principal.reset(token)


# --------------------------------------------------------------------------- #
# DB-backed: de-dup, ranking, cross-org admin.                                #
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
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'sourcing_gaps'"
        )
        if not has:
            return
        for org in (_TENANT_A, _TENANT_B):
            async with conn.transaction():
                await conn.execute("SELECT set_config('app.org_id', $1, true)", org)
                await conn.execute("DELETE FROM sourcing_gaps WHERE org_id = $1", org)
    finally:
        await conn.close()


@pytest.fixture
async def _clean() -> Any:
    await _cleanup()
    yield
    await _cleanup()


@_PG
@pytest.mark.asyncio
async def test_record_gap_dedups_and_counts(_clean: None) -> None:
    """Two reports of the same miss collapse to one row with hit_count=2."""
    from strata.db.engine import org_session_scope
    from strata.db.sourcing_gaps import list_gaps, record_gap

    async with org_session_scope(_TENANT_A) as s:
        g1 = await record_gap(
            s, org_id=_TENANT_A, source=GapSource.RESOLVE_MISS, query_text="market research tools"
        )
        assert g1.hit_count == 1
    async with org_session_scope(_TENANT_A) as s:
        g2 = await record_gap(
            s, org_id=_TENANT_A, source=GapSource.RESOLVE_MISS, query_text="Market Research Tools "
        )
        assert g2.hit_count == 2  # same dedup_key → bumped, not duplicated

    async with org_session_scope(_TENANT_A) as s:
        rows = await list_gaps(s, org_id=_TENANT_A)
        assert len(rows) == 1
        assert rows[0].hit_count == 2


@_PG
@pytest.mark.asyncio
async def test_gaps_rank_by_demand_and_isolate(_clean: None) -> None:
    """The queue is ranked by hit_count desc; a tenant sees only its own gaps."""
    from strata.db.engine import org_session_scope
    from strata.db.sourcing_gaps import list_gaps, record_gap

    async with org_session_scope(_TENANT_A) as s:
        await record_gap(s, org_id=_TENANT_A, source=GapSource.MANUAL, query_text="low demand")
        for _ in range(3):
            await record_gap(s, org_id=_TENANT_A, source=GapSource.MANUAL, query_text="hot market")
    async with org_session_scope(_TENANT_B) as s:
        await record_gap(s, org_id=_TENANT_B, source=GapSource.MANUAL, query_text="B only")

    async with org_session_scope(_TENANT_A) as s:
        rows = await list_gaps(s, org_id=_TENANT_A)
        assert [r.query_text for r in rows][0] == "hot market"  # most-demanded first
        assert all(r.org_id == _TENANT_A for r in rows)
        assert "B only" not in {r.query_text for r in rows}


@_PG
@pytest.mark.asyncio
async def test_list_gaps_filters_by_arg_even_if_rls_bypassed(_clean: None) -> None:
    """Defense-in-depth: the explicit ``org_id`` filter isolates even if the session
    could see other orgs' rows (the superuser/BYPASSRLS scenario). We simulate that
    by querying through an ADMIN session (which CAN see every org) but passing
    ``list_gaps``'s own ``org_id`` filter — only the named org's rows come back."""
    from strata.db.engine import admin_session_scope, org_session_scope
    from strata.db.sourcing_gaps import list_gaps, record_gap

    async with org_session_scope(_TENANT_A) as s:
        await record_gap(s, org_id=_TENANT_A, source=GapSource.MANUAL, query_text="A gap")
    async with org_session_scope(_TENANT_B) as s:
        await record_gap(s, org_id=_TENANT_B, source=GapSource.MANUAL, query_text="B gap")

    # Admin session sees every org (RLS open) — but list_gaps' org_id predicate
    # still restricts to _TENANT_A. Without the explicit filter this would leak B.
    async with admin_session_scope(_TENANT_A) as s:
        rows = await list_gaps(s, org_id=_TENANT_A)
        assert {r.org_id for r in rows} == {_TENANT_A}
        assert "B gap" not in {r.query_text for r in rows}


@_PG
@pytest.mark.asyncio
async def test_record_gap_refuses_org_mismatch(_clean: None) -> None:
    """A write whose org_id ≠ the session's app.org_id is refused (so a spoofed
    org can't be persisted even under a BYPASSRLS role)."""
    from strata.db.engine import OrgScopeMismatchError, org_session_scope
    from strata.db.sourcing_gaps import record_gap

    async with org_session_scope(_TENANT_A) as s:
        with pytest.raises(OrgScopeMismatchError):
            await record_gap(s, org_id=_TENANT_B, source=GapSource.MANUAL, query_text="spoofed")


@_PG
@pytest.mark.asyncio
async def test_admin_sees_every_org_gap_and_can_mark_sourced(_clean: None) -> None:
    from strata.db.engine import admin_session_scope, org_session_scope
    from strata.db.sourcing_gaps import admin_list_gaps, list_gaps, mark_gap_sourced, record_gap

    async with org_session_scope(_TENANT_A) as s:
        ga = await record_gap(s, org_id=_TENANT_A, source=GapSource.MANUAL, query_text="A market")
        gid = ga.id
    async with org_session_scope(_TENANT_B) as s:
        await record_gap(s, org_id=_TENANT_B, source=GapSource.MANUAL, query_text="B market")

    async with admin_session_scope("cli-admin") as s:
        rows = await admin_list_gaps(s)
        assert {_TENANT_A, _TENANT_B} <= {r.org_id for r in rows}

    # Closing a gap (its number got sourced) flips status under its own tenant.
    async with org_session_scope(_TENANT_A) as s:
        closed = await mark_gap_sourced(s, gid, org_id=_TENANT_A, note="sourced via census")
        assert closed is not None and closed.status is GapStatus.SOURCED
    async with org_session_scope(_TENANT_A) as s:
        open_rows = await list_gaps(s, org_id=_TENANT_A, status=GapStatus.OPEN)
        assert gid not in {r.id for r in open_rows}
