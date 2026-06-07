"""OAuth AS endpoints — metadata, DCR, authorize, decision, token.

Metadata tests are pure (settings only). DCR / authorize / token hit the
oauth_* tables, so they require a live Postgres migrated to head (skipped
locally when unreachable). Clerk is mocked at the decision endpoint so the
consent path can be exercised without a real Clerk instance.
"""

from __future__ import annotations

import secrets
import socket
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from strata.api.clerk_auth import ClerkClaims
from strata.api.routes import oauth as oauth_routes
from strata.config import settings

_ISSUER = "https://api.example.test"
_RES = "https://api.example.test/mcp/"
_CONSENT = "https://app.example.test/oauth/authorize"
_CB = "https://claude.ai/api/mcp/auth_callback"


def _pg_reachable() -> bool:
    dsn = str(settings.database_url)
    try:
        hostport = dsn.split("@", 1)[1].split("/", 1)[0]
        host, _, port = hostport.partition(":")
        with socket.create_connection((host, int(port or 5432)), timeout=1.0):
            return True
    except (OSError, IndexError, ValueError):
        return False


_needs_pg = pytest.mark.skipif(not _pg_reachable(), reason="no Postgres reachable")


@pytest.fixture
def _configured(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setattr(settings, "oauth_issuer", _ISSUER)
    monkeypatch.setattr(settings, "mcp_resource_url", _RES)
    monkeypatch.setattr(settings, "oauth_consent_url", _CONSENT)


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    from strata.api.app import create_app

    app: FastAPI = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --------------------------------------------------------------------------- #
# U4 — metadata documents
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_protected_resource_metadata(_configured: None, client: AsyncClient) -> None:
    r = await client.get("/.well-known/oauth-protected-resource")
    assert r.status_code == 200
    body = r.json()
    assert body["resource"] == _RES  # byte-exact, trailing slash preserved
    assert body["authorization_servers"] == [_ISSUER]
    assert r.headers.get("access-control-allow-origin") == "*"


@pytest.mark.asyncio
async def test_protected_resource_metadata_mcp_suffixed(
    _configured: None, client: AsyncClient
) -> None:
    r = await client.get("/.well-known/oauth-protected-resource/mcp/")
    assert r.status_code == 200
    assert r.json()["resource"] == _RES


@pytest.mark.asyncio
async def test_authorization_server_metadata(_configured: None, client: AsyncClient) -> None:
    r = await client.get("/.well-known/oauth-authorization-server")
    assert r.status_code == 200
    body = r.json()
    assert body["issuer"] == _ISSUER  # issuer == authorization_servers[0], byte-identical
    assert body["authorization_endpoint"] == f"{_ISSUER}/oauth/authorize"
    assert body["token_endpoint"] == f"{_ISSUER}/oauth/token"
    assert body["registration_endpoint"] == f"{_ISSUER}/oauth/register"
    assert body["code_challenge_methods_supported"] == ["S256"]
    assert "none" in body["token_endpoint_auth_methods_supported"]


@pytest.mark.asyncio
async def test_metadata_404_when_unconfigured(client: AsyncClient) -> None:
    # No _configured fixture → AS not enabled → honest 404, not a half-doc.
    r = await client.get("/.well-known/oauth-authorization-server")
    assert r.status_code == 404


# --------------------------------------------------------------------------- #
# U6 — Dynamic Client Registration
# --------------------------------------------------------------------------- #
@_needs_pg
@pytest.mark.asyncio
async def test_dcr_accepts_claude_callback(_configured: None, client: AsyncClient) -> None:
    r = await client.post("/oauth/register", json={"redirect_uris": [_CB], "client_name": "Claude"})
    assert r.status_code == 201
    body = r.json()
    assert body["client_id"].startswith("client_")
    assert body["redirect_uris"] == [_CB]
    assert body["token_endpoint_auth_method"] == "none"


@_needs_pg
@pytest.mark.asyncio
async def test_dcr_rejects_off_allowlist_host(_configured: None, client: AsyncClient) -> None:
    r = await client.post("/oauth/register", json={"redirect_uris": ["https://evil.test/cb"]})
    assert r.status_code == 400


@_needs_pg
@pytest.mark.asyncio
async def test_dcr_rejects_empty_redirect_uris(_configured: None, client: AsyncClient) -> None:
    r = await client.post("/oauth/register", json={"redirect_uris": []})
    assert r.status_code == 400


# --------------------------------------------------------------------------- #
# U7 — authorize (GET validation + decision)
# --------------------------------------------------------------------------- #
async def _register(client: AsyncClient, redirect_uri: str = _CB) -> str:
    r = await client.post("/oauth/register", json={"redirect_uris": [redirect_uri]})
    return r.json()["client_id"]


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    return verifier, str(create_s256_code_challenge(verifier))


@_needs_pg
@pytest.mark.asyncio
async def test_authorize_redirects_to_consent_when_valid(
    _configured: None, client: AsyncClient
) -> None:
    client_id = await _register(client)
    _, challenge = _pkce()
    r = await client.get(
        "/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": _CB,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": _RES,
            "state": "xyz",
        },
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"].startswith(_CONSENT)
    assert "state=xyz" in r.headers["location"]


@_needs_pg
@pytest.mark.asyncio
async def test_authorize_rejects_unregistered_redirect_uri(
    _configured: None, client: AsyncClient
) -> None:
    client_id = await _register(client)
    _, challenge = _pkce()
    # A different (registered-elsewhere) claude.ai path is not THIS client's URI.
    r = await client.get(
        "/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": "https://claude.ai/api/mcp/OTHER",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": _RES,
        },
        follow_redirects=False,
    )
    assert r.status_code == 400  # and crucially NOT a 302 to the bad URI


