"""Tests for the Clerk session-JWT verifier (PR 1 / U1).

Uses a freshly generated RSA keypair + a stubbed JWKS so no live Clerk instance
is needed. The single most important property: the verifier NEVER raises on the
hot path and is INERT when ``clerk_jwks_url`` is unset.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from strata.api import clerk_auth
from strata.config import settings

_KID = "test-kid-1"
_OTHER_KID = "test-kid-2"


def _make_keypair() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwks_for(key: rsa.RSAPrivateKey, kid: str) -> dict[str, Any]:
    pub_jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    pub_jwk["kid"] = kid
    pub_jwk["use"] = "sig"
    pub_jwk["alg"] = "RS256"
    return {"keys": [pub_jwk]}


def _sign(
    key: rsa.RSAPrivateKey,
    kid: str,
    *,
    claims: dict[str, Any] | None = None,
    exp_delta: int = 3600,
) -> str:
    now = dt.datetime.now(tz=dt.UTC)
    payload: dict[str, Any] = {
        "sub": "user_123",
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(seconds=exp_delta)).timestamp()),
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": kid})


@pytest.fixture(autouse=True)
def _clean_cache() -> Any:
    clerk_auth.reset_jwks_cache()
    yield
    clerk_auth.reset_jwks_cache()


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> rsa.RSAPrivateKey:
    """Point the verifier at a stubbed JWKS backed by a fresh keypair."""
    key = _make_keypair()
    jwks = _jwks_for(key, _KID)
    monkeypatch.setattr(settings, "clerk_jwks_url", "https://clerk.test/.well-known/jwks.json")
    monkeypatch.setattr(settings, "clerk_issuer", None)
    monkeypatch.setattr(settings, "clerk_audience", None)

    def _stub_fetch(url: str) -> dict[str, Any]:
        keys: dict[str, Any] = {}
        for j in jwks["keys"]:
            keys[j["kid"]] = RSAAlgorithm.from_jwk(j)
        return keys

    monkeypatch.setattr(clerk_auth, "_fetch_jwks", _stub_fetch)
    return key


def test_inert_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    """No JWKS url → returns None with no network attempt."""
    monkeypatch.setattr(settings, "clerk_jwks_url", None)

    def _boom(url: str) -> dict[str, Any]:
        raise AssertionError("must not fetch when inert")

    monkeypatch.setattr(clerk_auth, "_fetch_jwks", _boom)
    assert clerk_auth.verify_clerk_jwt("anything.at.all") is None


def test_valid_token_returns_claims(configured: rsa.RSAPrivateKey) -> None:
    token = _sign(configured, _KID)
    claims = clerk_auth.verify_clerk_jwt(token)
    assert claims is not None
    assert claims.sub == "user_123"
    assert claims.org_id is None


def test_org_claim_surfaces(configured: rsa.RSAPrivateKey) -> None:
    token = _sign(configured, _KID, claims={"org_id": "org_abc"})
    claims = clerk_auth.verify_clerk_jwt(token)
    assert claims is not None
    assert claims.org_id == "org_abc"


def test_org_claim_nested_shape(configured: rsa.RSAPrivateKey) -> None:
    token = _sign(configured, _KID, claims={"o": {"id": "org_nested"}})
    claims = clerk_auth.verify_clerk_jwt(token)
    assert claims is not None
    assert claims.org_id == "org_nested"


def test_expired_token_is_none(configured: rsa.RSAPrivateKey) -> None:
    token = _sign(configured, _KID, exp_delta=-10)
    assert clerk_auth.verify_clerk_jwt(token) is None


def test_bad_signature_is_none(configured: rsa.RSAPrivateKey) -> None:
    # Sign with a DIFFERENT key but the cached kid → signature won't verify.
    impostor = _make_keypair()
    token = _sign(impostor, _KID)
    assert clerk_auth.verify_clerk_jwt(token) is None


def test_unknown_kid_triggers_single_refetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unknown kid refetches once; if still unknown → None, and only one fetch."""
    key = _make_keypair()
    monkeypatch.setattr(settings, "clerk_jwks_url", "https://clerk.test/jwks")
    monkeypatch.setattr(settings, "clerk_issuer", None)
    monkeypatch.setattr(settings, "clerk_audience", None)

    calls = {"n": 0}
    jwks = _jwks_for(key, _KID)

    def _stub_fetch(url: str) -> dict[str, Any]:
        calls["n"] += 1
        return {j["kid"]: RSAAlgorithm.from_jwk(j) for j in jwks["keys"]}

    monkeypatch.setattr(clerk_auth, "_fetch_jwks", _stub_fetch)

    token = _sign(key, _OTHER_KID)  # kid never present in the JWKS
    assert clerk_auth.verify_clerk_jwt(token) is None
    assert calls["n"] == 1  # exactly one refetch, no stampede


def test_unknown_kid_refetch_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rotation: cache empty, refetch brings the key in → token verifies."""
    key = _make_keypair()
    monkeypatch.setattr(settings, "clerk_jwks_url", "https://clerk.test/jwks")
    monkeypatch.setattr(settings, "clerk_issuer", None)
    monkeypatch.setattr(settings, "clerk_audience", None)
    jwks = _jwks_for(key, _KID)

    def _stub_fetch(url: str) -> dict[str, Any]:
        return {j["kid"]: RSAAlgorithm.from_jwk(j) for j in jwks["keys"]}

    monkeypatch.setattr(clerk_auth, "_fetch_jwks", _stub_fetch)

    token = _sign(key, _KID)
    claims = clerk_auth.verify_clerk_jwt(token)
    assert claims is not None
    assert claims.sub == "user_123"


def test_issuer_mismatch_is_none(
    configured: rsa.RSAPrivateKey, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "clerk_issuer", "https://expected.clerk.dev")
    token = _sign(configured, _KID, claims={"iss": "https://attacker.example"})
    assert clerk_auth.verify_clerk_jwt(token) is None


def test_audience_mismatch_is_none(
    configured: rsa.RSAPrivateKey, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "clerk_audience", "strata-prod")
    token = _sign(configured, _KID, claims={"aud": "some-other-app"})
    assert clerk_auth.verify_clerk_jwt(token) is None


def test_audience_match_passes(
    configured: rsa.RSAPrivateKey, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "clerk_audience", "strata-prod")
    token = _sign(configured, _KID, claims={"aud": "strata-prod"})
    claims = clerk_auth.verify_clerk_jwt(token)
    assert claims is not None


def test_network_error_is_none_no_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    key = _make_keypair()
    monkeypatch.setattr(settings, "clerk_jwks_url", "https://clerk.test/jwks")
    monkeypatch.setattr(settings, "clerk_issuer", None)
    monkeypatch.setattr(settings, "clerk_audience", None)

    def _boom(url: str) -> dict[str, Any]:
        raise OSError("connection refused")

    monkeypatch.setattr(clerk_auth, "_fetch_jwks", _boom)
    token = _sign(key, _KID)
    # Must degrade to None, never propagate the network error.
    assert clerk_auth.verify_clerk_jwt(token) is None


def test_garbage_token_is_none(configured: rsa.RSAPrivateKey) -> None:
    assert clerk_auth.verify_clerk_jwt("not-a-jwt") is None
    assert clerk_auth.verify_clerk_jwt("") is None
