"""Shared FastAPI dependencies — registry loader, evaluated on first request.

In prod (``STRATA_ENV=prod``), the registry is loaded from Postgres at startup
(see ``lifespan`` in ``app.py``) and stored on ``app.state.registry``.
In dev/test, the registry is lazily built from YAML on the first request.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from strata.api.auth import Principal, require_principal
from strata.config import settings
from strata.db.engine import org_session_scope
from strata.loader import load_data_dir
from strata.registry import Registry

_require_principal = Depends(require_principal)


async def get_org_session(
    principal: Principal = _require_principal,
) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a Postgres session with RLS scoped to the
    caller's ``org_id`` (Wave-3 RLS, activated at request time)."""
    async with org_session_scope(principal.org_id) as session:
        yield session


# Module-level cache for the YAML-loaded registry (dev/test only).
_yaml_registry: Registry | None = None


def _load_yaml_registry() -> Registry:
    global _yaml_registry
    if _yaml_registry is not None:
        return _yaml_registry
    root = Path(settings.data_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[4] / root
    records = load_data_dir(root)
    _yaml_registry = Registry.from_loaded(records)
    return _yaml_registry


def get_registry(request: Request) -> Registry:
    """FastAPI dependency. Returns the pre-loaded DB registry in prod, or
    lazily loads from YAML in dev/test.
    """
    if settings.env == "prod":
        registry: Registry = request.app.state.registry  # type: ignore[assignment]
        return registry
    return _load_yaml_registry()
