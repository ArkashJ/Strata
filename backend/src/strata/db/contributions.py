"""Contribution persistence (Wave 4 / Risk-2 moat hardening).

Community contribution proposals are persisted (not ephemeral) so the human
review queue survives restarts and contributions are attributed to the
contributing ``org_id``. Best-effort like the audit writer — a failed persist
never breaks the contribution response.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from strata.db.models import ContributionRow

_log = logging.getLogger(__name__)


class Contribution(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: str
    kind: str
    status: str
    reasons: list[str]
    created_at: datetime


async def record_contribution_safe(
    org_id: str, kind: str, status: str, reasons: list[str], payload: dict[str, Any]
) -> int | None:
    """Persist a contribution on its own session; returns the row id (or None on
    failure — never raises into the request path)."""
    try:
        from strata.db.engine import SessionLocal

        async with SessionLocal() as session:
            row = ContributionRow(
                org_id=org_id, kind=kind, status=status, reasons=reasons, payload=payload
            )
            session.add(row)
            await session.commit()
            return int(row.id)
    except Exception:
        _log.warning("contribution.write_failed org=%s kind=%s", org_id, kind, exc_info=True)
        return None


async def list_contributions(
    session: AsyncSession, status: str | None = None, limit: int = 100
) -> list[Contribution]:
    stmt = select(ContributionRow).order_by(ContributionRow.created_at.desc()).limit(limit)
    if status is not None:
        stmt = stmt.where(ContributionRow.status == status)
    rows = (await session.execute(stmt)).scalars().all()
    return [Contribution.model_validate(r) for r in rows]
