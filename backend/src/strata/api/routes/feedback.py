"""Feedback / assumption-flagging routes (``/feedback``) — Phase F.

The improvement flywheel: a signed-in tenant (or an MCP agent) flags a bad
assumption, a failed query, a wrong primitive, or missing data; a maintainer
triages and resolves it. Every verb requires a real (non-anonymous) principal
via ``require_authenticated`` so a flag always lands under the caller's own org;
all persistence runs inside ``org_session_scope(principal.org_id)`` so the strict
RLS policy on ``feedback_events`` actually isolates tenants.

A flag is commentary on the TOOL, never an input to the math (E1).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from strata.api.auth import Principal, require_authenticated
from strata.api.responses import UNAUTHORIZED, error, merge
from strata.db.engine import org_session_scope
from strata.db.feedback import list_feedback, record_feedback, update_feedback
from strata.models.feedback import (
    FeedbackEvent,
    FeedbackKind,
    FeedbackStatus,
    TargetType,
)

router = APIRouter(prefix="/feedback", tags=["feedback"])

_AUTH = Depends(require_authenticated)
# Module-level Query singletons (repo convention — B008: never call Query() in a
# function default). FastAPI evaluates these once at import, exactly as Typer does.
_STATUS_Q = Query(None, description="Filter by triage status.")
_TARGET_Q = Query(None, description="Filter by target type.")
_LIMIT_Q = Query(50, ge=1, le=500)
_OFFSET_Q = Query(0, ge=0)


class SubmitFeedbackRequest(BaseModel):
    """A new flag. ``kind`` + ``target_type`` are enum-validated; ``body`` is the
    human-readable note. ``suggested_value`` is advisory JSON, never auto-applied."""

    kind: FeedbackKind
    target_type: TargetType
    body: str = Field(min_length=1, max_length=8192)
    target_id: str | None = Field(default=None, max_length=256)
    query_text: str | None = Field(default=None, max_length=2048)
    severity: str | None = Field(default=None, max_length=16)
    suggested_value: dict[str, Any] | None = None


class UpdateFeedbackRequest(BaseModel):
    """Triage / resolve a flag. Both fields optional — set ``status`` to move it
    through the lifecycle, ``resolution`` to record why it was closed."""

    status: FeedbackStatus | None = None
    resolution: str | None = Field(default=None, max_length=8192)


@router.post(
    "",
    response_model=FeedbackEvent,
    status_code=201,
    summary="Submit feedback / flag an assumption",
    description=(
        "Flag a bad assumption, a failed query, a wrong primitive, or missing "
        "data. The flag is stored org-scoped (RLS) and is commentary only — it "
        "never changes any sourced number (E1)."
    ),
    responses=UNAUTHORIZED,
)
async def submit_feedback(
    body: SubmitFeedbackRequest, principal: Principal = _AUTH
) -> FeedbackEvent:
    async with org_session_scope(principal.org_id) as session:
        return await record_feedback(
            session,
            org_id=principal.org_id,
            user_id=principal.user_id,
            kind=body.kind,
            target_type=body.target_type,
            body=body.body,
            target_id=body.target_id,
            query_text=body.query_text,
            severity=body.severity,
            suggested_value=body.suggested_value,
        )


@router.get(
    "",
    response_model=list[FeedbackEvent],
    summary="List feedback (triage queue)",
    description=(
        "The caller's flags newest-first, optionally filtered by ``status`` and "
        "``target_type``. RLS-scoped to the caller's org."
    ),
    responses=UNAUTHORIZED,
)
async def list_feedback_route(
    status: FeedbackStatus | None = _STATUS_Q,
    target_type: TargetType | None = _TARGET_Q,
    limit: int = _LIMIT_Q,
    offset: int = _OFFSET_Q,
    principal: Principal = _AUTH,
) -> list[FeedbackEvent]:
    async with org_session_scope(principal.org_id) as session:
        return await list_feedback(
            session,
            status=status,
            target_type=target_type,
            limit=limit,
            offset=offset,
        )


@router.patch(
    "/{feedback_id}",
    response_model=FeedbackEvent,
    summary="Triage / resolve a flag",
    description="Move a flag through its lifecycle (RLS-scoped; cannot touch another tenant's).",
    responses=merge(UNAUTHORIZED, error(404, "No such feedback for this tenant.")),
)
async def patch_feedback(
    feedback_id: int, body: UpdateFeedbackRequest, principal: Principal = _AUTH
) -> FeedbackEvent:
    async with org_session_scope(principal.org_id) as session:
        updated = await update_feedback(
            session, feedback_id, status=body.status, resolution=body.resolution
        )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"no feedback {feedback_id}")
    return updated
