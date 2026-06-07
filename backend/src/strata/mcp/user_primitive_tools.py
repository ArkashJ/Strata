"""Write/read MCP tools for the tenant's PRIVATE bank (``user_primitives``).

This is the bidirectional half of the hosted MCP surface: an agent writes a
sourced primitive to its org's private bank and it persists in Postgres
(org-scoped, RLS-enforced via ``org_session_scope`` — migration 009), durable
across restarts and replicas. The same rows are read back by the ``/bank`` web
page (``GET /me/primitives``) and by ``list_my_primitives`` here — so an agent's
write shows up for the signed-in user, and vice-versa.

These reuse the exact DB functions + MODELED fence behind ``POST /me/primitives``
(``db/user_primitives.py``); the only difference is the caller is an MCP agent
authenticated by an API key rather than a Clerk session. ``org_id`` threads from
the authenticated ``Principal`` via the auth-middleware ContextVar
(``current_org_id()``), so a write always lands under the caller's own org.

Handlers are ``async`` — ``server._call_tool`` awaits the coroutine on the app's
event loop, the same loop the global async engine is bound to (mirrors the HTTP
route), so there are no cross-loop / threaded-session hazards.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from ..db.engine import org_session_scope
from ..db.user_primitives import (
    ModeledFenceError,
    TooManyPrimitivesError,
    create_user_primitive,
    list_user_primitives,
)
from ..registry import Registry
from .context import current_org_id, current_principal


async def save_primitive(reg: Registry, *, payload: dict[str, Any]) -> dict[str, Any]:
    """[WRITE] Store a sourced primitive in your org's private bank.

    ``visibility`` is forced to private and ``org_id`` to the caller's org
    server-side; a modeled / analyst-tier number is refused (Q20). On success the
    row is durable in Postgres and visible at ``/bank`` + ``GET /me/primitives``.
    """
    org = current_org_id()
    if not payload:
        return {"error": "provide a primitive payload object (slug, value, unit, source, …)"}
    # Attribute the write to the calling key, mirroring the web route's
    # created_by=principal.user_id (an API-key principal has no user_id, so fall
    # back to its key_id) rather than the org string.
    principal = current_principal.get()
    created_by = principal.key_id if principal is not None else None
    try:
        async with org_session_scope(org) as session:
            prim = await create_user_primitive(
                session, org_id=org, created_by=created_by, payload=payload
            )
    except TooManyPrimitivesError as exc:
        return {"error": "org_limit_reached", "detail": str(exc)}
    except ModeledFenceError as exc:
        return {"error": "modeled_fence", "detail": str(exc)}
    except (ValidationError, ValueError) as exc:
        return {"error": "invalid_primitive", "detail": str(exc)}
    return {
        "saved": True,
        "slug": prim.slug,
        "org_id": prim.org_id,
        "visibility": prim.visibility,
        "readable_at": "/bank (web) · GET /me/primitives · list_my_primitives (MCP)",
    }


async def list_my_primitives(reg: Registry) -> dict[str, Any]:
    """[READ] The caller's private primitives (RLS-scoped to your org)."""
    org = current_org_id()
    async with org_session_scope(org) as session:
        rows = await list_user_primitives(session, org_id=org)
    return {
        "org_id": org,
        "count": len(rows),
        "primitives": [r.model_dump(mode="json") for r in rows],
    }
