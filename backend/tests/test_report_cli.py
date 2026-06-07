"""CLI smoke tests for `strata report --premium` and `strata verify`.

Drive the real Typer app against the committed data bank (../data). Offline:
no LLM, no network, no DB (concept-slug path only — the hash path needs the
durable store, exercised by the MCP suite).
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from strata.cli import app

runner = CliRunner()

_DATA_DIR = str(Path(__file__).resolve().parents[2] / "data")
_CONCEPT = "doc-gen-pc-insurance"


def test_report_premium_emits_html() -> None:
    result = runner.invoke(app, ["report", _CONCEPT, "--data-dir", _DATA_DIR, "--premium"])
    assert result.exit_code == 0, result.output
    assert "<!doctype html>" in result.output
    assert "<svg" in result.output


def test_report_premium_writes_to_out(tmp_path: Path) -> None:
    out = tmp_path / "deck.html"
    result = runner.invoke(
        app,
        [
            "report",
            _CONCEPT,
            "--data-dir",
            _DATA_DIR,
            "--premium",
            "--out",
            str(out),
            "--brand-name",
            "Altimeter",
            "--brand-color",
            "#5B5BD6",
        ],
    )
    assert result.exit_code == 0, result.output
    html = out.read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>")
    assert "Altimeter" in html


def test_report_plain_still_works() -> None:
    result = runner.invoke(app, ["report", _CONCEPT, "--data-dir", _DATA_DIR])
    assert result.exit_code == 0, result.output
    assert "Market report" in result.output


def test_verify_known_claim() -> None:
    result = runner.invoke(
        app, ["verify", "P&C insurance document generation", "--data-dir", _DATA_DIR]
    )
    assert result.exit_code == 0, result.output
    assert "Verdict:" in result.output
    assert "Sourced range" in result.output


def test_verify_unknown_claim_is_unverifiable() -> None:
    result = runner.invoke(
        app, ["verify", "completely-unknown-market-zzz-9999", "--data-dir", _DATA_DIR]
    )
    assert result.exit_code == 0, result.output
    assert "unverifiable" in result.output
