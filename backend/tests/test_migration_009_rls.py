"""Migration 009 — strict org-scoped RLS on ``user_primitives`` / ``boards`` / ``board_items``.

U4: three durable per-user-workspace tables that are NEVER world-readable. Unlike
migration 008's dual-purpose ``tam_outputs`` policy, these fail CLOSED like
migration 006 — an anonymous session (``app.org_id`` unset) sees zero rows, and
tenant A can never read tenant B's rows. ``(org_id, slug)`` is unique on
``user_primitives`` so a tenant can't shadow its own slug, while two tenants may
each own the same slug.

Requires a live Postgres migrated to head (skipped locally when unreachable).
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


async def _require_009(conn) -> None:
    """Skip if 009 hasn't been applied (table absent) — keeps the suite honest
    when run against an un-migrated DB rather than reporting a false failure."""
    has_table = await conn.fetchval(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'user_primitives'"
    )
    if not has_table:
        pytest.skip("migration 009 not applied (run alembic upgrade head)")


def _payload() -> str:
    return '{"k": "v"}'


async def _cleanup(conn) -> None:
    """Remove this module's test rows under each org scope so the tables are left
    clean (RLS means a DELETE only touches the current scope's rows)."""
    for org in (ORG_A, ORG_B):
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", org)
            await conn.execute("DELETE FROM board_items WHERE org_id = $1", org)
            await conn.execute("DELETE FROM boards WHERE org_id = $1", org)
            await conn.execute("DELETE FROM user_primitives WHERE org_id = $1", org)


@pytest.mark.asyncio
async def test_user_primitives_tenant_isolation() -> None:
    """Tenant A sees only its own; tenant B sees none of A's; anon sees zero."""
    conn = await _connect()
    try:
        await _require_009(conn)

        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", ORG_A)
            await conn.execute(
                "INSERT INTO user_primitives (org_id, slug, payload) VALUES ($1, 'p-a', $2::jsonb)",
                ORG_A,
                _payload(),
            )
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", ORG_B)
            await conn.execute(
                "INSERT INTO user_primitives (org_id, slug, payload) VALUES ($1, 'p-b', $2::jsonb)",
                ORG_B,
                _payload(),
            )

        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", ORG_A)
            a_orgs = {r["org_id"] for r in await conn.fetch("SELECT org_id FROM user_primitives")}
        assert a_orgs == {ORG_A}, f"user_primitives leaked across tenants: {a_orgs}"

        # Anonymous (unset app.org_id) sees ZERO rows — fails closed.
        async with conn.transaction():
            anon = await conn.fetch("SELECT org_id FROM user_primitives")
        assert anon == [], f"user_primitives visible to anonymous (should fail closed): {anon}"
    finally:
        await _cleanup(conn)
        await conn.close()


@pytest.mark.asyncio
async def test_user_primitives_org_slug_uniqueness() -> None:
    """``(org_id, slug)`` is unique within a tenant; same slug allowed cross-org."""
    import asyncpg

    conn = await _connect()
    try:
        await _require_009(conn)

        # Tenant A owns slug 's-shared'.
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", ORG_A)
            await conn.execute(
                "INSERT INTO user_primitives (org_id, slug, payload) "
                "VALUES ($1, 's-shared', $2::jsonb)",
                ORG_A,
                _payload(),
            )
        # Same (org, slug) for A — conflict.
        with pytest.raises(asyncpg.UniqueViolationError):
            async with conn.transaction():
                await conn.execute("SELECT set_config('app.org_id', $1, true)", ORG_A)
                await conn.execute(
                    "INSERT INTO user_primitives (org_id, slug, payload) "
                    "VALUES ($1, 's-shared', $2::jsonb)",
                    ORG_A,
                    _payload(),
                )
        # Tenant B may own the SAME slug — different (org, slug) pair.
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", ORG_B)
            await conn.execute(
                "INSERT INTO user_primitives (org_id, slug, payload) "
                "VALUES ($1, 's-shared', $2::jsonb)",
                ORG_B,
                _payload(),
            )
    finally:
        await _cleanup(conn)
        await conn.close()


@pytest.mark.asyncio
async def test_boards_and_board_items_tenant_isolation() -> None:
    """``boards`` + ``board_items`` fail closed and isolate per tenant."""
    conn = await _connect()
    try:
        await _require_009(conn)

        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", ORG_A)
            board_a = await conn.fetchval(
                "INSERT INTO boards (org_id, title) VALUES ($1, 'A board') RETURNING id",
                ORG_A,
            )
            await conn.execute(
                "INSERT INTO board_items (board_id, org_id, kind, ref) "
                "VALUES ($1, $2, 'tam', 'h-a')",
                board_a,
                ORG_A,
            )
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", ORG_B)
            board_b = await conn.fetchval(
                "INSERT INTO boards (org_id, title) VALUES ($1, 'B board') RETURNING id",
                ORG_B,
            )
            await conn.execute(
                "INSERT INTO board_items (board_id, org_id, kind, ref) "
                "VALUES ($1, $2, 'tam', 'h-b')",
                board_b,
                ORG_B,
            )

        # Tenant A sees only its own board + item.
        async with conn.transaction():
            await conn.execute("SELECT set_config('app.org_id', $1, true)", ORG_A)
            b_orgs = {r["org_id"] for r in await conn.fetch("SELECT org_id FROM boards")}
            i_orgs = {r["org_id"] for r in await conn.fetch("SELECT org_id FROM board_items")}
        assert b_orgs == {ORG_A}, f"boards leaked across tenants: {b_orgs}"
        assert i_orgs == {ORG_A}, f"board_items leaked across tenants: {i_orgs}"

        # Anonymous sees ZERO rows on both — fails closed.
        async with conn.transaction():
            anon_boards = await conn.fetch("SELECT id FROM boards")
            anon_items = await conn.fetch("SELECT id FROM board_items")
        assert anon_boards == [], f"boards visible to anonymous: {anon_boards}"
        assert anon_items == [], f"board_items visible to anonymous: {anon_items}"
    finally:
        await _cleanup(conn)
        await conn.close()
