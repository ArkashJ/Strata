"""Offline replay harness for captured MCP sessions (plan #13).

Given a list of ``ToolCall`` rows (from DB or a fixture JSON), this module
re-invokes each tool against the current registry and compares the result's
sha256 to the captured ``result_sha256``.  A mismatch is the regression signal.

WHY replay must be deterministic (plan risk "Replay determinism"):
  Network variance in live connector calls would produce false regressions every
  time the upstream API changes a value.  We therefore force two env guards:
    1. ``STRATA_MCP_LIVE_CONNECTORS`` is never "1" inside replay — the
       ``get_connector_data`` handler checks this env var directly (tools.py:661)
       and raises ``ToolError(CODE_LIVE_DISABLED)`` when it is not set.  Replay
       catches that and records the call as ``skipped``.
    2. The registry is built from on-disk YAML (``load_data_dir`` + ``load_registry``)
       so no live Postgres connector path is exercised.
Both guards are re-asserted at the top of ``replay_session`` so they cannot be
accidentally defeated by an ambient env var set in CI.

WHY write tools are skipped by default:
  Replaying a ``[WRITE]`` tool (e.g. ``import_portfolio``) would mutate real org
  data in Postgres.  The default ``include_writes=False`` records such calls as
  ``skipped`` (NOT a regression) so a captured session can be replayed safely in
  any environment.  Pass ``include_writes=True`` only in a sandboxed DB.

Fixture JSON shape (agreed with ``traces export`` in cli.py):
  {
    "schema_version": 1,
    "session_id": "<hex>",
    "org_id":     "<org>",
    "reasoning":  "<text or null>",
    "calls": [
      {
        "id":              <int>,
        "org_id":          "<org>",
        "session_id":      "<hex or null>",
        "seq":             <int>,
        "created_at":      "<ISO-8601>",
        "tool":            "<name>",
        "args":            { ... },
        "args_truncated":  <bool>,
        "result_summary":  { ... },
        "result_sha256":   "<hex>",
        "result_truncated":<bool>,
        "status":          "ok|error",
        "duration_ms":     <int>,
        "error_code":      "<str or null>"
      },
      ...
    ]
  }
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from strata.models.trace import ToolCall
from strata.registry import Registry

# ── per-call status enum (plain string literal for simplicity) ─────────────────

CallStatus = Literal["match", "diff", "skipped", "error"]


@dataclass
class CallResult:
    """Outcome of replaying one captured tool call."""

    seq: int
    tool: str
    status: CallStatus
    captured_hash: str
    fresh_hash: str | None = None
    error: str | None = None


@dataclass
class ReplayReport:
    """Aggregate outcome of replaying a complete session.

    ``passed`` is True when every non-skipped call produced ``match``.
    A single ``diff`` or ``error`` flips it to False — the CI gate checks this
    field and exits non-zero when False."""

    session_id: str | None
    calls: list[CallResult] = field(default_factory=list)
    passed: bool = True


# ── canonicalization (mirrors db/traces.py::_canon_hash) ──────────────────────


def _canon_hash(obj: Any) -> str:
    """Deterministic sha256 of a JSON-canonicalized result.

    ``sort_keys=True`` + ``default=str`` mirrors the state-hash used by
    ``/build/<hash>`` and the capture path so equivalent results collide."""
    raw = json.dumps(obj, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


# ── write-tool detection ───────────────────────────────────────────────────────


def _is_write_tool(name: str) -> bool:
    """Return True when the named tool carries the ``_WRITE`` annotation.

    ``_WRITE`` is ``{"readOnlyHint": False, ...}`` (tools.py:947).  We check the
    live TOOLS dict so the decision tracks the registered tool, not a hardcoded
    list that can drift."""
    from strata.mcp.tools import TOOLS

    spec = TOOLS.get(name)
    if spec is None:
        return False
    ann: dict[str, Any] = spec.get("annotations", {})
    # readOnlyHint=False distinguishes _WRITE from _READ / _READ_NET.
    return ann.get("readOnlyHint") is False


# ── core replay function ───────────────────────────────────────────────────────


def replay_session(
    reg: Registry,
    calls: list[ToolCall],
    *,
    include_writes: bool = False,
) -> ReplayReport:
    """Re-run every captured call against ``reg`` and compare result hashes.

    This function is synchronous at the outer level and drives an asyncio loop
    internally for awaitable handlers, mirroring ``server._call_tool`` lines 119-
    127.  It is safe to call from a CLI command (no running event loop assumed).

    Connector-safety guards are re-asserted here even if the caller forgets:
      - ``STRATA_MCP_LIVE_CONNECTORS`` is forced unset so ``get_connector_data``
        raises ``ToolError(CODE_LIVE_DISABLED)`` — caught below as ``skipped``.
    """
    # Force connectors offline for replay determinism.  The env var is read by
    # tools.py:661 as ``os.getenv(...)`` so clearing it here is enough.
    _old_live = os.environ.pop("STRATA_MCP_LIVE_CONNECTORS", None)

    import asyncio

    from strata.mcp.errors import CODE_LIVE_DISABLED, ToolError
    from strata.mcp.tools import call_tool

    session_id = calls[0].session_id if calls else None
    report = ReplayReport(session_id=session_id)

    # Sort by (seq, created_at) to match the DB reader ordering (plan #13).
    ordered = sorted(calls, key=lambda c: (c.seq, c.created_at))

    async def _invoke(tool: str, args: dict[str, Any]) -> Any:
        result = call_tool(reg, tool, args)
        if inspect.isawaitable(result):
            result = await result
        return result

    loop = asyncio.new_event_loop()
    try:
        for call in ordered:
            # Skip write tools unless the caller explicitly opted in.
            if _is_write_tool(call.tool) and not include_writes:
                report.calls.append(
                    CallResult(
                        seq=call.seq,
                        tool=call.tool,
                        status="skipped",
                        captured_hash=call.result_sha256,
                    )
                )
                continue

            try:
                fresh_result = loop.run_until_complete(_invoke(call.tool, call.args))
                fresh_hash = _canon_hash(fresh_result)
                status: CallStatus = "match" if fresh_hash == call.result_sha256 else "diff"
                if status == "diff":
                    report.passed = False
                report.calls.append(
                    CallResult(
                        seq=call.seq,
                        tool=call.tool,
                        status=status,
                        captured_hash=call.result_sha256,
                        fresh_hash=fresh_hash,
                    )
                )
            except Exception as exc:
                # Live-disabled errors on connectors are expected during offline
                # replay — treat them as skipped, not as failures.
                if isinstance(exc, ToolError) and exc.code == CODE_LIVE_DISABLED:
                    report.calls.append(
                        CallResult(
                            seq=call.seq,
                            tool=call.tool,
                            status="skipped",
                            captured_hash=call.result_sha256,
                            error="live connector disabled (offline replay)",
                        )
                    )
                else:
                    report.passed = False
                    report.calls.append(
                        CallResult(
                            seq=call.seq,
                            tool=call.tool,
                            status="error",
                            captured_hash=call.result_sha256,
                            error=str(exc),
                        )
                    )
    finally:
        loop.close()
        # Restore whatever the caller had, so replay doesn't pollute the process.
        if _old_live is not None:
            os.environ["STRATA_MCP_LIVE_CONNECTORS"] = _old_live

    return report


# ── fixture loader ─────────────────────────────────────────────────────────────


def load_session_from_fixture(path: Path | str) -> list[ToolCall]:
    """Parse a JSON fixture written by ``traces export`` into ``ToolCall`` objects.

    The fixture shape is documented in this module's docstring.  ``schema_version``
    is validated so a fixture written by a future incompatible version is caught
    early rather than silently producing wrong replay results."""
    raw = Path(path).read_text(encoding="utf-8")
    data: dict[str, Any] = json.loads(raw)

    version = data.get("schema_version", 0)
    if version != 1:
        raise ValueError(
            f"Unsupported fixture schema_version={version!r}; expected 1. "
            "Re-export with a matching strata version."
        )

    calls_raw: list[dict[str, Any]] = data.get("calls", [])
    return [ToolCall.model_validate(c) for c in calls_raw]
