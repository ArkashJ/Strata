"""Sourcing-gap writer + reader (Pillar B1 — measure the misses).

``record_gap`` / ``list_*`` / ``mark_gap_sourced`` take an already-org-scoped
session so the strict ``sourcing_gaps`` RLS isolates the tenant (the MCP tool /
CLI own the ``org_session_scope``, mirroring ``db/feedback.py``).

A gap is a demand signal, never a number — it never feeds the math (E1). The
recorder DE-DUPLICATES on ``(org_id, dedup_key)``: a repeat miss bumps
``hit_count`` + ``last_seen_at`` (atomic ``INSERT … ON CONFLICT``) instead of
inserting a duplicate, so the queue ranks by real demand.
"""

from __future__ import annotations

import logging
import re

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from strata.db.engine import assert_org_matches_session
from strata.db.models import SourcingGapRow
from strata.models.sourcing_gap import GapSource, GapStatus, SourcingGap

_WS = re.compile(r"\s+")

_log = logging.getLogger(__name__)

# The anonymous tenant sentinel (mirrors ``db/feedback.py`` / the audit writer).
# The closed RLS policy rejects an anon-org row by design, so an anonymous miss
# is dropped silently — never a 500 on the request that observed it.
_ANONYMOUS_ORG = "public"


def make_dedup_key(*, query_text: str | None, resource_target: str | None) -> str:
    """Collapse a miss onto a stable identity. A named ``resource_target`` (the
    connector/method that would fill it, e.g. ``bls:displacement-by-occupation``)
    wins — many phrasings map to one gap. Otherwise the normalized query text
    (lowercased, whitespace-collapsed, trimmed) is the key (``"query:"`` when
    empty — the f-string already yields that, no special-case needed)."""
    if resource_target:
        return f"target:{resource_target.strip().lower()}"
    q = _WS.sub(" ", (query_text or "").strip().lower())
    return f"query:{q}"


async def record_gap(
    session: AsyncSession,
    *,
    org_id: str,
    source: GapSource,
    query_text: str | None = None,
    concept_slug: str | None = None,
    role: str | None = None,
    lens: str | None = None,
    unit_hint: str | None = None,
    resource_target: str | None = None,
    note: str | None = None,
) -> SourcingGap:
    """Upsert one gap inside an already-org-scoped session. A repeat (same
    ``dedup_key``) bumps ``hit_count`` + ``last_seen_at`` rather than inserting a
    duplicate — so the row's count is how many times this number was asked for.
    The session-match guard refuses a spoofed/misrouted ``org_id`` even under a
    BYPASSRLS (superuser) role, where the RLS ``WITH CHECK`` would not catch it."""
    await assert_org_matches_session(session, org_id)
    dedup_key = make_dedup_key(query_text=query_text, resource_target=resource_target)
    insert_stmt = pg_insert(SourcingGapRow).values(
        org_id=org_id,
        source=source.value,
        dedup_key=dedup_key,
        query_text=query_text,
        concept_slug=concept_slug,
        role=role,
        lens=lens,
        unit_hint=unit_hint,
        resource_target=resource_target,
        note=note,
    )
    stmt = insert_stmt.on_conflict_do_update(
        constraint="uq_sourcing_gaps_org_dedup",
        set_={
            "hit_count": SourcingGapRow.hit_count + 1,
            "last_seen_at": func.now(),
            # Prefer the INCOMING resource_target (a later, more specific miss can
            # name the connector the first didn't), falling back to the existing
            # one. ``excluded`` is the proposed row; the bare column is the
            # existing row — so a named target is never silently dropped.
            "resource_target": func.coalesce(
                insert_stmt.excluded.resource_target, SourcingGapRow.resource_target
            ),
        },
    ).returning(SourcingGapRow)
    row = (await session.execute(stmt)).scalar_one()
    return SourcingGap.model_validate(row)


