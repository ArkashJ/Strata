"""Tool-call trace model (MCP trace-capture, Phase 1 substrate).

Every MCP tool call that passes through ``_call_tool`` is optionally captured
into ``tool_traces`` (migration 018) when ``STRATA_TRACE_CAPTURE=1``.  A
parallel ``trace_sessions`` table stitches sequential calls into a session and
optionally holds agent-submitted reasoning via the ``record_session_reasoning``
tool — the *why* the server can't observe on its own.

Traces carry real args + a structural result summary so the replay harness can
re-run a captured session and detect silent regressions (a hash mismatch is the
signal).  The privacy trade is a conscious decision (D4): heavier than audit
(which hashes args), lighter than full result storage (which is opt-in via
``STRATA_TRACE_FULL_RESULTS``), bounded by the same closed RLS as gaps/feedback.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class TraceStatus(StrEnum):
    """Outcome of a single tool call."""

    OK = "ok"
    ERROR = "error"


class ToolCall(BaseModel):
    """One captured tool-call row (read shape).

    ``result_sha256`` is the regression signal: replay re-hashes the fresh
    result and a mismatch surfaces the regression.  ``result_summary`` holds
    the structural digest (top-level keys, scalar values, array lengths) so
    ``traces show`` is diagnosable without dumping megabytes.  Both
    ``args_truncated`` / ``result_truncated`` are honest flags set when the
    field exceeded ``STRATA_TRACE_MAX_FIELD_BYTES`` at capture time."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: str
    session_id: str | None = None
    seq: int
    created_at: datetime
    tool: str
    args: dict[str, Any]
    args_truncated: bool
    result_summary: dict[str, Any] | None = None
    result_sha256: str
    result_truncated: bool
    status: TraceStatus
    duration_ms: int
    error_code: str | None = None


class TraceSession(BaseModel):
    """One session row grouping sequential tool calls.

    ``call_count`` is bumped atomically by ``record_trace_safe`` so replay has
    an accurate sequence count without a full scan.  ``reasoning`` and
    ``outcome`` are agent-submitted via ``record_session_reasoning`` — the
    structural context the server can't infer on its own.

    ``outcome`` is a coarse tag: ``ok | unsourced | unverifiable | error |
    flagged``.  It is advisory (E1) — never feeds the math, just surfaces in
    ``traces list`` to triage which sessions are worth inspecting."""

    model_config = ConfigDict(from_attributes=True)

    session_id: str
    org_id: str
    created_at: datetime
    last_seen_at: datetime
    call_count: int
    reasoning: str | None = None
    outcome: str | None = None
