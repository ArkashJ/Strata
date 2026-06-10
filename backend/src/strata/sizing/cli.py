"""``strata portfolio`` CLI — import | size | list | gaps (spec §7).

Local/default-org surface over the JSON-backed ``CompanyStore``. Gated behind
``STRATA_PORTFOLIO_ENABLED`` (F6): when off, every command exits 2 with a
"disabled" message so prod can't accept untrusted writes before review.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from strata.config import settings
from strata.loader import load_data_dir
from strata.models import CompanyRecord
from strata.registry import Registry
from strata.sizing.importer import parse_portfolio_csv
from strata.sizing.service import SizeOptions, size_company
from strata.sizing.store import DEFAULT_STORE_PATH, CompanyStore

portfolio_app = typer.Typer(
    name="portfolio",
    help="Link a portfolio of companies to your org and size them on demand.",
    no_args_is_help=True,
)

_CSV_ARG = typer.Argument(
    ..., exists=True, dir_okay=False, help="Portfolio CSV (Name,Website,Industry Vertical)."
)
_DATA_DIR_OPT = typer.Option(Path("data"), "--data-dir", "-d", help="Data directory.")
_STORE_OPT = typer.Option(DEFAULT_STORE_PATH, "--store", help="Company store JSON path.")
_ORG_OPT = typer.Option("default", "--org", help="Org id (local default).")
_STATUS_OPT = typer.Option(None, "--status", help="Filter: unsized|sized|unsizable.")
_VERTICAL_OPT = typer.Option(None, "--vertical", help="Filter by industry vertical.")
_DOMAIN_OPT = typer.Option(None, "--domain", help="Size a single company by domain.")
_LIMIT_OPT = typer.Option(None, "--limit", help="Max rows to size/list.")
_GAPS_OUT_OPT = typer.Option(None, "--out", help="Write lens-gap rows to this JSONL path.")
# `portfolio add` — single-company convenience twin of `import`.
_ADD_NAME_OPT = typer.Option(..., "--name", "-n", help="Company name (required).")
_ADD_DOMAIN_OPT = typer.Option(
    "", "--domain", help="Company website / domain (the idempotency key)."
)
_ADD_VERTICAL_OPT = typer.Option(None, "--vertical", help="Industry vertical.")
_ADD_MARKET_OPT = typer.Option(None, "--market", help="Map to an explicit market concept slug.")
_ADD_SIZE_OPT = typer.Option(False, "--size", help="Size the company immediately after adding.")


def _require_enabled() -> None:
    if not settings.portfolio_enabled:
        typer.echo(
            "portfolio surface disabled — set STRATA_PORTFOLIO_ENABLED=1 to enable "
            "(write surfaces ship dark per spec F6)."
        )
        raise typer.Exit(code=2)


def _store(store_path: Path, org: str) -> CompanyStore:
    return CompanyStore(store_path, org_id=org)


@portfolio_app.command("import")
def portfolio_import(
    csv_path: Path = _CSV_ARG,
    store_path: Path = _STORE_OPT,
    org: str = _ORG_OPT,
) -> None:
    """Bulk-import company pointers under your org (idempotent on domain)."""
    _require_enabled()
    rows = parse_portfolio_csv(csv_path, org_id=org)
    added, skipped = _store(store_path, org).upsert_many(rows)
    typer.echo(f"imported {added} new, {skipped} existing ({len(rows)} parsed) → org {org!r}")


@portfolio_app.command("add")
def portfolio_add(
    name: str = _ADD_NAME_OPT,
    domain: str = _ADD_DOMAIN_OPT,
    vertical: str | None = _ADD_VERTICAL_OPT,
    market: str | None = _ADD_MARKET_OPT,
    size: bool = _ADD_SIZE_OPT,
    data_dir: Path = _DATA_DIR_OPT,
    store_path: Path = _STORE_OPT,
    org: str = _ORG_OPT,
) -> None:
    """Add a single company pointer to your org (idempotent on domain, else name).

    The convenience twin of ``import`` for one company. Optionally map it to an
    explicit market concept (``--market``) and size it right away (``--size``);
    sizing is registry-first and offline-safe, so a miss is an honest
    ``unsizable``, never an invented number (Q20).
    """
    _require_enabled()
    store = _store(store_path, org)
    rec = CompanyRecord(
        org_id=org,
        name=name.strip(),
        domain=domain.strip(),
        vertical=vertical,
        market_concept_slug=market,
    )
    added, _skipped = store.upsert_many([rec])
    if added:
        typer.echo(f"added {rec.name!r} ({rec.key}) → org {org!r}")
    else:
        typer.echo(f"{rec.name!r} already in portfolio (idempotent on {rec.key!r})")

    if not size:
        return
    reg = Registry.from_loaded(load_data_dir(data_dir))
    # Size the stored record (the existing one on a re-add); honor a freshly
    # passed --market even when the row was already present.
    target = store.get(rec.key) or rec
    if market:
        target.market_concept_slug = market
    res = size_company(reg, target, opts=SizeOptions())
    store.save(res.company)
    if res.verdict == "sized":
        typer.echo(
            f"  sized     {target.name:30} → {target.market_concept_slug}  ${target.tam_value:,.0f}"
        )
    else:
        typer.echo(f"  unsizable {target.name:30} → {target.reason}")


@portfolio_app.command("size")
def portfolio_size(
    data_dir: Path = _DATA_DIR_OPT,
    store_path: Path = _STORE_OPT,
    org: str = _ORG_OPT,
    vertical: str | None = _VERTICAL_OPT,
    domain: str | None = _DOMAIN_OPT,
    limit: int | None = _LIMIT_OPT,
) -> None:
    """Size unsized companies registry-first (offline-safe; never live on demo)."""
    _require_enabled()
    reg = Registry.from_loaded(load_data_dir(data_dir))
    store = _store(store_path, org)

    if domain:
        rec = store.get(domain)
        if rec is None:
            typer.echo(f"no company with domain {domain!r}")
            raise typer.Exit(code=1)
        targets = [rec]
    else:
        targets = store.list(status="unsized", vertical=vertical, limit=limit)

    sized = unsizable = 0
    for rec in targets:
        res = size_company(reg, rec, opts=SizeOptions())
        store.save(res.company)
        if res.verdict == "sized":
            sized += 1
            typer.echo(
                f"  sized   {rec.name:30} → {rec.market_concept_slug}  ${rec.tam_value:,.0f}"
            )
        else:
            unsizable += 1
            typer.echo(f"  unsized {rec.name:30} → {rec.reason}")
    typer.echo(f"\n{sized} sized, {unsizable} unsizable of {len(targets)} attempted.")


@portfolio_app.command("list")
def portfolio_list(
    store_path: Path = _STORE_OPT,
    org: str = _ORG_OPT,
    status: str | None = _STATUS_OPT,
    vertical: str | None = _VERTICAL_OPT,
    limit: int | None = _LIMIT_OPT,
) -> None:
    """Show portfolio rows + progress counts."""
    _require_enabled()
    store = _store(store_path, org)
    counts = store.counts()
    typer.echo(
        f"org {org!r}: {counts['total']} total · {counts['sized']} sized · "
        f"{counts['unsized']} unsized · {counts['unsizable']} unsizable"
    )
    for rec in store.list(status=status, vertical=vertical, limit=limit):  # type: ignore[arg-type]
        tam = f"${rec.tam_value:,.0f}" if rec.tam_value else "—"
        typer.echo(f"  {rec.status:10} {rec.name:30} {rec.vertical or '':22} {tam}")


@portfolio_app.command("gaps")
def portfolio_gaps(
    data_dir: Path = _DATA_DIR_OPT,
    store_path: Path = _STORE_OPT,
    org: str = _ORG_OPT,
    out: Path | None = _GAPS_OUT_OPT,
) -> None:
    """Lens-gap log — every unsizable company is evidence for which lens to add next (§9)."""
    _require_enabled()
    reg = Registry.from_loaded(load_data_dir(data_dir))
    store = _store(store_path, org)
    gaps = []
    for rec in store.list(status="unsizable"):
        res = size_company(reg, rec, opts=SizeOptions())
        if res.lens_gap is not None:
            gaps.append(res.lens_gap.model_dump(mode="json"))
    typer.echo(f"{len(gaps)} unsizable companies (proven lens-gaps for P3):")
    by_lens: dict[str, int] = {}
    for g in gaps:
        by_lens[g.get("proposed_lens") or "(unknown)"] = (
            by_lens.get(g.get("proposed_lens") or "(unknown)", 0) + 1
        )
    for lens, n in sorted(by_lens.items(), key=lambda kv: -kv[1]):
        typer.echo(f"  {n:4}  {lens}")
    if out is not None:
        out.write_text("\n".join(json.dumps(g) for g in gaps))
        typer.echo(f"wrote {len(gaps)} rows → {out}")
