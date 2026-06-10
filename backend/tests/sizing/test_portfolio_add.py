"""CLI tests for `strata portfolio add` — single-company add (spec §7, F6 gate)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from strata.cli import app
from strata.sizing.store import CompanyStore

runner = CliRunner()

# Repo-root data dir (tests run from backend/): backend/tests/sizing -> repo root.
_DATA_DIR = Path(__file__).resolve().parents[3] / "data"


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


def test_add_blank_name_rejected(portfolio_enabled: None, tmp_path: Path) -> None:
    """ADV-5: a whitespace-only --name is a usage error, not a stored row."""
    store = tmp_path / "p.json"
    r = runner.invoke(app, ["portfolio", "add", "--name", "   ", "--store", str(store)])
    assert r.exit_code != 0
    assert "non-empty" in r.output
    assert not store.exists()


def test_add_explicit_unknown_market_exits_1_with_suggestions(
    portfolio_enabled: None, tmp_path: Path
) -> None:
    """ADV-1: an explicit --market slug missing from the registry must fail
    honestly (with near-miss suggestions), never fuzzy-reroute — and fail fast,
    before any row is written."""
    store = tmp_path / "p.json"
    r = runner.invoke(
        app,
        [
            "portfolio",
            "add",
            "--name",
            "Acme Insurtech",
            "--domain",
            "acme.example",
            "--market",
            "doc-gen-pc",
            "--size",
            "--store",
            str(store),
            "-d",
            str(_DATA_DIR),
        ],
    )
    assert r.exit_code == 1
    assert "unknown market concept slug" in r.output
    assert "doc-gen-pc-insurance" in r.output  # near-miss suggestion
    assert not store.exists()  # fail-fast: no partial state


def test_add_bad_data_dir_is_clean_error(portfolio_enabled: None, tmp_path: Path) -> None:
    """ADV-4: a missing data dir on the --size path is a one-line error
    suggesting `-d ../data`, not a raw traceback."""
    store = tmp_path / "p.json"
    r = runner.invoke(
        app,
        [
            "portfolio",
            "add",
            "--name",
            "Acme",
            "--size",
            "--store",
            str(store),
            "-d",
            str(tmp_path / "no-such-data"),
        ],
    )
    assert r.exit_code == 1
    assert "could not load data dir" in r.output
    assert "-d ../data" in r.output
    assert not store.exists()


def test_readd_with_market_updates_row(portfolio_enabled: None, tmp_path: Path) -> None:
    """ADV-3: a re-add carrying NEW info (--market/--vertical) updates the
    stored row instead of silently skipping it."""
    store = tmp_path / "p.json"
    base = ["portfolio", "add", "--name", "Acme", "--domain", "acme.example", "--store", str(store)]
    r1 = runner.invoke(app, base)
    assert r1.exit_code == 0 and "added" in r1.output

    r2 = runner.invoke(app, [*base, "--market", "doc-gen-pc-insurance"])
    assert r2.exit_code == 0
    assert "updated" in r2.output
    # Without --size there is no registry — the slug is stored with an
    # explicit "unvalidated" note, never silently trusted.
    assert "unvalidated" in r2.output

    rec = CompanyStore(store, org_id="default").get("acme.example")
    assert rec is not None
    assert rec.market_concept_slug == "doc-gen-pc-insurance"

    # A plain re-add with no new info stays idempotent.
    r3 = runner.invoke(app, base)
    assert r3.exit_code == 0 and "already in portfolio" in r3.output


def test_add_with_size_real_slug_sizes(portfolio_enabled: None, tmp_path: Path) -> None:
    """Happy path: an explicit, registry-known --market sizes immediately."""
    store = tmp_path / "p.json"
    r = runner.invoke(
        app,
        [
            "portfolio",
            "add",
            "--name",
            "Acme Insurtech",
            "--domain",
            "acme.example",
            "--market",
            "doc-gen-pc-insurance",
            "--size",
            "--store",
            str(store),
            "-d",
            str(_DATA_DIR),
        ],
    )
    assert r.exit_code == 0
    assert "sized" in r.output

    rec = CompanyStore(store, org_id="default").get("acme.example")
    assert rec is not None
    assert rec.status == "sized"
    assert rec.market_concept_slug == "doc-gen-pc-insurance"
    assert rec.tam_value and rec.tam_value > 0


def test_two_orgs_share_one_store_file(portfolio_enabled: None, tmp_path: Path) -> None:
    """ADV-2: a second org's write must not wipe the first org's rows."""
    store = tmp_path / "p.json"
    r1 = runner.invoke(
        app,
        [
            "portfolio",
            "add",
            "--name",
            "Alpha",
            "--domain",
            "alpha.example",
            "--org",
            "org-a",
            "--store",
            str(store),
        ],
    )
    assert r1.exit_code == 0 and "added" in r1.output
    r2 = runner.invoke(
        app,
        [
            "portfolio",
            "add",
            "--name",
            "Beta",
            "--domain",
            "beta.example",
            "--org",
            "org-b",
            "--store",
            str(store),
        ],
    )
    assert r2.exit_code == 0 and "added" in r2.output

    assert CompanyStore(store, org_id="org-a").get("alpha.example") is not None
    assert CompanyStore(store, org_id="org-b").get("beta.example") is not None


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
