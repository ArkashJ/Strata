"""Tests for the Clerk→Principal bridge in ``api/auth`` (PR 1 / U2).

The Clerk verifier itself is unit-tested in ``test_clerk_auth``; here we stub it
(``strata.api.auth.verify_clerk_jwt``) and assert the Bearer→Principal mapping,
the Bearer-before-API-key ordering, and the prod-vs-dev posture for an invalid
Bearer. Anonymous keeps ``user_id=None``; ``require_authenticated`` gates ``/me/*``.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from strata.api import auth
from strata.api.auth import (
    Principal,
    api_key_from_headers,
    principal_for_headers,
    register_key,
    require_authenticated,
)
from strata.api.clerk_auth import ClerkClaims
from strata.config import settings


class _FakeRequest:
    """Minimal stand-in for ``fastapi.Request`` (only ``.headers`` is read)."""

    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers


def _stub_verifier(monkeypatch: pytest.MonkeyPatch, result: ClerkClaims | None) -> None:
    monkeypatch.setattr(auth, "verify_clerk_jwt", lambda _token: result)


def test_valid_bearer_personal_account(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_verifier(monkeypatch, ClerkClaims(sub="user_42", org_id=None, raw={}))
    p = principal_for_headers({"authorization": "Bearer good.token"}, require=False)
    assert p.org_id == "clerk_user:user_42"
    assert p.user_id == "user_42"
    assert not p.is_anonymous


def test_valid_bearer_with_org_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_verifier(monkeypatch, ClerkClaims(sub="user_42", org_id="org_99", raw={}))
    p = principal_for_headers({"authorization": "Bearer good.token"}, require=False)
    assert p.org_id == "clerk_org:org_99"
    assert p.user_id == "user_42"


def test_bearer_case_insensitive_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_verifier(monkeypatch, ClerkClaims(sub="user_1", org_id=None, raw={}))
    p = principal_for_headers({"authorization": "bearer good.token"}, require=False)
    assert p.user_id == "user_1"


def test_invalid_bearer_prod_is_401(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_verifier(monkeypatch, None)
    monkeypatch.setattr(settings, "require_auth", True)
    with pytest.raises(HTTPException) as exc:
        principal_for_headers({"authorization": "Bearer bad"}, require=False)
    assert exc.value.status_code == 401


def test_invalid_bearer_require_flag_is_401(monkeypatch: pytest.MonkeyPatch) -> None:
    """``require=True`` (hosted surface) 401s an invalid Bearer even in dev."""
    _stub_verifier(monkeypatch, None)
    monkeypatch.setattr(settings, "require_auth", False)
    with pytest.raises(HTTPException) as exc:
        principal_for_headers({"authorization": "Bearer bad"}, require=True)
    assert exc.value.status_code == 401


def test_invalid_bearer_dev_falls_through_to_anonymous(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_verifier(monkeypatch, None)
    monkeypatch.setattr(settings, "require_auth", False)
    p = principal_for_headers({"authorization": "Bearer bad"}, require=False)
    assert p.is_anonymous
    assert p.user_id is None


def test_invalid_bearer_dev_falls_through_to_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bad Bearer in dev must not shadow a valid X-API-Key on the same request."""
    _stub_verifier(monkeypatch, None)
    monkeypatch.setattr(settings, "require_auth", False)
    register_key("bridge-key-1", "org_keyed")
    p = principal_for_headers(
        {"authorization": "Bearer bad", "x-api-key": "bridge-key-1"},
        require=False,
    )
    assert p.org_id == "org_keyed"
    assert p.user_id is None


def test_bearer_takes_precedence_over_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_verifier(monkeypatch, ClerkClaims(sub="user_7", org_id=None, raw={}))
    register_key("bridge-key-2", "org_keyed")
    p = principal_for_headers(
        {"authorization": "Bearer good", "x-api-key": "bridge-key-2"},
        require=False,
    )
    assert p.org_id == "clerk_user:user_7"
    assert p.user_id == "user_7"


def test_no_bearer_valid_api_key_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "require_auth", False)
    register_key("bridge-key-3", "org_keyed")
    p = principal_for_headers({"x-api-key": "bridge-key-3"}, require=False)
    assert p.org_id == "org_keyed"
    assert p.user_id is None


def test_no_auth_dev_is_anonymous(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "require_auth", False)
    p = principal_for_headers({}, require=False)
    assert p.is_anonymous
    assert p.user_id is None


def test_no_auth_prod_is_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "require_auth", True)
    with pytest.raises(HTTPException) as exc:
        principal_for_headers({}, require=False)
    assert exc.value.status_code == 401


def test_non_bearer_authorization_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ``Basic`` (non-Bearer) Authorization header is not treated as Clerk."""

    def _boom(_token: str) -> ClerkClaims | None:
        raise AssertionError("verifier must not run for non-Bearer schemes")

    monkeypatch.setattr(auth, "verify_clerk_jwt", _boom)
    monkeypatch.setattr(settings, "require_auth", False)
    p = principal_for_headers({"authorization": "Basic abc123"}, require=False)
    assert p.is_anonymous


def test_require_authenticated_rejects_anonymous(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "require_auth", False)
    req: Any = _FakeRequest({})
    with pytest.raises(HTTPException) as exc:
        require_authenticated(req)
    assert exc.value.status_code == 401


def test_require_authenticated_passes_clerk_principal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_verifier(monkeypatch, ClerkClaims(sub="user_88", org_id=None, raw={}))
    req: Any = _FakeRequest({"authorization": "Bearer good"})
    p = require_authenticated(req)
    assert isinstance(p, Principal)
    assert p.user_id == "user_88"
    assert not p.is_anonymous


# ── Bearer-presented Strata API key (the website "Connect to Claude" snippet) ──


def test_strata_key_as_bearer_resolves(monkeypatch: pytest.MonkeyPatch) -> None:
    """A minted ``strata_sk_`` key pasted as ``Authorization: Bearer …`` resolves
    to its org — the website snippets do exactly this against the hosted /mcp."""

    def _boom(_token: str) -> ClerkClaims | None:
        raise AssertionError("Clerk verifier must not run for a strata_sk_ Bearer token")

    monkeypatch.setattr(auth, "verify_clerk_jwt", _boom)
    register_key("strata_sk_live_demo123", "org_keyed")
    p = principal_for_headers({"authorization": "Bearer strata_sk_live_demo123"}, require=True)
    assert p.org_id == "org_keyed"
    assert not p.is_anonymous


def test_invalid_strata_key_as_bearer_is_401(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unknown ``strata_sk_`` Bearer is a hard 401 even in dev — a present but
    wrong key is a failed auth attempt, never an anonymous read."""
    monkeypatch.setattr(settings, "require_auth", False)
    with pytest.raises(HTTPException) as exc:
        principal_for_headers({"authorization": "Bearer strata_sk_live_nope"}, require=False)
    assert exc.value.status_code == 401


def test_api_key_from_headers_variants() -> None:
    """The shared extractor pulls the key from X-API-Key OR a Bearer strata_sk_
    token, and returns None for a Clerk Bearer JWT."""
    assert api_key_from_headers({"x-api-key": "strata_sk_live_x"}) == "strata_sk_live_x"
    assert api_key_from_headers({"authorization": "Bearer strata_sk_live_y"}) == "strata_sk_live_y"
    assert api_key_from_headers({"authorization": "Bearer some.clerk.jwt"}) is None
    assert api_key_from_headers({}) is None
