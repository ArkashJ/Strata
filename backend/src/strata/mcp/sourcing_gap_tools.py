"""Sourcing-gap MCP tools (Pillar B1) — the agent reports + reads the misses.

When ``resolve_market`` / ``verify_market_claim`` return an honest "no sourced
number here", the driving agent reports the gap so the miss becomes ranked
demand (``report_sourcing_gap``), and the owner reads the queue platform-wide
(``list_sourcing_gaps`` with ``scope="all"``, admin only). This is the agent-as-
contributor flywheel: agents surface what's missing far faster than humans file
tickets.

Org-scoped (RLS), async (awaited on the app loop like the feedback tools). A gap
is a demand signal, never a number (E1) — reporting one changes no math.
"""

from __future__ import annotations

from typing import Any

from ..api.auth import is_admin
from ..db.engine import admin_session_scope, org_session_scope
from ..db.sourcing_gaps import admin_list_gaps, list_gaps, record_gap
from ..models.sourcing_gap import GapSource, GapStatus
from ..registry import Registry
from .context import current_org_id, current_principal


async def report_sourcing_gap(reg: Registry, *, payload: dict[str, Any]) -> dict[str, Any]:
    """[WRITE] Record that sourced data was MISSING for a query / role — so the
    miss becomes ranked demand instead of vanishing. De-duplicated: reporting the
    same gap bumps its hit_count. Commentary on supply, never a number (E1).

    payload: { query_text?, concept_slug?, role?, lens?, unit_hint?,
    resource_target?, source? (resolve_miss|report_gap|unverifiable_claim|manual),
    note? }. Over local stdio there is no tenant, so it is refused honestly."""
    if current_principal.get() is None:
        return {
            "error": "no_tenant",
            "detail": "report_sourcing_gap needs an authenticated (hosted) connection; "
            "local stdio has no org to attribute the gap to.",
        }
    org = current_org_id()
    try:
        source = GapSource(str(payload.get("source", "manual")))
    except ValueError as exc:
        return {"error": "invalid_source", "detail": str(exc)}
    query_text = str(payload["query_text"]).strip() if payload.get("query_text") else None
    resource_target = (
        str(payload["resource_target"]).strip() if payload.get("resource_target") else None
    )
    if not query_text and not resource_target:
        return {
            "error": "empty_gap",
            "detail": "provide at least a query_text or a resource_target to identify the gap.",
        }
    async with org_session_scope(org) as session:
        gap = await record_gap(
            session,
            org_id=org,
            source=source,
            query_text=query_text,
            concept_slug=(str(payload["concept_slug"]) if payload.get("concept_slug") else None),
            role=(str(payload["role"]) if payload.get("role") else None),
            lens=(str(payload["lens"]) if payload.get("lens") else None),
            unit_hint=(str(payload["unit_hint"]) if payload.get("unit_hint") else None),
            resource_target=resource_target,
            note=(str(payload["note"]) if payload.get("note") else None),
        )
    return {
        "recorded": True,
        "id": gap.id,
        "dedup_key": gap.dedup_key,
        "hit_count": gap.hit_count,
        "status": gap.status.value,
        "readable_at": "list_sourcing_gaps (MCP) · strata gaps (CLI)",
    }


async def list_sourcing_gaps(
    reg: Registry, *, status: str | None = None, scope: str = "org", limit: int = 50
) -> dict[str, Any]:
    """[READ] List sourcing gaps, most-demanded first (hit_count desc).

    scope="org" (default) lists YOUR workspace's gaps. scope="all" lists every
    workspace's gaps ranked platform-wide — ADMIN only (refused otherwise). The
    demand-ranked connector / sourcing backlog."""
    principal = current_principal.get()
    if principal is None:
        return {
            "error": "no_tenant",
            "detail": "list_sourcing_gaps needs an authenticated connection",
        }
    status_filter: GapStatus | None = None
    if status:
        try:
            status_filter = GapStatus(status)
        except ValueError as exc:
            return {"error": "invalid_status", "detail": str(exc)}
    capped = max(1, min(limit, 500))
    if scope == "all":
        if not is_admin(principal):
            return {
                "error": "forbidden",
                "detail": "scope='all' is admin-only; use scope='org' for your workspace.",
            }
        async with admin_session_scope(principal.org_id) as session:
            rows = await admin_list_gaps(session, status=status_filter, limit=capped)
        return {
            "scope": "all",
            "count": len(rows),
            "gaps": [r.model_dump(mode="json") for r in rows],
        }
    org = current_org_id()
    async with org_session_scope(org) as session:
        rows = await list_gaps(session, status=status_filter, limit=capped)
    return {
        "scope": "org",
        "org_id": org,
        "count": len(rows),
        "gaps": [r.model_dump(mode="json") for r in rows],
    }
