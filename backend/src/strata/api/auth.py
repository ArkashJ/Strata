"""API-key authentication (Wave 3 / AC3.1).

A request authenticates with an ``X-API-Key`` header. Keys are stored **hashed**
(sha256) in an in-process store seeded from ``settings.api_keys_raw``
(``rawkey:org_id`` pairs) for dev/self-host. A valid key resolves to a
``Principal`` carrying the tenant ``org_id`` used for rate-limiting, metering,
and Postgres RLS.

The ``api_keys`` Postgres table (migration 003) is the **forward scaffolding** for
a DB-backed key store; loading it at boot into ``_KEY_STORE`` is a follow-up — the
in-process store is the active path today.

When ``settings.require_auth`` is False (dev default) the protected routes still
run but under an anonymous ``public`` principal, so the curated read API stays
open locally. In prod (``require_auth=True``) a missing/invalid key is a 401.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from ..config import settings
from .clerk_auth import verify_clerk_jwt

_API_KEY_HEADER = "x-api-key"
_AUTHORIZATION_HEADER = "authorization"
_BEARER_PREFIX = "bearer "
_ANONYMOUS_ORG = "public"
# Minted Strata keys share this prefix (``db.api_keys._RAW_PREFIX`` =
# ``strata_sk_live_``). We match the shorter stem so a key presented as a Bearer
# token is recognised as an API key (not mistaken for a Clerk JWT) before we ever
# try to verify it as one.
_API_KEY_PREFIX = "strata_sk_"

# OpenAPI security scheme. Declared with ``auto_error=False`` so it is purely a
# *documentation* hook — it surfaces the ``X-API-Key`` header in ``/openapi.json``
# (and the Authorize button in ``/docs``) and marks any route that depends on it
# as secured, without itself rejecting requests. The actual key validation stays
# in ``principal_for`` below, which reads the header directly. The ``X-API-Key``
# name here must match ``_API_KEY_HEADER`` (case-insensitive).
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)
_SECURITY = Security(api_key_scheme)


@dataclass(frozen=True, slots=True)
class Principal:
    org_id: str
    key_id: str
    scopes: tuple[str, ...] = field(default_factory=tuple)
    # The Clerk subject (``sub``) behind a ``Authorization: Bearer`` request, or
    # ``None`` for an API-key / anonymous principal. Carried so write paths can
    # record a real ``created_by`` actor (PR 1 / U5).
    user_id: str | None = None

    @property
    def is_anonymous(self) -> bool:
        return self.key_id == "anonymous"


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _parse_key_store(raw_pairs: str) -> dict[str, Principal]:
    """``rawkey:org_id`` pairs → {sha256(rawkey): Principal}."""
    store: dict[str, Principal] = {}
    for pair in raw_pairs.split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        raw, org = pair.split(":", 1)
        raw, org = raw.strip(), org.strip()
        if raw and org:
            store[hash_key(raw)] = Principal(org_id=org, key_id=hash_key(raw)[:12], scopes=("*",))
    return store


# Built once at import from config; prod merges DB-stored keys via ``register_key``.
_KEY_STORE: dict[str, Principal] = _parse_key_store(settings.api_keys_raw)


def register_key(raw: str, org_id: str, scopes: tuple[str, ...] = ("*",)) -> None:
    _KEY_STORE[hash_key(raw)] = Principal(org_id=org_id, key_id=hash_key(raw)[:12], scopes=scopes)


def register_hashed(
    key_hash: str, org_id: str, *, key_id: str, scopes: tuple[str, ...] = ("*",)
) -> None:
    """Register an already-hashed, DB-persisted key into the in-process cache.

    Used at startup (warm the cache from ``api_keys``) and on mint (a freshly
    minted key is usable immediately, same process) — so the hot auth path stays
    a synchronous dict lookup with no per-request DB round-trip."""
    _KEY_STORE[key_hash] = Principal(org_id=org_id, key_id=key_id, scopes=scopes)


def unregister(key_hash: str) -> None:
    """Evict a key from the cache (on revoke) so it stops authenticating at once."""
    _KEY_STORE.pop(key_hash, None)


def is_cached(key_hash: str) -> bool:
    return key_hash in _KEY_STORE


def _anonymous() -> Principal:
    return Principal(org_id=_ANONYMOUS_ORG, key_id="anonymous", scopes=("read",))


def api_key_from_headers(headers: Mapping[str, str]) -> str | None:
    """The raw Strata API key a request presents, via ``X-API-Key`` OR a Bearer
    ``strata_sk_`` token. Returns ``None`` for a Clerk Bearer JWT or no key.

    The MCP middleware's DB cache-warm + last-used paths use this so a key
    presented as a Bearer token resolves on a cold replica too (not just keys
    sent in the ``X-API-Key`` header)."""
    raw = headers.get(_API_KEY_HEADER)
    if raw:
        return raw
    authorization = headers.get(_AUTHORIZATION_HEADER)
    if authorization and authorization.lower().startswith(_BEARER_PREFIX):
        token = authorization[len(_BEARER_PREFIX) :].strip()
        if token.startswith(_API_KEY_PREFIX):
            return token
    return None


def principal_for_headers(headers: Mapping[str, str], *, require: bool) -> Principal:
    """Resolve a Principal from raw request headers (transport-agnostic).

    Factored out of ``principal_for`` so the pure-ASGI ``/mcp`` middleware can
    authenticate without a FastAPI ``Request``. ``require=True`` forces a key
    even when ``settings.require_auth`` is off — the hosted agent surface stays
    closed regardless of the REST API's dev posture.

    Resolution order (KTD-4): ``Authorization: Bearer`` (Clerk) first, then
    ``X-API-Key``, then the anonymous/require fallback."""
    authorization = headers.get(_AUTHORIZATION_HEADER)
    if authorization and authorization.lower().startswith(_BEARER_PREFIX):
        token = authorization[len(_BEARER_PREFIX) :].strip()
        # A Strata API key presented as a Bearer token. The website's "Connect to
        # Claude" snippets paste the minted ``strata_sk_…`` key as
        # ``Authorization: Bearer …``, so resolve it exactly like the X-API-Key
        # path — a key minted on the site must work as a Bearer credential too.
        if token.startswith(_API_KEY_PREFIX):
            principal = _KEY_STORE.get(hash_key(token))
            if principal is not None:
                return principal
            raise HTTPException(status_code=401, detail="invalid API key")
        # Otherwise treat it as a Clerk session JWT (the signed-in web app).
        claims = verify_clerk_jwt(token) if token else None
        if claims is not None:
            org_id = f"clerk_org:{claims.org_id}" if claims.org_id else f"clerk_user:{claims.sub}"
            return Principal(
                org_id=org_id,
                key_id=f"clerk:{claims.sub}"[:64],
                scopes=("*",),
                user_id=claims.sub,
            )
        # A present-but-invalid Bearer is a 401 in prod (mirrors the wrong-key
        # rule); in dev the verifier is inert/lenient, so we fall through to the
        # anonymous path rather than locking out keyless reads.
        if require or settings.require_auth:
            raise HTTPException(status_code=401, detail="invalid bearer token")

    raw = headers.get(_API_KEY_HEADER)
    if raw:
        principal = _KEY_STORE.get(hash_key(raw))
        if principal is not None:
            return principal
        # A *present but wrong* key is always a 401, even in dev — it's an
        # explicit (failed) auth attempt, not an anonymous read.
        raise HTTPException(status_code=401, detail="invalid API key")
    if require or settings.require_auth:
        raise HTTPException(status_code=401, detail="missing API key")
    return _anonymous()


def principal_for(request: Request) -> Principal:
    """Resolve the request's Principal. Raises 401 only when auth is required and
    the key is missing/invalid."""
    return principal_for_headers(request.headers, require=settings.require_auth)


def require_principal(request: Request, _key: str | None = _SECURITY) -> Principal:
    """FastAPI dependency for protected routes. The ``_key`` parameter only wires
    the ``X-API-Key`` security scheme into OpenAPI; validation uses the request
    header directly via ``principal_for``."""
    return principal_for(request)


def require_authenticated(request: Request, _key: str | None = _SECURITY) -> Principal:
    """Stricter dependency for routes that handle tenant secrets / private data
    (Wave 5B): an anonymous ``public`` principal is rejected even in dev, so
    unauthenticated callers can never share one tenant bucket. The ``_key``
    parameter only wires the ``X-API-Key`` security scheme into OpenAPI."""
    principal = principal_for(request)
    if principal.is_anonymous:
        raise HTTPException(status_code=401, detail="authentication required")
    return principal
