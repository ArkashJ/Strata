"""Clerk session-JWT verification (PR 1 / KTD-3).

Verifies a Clerk-issued session JWT against Clerk's JWKS and returns its claims,
or ``None`` on any failure. This is the bridge that lets the backend see the
signed-in user behind a ``Authorization: Bearer`` request.

Three load-bearing properties (KTD-3):

- **Inert when unconfigured.** If ``settings.clerk_jwks_url`` is None (the
  keyless/dev default and current prod), ``verify_clerk_jwt`` returns ``None``
  immediately with **no network call** — so existing anonymous permalinks resolve
  with no 401 storm.
- **Never raises on the hot path.** Every PyJWT / network / parse error is caught
  and degraded to ``None`` ("no principal"). The caller decides 401 (prod) vs
  anonymous (dev); this module never produces a 500.
- **Key rotation aware.** The JWKS is fetched once and cached module-level by
  ``kid``. An unknown ``kid`` triggers a single refetch (Clerk rotated a key)
  before giving up.

Pattern: module-level frozen-ish caches mirror ``resolver/citations.py``; the
fetch is guarded by a lock so concurrent first requests don't stampede the JWKS
endpoint.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, cast

import httpx
import jwt
from jwt import PyJWKError, PyJWTError
from jwt.algorithms import RSAAlgorithm
from jwt.types import Options

from ..config import settings

_JWKS_FETCH_TIMEOUT_SECONDS = 5.0

# Module-level cache: kid -> verifying key object (an RSA public key). Populated
# lazily from the configured JWKS endpoint. Guarded by ``_JWKS_LOCK`` so the
# first concurrent requests don't all fetch at once.
_JWKS_KEYS: dict[str, Any] = {}
_JWKS_LOCK = threading.Lock()


@dataclass(frozen=True, slots=True)
class ClerkClaims:
    """The subset of a Clerk session token we act on."""

    sub: str
    org_id: str | None
    raw: dict[str, Any]


def _fetch_jwks(url: str) -> dict[str, Any]:
    """Fetch and index the JWKS by ``kid``. Returns {kid: verifying_key}.

    Any network / parse error propagates to the caller, which catches it and
    degrades to ``None`` — this function deliberately does not swallow so the
    refetch path can distinguish "fetched, still unknown" from "fetch failed".
    """
    resp = httpx.get(url, timeout=_JWKS_FETCH_TIMEOUT_SECONDS)
    resp.raise_for_status()
    doc = resp.json()
    keys: dict[str, Any] = {}
    for jwk in doc.get("keys", []):
        kid = jwk.get("kid")
        if not kid:
            continue
        keys[kid] = RSAAlgorithm.from_jwk(jwk)
    return keys


def _key_for_kid(kid: str, url: str, *, allow_refetch: bool) -> Any | None:
    """Return the cached verifying key for ``kid``, refetching the JWKS once on a
    miss (key rotation). Returns ``None`` if still unknown or on fetch error."""
    cached = _JWKS_KEYS.get(kid)
    if cached is not None:
        return cached
    if not allow_refetch:
        return None
    with _JWKS_LOCK:
        # Re-check under the lock — another thread may have refetched already.
        cached = _JWKS_KEYS.get(kid)
        if cached is not None:
            return cached
        try:
            fresh = _fetch_jwks(url)
        except Exception:
            return None
        _JWKS_KEYS.update(fresh)
    return _JWKS_KEYS.get(kid)


def _org_id_from(claims: dict[str, Any]) -> str | None:
    """Clerk carries the active org under ``org_id`` (or ``o.id`` in some token
    shapes). Return it as a plain string, or None for a personal-account token."""
    org = claims.get("org_id")
    if isinstance(org, str) and org:
        return org
    o = claims.get("o")
    if isinstance(o, dict):
        oid = cast(dict[str, Any], o).get("id")
        if isinstance(oid, str) and oid:
            return oid
    return None


def verify_clerk_jwt(token: str) -> ClerkClaims | None:
    """Verify a Clerk session JWT; return its claims or ``None`` on any failure.

    Inert (returns ``None`` without a network call) when ``clerk_jwks_url`` is
    unset. Never raises — every error degrades to ``None`` (KTD-3).
    """
    url = settings.clerk_jwks_url
    if not url:
        return None
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            return None
        key = _key_for_kid(kid, url, allow_refetch=True)
        if key is None:
            return None

        options: Options = {"verify_exp": True}
        verify_kwargs: dict[str, Any] = {}
        if settings.clerk_audience:
            verify_kwargs["audience"] = settings.clerk_audience
        else:
            options["verify_aud"] = False
        if settings.clerk_issuer:
            verify_kwargs["issuer"] = settings.clerk_issuer

        decoded: dict[str, Any] = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            options=options,
            **verify_kwargs,
        )
        sub = decoded.get("sub")
        if not isinstance(sub, str) or not sub:
            return None
        return ClerkClaims(sub=sub, org_id=_org_id_from(decoded), raw=decoded)
    except (PyJWTError, PyJWKError):
        return None
    except Exception:
        # Defense in depth: any unexpected error (network, key parsing, decode
        # internals) must not 500 the hot path.
        return None


def reset_jwks_cache() -> None:
    """Test hook — clear the module-level JWKS cache between cases."""
    with _JWKS_LOCK:
        _JWKS_KEYS.clear()
