"""OAuth 2.1 Authorization Server endpoints — DCR, authorize, token.

The interactive flow (carry this mental model):

    connector ──GET /oauth/authorize──▶ (validate) ──302──▶ frontend consent page
    frontend (Clerk-gated) ──POST /oauth/authorize/decision (Clerk Bearer)──▶ mint code
                            ◀── { redirect_to: "<cb>?code=…&state=…" } ──
    connector ──POST /oauth/token (code + code_verifier)──▶ { access_token, refresh_token }

Design (KTD-5): authlib supplies only the PKCE S256 primitive (``oauth.grants``);
the grant orchestration here is async-native and backed by ``db.oauth``. The
three tables are not under RLS (KTD-2), so these handlers use the plain
non-tenant session — org isolation rides on the token's carried ``org_id`` and
the RFC 8707 audience check at the Resource Server.

Security posture:
- ``redirect_uri`` must exact-match a DCR-registered URI AND pass the
  trusted-host allowlist; a bad ``redirect_uri`` is a 400, never a redirect
  (open-redirect defense).
- PKCE ``S256`` is mandatory; ``plain`` / missing challenge is rejected (no downgrade).
- ``resource`` (RFC 8707) must equal our MCP URL; it is bound into the code and
  inherited by the issued token's audience.
- The authorization code is single-use; the refresh token rotates on use.
- Consent requires a real verified Clerk identity — never an auto-consented org.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from strata.api.clerk_auth import verify_clerk_jwt
from strata.api.oauth.allowlist import is_trusted_redirect_uri
from strata.api.oauth.grants import verify_pkce_s256
from strata.config import settings
from strata.db import oauth
from strata.db.engine import get_session

router = APIRouter(tags=["oauth"])

_SESSION = Depends(get_session)
_BEARER_PREFIX = "bearer "


def _require_enabled() -> tuple[str, str]:
    if not settings.oauth_enabled or not settings.oauth_issuer or not settings.mcp_resource_url:
        raise HTTPException(status_code=404, detail="oauth not configured")
    return settings.oauth_issuer, settings.mcp_resource_url


# --------------------------------------------------------------------------- #
# DCR — POST /oauth/register (RFC 7591, accept-any)
# --------------------------------------------------------------------------- #
class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    # Optional at the schema level so a missing/empty value is our explicit 400,
    # not FastAPI's 422 — RFC 7591 clients expect an OAuth-shaped error.
    redirect_uris: list[str] | None = None
    client_name: str | None = None


@router.post("/oauth/register", status_code=201)
async def register(body: RegisterRequest, session: AsyncSession = _SESSION) -> dict[str, Any]:
    """Dynamic Client Registration. Accept-any per RFC 7591, but every declared
    ``redirect_uri`` must be an absolute URL on the trusted-host allowlist — a
    client cannot register a callback we would never be willing to redirect to."""
    _require_enabled()
    uris = body.redirect_uris or []
    if not uris:
        raise HTTPException(status_code=400, detail="redirect_uris is required")
    for uri in uris:
        if not is_trusted_redirect_uri(uri):
            raise HTTPException(status_code=400, detail=f"redirect_uri not allowed: {uri}")
    client_id = await oauth.register_client(
        session, redirect_uris=uris, client_name=body.client_name
    )
    await session.commit()
    return {
        "client_id": client_id,
        "redirect_uris": uris,
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
    }


# --------------------------------------------------------------------------- #
# Shared authorize-request validation
# --------------------------------------------------------------------------- #
async def _validate_authorize(
    session: AsyncSession,
    *,
    response_type: str,
    client_id: str,
    redirect_uri: str,
    code_challenge: str | None,
    code_challenge_method: str | None,
    resource: str | None,
) -> None:
    """Raise 400 on any invalid authorize parameter. Never redirects — a bad
    ``redirect_uri`` must surface as an error page, not an open redirect."""
    _, mcp_resource = _require_enabled()
    if response_type != "code":
        raise HTTPException(status_code=400, detail="unsupported_response_type")
    client = await oauth.get_client(session, client_id)
    if client is None:
        raise HTTPException(status_code=400, detail="unknown client_id")
    if redirect_uri not in (client.redirect_uris or []):
        raise HTTPException(status_code=400, detail="redirect_uri not registered for client")
    if not is_trusted_redirect_uri(redirect_uri):
        raise HTTPException(status_code=400, detail="redirect_uri not allowed")
    if not code_challenge or (code_challenge_method or "").upper() != "S256":
        raise HTTPException(status_code=400, detail="PKCE S256 code_challenge required")
    if not resource or resource != mcp_resource:
        raise HTTPException(status_code=400, detail="resource must match the MCP resource URL")


# --------------------------------------------------------------------------- #
# GET /oauth/authorize — validate, then bounce to the Clerk-gated consent page
# --------------------------------------------------------------------------- #
@router.get("/oauth/authorize")
async def authorize(
    request: Request,
    session: AsyncSession = _SESSION,
    response_type: str = "code",
    client_id: str = "",
    redirect_uri: str = "",
    code_challenge: str | None = None,
    code_challenge_method: str | None = None,
    resource: str | None = None,
    scope: str = "*",
    state: str | None = None,
) -> RedirectResponse:
    """Validate the request, then 302 the browser to the frontend consent page.

    The connector opens this cross-origin (no Clerk cookie), so we cannot mint a
    code here — we hand off to the Clerk-gated frontend, which collects consent
    and POSTs the decision back with a real session token."""
    await _validate_authorize(
        session,
        response_type=response_type,
        client_id=client_id,
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        resource=resource,
    )
    if not settings.oauth_consent_url:
        raise HTTPException(status_code=503, detail="consent UI not configured")
    params = {
        "response_type": response_type,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge or "",
        "code_challenge_method": (code_challenge_method or "S256"),
        "resource": resource or "",
        "scope": scope,
    }
    if state is not None:
        params["state"] = state
    sep = "&" if "?" in settings.oauth_consent_url else "?"
    return RedirectResponse(
        url=f"{settings.oauth_consent_url}{sep}{urlencode(params)}", status_code=302
    )


# --------------------------------------------------------------------------- #
# POST /oauth/authorize/decision — the frontend's approve/deny, Clerk-gated
# --------------------------------------------------------------------------- #
class AuthorizeDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")
    response_type: str = "code"
    client_id: str
    redirect_uri: str
    code_challenge: str
    code_challenge_method: str = "S256"
    resource: str
    scope: str = "*"
    state: str | None = None
    approve: bool


def _clerk_identity(request: Request) -> tuple[str, str]:
    """Resolve (org_id, user_id) from the request's Clerk Bearer, or 401.

    Mirrors ``auth.principal_for_headers``' org derivation exactly so an OAuth
    token maps to the same tenant the API-key + website session use."""
    authorization = request.headers.get("authorization", "")
    if not authorization.lower().startswith(_BEARER_PREFIX):
        raise HTTPException(status_code=401, detail="clerk session required")
    token = authorization[len(_BEARER_PREFIX) :].strip()
    claims = verify_clerk_jwt(token) if token else None
    if claims is None:
        raise HTTPException(status_code=401, detail="invalid clerk session")
    org_id = f"clerk_org:{claims.org_id}" if claims.org_id else f"clerk_user:{claims.sub}"
    return org_id, claims.sub


def _redirect_with(redirect_uri: str, params: dict[str, str]) -> str:
    sep = "&" if "?" in redirect_uri else "?"
    return f"{redirect_uri}{sep}{urlencode(params)}"


@router.post("/oauth/authorize/decision")
async def authorize_decision(
    body: AuthorizeDecision, request: Request, session: AsyncSession = _SESSION
) -> dict[str, str]:
    """Approve or deny, from the Clerk-gated consent page. On approve, mint a
    single-use code bound to the verified Clerk org and return the connector
    callback to navigate to; on deny, return the standard ``access_denied``
    error callback."""
    await _validate_authorize(
        session,
        response_type=body.response_type,
        client_id=body.client_id,
        redirect_uri=body.redirect_uri,
        code_challenge=body.code_challenge,
        code_challenge_method=body.code_challenge_method,
        resource=body.resource,
    )
    org_id, user_id = _clerk_identity(request)

    if not body.approve:
        params = {"error": "access_denied"}
        if body.state is not None:
            params["state"] = body.state
        return {"redirect_to": _redirect_with(body.redirect_uri, params)}

    raw_code = await oauth.create_auth_code(
        session,
        client_id=body.client_id,
        redirect_uri=body.redirect_uri,
        code_challenge=body.code_challenge,
        code_challenge_method="S256",
        resource=body.resource,
        org_id=org_id,
        user_id=user_id,
        scope=body.scope,
        ttl_seconds=600,
    )
    await session.commit()
    params = {"code": raw_code}
    if body.state is not None:
        params["state"] = body.state
    return {"redirect_to": _redirect_with(body.redirect_uri, params)}


# --------------------------------------------------------------------------- #
# POST /oauth/token — authorization_code + refresh_token grants
# --------------------------------------------------------------------------- #
def _oauth_error(error: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": error}, status_code=status)


@router.post("/oauth/token")
async def token(
    request: Request,
    session: AsyncSession = _SESSION,
    grant_type: str = Form(default=""),
    code: str = Form(default=""),
    code_verifier: str = Form(default=""),
    redirect_uri: str = Form(default=""),
    client_id: str = Form(default=""),
    refresh_token: str = Form(default=""),
) -> JSONResponse:
    """Token endpoint. ``authorization_code`` verifies PKCE S256 + single-use +
    redirect/client match, then issues an opaque access+refresh pair carrying the
    code's bound ``resource``. ``refresh_token`` rotates (old refresh revoked,
    reuse rejected)."""
    _require_enabled()

    if grant_type == "authorization_code":
        # Verify everything BEFORE consuming, so a bad code_verifier (client bug /
        # corruption) does not burn a legitimate, retryable code. The atomic
        # single-use guarantee is the consume step below.
        row = await oauth.peek_auth_code(session, code)
        if row is None:
            return _oauth_error("invalid_grant")
        if row.redirect_uri != redirect_uri or row.client_id != client_id:
            return _oauth_error("invalid_grant")
        if not verify_pkce_s256(code_verifier=code_verifier, code_challenge=row.code_challenge):
            return _oauth_error("invalid_grant")
        # All checks passed — now atomically consume. ``None`` means a concurrent
        # request won the race (replay protection), so this exchange fails.
        if await oauth.consume_auth_code(session, code) is None:
            return _oauth_error("invalid_grant")
        issued = await oauth.issue_token(
            session,
            client_id=row.client_id,
            org_id=row.org_id,
            user_id=row.user_id,
            scope=row.scope,
            resource=row.resource,
            access_ttl_seconds=settings.oauth_access_ttl_seconds,
            refresh_ttl_seconds=settings.oauth_refresh_ttl_seconds,
        )
        await session.commit()
        return JSONResponse(
            {
                "access_token": issued.access_token,
                "token_type": "Bearer",
                "expires_in": issued.expires_in,
                "refresh_token": issued.refresh_token,
                "scope": issued.scope,
            }
        )

    if grant_type == "refresh_token":
        issued = await oauth.rotate_refresh(
            session,
            refresh_token,
            access_ttl_seconds=settings.oauth_access_ttl_seconds,
            refresh_ttl_seconds=settings.oauth_refresh_ttl_seconds,
        )
        if issued is None:
            return _oauth_error("invalid_grant")
        await session.commit()
        return JSONResponse(
            {
                "access_token": issued.access_token,
                "token_type": "Bearer",
                "expires_in": issued.expires_in,
                "refresh_token": issued.refresh_token,
                "scope": issued.scope,
            }
        )

    return _oauth_error("unsupported_grant_type")
