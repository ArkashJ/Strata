"""Migration 008 — dual-purpose RLS on ``tam_outputs`` + strict RLS on ``audit_events``.

The single highest-correctness-risk decision in PR 1 (KTD-1): ``tam_outputs`` must
serve BOTH anonymous content-addressed permalinks (``org_id IS NULL``,
world-readable) AND tenant saves (``org_id = <tenant>``, isolated), while
``audit_events`` fails CLOSED like migration 006.

Requires a live Postgres migrated to head (skipped locally when unreachable).
These tests are written test-first: against a pre-008 head they fail because the
``org_id`` column / dual-purpose policy do not yet exist.
"""

from __future__ import annotations

import socket

import pytest

from strata.config import settings

ANON = None
ORG_A = "clerk_user:a"
ORG_B = "clerk_user:b"


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


async def _connect():
    import asyncpg

    return await asyncpg.connect(_asyncpg_dsn())


async def _require_008(conn) -> None:
    """Skip if 008 hasn't been applied (column absent) — keeps the suite honest
    when run against an un-migrated DB rather than reporting a false failure."""
    has_col = await conn.fetchval(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'tam_outputs' AND column_name = 'org_id'"
    )
    if not has_col:
        pytest.skip("migration 008 not applied (run alembic upgrade head)")


def _payload() -> str:
    return '{"k": "v"}'


async def _cleanup(conn) -> None:
    """Remove this module's test rows under their org scope so the table is left
    clean — otherwise a same-hash global+tenant pair would block the downgrade's
    single-column UNIQUE re-creation (a test-data artifact, not a DDL bug)."""
    for org in (ORG_A, ORG_B):
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", org)
            await conn.execute("DELETE FROM tam_outputs WHERE org_id = $1", org)
            await conn.execute("DELETE FROM audit_events WHERE org_id = $1", org)
    await conn.execute(
        "DELETE FROM tam_outputs WHERE org_id IS NULL "
        "AND state_hash IN ('h-global', 'h-a', 'h-b', 'h-shared')"
    )


@pytest.mark.asyncio
async def test_tam_outputs_dual_purpose_rls() -> None:
    """Anon writes/reads globals; tenant A sees globals + own; tenant B sees none of A's."""
    conn = await _connect()
    try:
        await _require_008(conn)
        await conn.execute(
            "DELETE FROM tam_outputs WHERE state_hash IN "
            "('h-global', 'h-a', 'h-b') OR org_id IN ($1, $2)",
            ORG_A,
            ORG_B,
        )

        # Anonymous (app.org_id UNSET): writes + reads a global row.
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO tam_outputs (state_hash, payload, org_id) "
                "VALUES ('h-global', $1::jsonb, NULL)",
                _payload(),
            )
        async with conn.transaction():
            anon_rows = await conn.fetch("SELECT state_hash, org_id FROM tam_outputs")
            anon_hashes = {r["state_hash"] for r in anon_rows}
        assert "h-global" in anon_hashes
        # Anonymous cannot see a tenant row even after one exists (insert it as A).
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", ORG_A)
            await conn.execute(
                "INSERT INTO tam_outputs (state_hash, payload, org_id) "
                "VALUES ('h-a', $1::jsonb, $2)",
                _payload(),
                ORG_A,
            )
        async with conn.transaction():
            anon_orgs = {r["org_id"] for r in await conn.fetch("SELECT org_id FROM tam_outputs")}
        assert ORG_A not in anon_orgs, f"anon leaked tenant rows: {anon_orgs}"
        assert None in anon_orgs, "anon should still see global permalink rows"

        # Tenant B writes its own; sees globals + own, ZERO of A's.
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", ORG_B)
            await conn.execute(
                "INSERT INTO tam_outputs (state_hash, payload, org_id) "
                "VALUES ('h-b', $1::jsonb, $2)",
                _payload(),
                ORG_B,
            )
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", ORG_B)
            b_orgs = {r["org_id"] for r in await conn.fetch("SELECT org_id FROM tam_outputs")}
        assert ORG_A not in b_orgs, f"tenant B leaked tenant A rows: {b_orgs}"
        assert ORG_B in b_orgs
        assert None in b_orgs, "tenant should still see global permalinks"

        # Tenant A sees globals + own, ZERO of B's.
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", ORG_A)
            a_orgs = {r["org_id"] for r in await conn.fetch("SELECT org_id FROM tam_outputs")}
        assert ORG_B not in a_orgs, f"tenant A leaked tenant B rows: {a_orgs}"
        assert {None, ORG_A} <= a_orgs
    finally:
        await _cleanup(conn)
        await conn.close()


