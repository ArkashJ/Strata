"""Audit-event writer + reader (Strata Live Track C).

``record_audit`` appends one row per user-visible action. It is intentionally
best-effort: callers wrap it so a failed audit write never breaks the request.
``list_audit_events`` powers ``GET /audit`` and the dashboard feed.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from strata.db.models import AuditEventRow

_log = logging.getLogger(__name__)


class AuditEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor: str | None
    action: str
    target: str | None
    ts: datetime
    meta: dict[str, Any] | None = None


async def record_audit(
    session: AsyncSession,
    actor: str | None,
    action: str,
    target: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Append one audit row and commit. Caller is responsible for catching
    failures (the audit log is never allowed to break the request path)."""
    session.add(AuditEventRow(actor=actor or "anon", action=action, target=target, meta=meta))
    await session.commit()


async def record_audit_safe(
    actor: str | None,
    action: str,
    target: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Fire-and-forget audit write on its own session. Swallows (but logs) any
    failure so the audit log can never break the request that triggered it."""
    try:
        from strata.db.engine import SessionLocal

        async with SessionLocal() as session:
            await record_audit(session, actor, action, target, meta)
    except Exception:
        _log.warning("audit.write_failed action=%s target=%s", action, target, exc_info=True)


async def list_audit_events(
    session: AsyncSession, limit: int = 50, offset: int = 0
) -> list[AuditEvent]:
    """Return recent audit events, newest first."""
    stmt = (
        select(AuditEventRow)
        .order_by(AuditEventRow.ts.desc(), AuditEventRow.id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [AuditEvent.model_validate(r) for r in rows]
