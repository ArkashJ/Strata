"""DB-free unit tests for the open-redirect defense and PKCE verification.

These guard the two load-bearing security primitives that were previously only
exercised through Postgres-gated endpoint tests (which skip without a DB): the
``redirect_uri`` trusted-host allowlist and the S256 PKCE check. They run in any
environment, so the open-redirect and PKCE-downgrade defenses are always covered.
"""

from __future__ import annotations

import pytest
from authlib.oauth2.rfc7636 import create_s256_code_challenge

from strata.api.oauth.allowlist import is_trusted_redirect_uri
from strata.api.oauth.grants import verify_pkce_s256


# --------------------------------------------------------------------------- #
# is_trusted_redirect_uri — the open-redirect host allowlist
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "uri",
    [
        "https://claude.ai/api/mcp/auth_callback",
        "https://chatgpt.com/connector/oauth/abc123",
        "https://chatgpt.com/connector_platform_oauth_redirect",
        "https://chat.openai.com/cb",
        "http://127.0.0.1:8765/callback",
        "http://localhost:52000/cb",
        "http://[::1]:9000/cb",
    ],
)
def test_trusted_redirect_uris_accepted(uri: str) -> None:
    assert is_trusted_redirect_uri(uri) is True


@pytest.mark.parametrize(
    "uri",
    [
        # userinfo-spoof: trusted host in userinfo, attacker host is the real host
        "https://claude.ai@evil.test/cb",
        # userinfo-spoof the other way: attacker in userinfo, trusted real host —
        # rejected because we refuse ANY credentials in the URL
        "https://evil.test@claude.ai/cb",
        "https://user:pass@claude.ai/cb",
        # off-allowlist public hosts
        "https://evil.test/cb",
        "https://claude.ai.evil.test/cb",
        "https://notclaude.ai/cb",
        # non-loopback http (only loopback may use http)
        "http://evil.test/cb",
        "http://claude.ai/cb",
        # wrong scheme
        "ftp://claude.ai/cb",
        "javascript:alert(1)",
        "data:text/html,x",
        # garbage / empty
        "not a url",
        "",
        "https://",
    ],
)
def test_untrusted_redirect_uris_rejected(uri: str) -> None:
    assert is_trusted_redirect_uri(uri) is False


# --------------------------------------------------------------------------- #
# verify_pkce_s256 — PKCE S256 verification
# --------------------------------------------------------------------------- #
def test_pkce_matching_verifier_accepted() -> None:
    verifier = "a" * 64
    challenge = str(create_s256_code_challenge(verifier))
    assert verify_pkce_s256(code_verifier=verifier, code_challenge=challenge) is True


def test_pkce_mismatched_verifier_rejected() -> None:
    challenge = str(create_s256_code_challenge("a" * 64))
    assert verify_pkce_s256(code_verifier="b" * 64, code_challenge=challenge) is False


@pytest.mark.parametrize(
    ("verifier", "challenge"),
    [
        ("", "somechallenge"),
        ("someverifier", ""),
        ("", ""),
    ],
)
def test_pkce_empty_inputs_rejected(verifier: str, challenge: str) -> None:
    # An empty verifier or challenge must never validate (no PKCE bypass).
    assert verify_pkce_s256(code_verifier=verifier, code_challenge=challenge) is False
