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
            typer.echo(f"  ✓ Census  — NAICS 5112: {rec.establishments:,} estab, {rec.employees:,} emp")
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
            typer.echo(f"  ✓ EDGAR   — Apple revenue, {len(resp.concept.units.get('USD', ()))} facts")
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


if __name__ == "__main__":
    app()
