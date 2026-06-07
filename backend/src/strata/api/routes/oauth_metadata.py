"""OAuth 2.1 discovery documents (RFC 9728 + RFC 8414).

These are the docs claude.ai / ChatGPT fetch — from the **browser** — to learn
how to authenticate to the hosted MCP. They are unauthenticated and CORS-open
(``Access-Control-Allow-Origin: *``); they carry no secrets, only public URLs.

Load-bearing invariants (the top causes of a silent claude.ai connect failure):
- ``issuer`` == ``authorization_servers[0]`` == the origin that served the doc,
  **byte-identical** (``STRATA_OAUTH_ISSUER`` must be set to the exact API origin).
- ``resource`` in the protected-resource doc == the URL the user typed for the
  connector (``STRATA_MCP_RESOURCE_URL``, trailing slash and all) — Anthropic
  matches it exactly.
- The **path-suffixed** ``/.well-known/oauth-protected-resource/mcp/`` variant
  exists alongside the bare one (some clients probe the suffixed form).

When the AS is not configured (either env unset) every route 404s — an honest
"not enabled" rather than a half-formed document that would mislead a client.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from strata.config import settings

router = APIRouter(tags=["oauth"])

# CORS for these unauth, browser-fetched docs is owned entirely by the app-level
# CORSMiddleware (app.py), which allowlists claude.ai / chatgpt.com / chat.openai.com
# in prod and any localhost in dev. We must NOT also set a manual
# ``Access-Control-Allow-Origin`` here — the middleware echoes the request Origin,
# so a second header would make the browser see two ACAO values and reject the
# response (the exact failure that silently breaks a claude.ai connect).


def _require_enabled() -> tuple[str, str]:
    """Return ``(issuer, resource)`` or 404 when the AS is not configured."""
    if not settings.oauth_enabled or not settings.oauth_issuer or not settings.mcp_resource_url:
        raise HTTPException(status_code=404, detail="oauth not configured")
    return settings.oauth_issuer, settings.mcp_resource_url


def _protected_resource_doc() -> dict[str, Any]:
    issuer, resource = _require_enabled()
    return {"resource": resource, "authorization_servers": [issuer]}


@router.get("/.well-known/oauth-protected-resource", include_in_schema=False)
async def protected_resource() -> JSONResponse:
    """RFC 9728 — point the client at the Authorization Server for this resource."""
    return JSONResponse(_protected_resource_doc())


# RFC 9728 §3.1 forms the probe URL by inserting ``/.well-known/oauth-protected-resource``
# before the resource's path component, so a resource of ``…/mcp`` or ``…/mcp/`` yields
# ``…/oauth-protected-resource/mcp`` or ``…/oauth-protected-resource/mcp/`` respectively.
# Register BOTH path-suffixed variants so a client probing either form resolves (the
# trailing-slash sensitivity is the same class of bug that breaks the /mcp/ redirect).
@router.get("/.well-known/oauth-protected-resource/mcp", include_in_schema=False)
@router.get("/.well-known/oauth-protected-resource/mcp/", include_in_schema=False)
async def protected_resource_mcp_suffixed() -> JSONResponse:
    """Path-suffixed RFC 9728 probe variant (same body as the bare route)."""
    return JSONResponse(_protected_resource_doc())


@router.get("/.well-known/oauth-authorization-server", include_in_schema=False)
async def authorization_server_metadata() -> JSONResponse:
    """RFC 8414 — advertise the AS endpoints, PKCE S256, and public-client auth."""
    issuer, _ = _require_enabled()
    base = issuer.rstrip("/")
    doc = {
        "issuer": issuer,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
    }
    return JSONResponse(doc)
