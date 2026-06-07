"""Admin MCP tools — cross-org feedback governance (Pillar A).

The owner has admin visibility across **every** tenant's feedback queue and can
promote an org-private correction into the SHARED bank everyone reads. Both tools
gate on ``auth.is_admin`` (the caller's org must be on ``STRATA_ADMIN_ORGS``) and
run inside ``admin_session_scope`` — which sets the audited ``app.is_admin`` GUC
so the *additive* admin RLS policies (migration 016) widen the read to all orgs
without relaxing the closed tenant policy.

``admin_promote_correction`` is prod-safe: the hosted MCP server has no writable
repo checkout, so it does NOT write ``data/primitives/`` server-side. It
re-validates the correction through the SHARED-bank fence (Q20 holds) and
RETURNS the committable YAML payload, marking the originating flag resolved +
noting the promotion. The CLI (``strata admin promote``) is what writes the YAML
to disk in a repo checkout.
"""

from __future__ import annotations

from typing import Any

import yaml
from pydantic import ValidationError

from ..api.auth import is_admin
from ..db.engine import admin_session_scope
from ..db.feedback import (
    admin_correction_payload,
    admin_get_feedback_row,
)
from ..db.feedback import (
    admin_list_feedback as _admin_list_feedback,
)
from ..guards.fence import ModeledFenceError, validate_and_fence_shared_primitive
from ..models.feedback import FeedbackKind, FeedbackStatus
from ..registry import Registry
from .context import current_principal


def _require_admin() -> dict[str, Any] | None:
    """Return an error envelope when the caller is not an admin (or is over stdio
    with no principal), else ``None``. Keeps the gate identical across tools."""
    principal = current_principal.get()
    if principal is None:
        return {
            "error": "no_tenant",
            "detail": "admin tools need an authenticated (hosted) connection; "
            "local stdio has no principal to authorize.",
        }
    if not is_admin(principal):
        return {
            "error": "forbidden",
            "detail": "this org is not an admin; cross-org governance is restricted "
            "to orgs on STRATA_ADMIN_ORGS.",
        }
    return None


async def admin_list_feedback(
    reg: Registry,
    *,
    status: str | None = None,
    kind: str | None = None,
    org_id: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """[READ · ADMIN] List feedback across EVERY org's queue (newest-first).

    Restricted to admin orgs. Optionally filter by ``status`` (open / triaged /
    resolved / wontfix), ``kind``, or a single ``org_id``. Every row carries its
    originating ``org_id`` so the operator knows whose number to fix."""
    if (err := _require_admin()) is not None:
        return err
    status_filter: FeedbackStatus | None = None
    kind_filter: FeedbackKind | None = None
    if status:
        try:
            status_filter = FeedbackStatus(status)
        except ValueError as exc:
            return {"error": "invalid_status", "detail": str(exc)}
    if kind:
        try:
            kind_filter = FeedbackKind(kind)
        except ValueError as exc:
            return {"error": "invalid_kind", "detail": str(exc)}
    admin_org = current_principal.get().org_id  # type: ignore[union-attr]  # _require_admin guards None
    async with admin_session_scope(admin_org) as session:
        rows = await _admin_list_feedback(
            session,
            status=status_filter,
            kind=kind_filter,
            org_id=org_id,
            limit=max(1, min(limit, 500)),
        )
    return {
        "admin": True,
        "count": len(rows),
        "feedback": [r.model_dump(mode="json") for r in rows],
    }


async def admin_promote_correction(reg: Registry, *, feedback_id: int) -> dict[str, Any]:
    """[WRITE · ADMIN] Promote an org-private correction into the SHARED bank.

    Reads the correction (the org-private primitive the flag created, or its
    ``suggested_value``) cross-org, re-validates it through the shared-bank fence
    (a modeled / analyst-tier number is refused — Q20), marks the flag resolved
    with a promotion note, and RETURNS the committable shared YAML.

    Prod-safe: does NOT write to disk (the hosted server has no repo checkout).
    Run ``strata admin promote <id> --org <org>`` in a checkout to write
    ``data/primitives/<slug>.yaml`` and commit it."""
    if (err := _require_admin()) is not None:
        return err
    admin_org = current_principal.get().org_id  # type: ignore[union-attr]  # _require_admin guards None
    async with admin_session_scope(admin_org) as session:
        row = await admin_get_feedback_row(session, feedback_id)
        if row is None:
            return {"error": "not_found", "detail": f"no feedback {feedback_id}"}
        payload = await admin_correction_payload(session, row)
        if payload is None:
            return {
                "error": "no_payload",
                "detail": f"feedback {feedback_id} has no correction to promote "
                "(no applied primitive and no suggested_value).",
            }
        try:
            shared = validate_and_fence_shared_primitive(payload)
        except ModeledFenceError as exc:
            return {"error": "modeled_fence", "detail": str(exc)}
        except (ValidationError, ValueError) as exc:
            return {"error": "invalid_primitive", "detail": str(exc)}
        row.status = FeedbackStatus.RESOLVED.value
        note = f"promoted to shared bank → data/primitives/{shared['slug']}.yaml"
        row.resolution = f"{row.resolution} · {note}" if row.resolution else note
        await session.flush()
    return {
        "promoted": True,
        "feedback_id": feedback_id,
        "from_org": row.org_id,
        "slug": shared["slug"],
        "shared_yaml": yaml.safe_dump(shared, sort_keys=False),
        "shared_primitive": shared,
        "next_action": f"strata admin promote {feedback_id} --org {row.org_id} "
        "writes this to data/primitives/ in a repo checkout",
    }
