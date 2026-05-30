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
    """FastAPI dependency. Sessions are scoped to a single request."""
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
    async with SessionLocal() as session:
        async with session.begin():
            await set_org_scope(session, org_id)
            yield session
