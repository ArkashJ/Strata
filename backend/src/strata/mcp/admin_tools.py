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
from ..db.feedback import FeedbackNotApplicableError, admin_promote_payload
from ..db.feedback import admin_list_feedback as _admin_list_feedback
from ..guards.fence import ModeledFenceError
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


def _correction_path(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Next-actions to close a ``primitive_correction``. Honest: the steps differ
    on whether the flag actually carries a promotable payload — without one, the
    only real next action is a better submission, not a promote that will fail."""
    fid = row.get("id")
    if row.get("suggested_value"):
        return [
            {
                "tool": "apply_feedback",
                "arguments": {"feedback_id": fid},
                "description": "create the org-private corrected primitive (fenced, Q20)",
            },
            {
                "tool": "admin_promote_correction",
                "arguments": {"feedback_id": fid},
                "description": "re-fence for the SHARED bank and return the committable YAML",
            },
            {
                "cli": f"strata admin promote {fid}",
                "description": "write data/primitives/<slug>.yaml in a repo checkout",
            },
        ]
    return [
        {
            "tool": "submit_feedback",
            "description": (
                "this flag has no promotable correction; a promotable one needs a FULL "
                "primitive payload in suggested_value (value + unit + as_of + geo + a "
                "sourced, hash-pinned source — modeled/analyst tier cannot cross the "
                "shared fence)"
            ),
            "arguments": {
                "payload": {
                    "kind": "primitive_correction",
                    "target_type": "primitive",
                    "target_id": row.get("target_id") or "<primitive-slug>",
                    "body": "<why the current number is wrong>",
                    "suggested_value": {
                        "kind": "atomic_primitive",
                        "slug": "<new-slug>",
                        "value": "<corrected number>",
                        "unit": {"kind": "<stock|flow|price>", "dimension": "<people|money|…>"},
                        "source": {
                            "tier": "<regulator|first_party|aggregator>",
                            "url": "<citation url>",
                            "snapshot_sha256": "<64-hex content pin>",
                        },
                    },
                }
            },
        }
    ]


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
    feedback: list[dict[str, Any]] = []
    for r in rows:
        d = r.model_dump(mode="json")
        # Corrections carry their closing path so the operator (or the agent
        # driving the queue) never has to guess the apply → promote sequence.
        if r.kind is FeedbackKind.PRIMITIVE_CORRECTION:
            d["correction_path"] = _correction_path(d)
        feedback.append(d)
    return {
        "admin": True,
        "count": len(feedback),
        "feedback": feedback,
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
        try:
            shared, from_org = await admin_promote_payload(session, feedback_id, resolve=True)
        except FeedbackNotApplicableError as exc:
            return {"error": "not_applicable", "detail": str(exc)}
        except ModeledFenceError as exc:
            return {"error": "modeled_fence", "detail": str(exc)}
        except (ValidationError, ValueError) as exc:
            return {"error": "invalid_primitive", "detail": str(exc)}
    return {
        "promoted": True,
        "feedback_id": feedback_id,
        "from_org": from_org,
        "slug": shared["slug"],
        "shared_yaml": yaml.safe_dump(shared, sort_keys=False),
        "shared_primitive": shared,
        "next_action": f"strata admin promote {feedback_id} --org {from_org} "
        "writes this to data/primitives/ in a repo checkout",
    }
