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
import time
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


def _admin_orgs() -> frozenset[str]:
    """The set of org ids granted cross-tenant admin (from ``STRATA_ADMIN_ORGS``)."""
    return frozenset(o.strip() for o in settings.admin_orgs.split(",") if o.strip())


def is_admin(principal: Principal | None) -> bool:
    """True iff the principal's org is on the admin allowlist. An anonymous or
    unknown principal is never admin. Drives the cross-org feedback tools — the
    bypass is opt-in per org, audited, and additive to the closed tenant RLS."""
    if principal is None or principal.is_anonymous or principal.org_id == _ANONYMOUS_ORG:
        return False
    return principal.org_id in _admin_orgs()


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


# --------------------------------------------------------------------------- #
# OAuth access-token cache (the third bearer kind — KTD-4)
# --------------------------------------------------------------------------- #
# Opaque OAuth access tokens are resolved by hash, like API keys, but they
# EXPIRE — so the cache stores ``expires_at`` (epoch seconds) and the bound RFC
# 8707 ``resource``, and the resolution path enforces both. The cache is warmed
# from Postgres by the MCP middleware on a miss (mirror ``_KEY_STORE``); the DB
# row's expiry/revocation is authoritative at warm time.
# The cache entry is a SHORT-LIVED lookaside, not an authority for the token's
# whole lifetime. ``cache_until`` (a few seconds) bounds how long a warmed entry
# is trusted before the MCP middleware must re-warm it from Postgres; the DB row
# is where revocation lives. Without this, a refresh-rotated/revoked access token
# would keep authenticating from a stale cache entry until its full access TTL
# (and, across workers, revocation would never propagate). ``expires_at`` is the
# token's hard expiry; ``cache_until`` is the much-shorter re-warm horizon.
_OAUTH_CACHE_TTL_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class _OAuthEntry:
    principal: Principal
    resource: str
    expires_at: float  # token hard expiry, epoch seconds
    cache_until: float  # re-warm horizon, epoch seconds


_OAUTH_STORE: dict[str, _OAuthEntry] = {}


def _sweep_oauth_store(now: float) -> None:
    """Drop hard-expired entries so the cache can't grow without bound as tokens
    rotate (access tokens rotate on refresh; dead entries would otherwise linger
    until their exact hash was read again)."""
    for h in [h for h, e in _OAUTH_STORE.items() if e.expires_at <= now]:
        _OAUTH_STORE.pop(h, None)


def register_oauth_token(
    token_hash: str,
    *,
    org_id: str,
    user_id: str | None,
    resource: str,
    expires_at: float,
    scopes: tuple[str, ...] = ("*",),
) -> None:
    """Cache a DB-resolved OAuth access token so the sync auth path stays a dict
    lookup. ``expires_at`` is the token's hard expiry (epoch seconds); the entry
    is only trusted for ``_OAUTH_CACHE_TTL_SECONDS`` before a forced DB re-warm."""
    now = time.time()
    _sweep_oauth_store(now)
    _OAUTH_STORE[token_hash] = _OAuthEntry(
        principal=Principal(
            org_id=org_id, key_id=f"oauth:{token_hash[:12]}", scopes=scopes, user_id=user_id
        ),
        resource=resource,
        expires_at=expires_at,
        cache_until=now + _OAUTH_CACHE_TTL_SECONDS,
    )


def oauth_cached(token_hash: str) -> bool:
    """True iff an entry exists at all (regardless of freshness) — membership only."""
    return token_hash in _OAUTH_STORE


def oauth_cache_fresh(token_hash: str) -> bool:
    """True iff a cache entry exists and is still within its re-warm horizon and
    hard expiry. The MCP middleware re-warms from the DB whenever this is False,
    so revocation propagates within ``_OAUTH_CACHE_TTL_SECONDS`` (fleet-wide)."""
    entry = _OAUTH_STORE.get(token_hash)
    if entry is None:
        return False
    now = time.time()
    return now < entry.cache_until and now < entry.expires_at


def unregister_oauth(token_hash: str) -> None:
    """Evict an OAuth token from the cache (on re-warm miss = revoked/expired in DB)."""
    _OAUTH_STORE.pop(token_hash, None)


def reset_oauth_store() -> None:
    """Test hook — clear the in-process OAuth token cache between cases."""
    _OAUTH_STORE.clear()


def _oauth_principal_for(token: str) -> Principal | None:
    """Resolve an OAuth access token from the cache, enforcing expiry and the
    bound resource (audience). Returns ``None`` on miss / expiry / audience
    mismatch — the caller then 401s. Expired entries are evicted on read.

    Freshness/revocation is enforced upstream: the MCP middleware re-warms (or
    evicts) a stale entry from Postgres before this runs, so a revoked token has
    already been dropped here. This stays a pure cache read on the hot path."""
    entry = _OAUTH_STORE.get(hash_key(token))
    if entry is None:
        return None
    if entry.expires_at <= time.time():
        _OAUTH_STORE.pop(hash_key(token), None)
        return None
    # Audience check: a token bound to a different resource must never serve our
    # MCP — reject it (RFC 8707 audience-confusion defense).
    if entry.resource != settings.mcp_resource_url:
        return None
    return entry.principal


def bearer_token_from_headers(headers: Mapping[str, str]) -> str | None:
    """The raw Bearer credential a request presents (ANY kind), or ``None``.

    Unlike ``api_key_from_headers`` (which only returns ``strata_sk_`` Bearers),
    this returns whatever the client sent — so the MCP middleware can detect an
    OAuth access token and warm its cache from the DB."""
    authorization = headers.get(_AUTHORIZATION_HEADER)
    if authorization and authorization.lower().startswith(_BEARER_PREFIX):
        return authorization[len(_BEARER_PREFIX) :].strip() or None
    return None


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
        # Third bearer kind (KTD-4): an opaque OAuth access token — neither a
        # strata_sk_ key nor a Clerk JWT. Resolved from the oauth cache (warmed
        # from Postgres by the MCP middleware), with expiry + audience enforced.
        oauth_principal = _oauth_principal_for(token) if token else None
        if oauth_principal is not None:
            return oauth_principal
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
