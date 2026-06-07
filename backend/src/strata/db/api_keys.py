"""Self-serve API-key lifecycle (mint / list / revoke / lookup).

A VC signs in, mints a key on the website, and pastes it into Claude as the
Bearer credential for the hosted ``/mcp`` connector. The raw secret
(``strata_sk_live_…``) is returned exactly ONCE at mint and never stored — only
its sha256 hash lives in Postgres. A key resolves to the minting org, so the
agent sees the same tenant world the website session does.

This module is pure persistence + crypto-of-the-hash; the in-process auth cache
(``strata.api.auth``) is updated by the routes/middleware that call these.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from strata.api.auth import hash_key
from strata.db.models import ApiKeyRow

# Public, recognizable, environment-tagged. "live" leaves room for a future
# "test" tier without reissuing the format.
_RAW_PREFIX = "strata_sk_live_"
# 32 urlsafe chars ≈ 192 bits of entropy — far past guessing range.
_SECRET_BYTES = 24


def generate_raw_key() -> str:
    return _RAW_PREFIX + secrets.token_urlsafe(_SECRET_BYTES)


def _masked_prefix(raw: str) -> str:
    """A fragment safe to store and show: the tag + first 4 of the secret + last
    4, e.g. ``strata_sk_live_a1b2…z9k0``. Enough to recognize a key in a list,
    not enough to use it."""
    secret = raw[len(_RAW_PREFIX) :]
    head = secret[:4]
    tail = secret[-4:] if len(secret) >= 8 else ""
    return f"{_RAW_PREFIX}{head}…{tail}"


@dataclass(frozen=True, slots=True)
class ApiKeyRecord:
    """A key as shown to its owner — never includes the secret or its hash."""

    key_id: str
    label: str
    prefix: str
    org_id: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


def _to_record(row: ApiKeyRow) -> ApiKeyRecord:
    return ApiKeyRecord(
        key_id=row.key_id or row.key_hash[:12],
        label=row.label or "(unnamed)",
        prefix=row.prefix or "strata_sk_live_…",
        org_id=row.org_id,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        revoked_at=row.revoked_at,
    )


async def mint(
    session: AsyncSession, *, org_id: str, label: str, created_by: str | None
) -> tuple[str, ApiKeyRecord]:
    """Create a key for ``org_id``. Returns ``(raw_secret, record)``; the raw
    secret is the caller's only chance to read it."""
    raw = generate_raw_key()
    row = ApiKeyRow(
        key_hash=hash_key(raw),
        org_id=org_id,
        scopes="*",
        key_id="ak_" + secrets.token_urlsafe(8),
        label=label.strip()[:200] or "(unnamed)",
        prefix=_masked_prefix(raw),
        created_by=created_by,
    )
    session.add(row)
    await session.flush()
    return raw, _to_record(row)


async def list_for_org(session: AsyncSession, org_id: str) -> list[ApiKeyRecord]:
    """Active (non-revoked) keys for an org, newest first."""
    rows = (
        await session.execute(
            select(ApiKeyRow)
            .where(ApiKeyRow.org_id == org_id, ApiKeyRow.revoked_at.is_(None))
            .order_by(ApiKeyRow.created_at.desc())
        )
    ).scalars()
    return [_to_record(r) for r in rows]


async def revoke(session: AsyncSession, *, org_id: str, key_id: str) -> str | None:
    """Revoke a key the caller owns. Returns the key_hash (so the caller can evict
    it from the in-process auth cache), or ``None`` if no such active key exists
    for this org — so one tenant can never revoke another's key."""
    row = (
        await session.execute(
            select(ApiKeyRow).where(
                ApiKeyRow.org_id == org_id,
                ApiKeyRow.key_id == key_id,
                ApiKeyRow.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    row.revoked_at = datetime.now().astimezone()
    await session.flush()
    return row.key_hash


async def lookup_active(session: AsyncSession, raw: str) -> ApiKeyRow | None:
    """Resolve a raw key to its active row by hash, or ``None`` if absent/revoked.
    Used by the MCP auth path to populate the cache on a miss (DB-backed auth)."""
    row = (
        await session.execute(
            select(ApiKeyRow).where(
                ApiKeyRow.key_hash == hash_key(raw), ApiKeyRow.revoked_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    return row


async def load_all_active(session: AsyncSession) -> list[ApiKeyRow]:
    """Every non-revoked key, for warming the in-process auth cache at startup."""
    rows = (
        await session.execute(select(ApiKeyRow).where(ApiKeyRow.revoked_at.is_(None)))
    ).scalars()
    return list(rows)


async def touch_last_used(session: AsyncSession, key_hash: str) -> None:
    """Best-effort last-used stamp. Callers throttle and swallow errors — this
    must never affect an auth decision."""
    await session.execute(
        update(ApiKeyRow)
        .where(ApiKeyRow.key_hash == key_hash)
        .values(last_used_at=datetime.now().astimezone())
    )
