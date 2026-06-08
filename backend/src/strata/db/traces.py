"""Tool-call trace writer + reader (MCP trace-capture substrate, Phase 1).

``record_trace_safe`` is the fire-and-forget capture path: it opens its own
``org_session_scope``, never raises into the call path, and mirrors
``record_audit_safe`` (``db/audit.py:64``) exactly.  All other functions take an
already-org-scoped session so the closed ``tool_traces`` / ``trace_sessions`` RLS
enforces tenant isolation — the MCP tool / CLI own the ``org_session_scope``,
mirroring ``db/sourcing_gaps.py``.

Privacy trade (D4): traces keep real args + result summaries (unlike audit, which
hashes args) because replay needs the real inputs.  Mitigated by: off-by-default
gate, same closed RLS as gaps/feedback, and per-field size cap enforced here at
write time.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from strata.config import settings
from strata.db.models import ToolTraceRow, TraceSessionRow
from strata.models.trace import ToolCall, TraceSession, TraceStatus

_log = logging.getLogger(__name__)


# ── helpers ────────────────────────────────────────────────────────────────────


def _canon_hash(obj: Any) -> str:
    """Canonicalize an arbitrary result object and return its sha256 hex digest.

    ``sort_keys=True`` + ``default=str`` mirrors the state-hash canonicalization
    already used for ``/build/<hash>`` so equivalent results collide."""
    raw = json.dumps(obj, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _truncate_json(obj: Any, max_bytes: int) -> tuple[Any, bool]:
    """Return ``(obj, truncated)``.  When the canonical JSON encoding exceeds
    ``max_bytes``, replace the value with a sentinel dict so the field is still
    valid JSONB but the consumer knows data was dropped."""
    encoded = json.dumps(obj, sort_keys=True, default=str)
    if len(encoded.encode()) <= max_bytes:
        return obj, False
    return {"__truncated__": True, "size_bytes": len(encoded.encode())}, True


def _build_summary(result: Any) -> dict[str, Any]:
    """Structural digest of a tool result — enough to diagnose without full blobs.

    For dict results: top-level keys + scalar values + array lengths.
    For other types: type name + repr truncated to 200 chars.
    This is the ``result_summary`` stored in every trace row."""
    if isinstance(result, dict):
        summary: dict[str, Any] = {}
        for k, v in result.items():
            if isinstance(v, (str, int, float, bool, type(None))):
                summary[k] = v
            elif isinstance(v, list):
                summary[k] = f"list[{len(v)}]"
            elif isinstance(v, dict):
                summary[k] = f"dict[{len(v)}]"
            else:
                summary[k] = type(v).__name__
        return summary
    return {"__type__": type(result).__name__, "__repr__": repr(result)[:200]}


# ── fire-and-forget capture ────────────────────────────────────────────────────


async def record_trace_safe(
    *,
    org_id: str,
    session_id: str | None,
    tool: str,
    args: dict[str, Any],
    result: Any,
    status: TraceStatus,
    duration_ms: int,
    error_code: str | None = None,
) -> None:
    """Fire-and-forget trace write on its own ``org_session_scope``.

    Never raises — a capture failure must never break the MCP call that triggered
    it (AC-1.5).  Opens its own session so it is fully decoupled from the request
    transaction (mirroring ``record_audit_safe``).

    Write sequence per call:
      1. Canonicalize + hash the result (regression signal).
      2. Build a structural summary (diagnostic without full blobs).
      3. Truncate oversized args / summary fields (D3 privacy cap).
      4. INSERT the tool_traces row.
      5. Upsert the trace_sessions row (bump call_count + last_seen_at).
      6. Prune oldest sessions for this org beyond ``trace_max_sessions`` (D3 FIFO).
    """
    try:
        result_sha256 = _canon_hash(result)
        summary = _build_summary(result)
        max_bytes = settings.trace_max_field_bytes

        args_stored, args_truncated = _truncate_json(args, max_bytes)
        summary_stored, result_truncated = _truncate_json(summary, max_bytes)

        # seq: coalesce(max, 0) + 1 within this org+session; ties broken by created_at
        from strata.db.engine import org_session_scope

        async with org_session_scope(org_id) as session:
            seq = await next_seq(session, org_id=org_id, session_id=session_id)

            session.add(
                ToolTraceRow(
                    org_id=org_id,
                    session_id=session_id,
                    seq=seq,
                    tool=tool,
                    args=args_stored,
                    args_truncated=args_truncated,
                    result_summary=summary_stored,
                    result_sha256=result_sha256,
                    result_truncated=result_truncated,
                    status=status.value,
                    duration_ms=duration_ms,
                    error_code=error_code,
                )
            )

            # Upsert the session row — bump call_count + last_seen_at atomically.
            if session_id is not None:
                ins = pg_insert(TraceSessionRow).values(
                    session_id=session_id,
                    org_id=org_id,
                    call_count=1,
                )
                await session.execute(
                    ins.on_conflict_do_update(
                        constraint="uq_trace_sessions_org_session",
                        set_={
                            "call_count": TraceSessionRow.call_count + 1,
                            "last_seen_at": func.now(),
                        },
                    )
                )

            # Prune oldest sessions beyond the cap so the table doesn't grow unboundedly.
            await _prune_excess_sessions(session, org_id=org_id)

    except Exception:
        _log.warning("traces.record_failed tool=%s org=%s", tool, org_id, exc_info=True)


async def _prune_excess_sessions(session: AsyncSession, *, org_id: str) -> None:
    """Delete the oldest sessions for ``org_id`` beyond ``trace_max_sessions``.

    Runs inside the same transaction as the insert so the cap is enforced
    atomically — a race between two concurrent calls may temporarily exceed the
    cap by one row, which is benign (the next write corrects it)."""
    limit = settings.trace_max_sessions
    # Subquery: ids of sessions to KEEP (the N most-recent by last_seen_at).
    keep_sq = (
        select(TraceSessionRow.id)
        .where(TraceSessionRow.org_id == org_id)
        .order_by(TraceSessionRow.last_seen_at.desc())
        .limit(limit)
        .scalar_subquery()
    )
    # Delete any session row NOT in the keep set.
    from sqlalchemy import delete

    await session.execute(
        delete(TraceSessionRow).where(
            TraceSessionRow.org_id == org_id,
            TraceSessionRow.id.not_in(keep_sq),
        )
    )


# ── agent-submitted reasoning ──────────────────────────────────────────────────


async def record_reasoning(
    session: AsyncSession,
    *,
    org_id: str,
    session_id: str,
    reasoning: str,
    outcome: str | None = None,
) -> TraceSession:
    """Upsert the session row's reasoning + outcome fields.

    ``INSERT … ON CONFLICT (org_id, session_id) DO UPDATE`` mirrors ``record_gap``
    in ``db/sourcing_gaps.py``.  The session row is created here if it doesn't yet
    exist (an agent may submit reasoning before any call is captured)."""
    ins = pg_insert(TraceSessionRow).values(
        session_id=session_id,
        org_id=org_id,
        call_count=0,
        reasoning=reasoning,
        outcome=outcome,
    )
    stmt = ins.on_conflict_do_update(
        constraint="uq_trace_sessions_org_session",
        set_={
            "reasoning": ins.excluded.reasoning,
            # Prefer the incoming outcome when set; fall back to the existing one.
            "outcome": func.coalesce(ins.excluded.outcome, TraceSessionRow.outcome),
            "last_seen_at": func.now(),
        },
    ).returning(TraceSessionRow)
    row = (await session.execute(stmt)).scalar_one()
    return TraceSession.model_validate(row)


# ── sequence helper ────────────────────────────────────────────────────────────


async def next_seq(
    session: AsyncSession,
    org_id: str,
    session_id: str | None,
) -> int:
    """SELECT coalesce(max(seq), 0) + 1 for this org+session.

    Concurrency: two calls racing for the same seq is benign — seq is for
    ordering display/replay; ties are broken by ``created_at``.  No hard unique
    constraint on seq is needed."""
    stmt = select(func.coalesce(func.max(ToolTraceRow.seq), 0) + 1).where(
        ToolTraceRow.org_id == org_id,
        ToolTraceRow.session_id == session_id,
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())


# ── readers (org-scoped) ───────────────────────────────────────────────────────


async def list_sessions(
    session: AsyncSession,
    *,
    outcome: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[TraceSession]:
    """The org's sessions, most-recently-active first.  RLS restricts to ``app.org_id``."""
    stmt = select(TraceSessionRow)
    if outcome is not None:
        stmt = stmt.where(TraceSessionRow.outcome == outcome)
    stmt = stmt.order_by(TraceSessionRow.last_seen_at.desc()).limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return [TraceSession.model_validate(r) for r in rows]


