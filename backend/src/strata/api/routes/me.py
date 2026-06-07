"""Per-user workspace routes (``/me/*``) — PR 1 / U6.

The signed-in tenant's PRIVATE primitive store. Every verb requires a real
(non-anonymous) principal via ``require_authenticated``; an anonymous caller is
401 even in dev, so two unauthenticated users can never share one tenant bucket.

Server-authoritative honesty fences (KTD-5):
- ``visibility`` is forced to ``private`` and ``org_id`` to the caller's org,
  whatever the request body claims.
- the **MODELED fence** (reused from ``resolver/writer.py`` semantics) rejects a
  primitive whose source tier makes it a modeled estimate rather than a sourced
  number — no soft-data, no LLM numbers in the bank (Q20).
- ``promote`` does NOT write public: it packages the primitive into the existing
  ``/contribute`` review queue (migration 004), so going public always goes
  through review, never a direct tenant→public write.

All persistence runs inside ``org_session_scope(principal.org_id)`` so the strict
RLS policy on ``user_primitives`` actually isolates tenants.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError

from strata.api.auth import Principal, require_authenticated
from strata.api.responses import UNAUTHORIZED, error, format_validation_errors, merge
from strata.db.audit import AuditEvent, list_audit_events
from strata.db.contributions import record_contribution_safe
from strata.db.engine import org_session_scope
from strata.db.tams import list_saved_tams, save_tam_for_org
from strata.db.user_primitives import (
    ModeledFenceError,
    UserPrimitive,
    create_user_primitive,
    delete_user_primitive,
    get_user_primitive,
    list_user_primitives,
    update_user_primitive,
)
from strata.models import TAMOutput

router = APIRouter(prefix="/me", tags=["me"])

_AUTH = Depends(require_authenticated)


class PrimitivePayload(BaseModel):
    """A primitive proposal. The server forces ``visibility``/``org_id`` and runs
    the MODELED fence, so anything the body declares for those is overridden."""

    payload: dict[str, Any]


class PromoteResponse(BaseModel):
    status: str
    reasons: list[str]
    contribution_id: int | None = None


def _to_422(exc: Exception) -> HTTPException:
    """Map a validation / fence failure to a 422 with honest reasons."""
    if isinstance(exc, ValidationError):
        reasons = format_validation_errors(exc)
        return HTTPException(status_code=422, detail="; ".join(reasons))
    return HTTPException(status_code=422, detail=str(exc))


@router.get(
    "/primitives",
    response_model=list[UserPrimitive],
    summary="List my private primitives",
    description="The caller's private primitive store (RLS-scoped to the caller's org).",
    responses=UNAUTHORIZED,
)
async def list_my_primitives(principal: Principal = _AUTH) -> list[UserPrimitive]:
    async with org_session_scope(principal.org_id) as session:
        return await list_user_primitives(session)


@router.post(
    "/primitives",
    response_model=UserPrimitive,
    status_code=201,
    summary="Create a private primitive",
    description=(
        "Store a primitive in the caller's private bank. ``visibility`` is forced "
        "to private and ``org_id`` to the caller's org server-side; a modeled / "
        "analyst-tier number is rejected (422) — the private bank stores sourced "
        "output only (Q20)."
    ),
    responses=merge(UNAUTHORIZED, error(422, "Invalid primitive or modeled-tier claim.")),
)
async def create_my_primitive(
    body: PrimitivePayload, principal: Principal = _AUTH
) -> UserPrimitive:
    try:
        async with org_session_scope(principal.org_id) as session:
            return await create_user_primitive(
                session,
                org_id=principal.org_id,
                created_by=principal.user_id,
                payload=body.payload,
            )
    except (ValidationError, ModeledFenceError, ValueError) as exc:
        raise _to_422(exc) from exc


@router.patch(
    "/primitives/{slug}",
    response_model=UserPrimitive,
    summary="Update a private primitive",
    description="Replace the payload of the caller's primitive. Same fences as create.",
    responses=merge(
        UNAUTHORIZED,
        error(404, "No such primitive for this tenant."),
        error(422, "Invalid primitive or modeled-tier claim."),
    ),
)
async def update_my_primitive(
    slug: str, body: PrimitivePayload, principal: Principal = _AUTH
) -> UserPrimitive:
    try:
        async with org_session_scope(principal.org_id) as session:
            updated = await update_user_primitive(
                session, org_id=principal.org_id, slug=slug, payload=body.payload
            )
    except (ValidationError, ModeledFenceError, ValueError) as exc:
        raise _to_422(exc) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail=f"no private primitive {slug!r}")
    return updated


@router.delete(
    "/primitives/{slug}",
    status_code=204,
    summary="Delete a private primitive",
    description="Delete the caller's primitive (RLS-scoped; cannot touch another tenant's).",
    responses=merge(UNAUTHORIZED, error(404, "No such primitive for this tenant.")),
)
async def delete_my_primitive(slug: str, principal: Principal = _AUTH) -> None:
    async with org_session_scope(principal.org_id) as session:
        deleted = await delete_user_primitive(session, slug=slug)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"no private primitive {slug!r}")


@router.post(
    "/primitives/{slug}/promote",
    response_model=PromoteResponse,
    summary="Promote a private primitive to the review queue",
    description=(
        "Package the caller's private primitive into the ``/contribute`` review "
        "queue. This NEVER writes a public primitive directly — going public "
        "always goes through human review (migration 004 contributions)."
    ),
    responses=merge(UNAUTHORIZED, error(404, "No such primitive for this tenant.")),
)
async def promote_my_primitive(slug: str, principal: Principal = _AUTH) -> PromoteResponse:
    async with org_session_scope(principal.org_id) as session:
        existing = await get_user_primitive(session, slug=slug)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"no private primitive {slug!r}")

    # The contribution carries the SOURCED payload (the create/update fence already
    # guaranteed it is not modeled). Status is needs_review: a tenant's private
    # number is never auto-published, regardless of tier.
    status = "needs_review"
    reasons = ["promoted from private bank; queued for human review before publish"]
    contribution_id = await record_contribution_safe(
        principal.org_id, "atomic_primitive", status, reasons, existing.payload
    )
    return PromoteResponse(status=status, reasons=reasons, contribution_id=contribution_id)


# --------------------------------------------------------------------------- #
# U7 — saved research + per-user history (``/me/tams``, ``/me/audit``).         #
# --------------------------------------------------------------------------- #


class SaveTamRequest(BaseModel):
    """Save an existing build into the caller's research. ``state_hash`` is the
    content-addressed id of a build the caller already produced; ``title`` is
    optional free-text shown in the saved list."""

    state_hash: str
    title: str | None = None


@router.post(
    "/tams/save",
    response_model=TAMOutput,
    summary="Save a TAM to my research",
    description=(
        "Save an existing build (by ``state_hash``) into the caller's research. "
        "Upserts the caller's OWN ``tam_outputs`` row (org_id + created_by + title "
        "+ is_saved) on the ``(org_id, state_hash)`` partial index — it never "
        "touches the anonymous ``org_id IS NULL`` permalink, so the public artifact "
        "is left intact. Re-saving the same hash refreshes the title."
    ),
    responses=merge(UNAUTHORIZED, error(404, "No such build for this caller.")),
)
async def save_my_tam(body: SaveTamRequest, principal: Principal = _AUTH) -> TAMOutput:
    async with org_session_scope(principal.org_id) as session:
        saved = await save_tam_for_org(
            session,
            state_hash=body.state_hash,
            org_id=principal.org_id,
            created_by=principal.user_id,
            title=body.title,
        )
    if saved is None:
        raise HTTPException(status_code=404, detail=f"no build {body.state_hash!r}")
    return saved


@router.get(
    "/tams",
    response_model=list[TAMOutput],
    summary="My saved research",
    description="The caller's saved TAMs (``is_saved`` rows), RLS-scoped to the caller's org.",
    responses=UNAUTHORIZED,
)
async def list_my_tams(principal: Principal = _AUTH) -> list[TAMOutput]:
    async with org_session_scope(principal.org_id) as session:
        return await list_saved_tams(session)


@router.get(
    "/audit",
    response_model=list[AuditEvent],
    summary="My activity history",
    description=(
        "The caller's audit events (newest first) — each carries the action, the "
        "target hash, and the market in ``meta`` for a rebuild link. RLS-scoped to "
        "the caller's org so only the caller's events are returned."
    ),
    responses=UNAUTHORIZED,
)
async def list_my_audit(principal: Principal = _AUTH) -> list[AuditEvent]:
    async with org_session_scope(principal.org_id) as session:
        return await list_audit_events(session, limit=100)
