"""Tests for the ingest orchestrator + ``strata ingest`` CLI (Session 3).

The orchestrator is exercised with a fake ``call_and_convert`` so no network
or API keys are touched. Coverage:

  - manifest parsing into typed records
  - the run plan crosses all_capabilities() x manifest and honors filters
  - a connector with an unset required key is skipped (logged, non-fatal)
  - a failing arg-set is logged and does not abort the batch
  - dedup: same method args → same auto_args_hash → single file
  - status lists on-disk provenance
  - refresh rewrites only when snapshot_sha256 changed
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from strata.cli import app
from strata.ingest import orchestrator
from strata.ingest.manifest import load_manifest

runner = CliRunner()

# A self-contained manifest exercising one keyless connector and one key-gated
# connector, so the skip path is deterministic regardless of the dev env.
_MANIFEST = {
    "connectors": {
        "edgar": {
            "methods": {
                "get_company_concept": [
                    {
                        "cik": "0000320193",
                        "taxonomy": "us-gaap",
                        "concept": "Revenues",
                        "concept_slug": "us-public-company-revenue",
                        "primitive_slug": "edgar-aapl-revenue",
                        "name": "Apple revenue",
                        "description": "Apple total revenue.",
                        "source_url": "https://sec.gov/",
                        "unit_kind": "flow",
                        "unit_dimension": "currency",
                        "unit_currency": "USD",
                    }
                ]
            },
        },
        "fred": {
            "requires_key": "STRATA_FRED_API_KEY",
            "methods": {
                "get_observations": [
                    {
                        "series_id": "GDP",
                        "concept_slug": "us-gdp",
                        "primitive_slug": "fred-us-gdp",
                        "name": "US GDP",
                        "description": "US nominal GDP.",
                        "source_url": "https://fred.stlouisfed.org/",
                        "unit_kind": "flow",
                        "unit_dimension": "currency",
                        "unit_currency": "USD",
                    }
                ]
            },
        },
    }
}


@pytest.fixture
def manifest_file(tmp_path: Path) -> Path:
    path = tmp_path / "ingest-manifest.yaml"
    path.write_text(yaml.safe_dump(_MANIFEST))
    return path


def _fake_primitive(slug: str, snapshot: str, value: float = 1.0) -> dict[str, Any]:
    """A complete, schema-valid AtomicPrimitive dict — the writer validates it,
    so every required field must be present. ``snapshot`` drives the refresh
    freshness comparison; ``value`` lets a test confirm a rewrite landed."""
    return {
        "kind": "atomic_primitive",
        "slug": slug,
        "schema_version": 1,
        "concept_slug": "x",
        "name": "x",
        "description": "x",
        "value": value,
        "unit": {"kind": "flow", "dimension": "currency", "currency": "USD"},
        "as_of": "2024-01-01",
        "geo": {"level": "country", "codes": ["US"]},
        "geo_perspective": "supply",
        "distribution_shape": "normal",
        "delivery_mode": "n/a",
        "source": {
            "slug": f"{slug}-src",
            "tier": "regulator",
            "url": "https://example.gov/",
            "accessed": "2026-05-28",
            "snapshot_sha256": hashlib.sha256(snapshot.encode()).hexdigest(),
        },
    }


# ── manifest parsing ────────────────────────────────────────────────────


def test_load_manifest_parses_typed_records(manifest_file: Path) -> None:
    m = load_manifest(manifest_file)
    edgar = m.get("edgar")
    assert edgar is not None
    assert edgar.requires_key is None
    assert edgar.methods[0].method == "get_company_concept"
    assert edgar.methods[0].arg_sets[0]["cik"] == "0000320193"
    fred = m.get("fred")
    assert fred is not None and fred.requires_key == "STRATA_FRED_API_KEY"


def test_load_manifest_rejects_missing_connectors_key(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump({"nope": {}}))
    with pytest.raises(ValueError):
        load_manifest(bad)


def test_repo_manifest_loads() -> None:
    # The committed manifest must parse — guards against YAML drift. It lives
    # beside data/ (not inside it) so the registry loader does not walk it.
    repo_manifest = Path(__file__).resolve().parents[2] / "ingest-manifest.yaml"
    m = load_manifest(repo_manifest)
    assert m.get("edgar") is not None


# ── run: writes, skips, dedup ─────────────────────────────────────────────


def test_run_writes_keyless_skips_keyed(
    manifest_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("STRATA_FRED_API_KEY", raising=False)

    def fake_cc(connector: str, method: str, args: dict[str, Any]) -> dict[str, Any]:
        return _fake_primitive(args["primitive_slug"], "snap-a")

    monkeypatch.setattr(orchestrator, "call_and_convert", fake_cc)
    out = tmp_path / "auto"
    report = orchestrator.run_ingest(manifest_path=manifest_file, out_dir=out)

    assert report.written == 1  # only edgar
    assert ("fred", "missing API key STRATA_FRED_API_KEY") in report.skipped_connectors
    assert (out / "edgar-aapl-revenue.yaml").exists()


def test_run_keyed_connector_runs_when_key_present(
    manifest_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STRATA_FRED_API_KEY", "present")
    monkeypatch.setattr(
        orchestrator,
        "call_and_convert",
        lambda c, m, a: _fake_primitive(a["primitive_slug"], "snap-a"),
    )
    report = orchestrator.run_ingest(manifest_path=manifest_file, out_dir=tmp_path / "auto")
    assert report.written == 2
    assert report.skipped_connectors == ()


def test_run_tier_filter_only_regulator(
    manifest_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STRATA_FRED_API_KEY", "present")
    monkeypatch.setattr(
        orchestrator,
        "call_and_convert",
        lambda c, m, a: _fake_primitive(a["primitive_slug"], "snap-a"),
    )
    # Both edgar and fred are regulator tier, so a bogus tier yields nothing.
    report = orchestrator.run_ingest(
        manifest_path=manifest_file, tier_filter="aggregator", out_dir=tmp_path / "auto"
    )
    assert report.written == 0


def test_run_connector_filter(
    manifest_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STRATA_FRED_API_KEY", "present")
    monkeypatch.setattr(
        orchestrator,
        "call_and_convert",
        lambda c, m, a: _fake_primitive(a["primitive_slug"], "snap-a"),
    )
    report = orchestrator.run_ingest(
        manifest_path=manifest_file, connector_filter="edgar", out_dir=tmp_path / "auto"
    )
    assert report.written == 1
    assert all(r.connector == "edgar" for r in report.results)


def test_run_item_failure_is_non_fatal(
    manifest_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STRATA_FRED_API_KEY", "present")

    def boom(connector: str, method: str, args: dict[str, Any]) -> dict[str, Any]:
        if connector == "fred":
            raise RuntimeError("network down")
        return _fake_primitive(args["primitive_slug"], "snap-a")

    monkeypatch.setattr(orchestrator, "call_and_convert", boom)
    report = orchestrator.run_ingest(manifest_path=manifest_file, out_dir=tmp_path / "auto")
    assert report.written == 1
    assert report.failed == 1


def test_dedup_hash_stable_across_metadata_edits(manifest_file: Path) -> None:
    # The dedup hash is computed from method args only, so renaming the
    # primitive must not change it.
    a = orchestrator.method_only_args(
        "fred", "get_observations", {"series_id": "GDP", "primitive_slug": "x", "name": "n1"}
    )
    b = orchestrator.method_only_args(
        "fred", "get_observations", {"series_id": "GDP", "primitive_slug": "y", "name": "n2"}
    )
    assert a == b == {"series_id": "GDP"}
    assert orchestrator.dedup_hash("fred", "get_observations", a) == orchestrator.dedup_hash(
        "fred", "get_observations", b
    )


# ── status ────────────────────────────────────────────────────────────────


def test_status_lists_written_primitives(
    manifest_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "auto"
    monkeypatch.setattr(
        orchestrator,
        "call_and_convert",
        lambda c, m, a: _fake_primitive(a["primitive_slug"], "snap-a"),
    )
    monkeypatch.setenv("STRATA_FRED_API_KEY", "present")
    orchestrator.run_ingest(manifest_path=manifest_file, out_dir=out)
    rows = orchestrator.ingest_status(out_dir=out)
    slugs = {r.slug for r in rows}
    assert "edgar-aapl-revenue" in slugs
    edgar_row = next(r for r in rows if r.slug == "edgar-aapl-revenue")
    assert edgar_row.connector == "edgar"
    assert edgar_row.method == "get_company_concept"


def test_status_empty_when_no_dir(tmp_path: Path) -> None:
    assert orchestrator.ingest_status(out_dir=tmp_path / "nope") == []


# ── refresh: rewrite only on snapshot change ───────────────────────────────


def test_refresh_unchanged_when_snapshot_matches(
    manifest_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "auto"
    monkeypatch.setenv("STRATA_FRED_API_KEY", "present")
    monkeypatch.setattr(
        orchestrator,
        "call_and_convert",
        lambda c, m, a: _fake_primitive(a["primitive_slug"], "snap-a"),
    )
    orchestrator.run_ingest(manifest_path=manifest_file, out_dir=out)
    report = orchestrator.refresh_ingest(manifest_path=manifest_file, out_dir=out)
    assert report.refreshed == 0
    assert report.unchanged == 2


def test_refresh_rewrites_when_snapshot_changes(
    manifest_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "auto"
    monkeypatch.setenv("STRATA_FRED_API_KEY", "present")
    monkeypatch.setattr(
        orchestrator,
        "call_and_convert",
        lambda c, m, a: _fake_primitive(a["primitive_slug"], "snap-a", value=1.0),
    )
    orchestrator.run_ingest(manifest_path=manifest_file, out_dir=out)

    # Source moved: new snapshot hash → refresh must rewrite.
    monkeypatch.setattr(
        orchestrator,
        "call_and_convert",
        lambda c, m, a: _fake_primitive(a["primitive_slug"], "snap-b", value=2.0),
    )
    report = orchestrator.refresh_ingest(manifest_path=manifest_file, out_dir=out)
    assert report.refreshed == 2

    written = yaml.safe_load((out / "fred-us-gdp.yaml").read_text())
    assert written["value"] == 2.0
    assert written["source"]["snapshot_sha256"] == hashlib.sha256(b"snap-b").hexdigest()


# ── CLI wiring ──────────────────────────────────────────────────────────────


def test_cli_ingest_run_regulator_offline(
    manifest_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No keys, real call_and_convert: keyless connectors hit the network and
    # fail non-fatally; the command must still exit 0.
    monkeypatch.delenv("STRATA_FRED_API_KEY", raising=False)
    result = runner.invoke(
        app, ["ingest", "run", "--manifest", str(manifest_file), "--tier", "regulator"]
    )
    assert result.exit_code == 0, result.output


def test_cli_ingest_status_runs() -> None:
    result = runner.invoke(app, ["ingest", "status"])
    assert result.exit_code == 0


def test_cli_ingest_run_bad_manifest_exits_2(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("not: a manifest")
    result = runner.invoke(app, ["ingest", "run", "--manifest", str(bad)])
    assert result.exit_code == 2
