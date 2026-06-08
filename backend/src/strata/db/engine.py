"""Async engine + sessionmaker. One engine per process."""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from strata.config import settings

engine: AsyncEngine = create_async_engine(
    str(settings.database_url),
    echo=False,
    pool_pre_ping=True,
    future=True,
)

SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession]:
    """Use inside scripts/CLI; FastAPI routes should use `get_session` instead."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency for NON-tenant DB access (no RLS scoping).

    For any route reading/writing tenant-scoped rows (Wave 5B private data,
    anything under an RLS policy), use ``api.deps.get_org_session`` instead — it
    sets ``app.org_id`` so the Postgres RLS policies actually enforce isolation.
    """
    async with SessionLocal() as session:
        yield session


async def set_org_scope(session: AsyncSession, org_id: str) -> None:
    """Set the transaction-local ``app.org_id`` that the Wave-3 Postgres RLS
    policies key on. ``set_config(..., is_local=true)`` is transaction-scoped, so
    a pooled connection can't leak one request's org to the next."""
    await session.execute(text("SELECT set_config('app.org_id', :org, true)"), {"org": org_id})


@asynccontextmanager
async def org_session_scope(org_id: str) -> AsyncGenerator[AsyncSession]:
    """A transactional session with RLS scoped to ``org_id`` — every query inside
    sees only that tenant's rows. This is the runtime activation of the Wave-3
    RLS policies (the migration created them; this enforces them per request)."""
    async with SessionLocal() as session, session.begin():
        await set_org_scope(session, org_id)
        yield session


@asynccontextmanager
async def admin_session_scope(org_id: str) -> AsyncGenerator[AsyncSession]:
    """A transactional session that ALSO sets the transaction-local
    ``app.is_admin = 'on'`` GUC, activating the *additive* admin RLS policies
    (migration 016) so a cross-tenant operator can read every org's feedback and
    read any org-private primitive it is promoting.

    The bypass is explicit and transaction-scoped (``is_local=true``) so it can't
    leak to the next pooled request, and it never relaxes the closed tenant policy
    — it is a second permissive policy OR'd in only when this GUC is set. Callers
    MUST gate on ``auth.is_admin`` before entering this scope. ``app.org_id`` is
    still set (to the admin's own org) so any tenant-scoped WRITE the admin makes
    on its own behalf still lands in its bucket."""
    async with SessionLocal() as session, session.begin():
        await set_org_scope(session, org_id)
        await session.execute(text("SELECT set_config('app.is_admin', 'on', true)"))
        yield session
