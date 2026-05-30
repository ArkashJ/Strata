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
from dataclasses import dataclass, field

from fastapi import HTTPException, Request

from ..config import settings

_API_KEY_HEADER = "x-api-key"
_ANONYMOUS_ORG = "public"


@dataclass(frozen=True, slots=True)
class Principal:
    org_id: str
    key_id: str
    scopes: tuple[str, ...] = field(default_factory=tuple)

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


def _anonymous() -> Principal:
    return Principal(org_id=_ANONYMOUS_ORG, key_id="anonymous", scopes=("read",))


def principal_for(request: Request) -> Principal:
    """Resolve the request's Principal. Raises 401 only when auth is required and
    the key is missing/invalid."""
    raw = request.headers.get(_API_KEY_HEADER)
    if raw:
        principal = _KEY_STORE.get(hash_key(raw))
        if principal is not None:
            return principal
        # A *present but wrong* key is always a 401, even in dev — it's an
        # explicit (failed) auth attempt, not an anonymous read.
        raise HTTPException(status_code=401, detail="invalid API key")
    if settings.require_auth:
        raise HTTPException(status_code=401, detail="missing API key")
    return _anonymous()


def require_principal(request: Request) -> Principal:
    """FastAPI dependency for protected routes."""
    return principal_for(request)
