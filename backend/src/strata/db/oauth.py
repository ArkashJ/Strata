"""OAuth 2.1 persistence — clients, single-use codes, opaque rotating tokens.

The async counterpart to ``db/api_keys.py``. Pure persistence + crypto-of-the-hash:
raw secrets (authorization codes, access tokens, refresh tokens) are returned
ONCE to the caller and never stored — only their sha256 hash lives in Postgres,
exactly like an API key. The grant orchestration (validate → consume → issue →
rotate) lives in the async route handlers (``api/routes/oauth.py``); this module
is the storage substrate they call.

KTD-2: the three tables are NOT under RLS — a code/token is resolved by hash
before any ``org_id`` is known. The row *carries* ``org_id``; the resolved
principal then drives ``org_session_scope`` + RLS on the data tables.

Token prefixes are deliberately distinct from ``strata_sk_`` so an OAuth bearer
is never mistaken for an API key by the RS auth path (which prefix-detects
``strata_sk_`` first). Opaque (urlsafe, no dots) so they also can't be mistaken
for a Clerk JWT.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from strata.api.auth import hash_key
from strata.db.models import OAuthAuthCodeRow, OAuthClientRow, OAuthTokenRow

_CLIENT_PREFIX = "client_"
_CODE_PREFIX = "strata_oac_"  # oauth authorization code
_ACCESS_PREFIX = "strata_oat_"  # oauth access token
_REFRESH_PREFIX = "strata_ort_"  # oauth refresh token
_SECRET_BYTES = 24  # ≈192 bits of entropy


def _now() -> datetime:
    return datetime.now().astimezone()


# --------------------------------------------------------------------------- #
# Clients (RFC 7591 dynamic client registration)
# --------------------------------------------------------------------------- #
async def register_client(
    session: AsyncSession, *, redirect_uris: list[str], client_name: str | None
) -> str:
    """Persist a dynamically-registered client; return its public ``client_id``."""
    client_id = _CLIENT_PREFIX + secrets.token_urlsafe(_SECRET_BYTES)
    session.add(
        OAuthClientRow(
            client_id=client_id,
            redirect_uris=list(redirect_uris),
            client_name=(client_name or None),
        )
    )
    await session.flush()
    return client_id


async def get_client(session: AsyncSession, client_id: str) -> OAuthClientRow | None:
    return (
        await session.execute(select(OAuthClientRow).where(OAuthClientRow.client_id == client_id))
    ).scalar_one_or_none()


# --------------------------------------------------------------------------- #
# Authorization codes (short-lived, single-use)
# --------------------------------------------------------------------------- #
async def create_auth_code(
    session: AsyncSession,
    *,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    code_challenge_method: str,
    resource: str,
    org_id: str,
    user_id: str | None,
    scope: str,
    ttl_seconds: int,
) -> str:
    """Mint a single-use code bound to the grant. Returns the raw code (stored hashed)."""
    raw = _CODE_PREFIX + secrets.token_urlsafe(_SECRET_BYTES)
    session.add(
        OAuthAuthCodeRow(
            code_hash=hash_key(raw),
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            resource=resource,
            org_id=org_id,
            user_id=user_id,
            scope=scope,
            expires_at=_now() + timedelta(seconds=ttl_seconds),
        )
    )
    await session.flush()
    return raw


async def peek_auth_code(session: AsyncSession, raw_code: str) -> OAuthAuthCodeRow | None:
    """Read a live (unconsumed, unexpired) code WITHOUT consuming it, so the
    caller can verify PKCE + redirect/client match BEFORE the single-use consume.
    This means a bad ``code_verifier`` does not burn a legitimate client's code.
    Expiry is evaluated by Postgres (``func.now()``) to avoid app/DB clock skew."""
    return (
        await session.execute(
            select(OAuthAuthCodeRow).where(
                OAuthAuthCodeRow.code_hash == hash_key(raw_code),
                OAuthAuthCodeRow.consumed_at.is_(None),
                OAuthAuthCodeRow.expires_at > func.now(),
            )
        )
    ).scalar_one_or_none()


async def consume_auth_code(session: AsyncSession, raw_code: str) -> OAuthAuthCodeRow | None:
    """Atomically mark a code consumed and return it — only if not already
    consumed and not expired. A second call returns ``None`` (single-use).

    The ``WHERE consumed_at IS NULL`` clause in the UPDATE is the lock: two
    concurrent exchanges race on the same row and exactly one wins, so a replay
    can never succeed even under concurrency. ``RETURNING`` the row avoids a
    second SELECT (which could race a cleanup delete and raise). Expiry and the
    consumed-at stamp are evaluated by Postgres (``func.now()``)."""
    stmt = (
        update(OAuthAuthCodeRow)
        .where(
            OAuthAuthCodeRow.code_hash == hash_key(raw_code),
            OAuthAuthCodeRow.consumed_at.is_(None),
            OAuthAuthCodeRow.expires_at > func.now(),
        )
        .values(consumed_at=func.now())
        .returning(OAuthAuthCodeRow)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


# --------------------------------------------------------------------------- #
# Tokens (opaque access + rotating refresh)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class IssuedToken:
    """The raw secrets a caller must return to the client exactly once, plus the
    persisted access-token TTL (for the ``expires_in`` response field)."""

    access_token: str
    refresh_token: str
    expires_in: int
    scope: str


async def issue_token(
    session: AsyncSession,
    *,
    client_id: str,
    org_id: str,
    user_id: str | None,
    scope: str,
    resource: str,
    access_ttl_seconds: int,
    refresh_ttl_seconds: int,
) -> IssuedToken:
    """Issue an opaque access + refresh pair, persisted hashed and bound to org+resource."""
    raw_access = _ACCESS_PREFIX + secrets.token_urlsafe(_SECRET_BYTES)
    raw_refresh = _REFRESH_PREFIX + secrets.token_urlsafe(_SECRET_BYTES)
    now = _now()
    session.add(
        OAuthTokenRow(
            token_hash=hash_key(raw_access),
            refresh_hash=hash_key(raw_refresh),
            client_id=client_id,
            org_id=org_id,
            user_id=user_id,
            scope=scope,
            resource=resource,
            expires_at=now + timedelta(seconds=access_ttl_seconds),
            refresh_expires_at=now + timedelta(seconds=refresh_ttl_seconds),
        )
    )
    await session.flush()
    return IssuedToken(
        access_token=raw_access,
        refresh_token=raw_refresh,
        expires_in=access_ttl_seconds,
        scope=scope,
    )


async def lookup_access(session: AsyncSession, raw_access: str) -> OAuthTokenRow | None:
    """Resolve a raw access token to its live row by hash — None if absent,
    expired, or revoked. The RS auth path's DB cold-warm calls this."""
    return (
        await session.execute(
            select(OAuthTokenRow).where(
                OAuthTokenRow.token_hash == hash_key(raw_access),
                OAuthTokenRow.revoked_at.is_(None),
                OAuthTokenRow.expires_at > func.now(),
            )
        )
    ).scalar_one_or_none()


