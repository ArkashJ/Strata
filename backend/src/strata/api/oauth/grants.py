"""PKCE verification (KTD-5).

We do NOT hand-roll the S256 transform — authlib's
``create_s256_code_challenge`` is the audited primitive (base64url(sha256(verifier))
with the correct no-padding encoding). We only wrap it with a constant-time
compare and the OAuth 2.1 policy that ``plain`` is never accepted.

The async grant orchestration (consume code → issue/rotate token) lives in the
route handlers; authlib's sync ``AuthorizationServer`` machinery is deliberately
not used (it is Flask/Django-coupled and would fight the async FastAPI stack).
"""

from __future__ import annotations

import hmac

from authlib.oauth2.rfc7636 import create_s256_code_challenge


def verify_pkce_s256(*, code_verifier: str, code_challenge: str) -> bool:
    """True iff ``code_verifier`` matches ``code_challenge`` under S256.

    Constant-time compare. ``plain`` is intentionally unsupported — callers must
    have rejected any non-S256 ``code_challenge_method`` at ``/authorize``."""
    if not code_verifier or not code_challenge:
        return False
    expected = str(create_s256_code_challenge(code_verifier))  # authlib is untyped
    return hmac.compare_digest(expected, code_challenge)
