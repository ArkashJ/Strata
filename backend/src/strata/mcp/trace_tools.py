"""Trace-capture MCP tool — agent-submitted reasoning tier (Phase 3).

The server captures every tool call automatically (server.py ``_trace_call``).
What it structurally cannot see is *why* the agent made those calls — its plan,
the chain-of-thought between tool invocations, and its self-assessment of the
outcome.  This tool is the opt-in tier that closes that gap: the agent attaches
its reasoning to the current trace session so a captured failure is diagnosable,
not just reproducible (plan Direction 1, item #8).

Call this once per session — typically at the end, after the agent has observed
the full result — but it may also be called mid-session if the agent wants to
checkpoint its reasoning.  Multiple calls to the same session_id update the
stored reasoning in place (the most-recent write wins on the reasoning field;
outcome coalesces to the first non-null value so a late "ok" does not overwrite
an early "error").

Over local stdio there is no tenant to attribute the session to, so the tool
refuses with ``no_tenant`` exactly as ``report_sourcing_gap`` does — keep the
two guards identical so the behaviour is predictable for agent authors.
"""

from __future__ import annotations

from typing import Any

from ..db.engine import org_session_scope
from ..db.traces import record_reasoning
from ..registry import Registry
from .context import current_org_id, current_principal, current_trace_session_id


async def record_session_reasoning(reg: Registry, *, payload: dict[str, Any]) -> dict[str, Any]:
    """[WRITE] Attach your reasoning / chain-of-thought / plan for THIS session
    so a captured trace is diagnosable, not just reproducible.  The server
    records every tool call automatically; this adds the *why* it can't see.

    payload: { session_id? (defaults to the active trace session), reasoning
    (required, non-empty), outcome? (ok|unsourced|unverifiable|error|flagged) }.
    Over local stdio there is no tenant, so this is refused honestly.
    """
    # stdio (local-trust) never sets current_principal; there is no org to
    # attribute the session to, so we refuse rather than silently drop the data.
    if current_principal.get() is None:
        return {
            "error": "no_tenant",
            "detail": (
                "record_session_reasoning needs an authenticated (hosted) connection; "
                "local stdio has no org to attribute the trace session to."
            ),
        }

    org = current_org_id()

    # Resolve the session_id: explicit payload > active contextvar > error.
    # An agent may pass an explicit session_id to stitch reasoning to a session
    # that ran in a previous request (the contextvar wouldn't carry across).
    session_id: str | None = (
        str(payload["session_id"]).strip() if payload.get("session_id") else None
    )
    if not session_id:
        session_id = current_trace_session_id()
    if not session_id:
        return {
            "error": "no_session",
            "detail": (
                "No session_id was provided and no active trace session is set. "
                "Pass an explicit session_id (from X-Strata-Trace-Session header "
                "or a previous strata traces list call), or ensure the client sends "
                "the X-Strata-Trace-Session header so the server groups calls automatically."
            ),
        }

    reasoning_raw = payload.get("reasoning")
    if not reasoning_raw or not str(reasoning_raw).strip():
        return {
            "error": "empty_reasoning",
            "detail": "reasoning must be a non-empty string describing the agent's plan / chain-of-thought.",
        }
    reasoning = str(reasoning_raw).strip()

    outcome_raw = payload.get("outcome")
    outcome: str | None = str(outcome_raw).strip() if outcome_raw else None
    _valid_outcomes = {"ok", "unsourced", "unverifiable", "error", "flagged"}
    if outcome and outcome not in _valid_outcomes:
        return {
            "error": "invalid_outcome",
            "detail": f"outcome must be one of {sorted(_valid_outcomes)} (got {outcome!r}).",
        }

    async with org_session_scope(org) as session:
        trace_session = await record_reasoning(
            session,
            org_id=org,
            session_id=session_id,
            reasoning=reasoning,
            outcome=outcome,
        )

    return {
        "recorded": True,
        "session_id": trace_session.session_id,
        "outcome": trace_session.outcome,
        "readable_at": "strata traces show <session_id> (CLI)",
    }
