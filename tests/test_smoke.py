"""Smoke test: the package imports and the CLI is wired up."""

from __future__ import annotations

from typer.testing import CliRunner

import strata
from strata.cli import app


def test_package_has_version() -> None:
    assert isinstance(strata.__version__, str)
    assert len(strata.__version__) > 0


def test_cli_version_command_runs() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0, result.output
    assert strata.__version__ in result.stdout
