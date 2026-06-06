"""TAM artifact persistence — makes ``GET /tam/<hash>`` durable.

The product's distribution wedge is a *permanent, content-addressed* TAM you
paste into a memo. The in-memory registry cache (``Registry.remember_tam``)
404s after FIFO eviction or a server restart, which silently breaks that
promise. These helpers mirror the best-effort ``record_audit_safe`` pattern:
writes never break the request path, and reads degrade to ``None`` when no DB
is configured (dev/CI run off the in-memory registry).
"""

from __future__ import annotations

import logging

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from strata.db.models import TamOutputRow
from strata.models import TAMOutput

_log = logging.getLogger(__name__)

# Anonymous tenant sentinel (mirrors ``api.auth._ANONYMOUS_ORG``). An anonymous
# build persists a NULL-org global permalink; a real tenant persists under its
# own ``org_id``.
_ANONYMOUS_ORG = "public"


def _to_payload(tam: TAMOutput) -> dict[str, object]:
    return tam.model_dump(mode="json")


async def persist_tam(
    session: AsyncSession,
    tam: TAMOutput,
    *,
    org_id: str | None = None,
    created_by: str | None = None,
    title: str | None = None,
    is_saved: bool = False,
) -> None:
    """Upsert one TAM keyed by ``state_hash``. Equivalent states collide (Q38), so
    a re-build (or a later promote/save) updates the existing row in place.

    PR 1 / KTD-2: ``tam_outputs`` has two PARTIAL unique indexes, not a single
    ``UNIQUE(state_hash)``. An anonymous build (``org_id=None``) upserts on the
    public partial index (``WHERE org_id IS NULL``) — the global permalink. A
    tenant save upserts on ``(org_id, state_hash)`` (``WHERE org_id IS NOT NULL``)
    so the same hash can coexist as a permalink AND as a tenant copy. The session
    must already be org-scoped (``org_session_scope``) for a tenant write so the
    dual-purpose RLS ``WITH CHECK`` passes."""
    values: dict[str, object] = {
        "state_hash": tam.state_hash,
        "org_id": org_id,
        "created_by": created_by,
        "title": title,
        "is_saved": is_saved,
        "is_promoted": tam.is_promoted,
        "payload": _to_payload(tam),
    }
    stmt = pg_insert(TamOutputRow).values(**values)
    if org_id is None:
        # Global permalink: conflict on the public partial unique index.
        stmt = stmt.on_conflict_do_update(
            index_elements=[TamOutputRow.state_hash],
            index_where=text("org_id IS NULL"),
            set_={"is_promoted": stmt.excluded.is_promoted, "payload": stmt.excluded.payload},
        )
    else:
        # Tenant save: conflict on the (org_id, state_hash) partial unique index.
        # ``is_saved``/``title`` are intentionally updated so a re-save refreshes
        # the saved-research metadata without minting a duplicate row.
        stmt = stmt.on_conflict_do_update(
            index_elements=[TamOutputRow.org_id, TamOutputRow.state_hash],
            index_where=text("org_id IS NOT NULL"),
            set_={
                "is_promoted": stmt.excluded.is_promoted,
                "payload": stmt.excluded.payload,
                "title": stmt.excluded.title,
                "is_saved": stmt.excluded.is_saved,
                "created_by": stmt.excluded.created_by,
            },
        )
    await session.execute(stmt)
    await session.commit()


