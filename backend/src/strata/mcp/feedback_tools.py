"""Feedback MCP tools (Phase F) — the agent half of the improvement flywheel.

An agent (Claude in the harness) flags a bad assumption / failed query / wrong
primitive when a sourced number looks off, and lists the org's open flags. These
reuse the exact org-scoped DB functions behind ``POST /feedback`` /
``GET /feedback`` (``db/feedback.py``); the only difference is the caller is an
MCP agent authenticated by an API key. ``org_id`` threads from the authenticated
``Principal`` via ``current_org_id()`` so a flag always lands under the caller's
own org (and is dropped honestly over local stdio, which has no tenant).

Handlers are ``async`` — ``server._call_tool`` awaits the coroutine on the app's
event loop (the same loop the async engine is bound to), mirroring the HTTP route.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from ..db.engine import org_session_scope
from ..db.feedback import FeedbackNotApplicableError, apply_feedback_correction, record_feedback
from ..db.feedback import list_feedback as _list_feedback
from ..db.user_primitives import ModeledFenceError, TooManyPrimitivesError
from ..models.feedback import FeedbackKind, FeedbackStatus, TargetType
from ..registry import Registry
from .context import current_org_id, current_principal


async def submit_feedback(reg: Registry, *, payload: dict[str, Any]) -> dict[str, Any]:
    """[WRITE] Flag a bad assumption / failed query / correction on a tam,
    primitive, concept, framework, query, or report.

    Org-scoped (RLS); the flag is commentary only and never changes a sourced
    number (E1). Over local stdio there is no tenant, so the write is refused
    honestly rather than attributed to a placeholder org."""
    principal = current_principal.get()
    if principal is None:
        return {
            "error": "no_tenant",
            "detail": "submit_feedback needs an authenticated (hosted) connection; "
            "local stdio has no org to attribute the flag to.",
        }
    org = current_org_id()
    try:
        kind = FeedbackKind(str(payload.get("kind", "general")))
        target_type = TargetType(str(payload.get("target_type", "query")))
    except ValueError as exc:
        return {"error": "invalid_enum", "detail": str(exc)}
    body = str(payload.get("body", "")).strip()
    if not body:
        return {"error": "missing_body", "detail": "provide a 'body' describing the flag"}
    raw_suggested = payload.get("suggested_value")
    suggested: dict[str, Any] | None = raw_suggested if isinstance(raw_suggested, dict) else None
    try:
        async with org_session_scope(org) as session:
            event = await record_feedback(
                session,
                org_id=org,
                user_id=principal.key_id,
                kind=kind,
                target_type=target_type,
                body=body,
                target_id=(str(payload["target_id"]) if payload.get("target_id") else None),
                query_text=(str(payload["query_text"]) if payload.get("query_text") else None),
                severity=(str(payload["severity"]) if payload.get("severity") else None),
                suggested_value=suggested,
            )
    except (ValidationError, ValueError) as exc:
        return {"error": "invalid_feedback", "detail": str(exc)}
    return {
        "submitted": True,
        "id": event.id,
        "kind": event.kind.value,
        "target_type": event.target_type.value,
        "status": event.status.value,
        "readable_at": "/feedback (web) · GET /feedback · list_feedback (MCP)",
    }


async def apply_feedback(
    reg: Registry, *, feedback_id: int, primitive_payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    """[WRITE] Accept a primitive_correction / missing_data flag and write the
    correction into the data layer: create an org-private primitive (from
    ``primitive_payload`` or the flag's stored ``suggested_value``), mark the flag
    resolved, and link the new primitive.

    Same fence as ``save_primitive`` — a modeled / analyst-tier number is refused
    (Q20); the flag stays commentary (E1), this CREATES a new private number, it
    never mutates an existing sourced one. Over local stdio there is no tenant, so
    the apply is refused honestly."""
    principal = current_principal.get()
    if principal is None:
        return {
            "error": "no_tenant",
            "detail": "apply_feedback needs an authenticated (hosted) connection; "
            "local stdio has no org to attribute the correction to.",
        }
    org = current_org_id()
    try:
        async with org_session_scope(org) as session:
            event, prim = await apply_feedback_correction(
                session,
                feedback_id,
                org_id=org,
                created_by=principal.key_id,
                primitive_payload=primitive_payload,
            )
    except FeedbackNotApplicableError as exc:
        return {"error": "not_applicable", "detail": str(exc)}
    except TooManyPrimitivesError as exc:
        return {"error": "org_limit_reached", "detail": str(exc)}
    except ModeledFenceError as exc:
        return {"error": "modeled_fence", "detail": str(exc)}
    except (ValidationError, ValueError) as exc:
        return {"error": "invalid_primitive", "detail": str(exc)}
    return {
        "applied": True,
        "feedback": event.model_dump(mode="json"),
        "primitive": {
            "slug": prim.slug,
            "org_id": prim.org_id,
            "visibility": prim.visibility,
            **_cite_user_primitive(prim.payload),
        },
        "readable_at": "/bank (web) · GET /me/primitives · list_my_primitives (MCP)",
    }


def _cite_user_primitive(payload: dict[str, Any]) -> dict[str, Any]:
    """Surface the sourced-number contract from a stored private-primitive payload
    so the agent sees the cited fix it just created (value + unit + source)."""
    raw_source = payload.get("source")
    source: dict[str, Any] = raw_source if isinstance(raw_source, dict) else {}
    return {
        "value": payload.get("value"),
        "unit": payload.get("unit"),
        "source_url": source.get("url"),
        "source_tier": source.get("tier"),
        "snapshot_sha256": source.get("snapshot_sha256"),
    }


async def list_feedback(reg: Registry, *, status: str | None = None) -> dict[str, Any]:
    """[READ] List your org's flags (RLS-scoped), optionally filtered by status."""
    if current_principal.get() is None:
        return {"error": "no_tenant", "detail": "list_feedback needs an authenticated connection"}
    org = current_org_id()
    status_filter: FeedbackStatus | None = None
    if status:
        try:
            status_filter = FeedbackStatus(status)
        except ValueError as exc:
            return {"error": "invalid_status", "detail": str(exc)}
    async with org_session_scope(org) as session:
        rows = await _list_feedback(session, org_id=org, status=status_filter, limit=100)
    return {
        "org_id": org,
        "count": len(rows),
        "feedback": [r.model_dump(mode="json") for r in rows],
    }