@pytest.mark.asyncio
async def test_tam_outputs_same_state_hash_global_and_per_tenant() -> None:
    """KTD-2: the same content hash can exist once global AND once per tenant
    (partial unique indexes), but a second GLOBAL insert of that hash conflicts."""
    conn = await _connect()
    try:
        await _require_008(conn)
        await conn.execute(
            "DELETE FROM tam_outputs WHERE state_hash = 'h-shared' OR org_id IN ($1, $2)",
            ORG_A,
            ORG_B,
        )

        # One global row.
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO tam_outputs (state_hash, payload, org_id) "
                "VALUES ('h-shared', $1::jsonb, NULL)",
                _payload(),
            )
        # Same hash, tenant A — allowed (different partial index).
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", ORG_A)
            await conn.execute(
                "INSERT INTO tam_outputs (state_hash, payload, org_id) "
                "VALUES ('h-shared', $1::jsonb, $2)",
                _payload(),
                ORG_A,
            )
        # Same hash, tenant B — also allowed.
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", ORG_B)
            await conn.execute(
                "INSERT INTO tam_outputs (state_hash, payload, org_id) "
                "VALUES ('h-shared', $1::jsonb, $2)",
                _payload(),
                ORG_B,
            )

        # A second GLOBAL insert of the same hash conflicts (idempotent permalink).
        import asyncpg

        with pytest.raises(asyncpg.UniqueViolationError):
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO tam_outputs (state_hash, payload, org_id) "
                    "VALUES ('h-shared', $1::jsonb, NULL)",
                    _payload(),
                )
        # A second insert of the same hash for tenant A also conflicts.
        with pytest.raises(asyncpg.UniqueViolationError):
            async with conn.transaction():
                await conn.execute("SELECT set_config('app.org_id', $1, true)", ORG_A)
                await conn.execute(
                    "INSERT INTO tam_outputs (state_hash, payload, org_id) "
                    "VALUES ('h-shared', $1::jsonb, $2)",
                    _payload(),
                    ORG_A,
                )
    finally:
        await _cleanup(conn)
        await conn.close()


@pytest.mark.asyncio
async def test_audit_events_strict_closed_rls() -> None:
    """``audit_events`` is never world-readable: closed policy (no IS NULL clause)."""
    conn = await _connect()
    try:
        has_col = await conn.fetchval(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'audit_events' AND column_name = 'org_id'"
        )
        if not has_col:
            pytest.skip("migration 008 not applied (run alembic upgrade head)")

        await conn.execute("DELETE FROM audit_events WHERE org_id IN ($1, $2)", ORG_A, ORG_B)

        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", ORG_A)
            await conn.execute(
                "INSERT INTO audit_events (action, org_id) VALUES ('build', $1)", ORG_A
            )
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", ORG_B)
            await conn.execute(
                "INSERT INTO audit_events (action, org_id) VALUES ('build', $1)", ORG_B
            )

        # Tenant A sees only its own — and crucially NOT global/NULL rows.
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", ORG_A)
            a_orgs = {r["org_id"] for r in await conn.fetch("SELECT org_id FROM audit_events")}
        assert a_orgs == {ORG_A}, f"audit_events leaked or world-readable: {a_orgs}"

        # Anonymous (unset app.org_id) sees ZERO rows — fails closed.
        async with conn.transaction():
            anon = await conn.fetch("SELECT org_id FROM audit_events")
        assert anon == [], f"audit_events visible to anonymous (should fail closed): {anon}"
    finally:
        await _cleanup(conn)
        await conn.close()
