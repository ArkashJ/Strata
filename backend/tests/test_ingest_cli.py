"""Tests for the declarative ingest orchestrator + `strata ingest` CLI.

The orchestrator walks ``connectors._capability.all_capabilities()``, reads the
declarative ``data/ingest-manifest.yaml`` (per-connector methods + arg-sets),
calls ``connectors._dispatch.call_and_convert`` for each, and persists via
``resolver.writer.upsert_primitive`` (de-dup by ``metadata.auto_args_hash``).

All tests are offline: ``call_and_convert`` is injected so no network/keys are
touched. The single shared YAML fixture below conforms to the AtomicPrimitive
schema so ``upsert_primitive``'s validation chokepoint passes.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from strata.cli import app
from strata.connectors._capability import CapabilityArg, CapabilitySpec
from strata.ingest import (
    IngestTarget,
    ingest_status,
    load_manifest,
    refresh,
    run_ingest,
)

runner = CliRunner()


def _primitive_yaml(slug: str, *, value: float = 100.0, sha: str | None = None) -> dict[str, Any]:
    """A minimal AtomicPrimitive YAML dict the writer will accept."""
    return {
        "kind": "atomic_primitive",
        "slug": slug,
        "schema_version": 1,
        "concept_slug": "test-concept",
        "name": f"Test {slug}",
        "description": "fixture primitive",
        "value": value,
        "unit": {"kind": "stock", "dimension": "people"},
        "as_of": date.today().isoformat(),
        "geo": {"level": "country", "codes": ["US"]},
        "geo_perspective": "supply",
        "distribution_shape": "normal",
        "delivery_mode": "n/a",
        "source": {
            "slug": f"{slug}-src",
            "tier": "regulator",
            "url": "https://example.gov/data",
            "accessed": date.today().isoformat(),
            "snapshot_sha256": (sha or "a" * 64),
        },
    }


def _write_manifest(tmp_path: Path, body: dict[str, Any]) -> Path:
    path = tmp_path / "ingest-manifest.yaml"
    path.write_text(yaml.safe_dump(body, sort_keys=False))
    return path


_CAPS = [
    CapabilitySpec(
        connector="bls",
        method="get_series",
        description="BLS time series.",
        returns="a series",
        args=[CapabilityArg(name="series_id", type="str", description="id")],
        source_tier="regulator",
    ),
    CapabilitySpec(
        connector="worldbank",
        method="get_indicator",
        description="World Bank indicator.",
        returns="indicator values",
        args=[CapabilityArg(name="indicator", type="str", description="code")],
        source_tier="aggregator",
    ),
]


# ── manifest loading ──────────────────────────────────────────────────


def test_load_manifest_flattens_arg_sets(tmp_path: Path) -> None:
    path = _write_manifest(
        tmp_path,
        {
            "connectors": {
                "bls": [
                    {
                        "method": "get_series",
                        "arg_sets": [
                            {"series_id": "A", "primitive_slug": "bls-a"},
                            {"series_id": "B", "primitive_slug": "bls-b"},
                        ],
                    }
                ]
            }
        },
    )
    targets = load_manifest(path)
    assert [t.connector for t in targets] == ["bls", "bls"]
    assert [t.method for t in targets] == ["get_series", "get_series"]
    assert targets[0].args["series_id"] == "A"
    assert targets[1].args["primitive_slug"] == "bls-b"


def test_load_manifest_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises((FileNotFoundError, ValueError)):
        load_manifest(tmp_path / "nope.yaml")


# ── run_ingest core ───────────────────────────────────────────────────


def test_run_ingest_writes_one_primitive_per_arg_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STRATA_BLS_API_KEY", "k")
    out = tmp_path / "auto"
    manifest = _write_manifest(
        tmp_path,
        {
            "connectors": {
                "bls": [
                    {
                        "method": "get_series",
                        "arg_sets": [
                            {"series_id": "A", "primitive_slug": "bls-a"},
                            {"series_id": "B", "primitive_slug": "bls-b"},
                        ],
                    }
                ]
            }
        },
    )

    seen: list[dict[str, Any]] = []

    def fake_dispatch(connector: str, method: str, args: dict[str, Any]) -> dict[str, Any]:
        seen.append({"connector": connector, "method": method, "args": dict(args)})
        return _primitive_yaml(args["primitive_slug"])

    report = run_ingest(
        manifest_path=manifest,
        dir_override=out,
        capabilities=_CAPS,
        dispatch=fake_dispatch,
    )

    assert len(seen) == 2
    assert report.written == 2
    assert report.skipped_connectors == []
    assert (out / "bls-a.yaml").exists()
    assert (out / "bls-b.yaml").exists()


def test_run_ingest_skips_connector_without_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("STRATA_BLS_API_KEY", raising=False)
    out = tmp_path / "auto"
    manifest = _write_manifest(
        tmp_path,
        {
            "connectors": {
                "bls": [
                    {
                        "method": "get_series",
                        "arg_sets": [{"series_id": "A", "primitive_slug": "x"}],
                    }
                ]
            }
        },
    )

    def fake_dispatch(connector: str, method: str, args: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("dispatch must not run when the API key is absent")

    report = run_ingest(
        manifest_path=manifest,
        dir_override=out,
        capabilities=_CAPS,
        dispatch=fake_dispatch,
    )

    assert report.written == 0
    assert "bls" in report.skipped_connectors
    assert not out.exists() or not list(out.glob("*.yaml"))


def test_run_ingest_keyless_connector_not_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # worldbank takes no key; absence of STRATA_WORLDBANK_API_KEY must not skip it.
    monkeypatch.delenv("STRATA_WORLDBANK_API_KEY", raising=False)
    out = tmp_path / "auto"
    manifest = _write_manifest(
        tmp_path,
        {
            "connectors": {
                "worldbank": [
                    {
                        "method": "get_indicator",
                        "arg_sets": [{"indicator": "SP.POP.TOTL", "primitive_slug": "wb-pop"}],
                    }
                ]
            }
        },
    )

    def fake_dispatch(connector: str, method: str, args: dict[str, Any]) -> dict[str, Any]:
        return _primitive_yaml(args["primitive_slug"])

    report = run_ingest(
        manifest_path=manifest,
        dir_override=out,
        capabilities=_CAPS,
        dispatch=fake_dispatch,
        keyless_connectors={"worldbank"},
    )

    assert report.written == 1
    assert report.skipped_connectors == []


def test_run_ingest_tier_filter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRATA_BLS_API_KEY", "k")
    out = tmp_path / "auto"
    manifest = _write_manifest(
        tmp_path,
        {
            "connectors": {
                "bls": [
                    {
                        "method": "get_series",
                        "arg_sets": [{"series_id": "A", "primitive_slug": "b"}],
                    }
                ],
                "worldbank": [
                    {
                        "method": "get_indicator",
                        "arg_sets": [{"indicator": "X", "primitive_slug": "w"}],
                    }
                ],
            }
        },
    )

    def fake_dispatch(connector: str, method: str, args: dict[str, Any]) -> dict[str, Any]:
        return _primitive_yaml(args["primitive_slug"])

    report = run_ingest(
        manifest_path=manifest,
        dir_override=out,
        capabilities=_CAPS,
        dispatch=fake_dispatch,
        tier="aggregator",
        keyless_connectors={"worldbank"},
    )

    # Only the aggregator-tier worldbank target ran.
    assert report.written == 1
    assert (out / "w.yaml").exists()
    assert not (out / "b.yaml").exists()


def test_run_ingest_connector_filter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRATA_BLS_API_KEY", "k")
    out = tmp_path / "auto"
    manifest = _write_manifest(
        tmp_path,
        {
            "connectors": {
                "bls": [
                    {
                        "method": "get_series",
                        "arg_sets": [{"series_id": "A", "primitive_slug": "b"}],
                    }
                ],
                "worldbank": [
                    {
                        "method": "get_indicator",
                        "arg_sets": [{"indicator": "X", "primitive_slug": "w"}],
                    }
                ],
            }
        },
    )

    def fake_dispatch(connector: str, method: str, args: dict[str, Any]) -> dict[str, Any]:
        return _primitive_yaml(args["primitive_slug"])

    report = run_ingest(
        manifest_path=manifest,
        dir_override=out,
        capabilities=_CAPS,
        dispatch=fake_dispatch,
        connector="bls",
        keyless_connectors={"worldbank"},
    )

    assert report.written == 1
    assert (out / "b.yaml").exists()


def test_run_ingest_dispatch_failure_does_not_abort_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STRATA_BLS_API_KEY", "k")
    out = tmp_path / "auto"
    manifest = _write_manifest(
        tmp_path,
        {
            "connectors": {
                "bls": [
                    {
                        "method": "get_series",
                        "arg_sets": [
                            {"series_id": "BAD", "primitive_slug": "bad"},
                            {"series_id": "GOOD", "primitive_slug": "good"},
                        ],
                    }
                ]
            }
        },
    )

    def fake_dispatch(connector: str, method: str, args: dict[str, Any]) -> dict[str, Any]:
        if args["series_id"] == "BAD":
            raise ValueError("boom")
        return _primitive_yaml(args["primitive_slug"])

    report = run_ingest(
        manifest_path=manifest,
        dir_override=out,
        capabilities=_CAPS,
        dispatch=fake_dispatch,
    )

    assert report.written == 1
    assert report.failed == 1
    assert (out / "good.yaml").exists()


def test_run_ingest_dedup_metadata_hash_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STRATA_BLS_API_KEY", "k")
    out = tmp_path / "auto"
    manifest = _write_manifest(
        tmp_path,
        {
            "connectors": {
                "bls": [
                    {
                        "method": "get_series",
                        "arg_sets": [{"series_id": "A", "primitive_slug": "p"}],
                    }
                ]
            }
        },
    )

    def fake_dispatch(connector: str, method: str, args: dict[str, Any]) -> dict[str, Any]:
        return _primitive_yaml(args["primitive_slug"])

    run_ingest(manifest_path=manifest, dir_override=out, capabilities=_CAPS, dispatch=fake_dispatch)
    run_ingest(manifest_path=manifest, dir_override=out, capabilities=_CAPS, dispatch=fake_dispatch)

    files = list(out.glob("*.yaml"))
    assert len(files) == 1  # idempotent — re-run produced no second file
    written = yaml.safe_load(files[0].read_text())
    assert written["metadata"]["auto_args_hash"]
    assert written["metadata"]["auto_connector"] == "bls"


# ── status ────────────────────────────────────────────────────────────


def test_ingest_status_reads_written_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STRATA_BLS_API_KEY", "k")
    out = tmp_path / "auto"
    manifest = _write_manifest(
        tmp_path,
        {
            "connectors": {
                "bls": [
                    {
                        "method": "get_series",
                        "arg_sets": [{"series_id": "A", "primitive_slug": "p"}],
                    }
                ]
            }
        },
    )

    def fake_dispatch(connector: str, method: str, args: dict[str, Any]) -> dict[str, Any]:
        return _primitive_yaml(args["primitive_slug"])

    run_ingest(manifest_path=manifest, dir_override=out, capabilities=_CAPS, dispatch=fake_dispatch)

    rows = ingest_status(dir_override=out)
    assert len(rows) == 1
    assert rows[0].slug == "p"
    assert rows[0].connector == "bls"
    assert rows[0].snapshot_sha256 == "a" * 64


def test_ingest_status_empty_when_no_dir(tmp_path: Path) -> None:
    assert ingest_status(dir_override=tmp_path / "missing") == []


# ── refresh ───────────────────────────────────────────────────────────


def test_refresh_rewrites_only_when_snapshot_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("STRATA_BLS_API_KEY", "k")
    out = tmp_path / "auto"
    manifest = _write_manifest(
        tmp_path,
        {
            "connectors": {
                "bls": [
                    {
                        "method": "get_series",
                        "arg_sets": [{"series_id": "A", "primitive_slug": "p"}],
                    }
                ]
            }
        },
    )

    sha_state = {"value": "a" * 64}

    def fake_dispatch(connector: str, method: str, args: dict[str, Any]) -> dict[str, Any]:
        return _primitive_yaml(args["primitive_slug"], sha=sha_state["value"])

    run_ingest(manifest_path=manifest, dir_override=out, capabilities=_CAPS, dispatch=fake_dispatch)

    # Same sha → refresh is a no-op (unchanged).
    report1 = refresh(
        manifest_path=manifest, dir_override=out, capabilities=_CAPS, dispatch=fake_dispatch
    )
    assert report1.refreshed == 0
    assert report1.unchanged == 1

    # New sha → refresh rewrites.
    sha_state["value"] = "b" * 64
    report2 = refresh(
        manifest_path=manifest, dir_override=out, capabilities=_CAPS, dispatch=fake_dispatch
    )
    assert report2.refreshed == 1
    assert report2.unchanged == 0
    written = yaml.safe_load((out / "p.yaml").read_text())
    assert written["source"]["snapshot_sha256"] == "b" * 64


# ── CLI surface ───────────────────────────────────────────────────────


def test_cli_ingest_run_offline_no_keys(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # No connector keys set → every keyed connector is skipped; exit 0, no crash.
    for var in list(__import__("os").environ):
        if var.startswith("STRATA_") and var.endswith("_API_KEY"):
            monkeypatch.delenv(var, raising=False)
    result = runner.invoke(app, ["ingest", "run", "--tier", "regulator"])
    assert result.exit_code == 0, result.output


def test_cli_ingest_status_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    result = runner.invoke(app, ["ingest", "status"])
    assert result.exit_code == 0, result.output


def test_cli_ingest_help_lists_subcommands() -> None:
    result = runner.invoke(app, ["ingest", "--help"])
    assert result.exit_code == 0
    assert "run" in result.output
    assert "status" in result.output
    assert "refresh" in result.output


def test_target_is_hashable_dataclass() -> None:
    t = IngestTarget(connector="bls", method="get_series", args={"series_id": "A"})
    assert t.connector == "bls"
    assert t.args["series_id"] == "A"


def test_orchestrator_args_hash_matches_writer() -> None:
    # refresh correlates targets to prior auto-primitives by this hash, so it
    # MUST stay identical to the hash resolver.writer stamps into metadata.
    from strata.ingest.orchestrator import (
        _args_hash as ingest_hash,  # pyright: ignore[reportPrivateUsage]
    )
    from strata.resolver.writer import (
        _args_hash as writer_hash,  # pyright: ignore[reportPrivateUsage]
    )

    args = {"series_id": "A", "primitive_slug": "p", "n": 3}
    assert ingest_hash("bls", "get_series", args) == writer_hash("bls", "get_series", args)
