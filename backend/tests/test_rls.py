"""Wave 3 / AC3.6 — Postgres row-level-security isolates tenants.

Requires a live Postgres migrated to head (CI provides one; skipped locally when
unreachable). Sets ``app.org_id`` per transaction and asserts a session scoped to
one org sees zero rows belonging to another.
"""

from __future__ import annotations

import socket

import pytest

from strata.config import settings


def _pg_reachable() -> bool:
    dsn = str(settings.database_url)
    # postgresql+asyncpg://user:pass@host:port/db
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


@pytest.mark.asyncio
async def test_rls_cross_tenant_read_is_zero() -> None:
    import asyncpg  # imported lazily so the module loads without the driver

    conn = await asyncpg.connect(_asyncpg_dsn())
    try:
        exists = await conn.fetchval("SELECT to_regclass('public.tenant_data')")
        if exists is None:
            pytest.skip("tenant_data not migrated (run alembic upgrade head)")

        await conn.execute("DELETE FROM tenant_data WHERE org_id IN ('rls-org-a', 'rls-org-b')")

        # Insert as org A, then org B — each under its own session org.
        async with conn.transaction():
            await conn.execute("SET LOCAL app.org_id = 'rls-org-a'")
            await conn.execute(
                "INSERT INTO tenant_data (org_id, payload) VALUES ('rls-org-a', 'a1')"
            )
        async with conn.transaction():
            await conn.execute("SET LOCAL app.org_id = 'rls-org-b'")
            await conn.execute(
                "INSERT INTO tenant_data (org_id, payload) VALUES ('rls-org-b', 'b1')"
            )

        # Scoped to org A: sees its own row, zero of org B's.
        async with conn.transaction():
            await conn.execute("SET LOCAL app.org_id = 'rls-org-a'")
            visible = await conn.fetch("SELECT org_id FROM tenant_data")
            orgs = {r["org_id"] for r in visible}
        assert orgs == {"rls-org-a"}, f"RLS leaked cross-tenant rows: {orgs}"
    finally:
        await conn.close()
