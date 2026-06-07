"""Feedback-event writer + reader (Phase F — the improvement flywheel).

A user / agent flags a bad assumption, a failed query, a wrong primitive, or
missing data; the team triages and resolves it. Mirrors ``db/audit.py``:
``record_feedback_safe`` is fire-and-forget (a failed flag-write never breaks the
request that triggered it), while the explicit ``record_feedback`` / ``list_*`` /
``update_*`` functions take an already-org-scoped session (the route owns the
``org_session_scope`` so the strict RLS policy on ``feedback_events`` isolates).

A flag is commentary on the TOOL, never an input to the math (E1): persisting a
``suggested_value`` records a proposal, it does not change any sourced number.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from strata.db.models import FeedbackEventRow
from strata.models.feedback import (
    FeedbackEvent,
    FeedbackKind,
    FeedbackStatus,
    TargetType,
)

_log = logging.getLogger(__name__)

# The anonymous tenant sentinel (mirrors ``api.auth._ANONYMOUS_ORG`` and the
# audit writer). The closed RLS policy rejects a NULL/anon-org row by design, so
# an anonymous flag is attempted best-effort and silently dropped — never a 500.
_ANONYMOUS_ORG = "public"


async def record_feedback(
    session: AsyncSession,
    *,
    org_id: str,
    user_id: str | None,
    kind: FeedbackKind,
    target_type: TargetType,
    body: str,
    target_id: str | None = None,
    query_text: str | None = None,
    severity: str | None = None,
    suggested_value: dict[str, Any] | None = None,
    status: FeedbackStatus = FeedbackStatus.OPEN,
) -> FeedbackEvent:
    """Insert one feedback row inside an already-org-scoped session. The caller
    owns the scope (so ``app.org_id`` is set and the RLS ``WITH CHECK`` passes)."""
    row = FeedbackEventRow(
        org_id=org_id,
        user_id=user_id,
        kind=kind.value,
        target_type=target_type.value,
        target_id=target_id,
        query_text=query_text,
        severity=severity,
        body=body,
        suggested_value=suggested_value,
        status=status.value,
    )
    session.add(row)
    await session.flush()
    return FeedbackEvent.model_validate(row)


async def record_feedback_safe(
    *,
    org_id: str | None,
    user_id: str | None,
    kind: FeedbackKind,
    target_type: TargetType,
    body: str,
    target_id: str | None = None,
    query_text: str | None = None,
    severity: str | None = None,
    suggested_value: dict[str, Any] | None = None,
) -> int | None:
    """Fire-and-forget flag write on its own org-scoped session. Swallows (but
    logs) any failure so a flag can never break the request that triggered it
    (used by the failed-query auto-capture). Returns the new row id, or ``None``
    when the write was dropped (anonymous org has no tenant bucket under the
    closed RLS policy, exactly like the audit writer)."""
    if not org_id or org_id == _ANONYMOUS_ORG:
        return None
    try:
        from strata.db.engine import org_session_scope

        async with org_session_scope(org_id) as session:
            event = await record_feedback(
                session,
                org_id=org_id,
                user_id=user_id,
                kind=kind,
                target_type=target_type,
                body=body,
                target_id=target_id,
                query_text=query_text,
                severity=severity,
                suggested_value=suggested_value,
            )
            # org_session_scope commits on exit (session.begin()).
            return event.id
    except Exception:
        _log.warning("feedback.write_failed kind=%s target=%s", kind.value, target_type.value)
        return None


async def list_feedback(
    session: AsyncSession,
    *,
    status: FeedbackStatus | None = None,
    target_type: TargetType | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[FeedbackEvent]:
    """Return feedback rows newest-first, optionally filtered. RLS (the scoped
    session) restricts rows to ``app.org_id``."""
    stmt = select(FeedbackEventRow)
    if status is not None:
        stmt = stmt.where(FeedbackEventRow.status == status.value)
    if target_type is not None:
        stmt = stmt.where(FeedbackEventRow.target_type == target_type.value)
    stmt = (
        stmt.order_by(FeedbackEventRow.created_at.desc(), FeedbackEventRow.id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [FeedbackEvent.model_validate(r) for r in rows]


async def update_feedback(
    session: AsyncSession,
    feedback_id: int,
    *,
    status: FeedbackStatus | None = None,
    resolution: str | None = None,
) -> FeedbackEvent | None:
    """Triage / resolve one row (RLS-scoped to the caller's org). Returns ``None``
    when no such row is visible to this tenant."""
    row = (
        await session.execute(select(FeedbackEventRow).where(FeedbackEventRow.id == feedback_id))
    ).scalar_one_or_none()
    if row is None:
        return None
    if status is not None:
        row.status = status.value
    if resolution is not None:
        row.resolution = resolution
    await session.flush()
    return FeedbackEvent.model_validate(row)
