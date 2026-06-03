"""CLI tests for `strata promote` (spec §7)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from strata.cli import app
from strata.validator.pipeline import ValidationReport

runner = CliRunner()


def _good_primitive_yaml(slug: str) -> str:
    return f"""\
kind: atomic_primitive
slug: {slug}
schema_version: 1
concept_slug: test-concept
name: Test primitive
description: A test value
value: 100.0
unit:
  kind: stock
  dimension: people
as_of: '2026-05-27'
geo:
  level: country
  codes:
  - US
geo_perspective: supply
source:
  slug: test-source-2026
  tier: regulator
  url: https://example.com
  accessed: '2026-05-27'
  snapshot_sha256: {"a" * 64}
"""


def _empty_report() -> ValidationReport:
    return ValidationReport(findings=[], registry=None)


def test_promote_missing_file_exits_2(tmp_path: Path) -> None:
    """Slug that does not exist in ~/.strata/auto-primitives/ → exit 2."""
    with patch("strata.resolver.AUTO_PRIMITIVES_DIR", tmp_path):
        result = runner.invoke(app, ["promote", "nonexistent-slug"])
    assert result.exit_code == 2
    assert "does not exist" in result.output


def test_promote_happy_path(tmp_path: Path) -> None:
    """Auto-primitive copied to data/primitives/ and removed from auto dir."""
    auto_dir = tmp_path / "auto"
    auto_dir.mkdir()
    data_dir = tmp_path / "data"
    (data_dir / "primitives").mkdir(parents=True)
    slug = "fdic-test-bank-count-2024"
    (auto_dir / f"{slug}.yaml").write_text(_good_primitive_yaml(slug))

    with (
        patch("strata.resolver.AUTO_PRIMITIVES_DIR", auto_dir),
        patch("strata.cli.run_validate", return_value=_empty_report()),
    ):
        result = runner.invoke(app, ["promote", slug, "--data-dir", str(data_dir)])

    assert result.exit_code == 0, result.output
    assert "✓ Promoted" in result.output
    assert (data_dir / "primitives" / f"{slug}.yaml").exists()
    assert not (auto_dir / f"{slug}.yaml").exists()


def test_promote_idempotent_when_already_in_tree(tmp_path: Path) -> None:
    """Re-running promote on a slug already in data/primitives/ is a no-op."""
    auto_dir = tmp_path / "auto"
    auto_dir.mkdir()
    data_dir = tmp_path / "data"
    (data_dir / "primitives").mkdir(parents=True)
    slug = "fdic-test-2024"
    (auto_dir / f"{slug}.yaml").write_text(_good_primitive_yaml(slug))
    (data_dir / "primitives" / f"{slug}.yaml").write_text(_good_primitive_yaml(slug))

    with patch("strata.resolver.AUTO_PRIMITIVES_DIR", auto_dir):
        result = runner.invoke(app, ["promote", slug, "--data-dir", str(data_dir)])
    assert result.exit_code == 0
    assert "already promoted" in result.output


def test_promote_validator_rejects_rolls_back(tmp_path: Path) -> None:
    """If validator fails, the staged copy in data/primitives/ is removed."""
    from strata.validator import Severity
    from strata.validator.pipeline import ValidationFinding

    auto_dir = tmp_path / "auto"
    auto_dir.mkdir()
    data_dir = tmp_path / "data"
    (data_dir / "primitives").mkdir(parents=True)
    slug = "fdic-bad-2024"
    (auto_dir / f"{slug}.yaml").write_text(_good_primitive_yaml(slug))

    bad_report = ValidationReport(
        findings=[
            ValidationFinding(
                layer="structural",
                code="X001",
                severity=Severity.ERROR,
                message="some structural issue",
                slug=slug,
            )
        ],
        registry=None,
    )

    with (
        patch("strata.resolver.AUTO_PRIMITIVES_DIR", auto_dir),
        patch("strata.cli.run_validate", return_value=bad_report),
    ):
        result = runner.invoke(app, ["promote", slug, "--data-dir", str(data_dir)])

    assert result.exit_code == 1
    assert "validator rejected" in result.output
    # Rolled back: the file in data/primitives/ must not exist
    assert not (data_dir / "primitives" / f"{slug}.yaml").exists()
    # And the auto file must still be in place
    assert (auto_dir / f"{slug}.yaml").exists()


# ── bulk promote (`--from-ingest`) ──────────────────────────────────────


def _reject(slug: str) -> ValidationReport:
    from strata.validator import Severity
    from strata.validator.pipeline import ValidationFinding

    return ValidationReport(
        findings=[
            ValidationFinding(
                layer="semantic",
                code="X001",
                severity=Severity.ERROR,
                message="bad primitive",
                slug=slug,
            )
        ],
        registry=None,
    )


def test_promote_from_ingest_promotes_whole_batch(tmp_path: Path) -> None:
    auto_dir = tmp_path / "auto"
    auto_dir.mkdir()
    data_dir = tmp_path / "data"
    (data_dir / "primitives").mkdir(parents=True)
    slugs = ["census-firms-2022", "bls-wage-2024", "edgar-assets-2023"]
    for s in slugs:
        (auto_dir / f"{s}.yaml").write_text(_good_primitive_yaml(s))

    with (
        patch("strata.resolver.AUTO_PRIMITIVES_DIR", auto_dir),
        patch("strata.cli.run_validate", return_value=_empty_report()),
    ):
        result = runner.invoke(app, ["promote", "--from-ingest", "--data-dir", str(data_dir)])

    assert result.exit_code == 0, result.output
    assert "Promoted 3" in result.output
    for s in slugs:
        assert (data_dir / "primitives" / f"{s}.yaml").exists()
        assert not (auto_dir / f"{s}.yaml").exists()


def test_promote_from_ingest_rolls_back_only_offender(tmp_path: Path) -> None:
    """A single bad primitive is dropped; the rest of the batch still commits."""
    auto_dir = tmp_path / "auto"
    auto_dir.mkdir()
    data_dir = tmp_path / "data"
    (data_dir / "primitives").mkdir(parents=True)
    good = ["census-firms-2022", "bls-wage-2024"]
    bad = "edgar-broken-2023"
    for s in [*good, bad]:
        (auto_dir / f"{s}.yaml").write_text(_good_primitive_yaml(s))

    # First validate blames the offender; after it is rolled back the tree is clean.
    with (
        patch("strata.resolver.AUTO_PRIMITIVES_DIR", auto_dir),
        patch("strata.cli.run_validate", side_effect=[_reject(bad), _empty_report()]),
    ):
        result = runner.invoke(app, ["promote", "--from-ingest", "--data-dir", str(data_dir)])

    assert result.exit_code == 0, result.output
    assert "Promoted 2" in result.output
    for s in good:
        assert (data_dir / "primitives" / f"{s}.yaml").exists()
    assert not (data_dir / "primitives" / f"{bad}.yaml").exists()
    # offender stays in the staging dir for inspection
    assert (auto_dir / f"{bad}.yaml").exists()
    assert f"✗ {bad}" in result.output


def test_promote_from_ingest_validate_only_commits_nothing(tmp_path: Path) -> None:
    auto_dir = tmp_path / "auto"
    auto_dir.mkdir()
    data_dir = tmp_path / "data"
    (data_dir / "primitives").mkdir(parents=True)
    slug = "census-firms-2022"
    (auto_dir / f"{slug}.yaml").write_text(_good_primitive_yaml(slug))

    with (
        patch("strata.resolver.AUTO_PRIMITIVES_DIR", auto_dir),
        patch("strata.cli.run_validate", return_value=_empty_report()),
    ):
        result = runner.invoke(
            app, ["promote", "--from-ingest", "--validate-only", "--data-dir", str(data_dir)]
        )

    assert result.exit_code == 0, result.output
    assert "validate-only" in result.output
    assert "1 would promote" in result.output
    # nothing committed; the auto file is untouched
    assert not (data_dir / "primitives" / f"{slug}.yaml").exists()
    assert (auto_dir / f"{slug}.yaml").exists()


def test_promote_from_ingest_validate_only_cleans_up_with_rejection(tmp_path: Path) -> None:
    """Dry-run must leave NO files in data/primitives/, even when one is rejected."""
    auto_dir = tmp_path / "auto"
    auto_dir.mkdir()
    data_dir = tmp_path / "data"
    (data_dir / "primitives").mkdir(parents=True)
    good = "census-firms-2022"
    bad = "edgar-broken-2023"
    for s in (good, bad):
        (auto_dir / f"{s}.yaml").write_text(_good_primitive_yaml(s))

    with (
        patch("strata.resolver.AUTO_PRIMITIVES_DIR", auto_dir),
        patch("strata.cli.run_validate", side_effect=[_reject(bad), _empty_report()]),
    ):
        result = runner.invoke(
            app, ["promote", "--from-ingest", "--validate-only", "--data-dir", str(data_dir)]
        )

    assert result.exit_code == 0, result.output
    assert "1 would promote" in result.output
    # Nothing committed — neither the good nor the bad primitive lands on disk.
    assert list((data_dir / "primitives").glob("*.yaml")) == []
    # Both staging files remain for re-runs.
    assert (auto_dir / f"{good}.yaml").exists()
    assert (auto_dir / f"{bad}.yaml").exists()


def test_promote_requires_slug_or_flag() -> None:
    result = runner.invoke(app, ["promote"])
    assert result.exit_code == 2
    assert "--from-ingest" in result.output
