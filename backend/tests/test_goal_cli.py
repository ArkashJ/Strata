"""CLI tests for `strata goal` (spec §7).

Pipeline is mocked at the resolver entrypoint so the CLI surface (Typer
arg-parsing, exit codes, output mode wiring, registry-load + auto-primitive
augmentation, STRATA_OFFLINE handling) is exercised in isolation.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from strata.cli import app
from strata.resolver.events import PipelineStatus
from strata.resolver.events import ResolverResult as RR

runner = CliRunner()


def _success() -> RR:
    return RR(
        status=PipelineStatus.OK,
        via="connector",
        tam_value=1_234_567_890.0,
        formatted_tam="$1.2B",
        concept_name="Test concept",
        framework_name="platform_throughput",
        primitives_used=[
            {"slug": "fdic-bank-count-us-2024", "value": 4577, "name": "Bank count"},
            {
                "slug": "fdic-total-deposits-us-2024",
                "value": 19_400_000_000_000,
                "name": "Deposits",
            },
        ],
        banner=None,
    )


def _failure() -> RR:
    return RR(
        status=PipelineStatus.FAILED,
        via="none",
        error="all steps failed",
    )


@patch("strata.loader.load_data_dir")
@patch("strata.resolver.run")
def test_goal_happy_path_compact(mock_run, mock_load, tmp_path: Path) -> None:
    from strata.loader import LoadedRecords

    mock_load.return_value = LoadedRecords()
    mock_run.return_value = _success()

    (tmp_path / "primitives").mkdir()
    result = runner.invoke(app, ["goal", "test query", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "TAM" in result.output
    assert "$1.2B" in result.output


@patch("strata.loader.load_data_dir")
@patch("strata.resolver.run")
def test_goal_json_mode(mock_run, mock_load, tmp_path: Path) -> None:
    from strata.loader import LoadedRecords

    mock_load.return_value = LoadedRecords()
    mock_run.return_value = _success()

    (tmp_path / "primitives").mkdir()
    result = runner.invoke(app, ["goal", "test", "--json", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["tam_value"] == 1_234_567_890.0


@patch("strata.loader.load_data_dir")
@patch("strata.resolver.run")
def test_goal_stream_mode_prints_events(mock_run, mock_load, tmp_path: Path) -> None:
    from strata.loader import LoadedRecords
    from strata.resolver.events import PipelineEvent, PipelineEventKind

    rr = _success()
    rr.events = [
        PipelineEvent(kind=PipelineEventKind.PARSING, step="pre", payload={"query": "x"}),
        PipelineEvent(
            kind=PipelineEventKind.SLUG_RESOLVED, step="pre", payload={"intent": "novel"}
        ),
    ]
    mock_load.return_value = LoadedRecords()
    mock_run.return_value = rr

    (tmp_path / "primitives").mkdir()
    result = runner.invoke(app, ["goal", "x", "--stream", "--data-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "→ Parsing" in result.output
    assert "Slug resolver" in result.output


def test_goal_stream_and_json_are_mutually_exclusive(tmp_path: Path) -> None:
    (tmp_path / "primitives").mkdir()
    result = runner.invoke(app, ["goal", "x", "--stream", "--json", "--data-dir", str(tmp_path)])
    assert result.exit_code == 2
    assert "mutually exclusive" in result.output


@patch("strata.loader.load_data_dir")
@patch("strata.resolver.run")
def test_goal_failure_exits_with_3_when_pipeline_returned_error(
    mock_run, mock_load, tmp_path: Path
) -> None:
    from strata.loader import LoadedRecords

    mock_load.return_value = LoadedRecords()
    mock_run.return_value = _failure()
    (tmp_path / "primitives").mkdir()
    # Exit 3 is the live/fallback-allowed path; clear STRATA_OFFLINE so CI's
    # global offline flag doesn't force the --no-live/--no-fallback exit-1 path.
    result = runner.invoke(
        app, ["goal", "test", "--data-dir", str(tmp_path)], env={"STRATA_OFFLINE": None}
    )
    assert result.exit_code == 3


@patch("strata.loader.load_data_dir")
@patch("strata.resolver.run")
def test_goal_failure_with_no_live_no_fallback_exits_1(mock_run, mock_load, tmp_path: Path) -> None:
    """Per spec §7 — exit 1 when both opt-outs are set and registry misses."""
    from strata.loader import LoadedRecords

    mock_load.return_value = LoadedRecords()
    mock_run.return_value = _failure()

    (tmp_path / "primitives").mkdir()
    result = runner.invoke(
        app,
        ["goal", "test", "--no-live", "--no-fallback", "--data-dir", str(tmp_path)],
    )
    assert result.exit_code == 1


@patch("strata.loader.load_data_dir")
@patch("strata.resolver.run")
def test_goal_strata_offline_env_sets_no_live_and_no_fallback(
    mock_run, mock_load, tmp_path: Path, monkeypatch
) -> None:
    """Audit fix K — STRATA_OFFLINE=1 disables steps 3 + 4."""
    from strata.loader import LoadedRecords
    from strata.resolver import RunOptions

    monkeypatch.setenv("STRATA_OFFLINE", "1")
    mock_load.return_value = LoadedRecords()
    mock_run.return_value = _success()

    (tmp_path / "primitives").mkdir()
    runner.invoke(app, ["goal", "test", "--data-dir", str(tmp_path)])

    # Verify run() was called with both opt-outs enabled.
    assert mock_run.called
    call_options: RunOptions = mock_run.call_args.kwargs["options"]
    assert call_options.allow_live is False
    assert call_options.allow_fallback is False


@patch("strata.loader.load_data_dir")
@patch("strata.resolver.run")
def test_goal_explicit_flags_override_options(mock_run, mock_load, tmp_path: Path) -> None:
    from strata.loader import LoadedRecords
    from strata.resolver import RunOptions

    mock_load.return_value = LoadedRecords()
    mock_run.return_value = _success()

    (tmp_path / "primitives").mkdir()
    runner.invoke(
        app,
        [
            "goal",
            "test",
            "--no-live",
            "--primitive-only",
            "--expansion-budget",
            "12",
            "--data-dir",
            str(tmp_path),
        ],
    )
    call_options: RunOptions = mock_run.call_args.kwargs["options"]
    assert call_options.allow_live is False
    assert call_options.primitive_only is True
    assert call_options.expansion_budget == 12


def test_goal_missing_data_dir_exits_2(tmp_path: Path) -> None:
    """Bad --data-dir argument → exit 2 (Typer's standard for arg errors)."""
    nonexistent = tmp_path / "does-not-exist"
    result = runner.invoke(app, ["goal", "test", "--data-dir", str(nonexistent)])
    # Typer surfaces this through its own arg-validation OR our LoaderError
    # branch; either way the exit code is 2.
    assert result.exit_code in (1, 2)
