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
import time
from typing import Any

from fastapi import HTTPException

from ..config import settings
from .auth import (
    api_key_from_headers,
    bearer_token_from_headers,
    hash_key,
    is_cached,
    oauth_cache_fresh,
    principal_for_headers,
    register_hashed,
    register_oauth_token,
    unregister_oauth,
)
from .metering import get_meter
from .ratelimit import enforce_rate_limit

# An OAuth access token is any Bearer that is NOT a strata_sk_ key (those warm
# via the api-key path) and NOT a Clerk JWT (those verify by signature, no warm).
_API_KEY_PREFIX = "strata_sk_"

# ASGI scope key under which the resolved Principal is stashed (kept for any
# consumer that reads scope state). The tool handlers read the principal via the
# ``strata.mcp.context`` ContextVar set below, which DOES thread through the SDK.
_PRINCIPAL_STATE_KEY = "principal"

# Throttle for the best-effort ``last_used`` stamp: at most one DB write per key
# per window, so a chatty agent doesn't turn every tool call into a write.
_TOUCH_WINDOW_SECONDS = 60.0
_last_touch: dict[str, float] = {}


async def _ensure_key_loaded(headers: dict[str, str]) -> None:
    """DB-backed auth: if a presented X-API-Key isn't in the in-process cache
    (minted on another replica, or after a restart that lost the warm cache),
    look it up once and populate the cache so the sync auth path can resolve it.
    Best-effort — a DB hiccup just leaves the cache as-is (the request then 401s
    honestly rather than erroring). Resolves the key from X-API-Key OR a Bearer
    ``strata_sk_`` token, so a Bearer-presented key warms the cache too."""
    raw = api_key_from_headers(headers)
    if raw and not is_cached(hash_key(raw)):
        try:
            from ..db.api_keys import lookup_active
            from ..db.engine import session_scope

            async with session_scope() as session:
                row = await lookup_active(session, raw)
            if row is not None:
                scopes = tuple(s for s in (row.scopes or "*").split(",") if s) or ("*",)
                register_hashed(
                    row.key_hash, row.org_id, key_id=row.key_id or row.key_hash[:12], scopes=scopes
                )
        except Exception:  # auth must degrade to cache-only, never 500 on a DB blip
            pass
        return

    # Detection gap: ``api_key_from_headers`` returns None for any Bearer that is
    # not strata_sk_-prefixed, so an OAuth access token would silently skip the
    # warm above. Extract the raw Bearer directly. Skip strata_sk_ keys (handled
    # above), Clerk JWTs (opaque OAuth tokens are dot-free; a JWT has dots and
    # verifies by signature — never hits oauth_tokens, so the lookup would always
    # miss and waste a DB round-trip on every signed-in web request), and entries
    # already FRESH in the cache. A stale-but-present entry IS re-warmed so a
    # rotated/revoked token (revoked in DB) gets evicted within the cache TTL.
    bearer = bearer_token_from_headers(headers)
    if (
        not bearer
        or bearer.startswith(_API_KEY_PREFIX)
        or "." in bearer  # JWT-shaped → not an opaque OAuth token
        or oauth_cache_fresh(hash_key(bearer))
    ):
        return
    try:
        from ..db.engine import session_scope
        from ..db.oauth import lookup_access

        async with session_scope() as session:
            row = await lookup_access(session, bearer)
        # Only cache a token bound to OUR resource (audience) — a token minted
        # for a different resource must never authenticate here. A miss (revoked,
        # expired, or wrong-audience) EVICTS any stale entry so revocation in the
        # DB propagates to this process within the cache TTL.
        if (
            row is not None
            and settings.mcp_resource_url is not None
            and row.resource.rstrip("/") == settings.mcp_resource_url.rstrip("/")
        ):
            scopes = tuple(s for s in (row.scope or "*").split(",") if s) or ("*",)
            register_oauth_token(
                row.token_hash,
                org_id=row.org_id,
                user_id=row.user_id,
                resource=row.resource,
                expires_at=row.expires_at.timestamp(),
                scopes=scopes,
            )
        else:
            unregister_oauth(hash_key(bearer))
    except Exception:  # auth must degrade to cache-only, never 500 on a DB blip
        pass


async def _touch_last_used(headers: dict[str, str]) -> None:
    """Stamp ``last_used_at`` for the presented key, throttled and best-effort."""
    raw = api_key_from_headers(headers)
    if not raw:
        return
    key_hash = hash_key(raw)
    now = time.monotonic()
    if now - _last_touch.get(key_hash, 0.0) < _TOUCH_WINDOW_SECONDS:
        return
    _last_touch[key_hash] = now
    try:
        from ..db.api_keys import touch_last_used
        from ..db.engine import session_scope

        async with session_scope() as session:
            await touch_last_used(session, key_hash)
    except Exception:
        pass


async def _send_json(
    send: Any, status: int, body: dict[str, str], headers: dict[str, str] | None = None
) -> None:
    payload = json.dumps(body).encode()
    raw_headers = [(b"content-type", b"application/json")]
    for k, v in (headers or {}).items():
        raw_headers.append((k.encode(), str(v).encode()))
    await send({"type": "http.response.start", "status": status, "headers": raw_headers})
    await send({"type": "http.response.body", "body": payload, "more_body": False})


def _www_authenticate_header() -> dict[str, str] | None:
    """The RFC 9728 ``WWW-Authenticate`` challenge pointing at the
    protected-resource metadata, or ``None`` when the AS is not configured."""
    if not settings.oauth_enabled or not settings.oauth_issuer:
        return None
    base = settings.oauth_issuer.rstrip("/")
    resource_metadata = f"{base}/.well-known/oauth-protected-resource/mcp/"
    return {"WWW-Authenticate": f'Bearer resource_metadata="{resource_metadata}"'}


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
        await _ensure_key_loaded(headers)  # DB-backed lookup on cache miss
        try:
            principal = principal_for_headers(headers, require=True)  # 401 on miss/bad
        except HTTPException as exc:
            # On a 401, advertise OAuth discovery (RFC 9728) so a browser
            # connector (claude.ai / ChatGPT) can begin the OAuth flow instead of
            # failing silently. Only when the AS is configured; the static-key
            # clients (Claude Code/Desktop) ignore this header.
            extra = _www_authenticate_header() if exc.status_code == 401 else None
            await _send_json(send, exc.status_code, {"error": str(exc.detail)}, headers=extra)
            return
        try:
            enforce_rate_limit(principal.org_id)  # 429 + Retry-After
        except HTTPException as exc:
            extra = {k: str(v) for k, v in (exc.headers or {}).items()}
            await _send_json(send, exc.status_code, {"error": str(exc.detail)}, headers=extra)
            return

        await _touch_last_used(headers)  # best-effort staleness stamp

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

        # Thread the principal to the tool handlers. The SDK runs the tool call
        # within this awaited task, so a ContextVar set here is visible there
        # (scope["state"] is NOT threaded by the session manager).
        from ..mcp.context import current_principal

        token = current_principal.set(principal)
        try:
            await self.app(scope, receive, _metered_send)
        finally:
            current_principal.reset(token)
