"""MCP trace replay harness (Direction 1, plan #13/#15).

These tests are pure + offline — no Postgres needed.  They drive
``replay_session`` against the checked-in golden fixture and assert the three
behaviours the harness exists to guarantee:

  AC-1.2/1.3  a captured session round-trips green on unchanged code (every call
              reports ``match``, ``passed=True``).
  Divergence  a handler returning a different result surfaces a ``diff`` and
              flips ``passed`` to False (the CI regression signal).
  Writes      ``_WRITE``-annotated tools are reported ``skipped`` (not mutated,
              not a false regression) under the default ``include_writes=False``.

Per the fixture review (design D2): replay hashes the FULL fresh result and
compares it to the captured ``result_sha256``; ``result_summary`` is display-only
and is never asserted on here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from strata.loader import load_data_dir
from strata.models.trace import ToolCall, TraceStatus
from strata.registry import Registry
from strata.traces.replay import load_session_from_fixture, replay_session

_DATA = Path(__file__).resolve().parents[2] / "data"
_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "traces" / "golden_session.json"


@pytest.fixture(scope="module")
def reg() -> Registry:
    return Registry.from_loaded(load_data_dir(_DATA))


# --------------------------------------------------------------------------- #
# Round-trip green on unchanged code (AC-1.2 / AC-1.3).                        #
# --------------------------------------------------------------------------- #


def test_golden_fixture_round_trips_green(reg: Registry) -> None:
    """The checked-in golden session replays clean: every read-only call matches
    its captured hash, so ``passed`` is True."""
    calls = load_session_from_fixture(_FIXTURE)
    assert len(calls) == 2  # list_frameworks + search_concepts

    report = replay_session(reg, calls)

    assert report.passed is True
    assert {c.status for c in report.calls} == {"match"}
    # Each match recomputed a fresh hash equal to the captured one.
    for cr in report.calls:
        assert cr.fresh_hash == cr.captured_hash


def test_fixture_loader_rejects_wrong_schema_version(tmp_path: Path) -> None:
    """A fixture written by a future incompatible version is caught early rather
    than silently producing wrong replay results."""
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema_version": 99, "calls": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        load_session_from_fixture(bad)


# --------------------------------------------------------------------------- #
# Divergence is caught (AC-1.3).                                               #
# --------------------------------------------------------------------------- #


def test_divergence_is_reported_and_fails(reg: Registry, monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch a read handler so its fresh result differs from the captured
    one — replay must flag a ``diff`` and flip ``passed`` to False (the signal a
    CI gate exits non-zero on)."""
    calls = load_session_from_fixture(_FIXTURE)

    # Make list_frameworks return a brand-new shape so its fresh hash can't match.
    import strata.mcp.tools as tools

    def _drifted(_reg: Registry, _args: object) -> dict[str, object]:
        return {"count": -999, "frameworks": ["this", "changed"]}

    monkeypatch.setitem(tools.TOOLS["list_frameworks"], "handler", _drifted)

    report = replay_session(reg, calls)

    assert report.passed is False
    by_tool = {c.tool: c for c in report.calls}
    assert by_tool["list_frameworks"].status == "diff"
    assert by_tool["list_frameworks"].fresh_hash != by_tool["list_frameworks"].captured_hash
    # The unmodified call still matched — only the drifted one regressed.
    assert by_tool["search_concepts"].status == "match"


def test_handler_error_is_reported_as_error_not_crash(
    reg: Registry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A handler that raises a non-live ToolError during replay is recorded as an
    ``error`` call (passed=False), not propagated out of replay_session."""
    import strata.mcp.tools as tools
    from strata.mcp.errors import CODE_INVALID_INPUT, ToolError

    def _boom(_reg: Registry, _args: object) -> dict[str, object]:
        raise ToolError("intentional", code=CODE_INVALID_INPUT)

    calls = load_session_from_fixture(_FIXTURE)
    monkeypatch.setitem(tools.TOOLS["list_frameworks"], "handler", _boom)

    report = replay_session(reg, calls)

    assert report.passed is False
    by_tool = {c.tool: c for c in report.calls}
    assert by_tool["list_frameworks"].status == "error"
    assert by_tool["list_frameworks"].error is not None


# --------------------------------------------------------------------------- #
# Write tools are skipped, not replayed (default include_writes=False).        #
# --------------------------------------------------------------------------- #


def _write_call(tool: str, args: dict[str, object]) -> ToolCall:
    """Hand-build a captured ToolCall row for a write tool (the golden fixture is
    read-only by design; replaying a real write would mutate org data)."""
    return ToolCall(
        id=1,
        org_id="test-org",
        session_id="write-sess",
        seq=1,
        created_at=datetime(2026, 6, 8, tzinfo=UTC),
        tool=tool,
        args=args,
        args_truncated=False,
        result_summary={"recorded": True},
        result_sha256="0" * 64,
        result_truncated=False,
        status=TraceStatus.OK,
        duration_ms=1,
    )


def test_write_tools_skipped_by_default(reg: Registry) -> None:
    """A ``_WRITE``-annotated tool in the captured sequence is reported
    ``skipped`` under the default — never invoked, never a false regression."""
    # record_session_reasoning carries the _WRITE annotation (readOnlyHint=False).
    calls = [_write_call("record_session_reasoning", {"payload": {"reasoning": "x"}})]

    report = replay_session(reg, calls)

    assert len(report.calls) == 1
    assert report.calls[0].status == "skipped"
    assert report.calls[0].tool == "record_session_reasoning"
    # Skipped calls never flip passed — they are not regressions.
    assert report.passed is True


def test_write_tool_skipped_does_not_invoke_handler(
    reg: Registry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The skip happens BEFORE dispatch: a rigged handler for a write tool is
    never called under the default include_writes=False."""
    import strata.mcp.tools as tools

    invoked = False

    def _tripwire(_reg: Registry, _args: object) -> dict[str, object]:
        nonlocal invoked
        invoked = True
        return {}

    monkeypatch.setitem(tools.TOOLS["import_portfolio"], "handler", _tripwire)

    calls = [_write_call("import_portfolio", {"rows": []})]
    report = replay_session(reg, calls)

    assert invoked is False, "a write tool must not be dispatched on default replay"
    assert report.calls[0].status == "skipped"
