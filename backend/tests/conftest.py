"""Shared pytest fixtures.

The async engine in ``strata.db.engine`` is a single process-wide
``create_async_engine`` with the default connection pool. ``pytest-asyncio`` in
``asyncio_mode = "auto"`` gives **each** test its own event loop, so a pooled
asyncpg connection opened by one test's request path (e.g. the fire-and-forget
``persist_tam_safe``) survives into the next test bound to a now-closed loop —
SQLAlchemy then raises ``RuntimeError: ... attached to a different loop`` and the
best-effort persist swallows it, leaving the row unwritten. That manifests as an
order-dependent failure (the anonymous-build permalink test sees no row).

Disposing the engine after every test guarantees no connection crosses an event
loop. This is test-infrastructure only — it does not change production pooling.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio

from strata.config import settings


@pytest.fixture
def portfolio_enabled() -> Iterator[None]:
    """Flip the F6 portfolio write gate on for one test, restoring it after."""
    prev = settings.portfolio_enabled
    settings.portfolio_enabled = True
    try:
        yield
    finally:
        settings.portfolio_enabled = prev


@pytest_asyncio.fixture(autouse=True)
async def _dispose_shared_engine() -> AsyncIterator[None]:
    """Dispose the process-wide async engine after each test so a pooled asyncpg
    connection never leaks into the next test's event loop."""
    yield
    from strata.db.engine import engine

    await engine.dispose()
