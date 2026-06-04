"""Audit feed route (Strata Live Track C).

``GET /audit`` returns recent audit events newest-first for the dashboard.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from strata.api.auth import Principal, require_principal
from strata.api.responses import UNAUTHORIZED
from strata.db.audit import AuditEvent, list_audit_events
from strata.db.engine import get_session

router = APIRouter(tags=["audit"])

# Read-only public window for anonymous callers (demo/non-prod). Keeps the
# dashboard "trust trail" populated for a VC who has never seen a key, instead
# of hard-401-ing the panel. Authenticated callers get the full feed.
_ANON_LIMIT = 100

_SESSION = Depends(get_session)
# Degrade, don't slam the door: require_principal returns an anonymous principal
# in non-prod and only 401s in prod (require_auth) when a key is missing.
_PRINCIPAL = Depends(require_principal)


@router.get(
    "/audit",
    response_model=list[AuditEvent],
    summary="Recent audit events (newest first)",
    description="Fetch audit trail of resolve and recompute events.",
    responses=UNAUTHORIZED,
)
async def get_audit(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = _SESSION,
    principal: Principal = _PRINCIPAL,
) -> list[AuditEvent]:
    effective_limit = min(limit, _ANON_LIMIT) if principal.is_anonymous else limit
    return await list_audit_events(session, limit=effective_limit, offset=offset)
