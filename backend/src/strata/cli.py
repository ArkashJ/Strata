"""Strata CLI entry point."""

from __future__ import annotations

from pathlib import Path

import typer

from strata import __version__
from strata.evaluator import EvaluatorError, size_concept
from strata.loader import LoaderError
from strata.models import TAMOutput, Unit
from strata.registry import RegistryError
from strata.validator import Severity
from strata.validator import validate as run_validate

app = typer.Typer(
    name="strata",
    help="Open-source community-curated market-sizing tool.",
    no_args_is_help=True,
    add_completion=False,
)

# Typer Argument/Option must be created at module scope (B008) — Python evaluates
# function defaults once at definition time, which is exactly what Typer expects.
_DATA_DIR_ARG = typer.Argument(
    ...,
    exists=True,
    file_okay=False,
    dir_okay=True,
    readable=True,
    help="Path to the data directory (YAML records).",
)
_CONCEPT_SLUG_ARG = typer.Argument(..., help="Concept slug to size.")
_DATA_DIR_OPT = typer.Option(
    Path("data"), "--data-dir", "-d", help="Data directory (defaults to ./data)."
)


@app.callback()
def root() -> None:
    """Preserve sub-command structure even when only one command exists."""


@app.command()
def version() -> None:
    """Print the installed Strata version."""
    typer.echo(__version__)


@app.command()
def validate(data_dir: Path = _DATA_DIR_ARG) -> None:
    """Run the three-layer validator pipeline (structural → semantic → cross-record)."""
    report = run_validate(data_dir)
    for finding in report.findings:
        prefix = "ERROR" if finding.severity == Severity.ERROR else "WARN "
        slug = f" [{finding.slug}]" if finding.slug else ""
        typer.echo(f"{prefix} {finding.layer:13} {finding.code}{slug}: {finding.message}")
    if report.errors:
        typer.echo(f"\n{len(report.errors)} error(s), {len(report.warnings)} warning(s).")
        raise typer.Exit(code=1)
    typer.echo(f"\nOK — {len(report.warnings)} warning(s).")


