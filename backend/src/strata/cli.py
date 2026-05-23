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


if __name__ == "__main__":
    app()
