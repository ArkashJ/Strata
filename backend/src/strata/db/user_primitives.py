"""Per-user PRIVATE primitive store (PR 1 / U6).

A tenant keeps its own numbers here without touching the shared seed bank. Every
write is forced to ``visibility=private`` + the caller's ``org_id`` server-side,
validated against the ``AtomicPrimitive`` schema, and run through the **MODELED
fence** — the same guard ``resolver/writer.py`` applies, so a community-modeled /
analyst estimate can never be stored as a sourced number (Q20, KTD-5).

All reads/writes here MUST run inside ``org_session_scope(org_id)`` so the strict
006-style RLS policy on ``user_primitives`` actually isolates tenants. The store
functions take an already-scoped ``AsyncSession`` and never set the scope
themselves — the route owns the scope (mirrors the rest of the DB layer).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from strata.db.models import UserPrimitiveRow
from strata.models import AtomicPrimitive, ProvenanceClass


class ModeledFenceError(ValueError):
    """Raised when a primitive claims a sourced number that is actually modeled.

    Mirrors ``resolver/writer.py``: a community-modeled / analyst-paraphrase /
    analyst tier derives ``provenance_class=modeled`` — refuse it here so a
    soft-data estimate can never enter a tenant's private bank as sourced data."""


class UserPrimitive(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: str
    created_by: str | None
    slug: str
    visibility: str
    payload: dict[str, Any]
    created_at: datetime


def _validate_and_fence(payload: dict[str, Any], *, org_id: str) -> dict[str, Any]:
    """Force private+org, validate the AtomicPrimitive shape, enforce the MODELED
    fence. Returns the normalized payload to persist. Raises ``ValueError`` on a
    schema violation and ``ModeledFenceError`` on a soft-data claim."""
    normalized = dict(payload)
    # Server-authoritative: the store never trusts a client-supplied visibility /
    # org_id. A body saying "public" or another tenant's org is overwritten.
    normalized["visibility"] = "private"
    normalized["org_id"] = org_id
    normalized.setdefault("kind", "atomic_primitive")

    prim = TypeAdapter(AtomicPrimitive).validate_python(normalized)

    # The same fence as the connector writer: provenance_class is DERIVED from the
    # source tier, so a modeled estimate cannot be relabelled as sourced.
    if prim.provenance_class is ProvenanceClass.MODELED:
        raise ModeledFenceError(
            f"primitive {prim.slug!r} (tier={prim.source.tier.value}) is modeled, not "
            f"sourced; the private bank stores sourced output only (Q20)"
        )

    # Re-serialize from the validated model so what we store matches what loads
    # (coerced enums, forced visibility/org_id).
    return prim.model_dump(mode="json")


async def create_user_primitive(
    session: AsyncSession, *, org_id: str, created_by: str | None, payload: dict[str, Any]
) -> UserPrimitive:
    validated = _validate_and_fence(payload, org_id=org_id)
    row = UserPrimitiveRow(
        org_id=org_id,
        created_by=created_by,
        slug=validated["slug"],
        payload=validated,
        visibility="private",
    )
    session.add(row)
    await session.flush()
    return UserPrimitive.model_validate(row)


async def list_user_primitives(session: AsyncSession) -> list[UserPrimitive]:
    """List the caller's private primitives. RLS (the scoped session) already
    restricts the rows to ``app.org_id`` — no explicit org filter needed."""
    stmt = select(UserPrimitiveRow).order_by(UserPrimitiveRow.created_at.desc())
    rows = (await session.execute(stmt)).scalars().all()
    return [UserPrimitive.model_validate(r) for r in rows]


async def get_user_primitive(session: AsyncSession, *, slug: str) -> UserPrimitive | None:
    stmt = select(UserPrimitiveRow).where(UserPrimitiveRow.slug == slug)
    row = (await session.execute(stmt)).scalar_one_or_none()
    return UserPrimitive.model_validate(row) if row is not None else None


async def update_user_primitive(
    session: AsyncSession, *, org_id: str, slug: str, payload: dict[str, Any]
) -> UserPrimitive | None:
    """Replace the payload of the caller's primitive ``slug``. The path slug is
    authoritative — the body's slug is overwritten so an update can't rename a row
    onto another. Returns ``None`` when the caller owns no such slug (RLS)."""
    stmt = select(UserPrimitiveRow).where(UserPrimitiveRow.slug == slug)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    body = dict(payload)
    body["slug"] = slug
    validated = _validate_and_fence(body, org_id=org_id)
    row.payload = validated
    await session.flush()
    return UserPrimitive.model_validate(row)


async def delete_user_primitive(session: AsyncSession, *, slug: str) -> bool:
    """Delete the caller's primitive ``slug``. RLS bounds the lookup + delete to
    the caller's org; returns True iff a row was removed."""
    stmt = select(UserPrimitiveRow).where(UserPrimitiveRow.slug == slug)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return False
    await session.delete(row)
    await session.flush()
    return True