async def get_session_calls(
    session: AsyncSession,
    *,
    session_id: str,
    limit: int = 200,
) -> list[ToolCall]:
    """Ordered tool calls for one session (seq asc, then created_at for ties).
    RLS restricts to ``app.org_id``."""
    stmt = (
        select(ToolTraceRow)
        .where(ToolTraceRow.session_id == session_id)
        .order_by(ToolTraceRow.seq.asc(), ToolTraceRow.created_at.asc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [ToolCall.model_validate(r) for r in rows]


# ── readers (admin-scoped, additive RLS policy) ────────────────────────────────


async def admin_list_sessions(
    session: AsyncSession,
    *,
    org_id: str | None = None,
    outcome: str | None = None,
    limit: int = 100,
) -> list[TraceSession]:
    """Cross-org session list for an admin session (``app.is_admin`` GUC opens the
    additive admin SELECT policy).  Mirrors ``admin_list_gaps``."""
    stmt = select(TraceSessionRow)
    if org_id is not None:
        stmt = stmt.where(TraceSessionRow.org_id == org_id)
    if outcome is not None:
        stmt = stmt.where(TraceSessionRow.outcome == outcome)
    stmt = stmt.order_by(TraceSessionRow.last_seen_at.desc()).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [TraceSession.model_validate(r) for r in rows]


async def admin_get_session_calls(
    session: AsyncSession,
    *,
    session_id: str,
    org_id: str | None = None,
    limit: int = 200,
) -> list[ToolCall]:
    """Ordered calls for one session under admin scope.  ``org_id`` narrows when
    set (safety: prevents an admin typo reading the wrong org's session)."""
    stmt = select(ToolTraceRow).where(ToolTraceRow.session_id == session_id)
    if org_id is not None:
        stmt = stmt.where(ToolTraceRow.org_id == org_id)
    stmt = stmt.order_by(ToolTraceRow.seq.asc(), ToolTraceRow.created_at.asc()).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [ToolCall.model_validate(r) for r in rows]


# ── retention / purge ──────────────────────────────────────────────────────────


async def purge_sessions(
    session: AsyncSession,
    *,
    before: datetime | None = None,
    session_id: str | None = None,
) -> int:
    """Delete sessions (and their call rows) matching the filter.  Returns the
    number of session rows deleted.  Caller must be in an appropriate scope
    (org_session_scope for own-org purge, admin_session_scope for cross-org).

    ``before`` — purge sessions whose ``last_seen_at`` is older than this timestamp.
    ``session_id`` — purge exactly one session by id (ignores ``before``)."""
    from sqlalchemy import delete

    if session_id is not None:
        # Purge the call rows first (no FK cascade — no FK defined to keep the
        # schema simple and avoid cross-RLS-policy FK complications).
        await session.execute(delete(ToolTraceRow).where(ToolTraceRow.session_id == session_id))
        result = await session.execute(
            delete(TraceSessionRow)
            .where(TraceSessionRow.session_id == session_id)
            .returning(TraceSessionRow.id)
        )
        return len(result.fetchall())

    if before is not None:
        # Collect sessions to purge so we can delete their call rows too.
        old_ids_result = await session.execute(
            select(TraceSessionRow.session_id).where(TraceSessionRow.last_seen_at < before)
        )
        old_session_ids = [r[0] for r in old_ids_result.fetchall()]
        if old_session_ids:
            await session.execute(
                delete(ToolTraceRow).where(ToolTraceRow.session_id.in_(old_session_ids))
            )
        result = await session.execute(
            delete(TraceSessionRow)
            .where(TraceSessionRow.last_seen_at < before)
            .returning(TraceSessionRow.id)
        )
        return len(result.fetchall())

    return 0
