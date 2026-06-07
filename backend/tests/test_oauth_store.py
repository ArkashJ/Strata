"""OAuth persistence (``db/oauth.py``) — round-trip, single-use, rotation, cross-tenant.

Requires a live Postgres migrated to head (skipped locally when unreachable),
since the single-use code consume and refresh-rotation guarantees are enforced
by atomic ``UPDATE ... WHERE ... RETURNING`` — they can't be proven against a
mock. A NullPool engine avoids pytest-asyncio cross-event-loop pool reuse.
"""

from __future__ import annotations

import socket
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from strata.config import settings
from strata.db import oauth


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

_RES = "https://api.example.test/mcp/"


@pytest_asyncio.fixture
async def maker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    eng = create_async_engine(str(settings.database_url), poolclass=NullPool)
    # Tables must exist (migrated to head). Skip if not.
    async with eng.connect() as conn:
        exists = await conn.scalar(text("SELECT to_regclass('public.oauth_tokens')"))
    if exists is None:
        await eng.dispose()
        pytest.skip("oauth tables not migrated (run alembic upgrade head)")
    try:
        yield async_sessionmaker(bind=eng, expire_on_commit=False)
    finally:
        await eng.dispose()


async def _mk_code(
    session: AsyncSession, *, org_id: str = "org-a", client_id: str = "client_test"
) -> str:
    return await oauth.create_auth_code(
        session,
        client_id=client_id,
        redirect_uri="https://claude.ai/api/mcp/auth_callback",
        code_challenge="abc123",
        code_challenge_method="S256",
        resource=_RES,
        org_id=org_id,
        user_id="user_1",
        scope="*",
        ttl_seconds=300,
    )


@pytest.mark.asyncio
async def test_register_and_get_client(maker: async_sessionmaker[AsyncSession]) -> None:
    async with maker() as s, s.begin():
        cid = await oauth.register_client(
            s, redirect_uris=["https://claude.ai/api/mcp/auth_callback"], client_name="Claude"
        )
    async with maker() as s, s.begin():
        row = await oauth.get_client(s, cid)
    assert row is not None
    assert row.redirect_uris == ["https://claude.ai/api/mcp/auth_callback"]
    assert cid.startswith("client_")


@pytest.mark.asyncio
async def test_auth_code_single_use(maker: async_sessionmaker[AsyncSession]) -> None:
    async with maker() as s, s.begin():
        raw = await _mk_code(s)
    async with maker() as s, s.begin():
        first = await oauth.consume_auth_code(s, raw)
    assert first is not None
    assert first.org_id == "org-a"
    # Second consume of the same code must fail (single-use / replay).
    async with maker() as s, s.begin():
        second = await oauth.consume_auth_code(s, raw)
    assert second is None


@pytest.mark.asyncio
async def test_auth_code_expired(maker: async_sessionmaker[AsyncSession]) -> None:
    async with maker() as s, s.begin():
        raw = await oauth.create_auth_code(
            s,
            client_id="client_test",
            redirect_uri="https://claude.ai/api/mcp/auth_callback",
            code_challenge="abc",
            code_challenge_method="S256",
            resource=_RES,
            org_id="org-a",
            user_id=None,
            scope="*",
            ttl_seconds=-1,  # already expired
        )
    async with maker() as s, s.begin():
        assert await oauth.consume_auth_code(s, raw) is None


@pytest.mark.asyncio
async def test_issue_and_lookup_access(maker: async_sessionmaker[AsyncSession]) -> None:
    async with maker() as s, s.begin():
        issued = await oauth.issue_token(
            s,
            client_id="client_test",
            org_id="org-a",
            user_id="user_1",
            scope="*",
            resource=_RES,
            access_ttl_seconds=3600,
            refresh_ttl_seconds=86400,
        )
    async with maker() as s, s.begin():
        row = await oauth.lookup_access(s, issued.access_token)
    assert row is not None
    assert row.org_id == "org-a"
    assert row.resource == _RES
    assert row.token_hash == oauth.hash_key(issued.access_token)  # stored hashed, not raw


@pytest.mark.asyncio
async def test_lookup_access_unknown_returns_none(maker: async_sessionmaker[AsyncSession]) -> None:
    async with maker() as s, s.begin():
        assert await oauth.lookup_access(s, "strata_oat_does_not_exist") is None


@pytest.mark.asyncio
async def test_refresh_rotation_and_reuse_rejected(maker: async_sessionmaker[AsyncSession]) -> None:
    async with maker() as s, s.begin():
        issued = await oauth.issue_token(
            s,
            client_id="client_test",
            org_id="org-a",
            user_id="user_1",
            scope="*",
            resource=_RES,
            access_ttl_seconds=3600,
            refresh_ttl_seconds=86400,
        )
    # Rotate once → new pair.
    async with maker() as s, s.begin():
        rotated = await oauth.rotate_refresh(
            s, issued.refresh_token, access_ttl_seconds=3600, refresh_ttl_seconds=86400
        )
    assert rotated is not None
    assert rotated.access_token != issued.access_token
    assert rotated.refresh_token != issued.refresh_token
    # The OLD access token is now revoked (rotation killed the pair).
    async with maker() as s, s.begin():
        assert await oauth.lookup_access(s, issued.access_token) is None
    # The new access token works.
    async with maker() as s, s.begin():
        assert await oauth.lookup_access(s, rotated.access_token) is not None
    # Reusing the OLD refresh token is rejected (reuse detection).
    async with maker() as s, s.begin():
        assert (
            await oauth.rotate_refresh(
                s, issued.refresh_token, access_ttl_seconds=3600, refresh_ttl_seconds=86400
            )
            is None
        )


@pytest.mark.asyncio
async def test_cross_tenant_token_carries_its_own_org(
    maker: async_sessionmaker[AsyncSession],
) -> None:
    """A token issued for org A resolves only as org A — never as org B."""
    async with maker() as s, s.begin():
        a = await oauth.issue_token(
            s,
            client_id="client_test",
            org_id="org-a",
            user_id=None,
            scope="*",
            resource=_RES,
            access_ttl_seconds=3600,
            refresh_ttl_seconds=86400,
        )
        b = await oauth.issue_token(
            s,
            client_id="client_test",
            org_id="org-b",
            user_id=None,
            scope="*",
            resource=_RES,
            access_ttl_seconds=3600,
            refresh_ttl_seconds=86400,
        )
    async with maker() as s, s.begin():
        ra = await oauth.lookup_access(s, a.access_token)
        rb = await oauth.lookup_access(s, b.access_token)
    assert ra is not None and ra.org_id == "org-a"
    assert rb is not None and rb.org_id == "org-b"
