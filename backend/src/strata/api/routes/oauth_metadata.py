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

# These docs are fetched cross-origin from the browser by the connector UIs and
# carry no secrets, so a wildcard is correct and intentional.
_CORS_OPEN = {"Access-Control-Allow-Origin": "*"}


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
    return JSONResponse(_protected_resource_doc(), headers=_CORS_OPEN)


@router.get("/.well-known/oauth-protected-resource/mcp/", include_in_schema=False)
async def protected_resource_mcp_suffixed() -> JSONResponse:
    """Path-suffixed RFC 9728 probe variant (same body as the bare route)."""
    return JSONResponse(_protected_resource_doc(), headers=_CORS_OPEN)


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
    return JSONResponse(doc, headers=_CORS_OPEN)