@_needs_pg
@pytest.mark.asyncio
async def test_authorize_rejects_missing_pkce(_configured: None, client: AsyncClient) -> None:
    client_id = await _register(client)
    r = await client.get(
        "/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": _CB,
            "resource": _RES,
        },
        follow_redirects=False,
    )
    assert r.status_code == 400


@_needs_pg
@pytest.mark.asyncio
async def test_authorize_rejects_wrong_resource(_configured: None, client: AsyncClient) -> None:
    client_id = await _register(client)
    _, challenge = _pkce()
    r = await client.get(
        "/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": _CB,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": "https://wrong.test/mcp/",
        },
        follow_redirects=False,
    )
    assert r.status_code == 400


@_needs_pg
@pytest.mark.asyncio
async def test_decision_requires_clerk(_configured: None, client: AsyncClient) -> None:
    client_id = await _register(client)
    _, challenge = _pkce()
    r = await client.post(
        "/oauth/authorize/decision",
        json={
            "client_id": client_id,
            "redirect_uri": _CB,
            "code_challenge": challenge,
            "resource": _RES,
            "approve": True,
        },
    )
    assert r.status_code == 401  # no Clerk bearer → refused


def _mock_clerk(
    monkeypatch: pytest.MonkeyPatch, *, org_id: str | None, sub: str = "user_1"
) -> None:
    monkeypatch.setattr(
        oauth_routes,
        "verify_clerk_jwt",
        lambda _token: ClerkClaims(sub=sub, org_id=org_id, raw={}),
    )


