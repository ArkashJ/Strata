"""Audit feed route (Strata Live Track C).

``GET /audit`` returns recent audit events newest-first for the dashboard.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from strata.api.auth import Principal, require_authenticated
from strata.db.audit import AuditEvent, list_audit_events
from strata.db.engine import get_session

router = APIRouter(tags=["audit"])

_SESSION = Depends(get_session)
# The audit feed is operational data — require a real key, never anonymous.
_PRINCIPAL = Depends(require_authenticated)


@router.get(
    "/audit",
    response_model=list[AuditEvent],
    summary="Recent audit events (newest first)",
)
async def get_audit(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = _SESSION,
    principal: Principal = _PRINCIPAL,
) -> list[AuditEvent]:
    return await list_audit_events(session, limit=limit, offset=offset)