@app.command()
def size(
    concept_slug: str = _CONCEPT_SLUG_ARG,
    data_dir: Path = _DATA_DIR_OPT,
) -> None:
    """Load the concept, run its applicable frameworks, and print the scenario tree.

    Runs the three-layer validator first; if validation errors are present
    ``size`` refuses to mint a TAM so the user fixes the data, not the
    evaluator's downstream symptom.
    """
    try:
        report = run_validate(data_dir)
    except LoaderError as exc:
        typer.echo(f"ERROR loader: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if report.errors:
        typer.echo(
            f"ERROR data has {len(report.errors)} validation error(s); "
            f"run `strata validate {data_dir}` for details.",
            err=True,
        )
        raise typer.Exit(code=1)
    if report.registry is None:
        typer.echo("ERROR validator did not return a registry", err=True)
        raise typer.Exit(code=1)
    registry = report.registry
    try:
        tam = size_concept(registry, concept_slug)
    except EvaluatorError as exc:
        typer.echo(f"ERROR evaluator: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except RegistryError as exc:
        typer.echo(f"ERROR registry: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    _render(tam)


def _render(tam: TAMOutput) -> None:
    typer.echo(f"TAM /tam/{tam.state_hash}")
    typer.echo(f"  concept: {tam.target.concept}")
    typer.echo(
        f"  method_families: {[m.value for m in tam.method_families_used]}  "
        f"independence_score: {tam.independence_score:.2f}"
    )
    typer.echo("")
    for scenario in tam.scenarios:
        typer.echo(
            f"• {scenario.lens.value:24} {scenario.framework:36} "
            f"= {scenario.value:>16,.0f} {_unit_label(scenario.unit)}"
        )
        for iu in scenario.inputs_used:
            typer.echo(
                f"    {iu.role_name:22} ← {iu.primitive_slug}  "
                f"(snapshot {iu.snapshot_sha256[:12]}…)"
            )
        for banner in scenario.banners:
            typer.echo(f"    ⚠ {banner.kind.value}: {banner.message}")
        typer.echo("")


def _unit_label(unit: Unit) -> str:
    label = f"{unit.currency} " if unit.currency else ""
    label += unit.dimension.value
    if unit.denominator:
        label += f" {unit.denominator}"
    return label


# ── Database sub-commands ────────────────────────────────────────────

db_app = typer.Typer(name="db", help="Database management commands.", no_args_is_help=True)
app.add_typer(db_app)


@db_app.command("seed")
def db_seed(data_dir: Path = _DATA_DIR_OPT) -> None:
    """Sync YAML data bank into Postgres (upsert — safe to run repeatedly)."""
    import asyncio

    from strata.db.sync import sync_yaml_to_db

    typer.echo(f"Syncing {data_dir} → Postgres ...")
    try:
        counts = asyncio.run(sync_yaml_to_db(data_dir))
    except Exception as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    for table, count in counts.items():
        typer.echo(f"  {table:20} {count:>6} rows upserted")
    typer.echo("Done.")


@db_app.command("stats")
def db_stats() -> None:
    """Show row counts for all data bank tables in Postgres."""
    import asyncio

    from strata.db.sync import get_db_stats

    try:
        counts = asyncio.run(get_db_stats())
    except Exception as exc:
        typer.echo(f"ERROR connecting to database: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo("Data bank (Postgres):")
    for table, count in counts.items():
        typer.echo(f"  {table:20} {count:>6} rows")
    total = sum(counts.values())
    typer.echo(f"  {'TOTAL':20} {total:>6} rows")


# ── Data bank stats (YAML) ──────────────────────────────────────────


@app.command("stats")
def stats(data_dir: Path = _DATA_DIR_OPT) -> None:
    """Show data bank statistics from YAML files."""
    from strata.loader import load_data_dir
    from strata.registry import Registry

    try:
        records = load_data_dir(data_dir)
    except LoaderError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    reg = Registry.from_loaded(records)
    typer.echo("Data bank (YAML):")
    typer.echo(f"  {'atomic_primitives':20} {len(reg.atomic):>6}")
    typer.echo(f"  {'concepts':20} {len(reg.concepts):>6}")
    typer.echo(f"  {'frameworks':20} {len(reg.frameworks):>6}")
    typer.echo(f"  {'sources':20} {len(records.source_registries):>6}")
    typer.echo(f"  {'annotations':20} {len(reg.annotations):>6}")

    by_lens: dict[str, int] = {}
    for p in reg.atomic.values():
        concept = reg.concepts.get(p.concept_slug)
        if concept:
            lens = concept.analysis_lens.primary.value
            by_lens[lens] = by_lens.get(lens, 0) + 1
        else:
            by_lens["unlinked"] = by_lens.get("unlinked", 0) + 1
    typer.echo("\nPrimitives by lens:")
    for lens, count in sorted(by_lens.items(), key=lambda x: -x[1]):
        typer.echo(f"  {lens:24} {count:>4}")


# ── Connector smoke tests ───────────────────────────────────────────


@app.command("test-connectors")
def test_connectors() -> None:
    """Run live smoke tests against all 5 data source APIs."""
    from strata.config import get_settings

    settings = get_settings()

    typer.echo("Testing data source APIs...\n")
    passed = 0
    failed = 0

    # BLS
    try:
        from strata.connectors.bls import BLSClient

        with BLSClient(api_key=settings.bls_api_key) as client:
            resp = client.get_series("CUUR0000SA0")
            assert resp.series, "No series returned"
            typer.echo(f"  ✓ BLS     — CPI series, {len(resp.series[0].data)} data points")
            passed += 1
    except Exception as exc:
        typer.echo(f"  ✗ BLS     — {exc}")
        failed += 1

    # FRED
    try:
        from strata.connectors.fred import FREDClient

        with FREDClient(api_key=settings.fred_api_key) as client:
            resp = client.get_observations("GDP", limit=3, sort_order="desc")
            assert resp.observations, "No observations"
            typer.echo(f"  ✓ FRED    — GDP series, latest={resp.observations[0].value}")
            passed += 1
    except Exception as exc:
        typer.echo(f"  ✗ FRED    — {exc}")
        failed += 1

    # Census
    try:
        from strata.connectors.census import CensusClient

        with CensusClient(api_key=settings.census_api_key) as client:
            resp = client.get_cbp(2022, naics="5112")
            assert resp.records, "No records"
            rec = resp.records[0]
            typer.echo(
                f"  ✓ Census  — NAICS 5112: {rec.establishments:,} estab, {rec.employees:,} emp"
            )
            passed += 1
    except Exception as exc:
        typer.echo(f"  ✗ Census  — {exc}")
        failed += 1

    # EDGAR
    try:
        from strata.connectors.edgar import EDGARClient

        with EDGARClient() as client:
            resp = client.get_company_concept("0000320193", concept="Revenues")
            assert resp.concept, "No concept"
            typer.echo(
                f"  ✓ EDGAR   — Apple revenue, {len(resp.concept.units.get('USD', ()))} facts"
            )
            passed += 1
    except Exception as exc:
        typer.echo(f"  ✗ EDGAR   — {exc}")
        failed += 1

    # World Bank
    try:
        from strata.connectors.worldbank import WorldBankClient

        with WorldBankClient() as client:
            resp = client.get_indicator("SP.POP.TOTL", country="US", date_range="2023:2023")
            assert resp.values, "No values"
            typer.echo(f"  ✓ WBank   — US population={resp.values[0].value:,.0f}")
            passed += 1
    except Exception as exc:
        typer.echo(f"  ✗ WBank   — {exc}")
        failed += 1

    typer.echo(f"\n{passed} passed, {failed} failed")
    if failed:
        raise typer.Exit(code=1)


# ── `strata goal` — hybrid TAM resolver CLI (spec §7) ──────────────────

_GOAL_QUERY_ARG = typer.Argument(..., help="Free-form market-sizing question.")
_GOAL_STREAM_OPT = typer.Option(
    False, "--stream", help="SSE-style chain-of-thought, one line per pipeline step."
)
_GOAL_JSON_OPT = typer.Option(False, "--json", help="Pure JSON to stdout.")
_GOAL_VERBOSE_OPT = typer.Option(
    False, "--verbose", help="Include scenario tree + all sources in compact output."
)
_GOAL_NO_LIVE_OPT = typer.Option(
    False, "--no-live", help="Skip step 3 (no connector calls at query time)."
)
_GOAL_NO_FALLBACK_OPT = typer.Option(
    False, "--no-fallback", help="Skip step 4 (no Claude+Exa fallback)."
)
_GOAL_PRIMITIVE_ONLY_OPT = typer.Option(
    False,
    "--primitive-only",
    help="Step 2 returns a single primitive without composing a TAM (audit fix C).",
)
_GOAL_BUDGET_OPT = typer.Option(
    6, "--expansion-budget", help="Max connector calls in step 3 per invocation."
)


@app.command("goal")
def goal(
    query: str = _GOAL_QUERY_ARG,
    data_dir: Path = _DATA_DIR_OPT,
    stream: bool = _GOAL_STREAM_OPT,
    as_json: bool = _GOAL_JSON_OPT,
    verbose: bool = _GOAL_VERBOSE_OPT,  # reserved for §7 --verbose
    no_live: bool = _GOAL_NO_LIVE_OPT,
    no_fallback: bool = _GOAL_NO_FALLBACK_OPT,
    primitive_only: bool = _GOAL_PRIMITIVE_ONLY_OPT,
    expansion_budget: int = _GOAL_BUDGET_OPT,
) -> None:
    """Ask a free-form TAM question — runs the 4-step hybrid resolver.

    Pipeline (spec §3):
      pre. slug resolver  — Claude → ResolvedQuery (concept | primitive | novel)
      1.   concept match  → registry.concept → evaluator.size_concept
      2.   primitive match → return single primitive or compose
      3.   connector live  → router.choose → connector.method → upsert
      4.   fallback        → parse + search (Claude+Exa, ephemeral)

    Three output modes (mutually exclusive): compact (default), --stream,
    --json. Env var STRATA_OFFLINE=1 sets --no-live + --no-fallback.
    """
    import os

    from strata.loader import load_data_dir
    from strata.registry import Registry
    from strata.resolver import (
        AUTO_PRIMITIVES_DIR,
        RenderMode,
        RunOptions,
        render_result,
        run,
    )

    if stream and as_json:
        typer.echo("ERROR: --stream and --json are mutually exclusive", err=True)
        raise typer.Exit(code=2)

    # STRATA_OFFLINE=1 → --no-live + --no-fallback unless flags override (fix K).
    if os.environ.get("STRATA_OFFLINE") == "1":
        no_live = True
        no_fallback = True

    try:
        records = load_data_dir(data_dir)
    except LoaderError as exc:
        typer.echo(f"ERROR loader: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    registry = Registry.from_loaded(records)

    # Augment in-memory registry with auto-primitives (spec §8). Loaded with
    # is_auto=True metadata so callers can filter them out if they only trust
    # the committed tree.
    if AUTO_PRIMITIVES_DIR.exists():
        try:
            extras = load_data_dir(AUTO_PRIMITIVES_DIR)
        except LoaderError:
            extras = None
        if extras is not None:
            for prim in extras.atomic_primitives:
                registry.atomic[prim.slug] = prim

    options = RunOptions(
        allow_live=not no_live,
        allow_fallback=not no_fallback,
        expansion_budget=expansion_budget,
        primitive_only=primitive_only,
    )

    try:
        result = run(query, registry=registry, options=options)
    except Exception as exc:
        typer.echo(f"ERROR pipeline: {exc.__class__.__name__}: {exc}", err=True)
        raise typer.Exit(code=3) from exc

    mode = RenderMode.JSON if as_json else (RenderMode.STREAM if stream else RenderMode.COMPACT)
    typer.echo(render_result(result, mode=mode))

    # Exit codes per spec §7.
    if result.status.value == "failed":
        if no_live and no_fallback:
            raise typer.Exit(code=1)
        raise typer.Exit(code=3 if result.error else 1)


# ── `strata promote` — move auto-primitive into the committed tree (§7) ─

_PROMOTE_SLUG_ARG = typer.Argument(..., help="Slug of the auto-primitive to promote.")
_PROMOTE_DATA_DIR_OPT = typer.Option(
    Path("data"), "--data-dir", "-d", help="Target data directory."
)


@app.command("promote")
def promote(
    slug: str = _PROMOTE_SLUG_ARG,
    data_dir: Path = _PROMOTE_DATA_DIR_OPT,
) -> None:
    """Move ~/.strata/auto-primitives/{slug}.yaml → data/primitives/{slug}.yaml.

    Refuses promotion if the validator rejects (mirrors v0.5 contribution flow).
    Idempotent: re-running on an already-promoted slug is a no-op.
    """
    from strata.resolver import AUTO_PRIMITIVES_DIR

    src = AUTO_PRIMITIVES_DIR / f"{slug}.yaml"
    if not src.exists():
        typer.echo(
            f"ERROR: {src} does not exist. Run `strata goal` first to mint an auto-primitive.",
            err=True,
        )
        raise typer.Exit(code=2)

    target_dir = data_dir / "primitives"
    target_dir.mkdir(parents=True, exist_ok=True)
    dst = target_dir / f"{slug}.yaml"
    if dst.exists():
        typer.echo(f"{slug} is already promoted — no-op.")
        return

    # Stage by copying, then run the validator on data_dir. Roll back on reject.
    import shutil

    shutil.copy(src, dst)
    try:
        report = run_validate(data_dir)
    except LoaderError as exc:
        dst.unlink(missing_ok=True)
        typer.echo(f"ERROR loader after promote: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if report.errors:
        dst.unlink(missing_ok=True)
        typer.echo(
            f"ERROR validator rejected {slug}: "
            f"{len(report.errors)} error(s). Promotion rolled back.",
            err=True,
        )
        for finding in report.errors[:3]:
            typer.echo(f"  • {finding.code}: {finding.message}", err=True)
        raise typer.Exit(code=1)

    src.unlink()
    typer.echo(f"✓ Promoted {slug} → {dst}")
    if report.warnings:
        typer.echo(f"  (with {len(report.warnings)} warning(s) — review with `strata validate`)")


# ── `strata ingest` — connector-agnostic ingest + freshness (Session 3) ─

ingest_app = typer.Typer(
    name="ingest", help="Connector ingest + freshness orchestration.", no_args_is_help=True
)
app.add_typer(ingest_app)

# B008: Typer Option/Argument singletons at module scope.
_INGEST_MANIFEST_OPT = typer.Option(
    None,
    "--manifest",
    "-m",
    help="Path to ingest-manifest.yaml (defaults to ../ingest-manifest.yaml, beside data/).",
)
_INGEST_CONNECTOR_OPT = typer.Option(None, "--connector", "-c", help="Ingest only this connector.")
_INGEST_TIER_OPT = typer.Option(
    None, "--tier", "-t", help="Ingest only capabilities at this source tier."
)
_REFRESH_TIER_OPT = typer.Option(
    None, "--tier", "-t", help="Refresh only capabilities at this source tier."
)
_REFRESH_OLDER_THAN_OPT = typer.Option(
    None, "--older-than", help="Refresh only primitives whose as_of is older than N days."
)


@ingest_app.command("run")
def ingest_run(
    manifest: Path | None = _INGEST_MANIFEST_OPT,
    connector: str | None = _INGEST_CONNECTOR_OPT,
    tier: str | None = _INGEST_TIER_OPT,
) -> None:
    """Ingest manifest primitives → ~/.strata/auto-primitives/.

    Connectors lacking their API key are skipped (logged, never fatal) so an
    offline ``ingest run --tier regulator`` still ingests the keyless sources.
    Per-item failures (network, validation) are also logged and non-fatal.
    """
    from strata.ingest import run_ingest

    try:
        report = run_ingest(manifest_path=manifest, connector_filter=connector, tier_filter=tier)
    except (ValueError, OSError) as exc:
        typer.echo(f"ERROR ingest: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    for conn, reason in report.skipped_connectors:
        typer.echo(f"  ⤵ skipped {conn} — {reason}")
    for r in report.results:
        if r.status == "written":
            typer.echo(f"  ✓ {r.connector}.{r.method} → {r.primitive_slug}")
        else:
            typer.echo(f"  ✗ {r.connector}.{r.method} ({r.primitive_slug}) — {r.detail}")
    typer.echo(
        f"\n{report.written} written, {report.failed} failed, "
        f"{len(report.skipped_connectors)} connector(s) skipped."
    )


@ingest_app.command("status")
def ingest_status_cmd() -> None:
    """List auto-primitives on disk with their ingest provenance."""
    from strata.ingest import ingest_status

    rows = ingest_status()
    if not rows:
        typer.echo("No auto-primitives ingested yet.")
        return
    typer.echo(f"{len(rows)} auto-primitive(s):")
    for row in rows:
        typer.echo(
            f"  {row.slug:40} {row.connector}.{row.method}  as_of={row.as_of}  hash={row.args_hash}"
        )


@ingest_app.command("refresh")
def ingest_refresh(
    manifest: Path | None = _INGEST_MANIFEST_OPT,
    tier: str | None = _REFRESH_TIER_OPT,
    older_than: int | None = _REFRESH_OLDER_THAN_OPT,
) -> None:
    """Re-fetch manifest primitives; rewrite ONLY when the snapshot changed."""
    from strata.ingest import refresh_ingest

    try:
        report = refresh_ingest(
            manifest_path=manifest, tier_filter=tier, older_than_days=older_than
        )
    except (ValueError, OSError) as exc:
        typer.echo(f"ERROR refresh: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    for r in report.results:
        marker = {"refreshed": "↻", "unchanged": "=", "skipped": "⤵"}.get(r.status, "✗")
        typer.echo(f"  {marker} {r.connector}.{r.method} ({r.primitive_slug}) — {r.status}")
    typer.echo(f"\n{report.refreshed} refreshed, {report.unchanged} unchanged.")


if __name__ == "__main__":
    app()
