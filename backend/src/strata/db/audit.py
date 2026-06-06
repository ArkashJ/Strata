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


# The anonymous tenant sentinel (mirrors ``api.auth._ANONYMOUS_ORG``). Audit rows
# under ``audit_events`` use the STRICT closed RLS policy (migration 008), so an
# anonymous caller has no tenant bucket to attribute an event to and the row's
# ``org_id`` is left NULL — which the closed policy then rejects on write. That is
# by design: the audit trail is per-tenant, never world-readable. The anonymous
# write is therefore best-effort and silently dropped (see ``record_audit_safe``).
_ANONYMOUS_ORG = "public"


class AuditEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor: str | None
    action: str
    target: str | None
    ts: datetime
    meta: dict[str, Any] | None = None
    org_id: str | None = None


async def record_audit(
    session: AsyncSession,
    actor: str | None,
    action: str,
    target: str | None = None,
    meta: dict[str, Any] | None = None,
    org_id: str | None = None,
) -> None:
    """Append one audit row and commit. ``actor`` is the Clerk user id (or
    ``'anon'``); ``org_id`` is the tenant the event belongs to and is what the
    strict RLS policy on ``audit_events`` keys on. The caller is responsible for
    setting ``app.org_id`` to ``org_id`` (e.g. via ``org_session_scope``) so the
    ``WITH CHECK`` passes — ``record_audit_safe`` does this. Caller catches
    failures (the audit log is never allowed to break the request path)."""
    session.add(
        AuditEventRow(actor=actor or "anon", action=action, target=target, meta=meta, org_id=org_id)
    )
    await session.commit()


async def record_audit_safe(
    actor: str | None,
    action: str,
    target: str | None = None,
    meta: dict[str, Any] | None = None,
    org_id: str | None = None,
) -> None:
    """Fire-and-forget audit write on its own session. Swallows (but logs) any
    failure so the audit log can never break the request that triggered it.

    An authenticated event (a real ``org_id``) is written under that tenant's
    ``org_session_scope`` so the strict RLS ``WITH CHECK`` passes. An anonymous
    event (``org_id`` None or the ``public`` sentinel) has no tenant bucket; the
    closed audit policy rejects a NULL-org row by design, so the write is
    attempted best-effort and silently dropped — it never breaks the request."""
    try:
        if org_id and org_id != _ANONYMOUS_ORG:
            from strata.db.engine import org_session_scope

            async with org_session_scope(org_id) as session:
                session.add(
                    AuditEventRow(
                        actor=actor or "anon",
                        action=action,
                        target=target,
                        meta=meta,
                        org_id=org_id,
                    )
                )
                # org_session_scope commits on exit (session.begin()).
        else:
            from strata.db.engine import SessionLocal

            async with SessionLocal() as session:
                await record_audit(session, actor, action, target, meta, org_id=None)
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