async def rotate_refresh(
    session: AsyncSession,
    raw_refresh: str,
    *,
    access_ttl_seconds: int,
    refresh_ttl_seconds: int,
) -> IssuedToken | None:
    """Rotate a refresh token: atomically revoke the presented one and issue a
    new pair carrying the same org/client/scope/resource. Returns ``None`` when
    the refresh is unknown, already-revoked (reuse!), or expired.

    Revoking the old row via ``WHERE revoked_at IS NULL`` is the single-use lock —
    a reused refresh finds no live row and is rejected (reuse detection). Revoking
    also kills the old *access* token of that pair (``lookup_access`` filters on
    ``revoked_at``)."""
    stmt = (
        update(OAuthTokenRow)
        .where(
            OAuthTokenRow.refresh_hash == hash_key(raw_refresh),
            OAuthTokenRow.revoked_at.is_(None),
            OAuthTokenRow.refresh_expires_at > func.now(),
        )
        .values(revoked_at=func.now())
        .returning(
            OAuthTokenRow.client_id,
            OAuthTokenRow.org_id,
            OAuthTokenRow.user_id,
            OAuthTokenRow.scope,
            OAuthTokenRow.resource,
        )
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        return None
    return await issue_token(
        session,
        client_id=row.client_id,
        org_id=row.org_id,
        user_id=row.user_id,
        scope=row.scope,
        resource=row.resource,
        access_ttl_seconds=access_ttl_seconds,
        refresh_ttl_seconds=refresh_ttl_seconds,
    )
