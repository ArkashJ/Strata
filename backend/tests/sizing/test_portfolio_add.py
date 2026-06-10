"""CLI tests for `strata portfolio add` — single-company add (spec §7, F6 gate)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from strata.cli import app
from strata.config import settings
from strata.sizing.store import CompanyStore

runner = CliRunner()

# Repo-root data dir (tests run from backend/): backend/tests/sizing -> repo root.
_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


@pytest.fixture
def portfolio_enabled() -> Iterator[None]:
    prev = settings.portfolio_enabled
    settings.portfolio_enabled = True
    try:
        yield
    finally:
        settings.portfolio_enabled = prev


def test_add_disabled_by_default(tmp_path: Path) -> None:
    """F6: the write surface ships dark — add exits 2 when the gate is off."""
    store = tmp_path / "p.json"
    result = runner.invoke(app, ["portfolio", "add", "--name", "X", "--store", str(store)])
    assert result.exit_code == 2
    assert "disabled" in result.stdout


def test_add_single_company_idempotent(portfolio_enabled: None, tmp_path: Path) -> None:
    store = tmp_path / "p.json"
    args = [
        "portfolio",
        "add",
        "--name",
        "Synthio Labs",
        "--domain",
        "https://www.synthiolabs.com/platform",
        "--vertical",
        "Pharma",
        "--store",
        str(store),
    ]
    r1 = runner.invoke(app, args)
    assert r1.exit_code == 0
    assert "added" in r1.stdout

    # Second add is a no-op (idempotent on the normalized domain).
    r2 = runner.invoke(app, args)
    assert r2.exit_code == 0
    assert "already in portfolio" in r2.stdout

    # Domain was normalized (scheme/www/path stripped) and the row persisted.
    rec = CompanyStore(store, org_id="default").get("synthiolabs.com")
    assert rec is not None
    assert rec.name == "Synthio Labs"
    assert rec.domain == "synthiolabs.com"
    assert rec.vertical == "Pharma"
    assert rec.status == "unsized"


def test_add_with_size_unsizable_is_honest(portfolio_enabled: None, tmp_path: Path) -> None:
    """--size sizes registry-first; an uncurated market is an honest unsizable,
    never an invented number (Q20)."""
    store = tmp_path / "p.json"
    r = runner.invoke(
        app,
        [
            "portfolio",
            "add",
            "--name",
            "Synthio Labs",
            "--domain",
            "synthiolabs.com",
            "--vertical",
            "Pharma commercialization / HCP engagement",
            "--size",
            "--store",
            str(store),
            "-d",
            str(_DATA_DIR),
        ],
    )
    assert r.exit_code == 0
    assert "unsizable" in r.stdout

    rec = CompanyStore(store, org_id="default").get("synthiolabs.com")
    assert rec is not None
    assert rec.status == "unsizable"
    assert rec.reason  # honesty: the miss explains itself
