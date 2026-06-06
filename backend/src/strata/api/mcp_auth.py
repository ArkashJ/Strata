"""Pure-ASGI auth guard for the mounted ``/mcp`` subtree (Phase 3 / Workstream A).

The hosted MCP transport is a *mounted* Starlette sub-app, so FastAPI route
dependencies (``Depends(require_principal)``) never run for it and the
``@app.middleware`` observability hook deliberately excludes its path prefix.
That left the public agent surface unauthenticated. This middleware wraps the
mount and reuses the SAME primitives the REST API uses — ``principal_for_headers``
(401), ``enforce_rate_limit`` (429 + Retry-After), ``get_meter`` (per-org usage) —
so the hosted ``/mcp`` gets identical org-scoped auth, rate-limiting, and metering.

``/mcp`` ALWAYS requires a key (``require=True``), independent of
``settings.require_auth``: even a dev server that leaves the curated read API open
keeps the agent surface closed. The local stdio transport never instantiates this
wrapper, so ``claude mcp add strata --command strata-mcp`` stays local-trust.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException

from .auth import principal_for_headers
from .metering import get_meter
from .ratelimit import enforce_rate_limit

# ASGI scope key under which the resolved Principal is stashed. This is
# FORWARD-WIRING: the auth gate resolves the principal now, but the MCP SDK's
# session manager does not yet thread scope["state"] into the tool handlers, so
# the tools still run org-agnostic (org_id="default"). Org-scoping the tool
# behaviour off this principal is Workstream B; the stash is here so that wiring
# has the principal available without re-resolving it.
_PRINCIPAL_STATE_KEY = "principal"


async def _send_json(
    send: Any, status: int, body: dict[str, str], headers: dict[str, str] | None = None
) -> None:
    payload = json.dumps(body).encode()
    raw_headers = [(b"content-type", b"application/json")]
    for k, v in (headers or {}).items():
        raw_headers.append((k.encode(), str(v).encode()))
    await send({"type": "http.response.start", "status": status, "headers": raw_headers})
    await send({"type": "http.response.body", "body": payload, "more_body": False})


class McpAuthMiddleware:
    """Wraps the ``build_streamable_http_app()`` result. Only HTTP requests are
    gated; lifespan / websocket scopes pass straight through to the inner app."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        try:
            principal = principal_for_headers(headers, require=True)  # 401 on miss/bad
        except HTTPException as exc:
            await _send_json(send, exc.status_code, {"error": str(exc.detail)})
            return
        try:
            enforce_rate_limit(principal.org_id)  # 429 + Retry-After
        except HTTPException as exc:
            extra = {k: str(v) for k, v in (exc.headers or {}).items()}
            await _send_json(send, exc.status_code, {"error": str(exc.detail)}, headers=extra)
            return

        scope = dict(scope)
        scope["state"] = {**scope.get("state", {}), _PRINCIPAL_STATE_KEY: principal}

        # Meter once, but only after the inner app reports a SUCCESSFUL response —
        # a malformed MCP request the session manager rejects (4xx/5xx) must not
        # inflate the org's usage (mirrors the REST observability MW, which skips
        # metering non-2xx). The observability MW skips /mcp, so this is the sole
        # meter for the route (no double-count).
        metered = False

        async def _metered_send(message: dict[str, Any]) -> None:
            nonlocal metered
            if (
                not metered
                and message.get("type") == "http.response.start"
                and int(message.get("status", 500)) < 400
            ):
                get_meter().record(principal.org_id, "/mcp")
                metered = True
            await send(message)

        await self.app(scope, receive, _metered_send)
