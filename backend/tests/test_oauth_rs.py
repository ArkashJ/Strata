"""Resource-Server acceptance of OAuth access tokens (the third bearer branch).

Covers KTD-4 (oauth is a third branch, additive — strata_sk_ + Clerk unchanged),
the RFC 8707 audience check, token expiry eviction, the WWW-Authenticate 401
challenge, and the MCP middleware's DB cold-warm for an OAuth bearer. Cross-tenant
isolation is asserted at the principal level (org A's token resolves only as org A).
"""

from __future__ import annotations

import socket
import time

import pytest
from fastapi import HTTPException

from strata.api.auth import (
    hash_key,
    oauth_cached,
    principal_for_headers,
    register_key,
    register_oauth_token,
    reset_oauth_store,
    unregister,
)
from strata.config import settings

_RES = "https://api.example.test/mcp/"


@pytest.fixture(autouse=True)
def _clean_oauth_store():  # pyright: ignore[reportUnusedFunction]
    reset_oauth_store()
    yield
    reset_oauth_store()


@pytest.fixture
def _oauth_configured(monkeypatch: pytest.MonkeyPatch):  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setattr(settings, "oauth_issuer", "https://api.example.test")
    monkeypatch.setattr(settings, "mcp_resource_url", _RES)


def _hdr(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
# Third bearer branch — happy path, audience, expiry
# --------------------------------------------------------------------------- #
def test_oauth_token_resolves_to_its_org(_oauth_configured: None) -> None:
    tok = "strata_oat_alpha"
    register_oauth_token(
        hash_key(tok), org_id="org-a", user_id="u1", resource=_RES, expires_at=time.time() + 3600
    )
    principal = principal_for_headers(_hdr(tok), require=True)
    assert principal.org_id == "org-a"
    assert principal.user_id == "u1"


def test_oauth_audience_mismatch_rejected(_oauth_configured: None) -> None:
    """A token bound to a different resource must not authenticate here."""
    tok = "strata_oat_wrongaud"
    register_oauth_token(
        hash_key(tok),
        org_id="org-a",
        user_id=None,
        resource="https://someone-else.test/mcp/",
        expires_at=time.time() + 3600,
    )
    with pytest.raises(HTTPException) as exc:
        principal_for_headers(_hdr(tok), require=True)
    assert exc.value.status_code == 401


def test_oauth_expired_token_rejected_and_evicted(_oauth_configured: None) -> None:
    tok = "strata_oat_expired"
    register_oauth_token(
        hash_key(tok), org_id="org-a", user_id=None, resource=_RES, expires_at=time.time() - 1
    )
    with pytest.raises(HTTPException) as exc:
        principal_for_headers(_hdr(tok), require=True)
    assert exc.value.status_code == 401
    assert not oauth_cached(hash_key(tok))  # evicted on read


def test_oauth_cross_tenant_tokens_keep_their_own_org(_oauth_configured: None) -> None:
    register_oauth_token(
        hash_key("strata_oat_a"),
        org_id="org-a",
        user_id=None,
        resource=_RES,
        expires_at=time.time() + 3600,
    )
    register_oauth_token(
        hash_key("strata_oat_b"),
        org_id="org-b",
        user_id=None,
        resource=_RES,
        expires_at=time.time() + 3600,
    )
    assert principal_for_headers(_hdr("strata_oat_a"), require=True).org_id == "org-a"
    assert principal_for_headers(_hdr("strata_oat_b"), require=True).org_id == "org-b"


# --------------------------------------------------------------------------- #
# Additive: the existing two bearer paths are unchanged
# --------------------------------------------------------------------------- #
def test_strata_sk_key_still_resolves(_oauth_configured: None) -> None:
    register_key("strata_sk_live_regressioncheck", "org-key")
    try:
        principal = principal_for_headers(_hdr("strata_sk_live_regressioncheck"), require=True)
        assert principal.org_id == "org-key"
    finally:
        unregister(hash_key("strata_sk_live_regressioncheck"))


def test_unknown_bearer_is_401_when_required(_oauth_configured: None) -> None:
    with pytest.raises(HTTPException) as exc:
        principal_for_headers(_hdr("not_a_known_token"), require=True)
    assert exc.value.status_code == 401


# --------------------------------------------------------------------------- #
# WWW-Authenticate 401 challenge (RFC 9728)
# --------------------------------------------------------------------------- #
def test_www_authenticate_header_present_when_configured(_oauth_configured: None) -> None:
    from strata.api.mcp_auth import _www_authenticate_header  # pyright: ignore[reportPrivateUsage]

    hdr = _www_authenticate_header()
    assert hdr is not None
    assert "WWW-Authenticate" in hdr
    assert (
        hdr["WWW-Authenticate"]
        == 'Bearer resource_metadata="https://api.example.test/.well-known/oauth-protected-resource/mcp/"'
    )


def test_www_authenticate_header_none_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    from strata.api.mcp_auth import _www_authenticate_header  # pyright: ignore[reportPrivateUsage]

    monkeypatch.setattr(settings, "oauth_issuer", None)
    monkeypatch.setattr(settings, "mcp_resource_url", None)
    assert _www_authenticate_header() is None


# --------------------------------------------------------------------------- #
# MCP middleware DB cold-warm for an OAuth bearer (the detection-gap fix)
# --------------------------------------------------------------------------- #
def _pg_reachable() -> bool:
    dsn = str(settings.database_url)
    try:
        hostport = dsn.split("@", 1)[1].split("/", 1)[0]
        host, _, port = hostport.partition(":")
        with socket.create_connection((host, int(port or 5432)), timeout=1.0):
            return True
    except (OSError, IndexError, ValueError):
        return False


@pytest.mark.skipif(not _pg_reachable(), reason="no Postgres reachable")
@pytest.mark.asyncio
async def test_ensure_key_loaded_warms_oauth_bearer(_oauth_configured: None) -> None:
    """An OAuth bearer not in cache is resolved from oauth_tokens and cached,
    then the sync auth path returns its principal (the detection-gap fix)."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from strata.api.mcp_auth import _ensure_key_loaded  # pyright: ignore[reportPrivateUsage]
    from strata.db import oauth

    eng = create_async_engine(str(settings.database_url), poolclass=NullPool)
    async with eng.connect() as conn:
        if await conn.scalar(text("SELECT to_regclass('public.oauth_tokens')")) is None:
            await eng.dispose()
            pytest.skip("oauth tables not migrated")
    maker = async_sessionmaker(bind=eng, expire_on_commit=False)
    try:
        async with maker() as s, s.begin():
            issued = await oauth.issue_token(
                s,
                client_id="client_test",
                org_id="org-warm",
                user_id="u1",
                scope="*",
                resource=_RES,
                access_ttl_seconds=3600,
                refresh_ttl_seconds=86400,
            )
        # Not cached yet → warm from DB, then the sync path resolves it.
        assert not oauth_cached(hash_key(issued.access_token))
        await _ensure_key_loaded(_hdr(issued.access_token))
        assert oauth_cached(hash_key(issued.access_token))
        principal = principal_for_headers(_hdr(issued.access_token), require=True)
        assert principal.org_id == "org-warm"
    finally:
        await eng.dispose()
