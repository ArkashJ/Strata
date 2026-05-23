"""Strata CLI entry point.

Commands land here as they're implemented:
  strata validate <data-dir>     — Task 13 (validator pipeline)
  strata serve [--port]          — Task 17 (FastAPI app)
  strata mint <state.json>       — Task 14 (content-hash debug)
"""

from __future__ import annotations

import typer

from strata import __version__

app = typer.Typer(
    name="strata",
    help="Open-source community-curated market-sizing tool.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def root() -> None:
    """Preserve sub-command structure even when only one command exists."""


@app.command()
def version() -> None:
    """Print the installed Strata version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