async def record_gap_safe(
    *,
    org_id: str | None,
    source: GapSource,
    query_text: str | None = None,
    concept_slug: str | None = None,
    role: str | None = None,
    lens: str | None = None,
    unit_hint: str | None = None,
    resource_target: str | None = None,
    note: str | None = None,
) -> int | None:
    """Fire-and-forget gap write on its own org-scoped session (mirrors
    ``record_feedback_safe``). Swallows (but logs) any failure so recording a
    miss can never break the request that observed it. Returns the row id, or
    ``None`` when the write was dropped (anonymous org has no tenant bucket
    under the closed RLS policy).

    Resolve-vs-verify phrasings of the same market can land two rows — the
    dedup key is the normalized query text and the two surfaces see different
    strings. Acceptable: both still rank as demand for the same missing number.
    """
    if not org_id or org_id == _ANONYMOUS_ORG:
        return None
    try:
        from strata.db.engine import org_session_scope

        async with org_session_scope(org_id) as session:
            gap = await record_gap(
                session,
                org_id=org_id,
                source=source,
                query_text=query_text,
                concept_slug=concept_slug,
                role=role,
                lens=lens,
                unit_hint=unit_hint,
                resource_target=resource_target,
                note=note,
            )
            # org_session_scope commits on exit (session.begin()).
            return gap.id
    except Exception:
        _log.warning("sourcing_gap.write_failed source=%s", source.value)
        return None


async def list_gaps(
    session: AsyncSession,
    *,
    org_id: str,
    status: GapStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[SourcingGap]:
    """The org's gaps, most-demanded first (hit_count desc, then most-recent). RLS
    restricts rows to ``app.org_id``; the explicit ``org_id`` filter is a
    defense-in-depth backstop so isolation does not depend on RLS alone (e.g. a
    superuser / BYPASSRLS runtime role)."""
    stmt = select(SourcingGapRow).where(SourcingGapRow.org_id == org_id)
    if status is not None:
        stmt = stmt.where(SourcingGapRow.status == status.value)
    stmt = (
        stmt.order_by(SourcingGapRow.hit_count.desc(), SourcingGapRow.last_seen_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [SourcingGap.model_validate(r) for r in rows]


async def admin_list_gaps(
    session: AsyncSession,
    *,
    status: GapStatus | None = None,
    org_id: str | None = None,
    limit: int = 100,
) -> list[SourcingGap]:
    """Cross-org gap queue for an admin session (the ``app.is_admin`` GUC opens the
    additive admin SELECT policy). Demand-ranked platform-wide — the connector /
    sourcing backlog ordered by how many workspaces asked."""
    stmt = select(SourcingGapRow)
    if status is not None:
        stmt = stmt.where(SourcingGapRow.status == status.value)
    if org_id is not None:
        stmt = stmt.where(SourcingGapRow.org_id == org_id)
    stmt = stmt.order_by(SourcingGapRow.hit_count.desc(), SourcingGapRow.last_seen_at.desc()).limit(
        limit
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [SourcingGap.model_validate(r) for r in rows]


async def mark_gap_sourced(
    session: AsyncSession,
    gap_id: int,
    *,
    org_id: str,
    resolved_primitive_id: int | None = None,
    note: str | None = None,
) -> SourcingGap | None:
    """Close a gap once the number is sourced (RLS-scoped). The explicit ``org_id``
    predicate is a defense-in-depth backstop so a caller can't close another
    tenant's gap even if RLS were bypassed. ``None`` when no such row is visible."""
    row = (
        await session.execute(
            select(SourcingGapRow).where(
                SourcingGapRow.id == gap_id, SourcingGapRow.org_id == org_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    row.status = GapStatus.SOURCED.value
    if resolved_primitive_id is not None:
        row.resolved_primitive_id = resolved_primitive_id
    if note is not None:
        row.note = note
    await session.flush()
    return SourcingGap.model_validate(row)