async def persist_tam_safe(
    tam: TAMOutput,
    *,
    org_id: str | None = None,
    created_by: str | None = None,
    title: str | None = None,
    is_saved: bool = False,
) -> None:
    """Fire-and-forget TAM persistence on its own session. Swallows (but logs)
    any failure so a missing/unhealthy DB never breaks a build/recompute.

    An authenticated build (a real tenant ``org_id``) writes under that tenant's
    ``org_session_scope`` so the dual-purpose RLS ``WITH CHECK`` passes and the
    row carries ``org_id``/``created_by``. An anonymous build (``org_id`` None or
    the ``public`` sentinel) writes a NULL-org global permalink with no scope —
    the dual-purpose policy admits ``org_id IS NULL`` writes, so permalinks keep
    working with byte-identical pre-PR behaviour."""
    tenant = org_id if (org_id and org_id != _ANONYMOUS_ORG) else None
    try:
        from strata.db.engine import SessionLocal, set_org_scope

        async with SessionLocal() as session:
            if tenant is not None:
                # ``set_config(..., is_local=true)`` is transaction-scoped, so the
                # scope and the upsert must share one transaction. ``persist_tam``
                # commits it. (We don't use ``org_session_scope`` here because it
                # owns its own commit, which would conflict with persist_tam's.)
                await set_org_scope(session, tenant)
            await persist_tam(
                session,
                tam,
                org_id=tenant,
                created_by=created_by if tenant is not None else None,
                title=title if tenant is not None else None,
                is_saved=is_saved if tenant is not None else False,
            )
    except Exception:
        _log.warning("tam.persist_failed hash=%s", tam.state_hash, exc_info=True)


async def get_tam_from_db_safe(state_hash: str) -> TAMOutput | None:
    """Best-effort durable lookup for ``GET /tam/<hash>`` when the in-memory
    registry has evicted (or never held) the artifact. Returns ``None`` on miss
    or when no DB is configured."""
    try:
        from strata.db.engine import SessionLocal

        async with SessionLocal() as session:
            row = (
                await session.execute(
                    select(TamOutputRow).where(TamOutputRow.state_hash == state_hash)
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return TAMOutput.model_validate(row.payload)
    except Exception:
        _log.warning("tam.lookup_failed hash=%s", state_hash, exc_info=True)
        return None


async def get_any_tam_payload(session: AsyncSession, state_hash: str) -> dict[str, object] | None:
    """Return the stored payload for ``state_hash`` from ANY visible row (the
    global permalink under the dual-purpose RLS policy, or the caller's own tenant
    copy). Used by ``POST /me/tams/save`` to copy an existing build's payload into
    a tenant-saved row. Returns ``None`` when the hash is unknown to this session."""
    row = (
        await session.execute(
            select(TamOutputRow.payload).where(TamOutputRow.state_hash == state_hash).limit(1)
        )
    ).scalar_one_or_none()
    return row


async def save_tam_for_org(
    session: AsyncSession,
    *,
    state_hash: str,
    org_id: str,
    created_by: str | None,
    title: str | None,
) -> TAMOutput | None:
    """Upsert the caller's saved copy of a TAM (``org_id``/``created_by``/``title``
    + ``is_saved=true``) keyed by the ``(org_id, state_hash)`` partial index.

    The session MUST already be org-scoped so the dual-purpose RLS ``WITH CHECK``
    passes and the tenant write lands. The payload is copied from whatever row this
    session can already see for the hash (the global permalink or a prior tenant
    copy); the upsert touches ONLY the tenant row (``WHERE org_id IS NOT NULL``),
    never the ``org_id IS NULL`` permalink. Returns the saved ``TAMOutput`` or
    ``None`` when the hash is unknown."""
    payload = await get_any_tam_payload(session, state_hash)
    if payload is None:
        return None
    tam = TAMOutput.model_validate(payload)
    await persist_tam(
        session, tam, org_id=org_id, created_by=created_by, title=title, is_saved=True
    )
    return tam


async def list_saved_tams(session: AsyncSession, *, limit: int = 100) -> list[TAMOutput]:
    """The caller's saved research — ``is_saved`` rows for the org-scoped session,
    newest first. RLS restricts this to the caller's own tenant rows (it never
    returns the ``org_id IS NULL`` permalinks, which are not ``is_saved``)."""
    rows = (
        (
            await session.execute(
                select(TamOutputRow)
                .where(TamOutputRow.is_saved.is_(True))
                .order_by(TamOutputRow.created_at.desc(), TamOutputRow.id.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [TAMOutput.model_validate(r.payload) for r in rows]


async def load_promoted_tams_from_db(session: AsyncSession) -> list[TAMOutput]:
    """All promoted TAMs — seeds ``/browse`` and the registry on prod boot."""
    rows = (
        (await session.execute(select(TamOutputRow).where(TamOutputRow.is_promoted.is_(True))))
        .scalars()
        .all()
    )
    return [TAMOutput.model_validate(r.payload) for r in rows]
