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

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from strata.db.models import TamOutputRow
from strata.models import TAMOutput

_log = logging.getLogger(__name__)


def _to_payload(tam: TAMOutput) -> dict[str, object]:
    return tam.model_dump(mode="json")


async def persist_tam(session: AsyncSession, tam: TAMOutput) -> None:
    """Upsert one TAM keyed by state_hash. Equivalent states collide (Q38), so a
    re-build (or a later promote) updates the existing row in place."""
    stmt = pg_insert(TamOutputRow).values(
        state_hash=tam.state_hash,
        is_promoted=tam.is_promoted,
        payload=_to_payload(tam),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[TamOutputRow.state_hash],
        set_={"is_promoted": stmt.excluded.is_promoted, "payload": stmt.excluded.payload},
    )
    await session.execute(stmt)
    await session.commit()


async def persist_tam_safe(tam: TAMOutput) -> None:
    """Fire-and-forget TAM persistence on its own session. Swallows (but logs)
    any failure so a missing/unhealthy DB never breaks a build/recompute."""
    try:
        from strata.db.engine import SessionLocal

        async with SessionLocal() as session:
            await persist_tam(session, tam)
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


async def load_promoted_tams_from_db(session: AsyncSession) -> list[TAMOutput]:
    """All promoted TAMs — seeds ``/browse`` and the registry on prod boot."""
    rows = (
        (await session.execute(select(TamOutputRow).where(TamOutputRow.is_promoted.is_(True))))
        .scalars()
        .all()
    )
    return [TAMOutput.model_validate(r.payload) for r in rows]