@_needs_pg
@pytest.mark.asyncio
async def test_decision_deny_returns_access_denied(
    _configured: None, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_clerk(monkeypatch, org_id="org-x")
    client_id = await _register(client)
    _, challenge = _pkce()
    r = await client.post(
        "/oauth/authorize/decision",
        headers={"authorization": "Bearer clerk_fake"},
        json={
            "client_id": client_id,
            "redirect_uri": _CB,
            "code_challenge": challenge,
            "resource": _RES,
            "state": "s1",
            "approve": False,
        },
    )
    assert r.status_code == 200
    assert "error=access_denied" in r.json()["redirect_to"]
    assert "state=s1" in r.json()["redirect_to"]


# --------------------------------------------------------------------------- #
# U8 — token (full grant flow, replay, PKCE, refresh rotation)
# --------------------------------------------------------------------------- #
async def _full_grant_to_code(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, *, org_id: str = "org-x"
) -> tuple[str, str, str]:
    """Register → consent decision (mock Clerk) → return (client_id, code, verifier)."""
    _mock_clerk(monkeypatch, org_id=org_id)
    client_id = await _register(client)
    verifier, challenge = _pkce()
    r = await client.post(
        "/oauth/authorize/decision",
        headers={"authorization": "Bearer clerk_fake"},
        json={
            "client_id": client_id,
            "redirect_uri": _CB,
            "code_challenge": challenge,
            "resource": _RES,
            "approve": True,
        },
    )
    redirect_to = r.json()["redirect_to"]
    code = redirect_to.split("code=", 1)[1].split("&", 1)[0]
    return client_id, code, verifier


@_needs_pg
@pytest.mark.asyncio
async def test_token_happy_path(
    _configured: None, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client_id, code, verifier = await _full_grant_to_code(client, monkeypatch)
    r = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": _CB,
            "client_id": client_id,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "Bearer"
    assert body["access_token"].startswith("strata_oat_")
    assert body["refresh_token"].startswith("strata_ort_")
    assert body["expires_in"] == settings.oauth_access_ttl_seconds


@_needs_pg
@pytest.mark.asyncio
async def test_token_code_replay_rejected(
    _configured: None, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client_id, code, verifier = await _full_grant_to_code(client, monkeypatch)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": verifier,
        "redirect_uri": _CB,
        "client_id": client_id,
    }
    first = await client.post("/oauth/token", data=data)
    assert first.status_code == 200
    second = await client.post("/oauth/token", data=data)
    assert second.status_code == 400
    assert second.json()["error"] == "invalid_grant"


@_needs_pg
@pytest.mark.asyncio
async def test_token_pkce_mismatch_rejected(
    _configured: None, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client_id, code, _verifier = await _full_grant_to_code(client, monkeypatch)
    r = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": "wrong_verifier_entirely",
            "redirect_uri": _CB,
            "client_id": client_id,
        },
    )
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_grant"


@_needs_pg
@pytest.mark.asyncio
async def test_bad_verifier_does_not_burn_code(
    _configured: None, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed PKCE exchange must NOT consume the code — the legitimate client
    can still redeem it with the correct verifier (review fix: peek-then-consume)."""
    client_id, code, verifier = await _full_grant_to_code(client, monkeypatch)
    bad = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": "definitely_the_wrong_verifier",
            "redirect_uri": _CB,
            "client_id": client_id,
        },
    )
    assert bad.status_code == 400
    # The code survived the bad attempt — the correct verifier still works.
    good = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": _CB,
            "client_id": client_id,
        },
    )
    assert good.status_code == 200


@_needs_pg
@pytest.mark.asyncio
async def test_refresh_rotation_and_reuse(
    _configured: None, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    client_id, code, verifier = await _full_grant_to_code(client, monkeypatch)
    tok = (
        await client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": _CB,
                "client_id": client_id,
            },
        )
    ).json()
    # Rotate.
    rotated = await client.post(
        "/oauth/token",
        data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]},
    )
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != tok["refresh_token"]
    # Reuse of the OLD refresh token is rejected (rotation/reuse detection).
    reused = await client.post(
        "/oauth/token",
        data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]},
    )
    assert reused.status_code == 400
    assert reused.json()["error"] == "invalid_grant"


@_needs_pg
@pytest.mark.asyncio
async def test_token_unsupported_grant(_configured: None, client: AsyncClient) -> None:
    r = await client.post("/oauth/token", data={"grant_type": "password"})
    assert r.status_code == 400
    assert r.json()["error"] == "unsupported_grant_type"
