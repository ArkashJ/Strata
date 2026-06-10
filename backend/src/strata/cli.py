"""Strata CLI entry point."""

from __future__ import annotations

import asyncio
import base64
import csv
import os
import re
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import Any

import typer
from dotenv import load_dotenv

from strata import __version__
from strata.evaluator import EvaluatorError, size_concept
from strata.loader import LoaderError, load_data_dir
from strata.models import QuestionCategory, ResolvedAnswer, TAMOutput, Unit
from strata.registry import Registry, RegistryError
from strata.report import (
    Branding,
    PdfUnavailableError,
    PremiumReport,
    assemble_premium_report_for_tam,
    assemble_report,
    render_premium_html,
    render_premium_pdf,
)
from strata.sizing.cli import portfolio_app
from strata.sizing.revenue_lookup import RevenueLookupError, resolve_revenue
from strata.sizing.sense_check import (
    Player,
    SenseCheckError,
    SenseCheckResult,
    normalize_share,
    parse_player,
    sense_check,
)
from strata.validator import Severity, ValidationFinding
from strata.validator import validate as run_validate

app = typer.Typer(
    name="strata",
    help="Open-source community-curated market-sizing tool.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(portfolio_app)

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
_REPORT_CONCEPT_ARG = typer.Argument(
    ..., help="Concept slug to assemble the report for, or a 64-hex TAM state hash."
)
_REPORT_CATEGORY_OPT = typer.Option(
    None, "--category", "-c", help="Only show answers in this question category."
)
_REPORT_PREMIUM_OPT = typer.Option(
    False, "--premium", help="Render the premium ($1M-grade) HTML report deck."
)
_REPORT_PDF_OPT = typer.Option(
    False, "--pdf", help="Also render a PDF (needs WeasyPrint + native libs; falls back to HTML)."
)
_REPORT_OUT_OPT = typer.Option(
    None, "--out", "-o", help="Write the rendered report here (default: stdout for HTML)."
)
_REPORT_BRAND_NAME_OPT = typer.Option(None, "--brand-name", help="Firm name in the report header.")
_REPORT_BRAND_COLOR_OPT = typer.Option(
    None, "--brand-color", help="Brand accent color (hex, e.g. #5B5BD6)."
)
_REPORT_LOGO_OPT = typer.Option(
    None, "--logo", help="Path to a logo image (embedded as a data URI)."
)
_REPORT_PREPARED_BY_OPT = typer.Option(
    None, "--prepared-by", help="Analyst name for the report header."
)
_VERIFY_CLAIM_ARG = typer.Argument(..., help="A market claim to verify against the sourced bank.")
_VERIFY_VALUE_OPT = typer.Option(
    None, "--value", help="The numeric figure the claim asserts (same unit as the market)."
)
# `sense-check` — market-share-implied (comparable-revenue) cross-check.
_SC_PLAYER_OPT = typer.Option(
    [],
    "--player",
    "-p",
    help="A top player as 'Name|revenue|share' (repeatable). revenue: 31e9 / 3.1b / $300m, "
    "or 'edgar:TICKER' to pull a SOURCED revenue from SEC EDGAR; share: 0.15 or 15.",
)
_SC_FILE_OPT = typer.Option(
    None, "--players-file", help="CSV with columns: name,revenue,market_share."
)
_SC_CONCEPT_OPT = typer.Option(
    None, "--concept", help="Curated concept slug to cross-check the implied TAM against."
)

# A 64-char hex string is a TAM state hash; anything else is a concept slug.
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


@app.callback()
def root() -> None:
    """Preserve sub-command structure even when only one command exists."""
    # Load .env (walks up from CWD) so `strata goal`, connectors, and `db`
    # commands pick up EXA_API_KEY / DATABASE_URL the same way the HTTP layer
    # does — without the caller having to source it manually.
    load_dotenv()


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
    typer.echo(
        f"\nSense-check (comparable-revenue): strata sense-check --concept {concept_slug} "
        f'--player "Name|revenue|share" ...'
    )


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


def _load_registry_or_exit(data_dir: Path) -> Registry:
    """Validate the data dir and return its registry, exiting non-zero on errors
    (shared by the text and premium report paths so the gate behaves identically)."""
    try:
        validation = run_validate(data_dir)
    except LoaderError as exc:
        typer.echo(f"ERROR loader: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if validation.errors:
        typer.echo(
            f"ERROR data has {len(validation.errors)} validation error(s); "
            f"run `strata validate {data_dir}` for details.",
            err=True,
        )
        raise typer.Exit(code=1)
    if validation.registry is None:
        typer.echo("ERROR validator did not return a registry", err=True)
        raise typer.Exit(code=1)
    return validation.registry


def _branding_from_opts(
    brand_name: str | None, brand_color: str | None, logo: Path | None, prepared_by: str | None
) -> Branding | None:
    """Build the optional Branding from CLI flags; ``None`` when nothing is set.

    A ``--logo`` path is embedded as a base64 data URI so the rendered HTML/PDF
    stays self-contained (no external asset fetch for a forwarded deliverable)."""
    if not any((brand_name, brand_color, logo, prepared_by)):
        return None
    logo_data_uri: str | None = None
    if logo is not None:
        data = logo.read_bytes()
        suffix = logo.suffix.lower().lstrip(".") or "png"
        mime = "svg+xml" if suffix == "svg" else suffix
        logo_data_uri = f"data:image/{mime};base64,{base64.b64encode(data).decode('ascii')}"
    return Branding(
        firm_name=brand_name,
        prepared_by=prepared_by,
        brand_color=brand_color,
        logo_data_uri=logo_data_uri,
    )


def _resolve_premium_report(registry: Registry, concept_or_hash: str) -> PremiumReport:
    """Resolve the premium report by concept slug (size then bind) or by a TAM
    state hash (durable store). Exits non-zero with an honest message on a miss."""
    if _HASH_RE.match(concept_or_hash):
        from strata.db.tams import get_tam_from_db_safe

        tam = asyncio.run(get_tam_from_db_safe(concept_or_hash))
        if tam is None:
            typer.echo(
                f"ERROR no TAM with state hash {concept_or_hash!r} in the durable store; "
                "size it first (e.g. via the API or MCP), or pass a concept slug.",
                err=True,
            )
            raise typer.Exit(code=1)
        return assemble_premium_report_for_tam(registry, tam)
    try:
        tam = size_concept(registry, concept_or_hash)
    except (EvaluatorError, RegistryError) as exc:
        typer.echo(f"ERROR could not size {concept_or_hash!r}: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    return assemble_premium_report_for_tam(registry, tam)


@app.command("report")
def report_cmd(
    concept_slug: str = _REPORT_CONCEPT_ARG,
    data_dir: Path = _DATA_DIR_OPT,
    category: QuestionCategory | None = _REPORT_CATEGORY_OPT,
    premium: bool = _REPORT_PREMIUM_OPT,
    pdf: bool = _REPORT_PDF_OPT,
    out: Path | None = _REPORT_OUT_OPT,
    brand_name: str | None = _REPORT_BRAND_NAME_OPT,
    brand_color: str | None = _REPORT_BRAND_COLOR_OPT,
    logo: Path | None = _REPORT_LOGO_OPT,
    prepared_by: str | None = _REPORT_PREPARED_BY_OPT,
) -> None:
    """Assemble a concept's market report — plain-text by default, or a premium deck.

    Runs the three-layer validator first (refusing on errors, exactly like
    ``size``). Plain mode resolves every applicable question purely from the
    registry and prints each answer (gaps shown honestly). ``--premium`` renders
    the $1M-grade HTML deck (editorial headline, sourced range, inline-SVG charts,
    sources appendix), optionally to ``--pdf``, with optional firm branding.
    The argument may be a concept slug or a 64-hex TAM state hash.
    """
    registry = _load_registry_or_exit(data_dir)

    if premium or pdf:
        _emit_premium_report(
            registry, concept_slug, pdf, out, brand_name, brand_color, logo, prepared_by
        )
        return

    try:
        report = assemble_report(registry, concept_slug)
    except RegistryError as exc:
        typer.echo(f"ERROR registry: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    answers = report.answers
    if category is not None:
        answers = tuple(a for a in answers if a.category == category)

    typer.echo(f"Market report: {report.concept_name} [{report.concept_slug}]")
    typer.echo(f"  {len(answers)} question(s)\n")
    if not answers:
        typer.echo("  (no applicable questions)")
        return
    for ans in answers:
        _render_answer(ans)


def _emit_premium_report(
    registry: Registry,
    concept_or_hash: str,
    pdf: bool,
    out: Path | None,
    brand_name: str | None,
    brand_color: str | None,
    logo: Path | None,
    prepared_by: str | None,
) -> None:
    """Render the premium HTML (and optionally PDF) report and write it out."""
    pr = _resolve_premium_report(registry, concept_or_hash)
    branding = _branding_from_opts(brand_name, brand_color, logo, prepared_by)
    html = render_premium_html(pr, branding)

    if pdf:
        try:
            pdf_bytes = render_premium_pdf(html)
        except PdfUnavailableError as exc:
            typer.echo(f"WARN {exc}", err=True)
            typer.echo("WARN falling back to HTML output.", err=True)
        else:
            target = out or Path(f"{pr.concept_slug}-report.pdf")
            target.write_bytes(pdf_bytes)
            typer.echo(f"Wrote PDF report to {target}", err=True)
            return

    if out is not None:
        out.write_text(html, encoding="utf-8")
        typer.echo(f"Wrote HTML report to {out}", err=True)
    else:
        typer.echo(html)


def _render_answer(ans: ResolvedAnswer) -> None:
    if ans.status == "gap":
        typer.echo(f"⊘ [{ans.category.value}] {ans.prompt}")
        typer.echo(f"    {ans.narrative}")
        if ans.resource_target:
            typer.echo(f"    → fill via {ans.resource_target}")
        typer.echo("")
        return
    typer.echo(f"✓ [{ans.category.value}] {ans.prompt}")
    typer.echo(f"    {ans.narrative}")
    if ans.synthesis:
        typer.echo(f"    synthesis: {ans.synthesis}")
    for prov in ans.provenance:
        tier = f" ({prov.source_tier})" if prov.source_tier else ""
        typer.echo(f"    ← {prov.primitive_slug}{tier} (snapshot {prov.snapshot_sha256[:12]}…)")
    typer.echo("")


@app.command("verify")
def verify_cmd(
    claim: str = _VERIFY_CLAIM_ARG,
    data_dir: Path = _DATA_DIR_OPT,
    value: float | None = _VERIFY_VALUE_OPT,
) -> None:
    """Verify a market claim against the sourced bank (the verify_market_claim tool).

    Matches the claim to a curated concept (registry-first, LLM-free), sizes it,
    and prints the verdict + sourced range + cited inputs. An unknown claim is
    ``unverifiable`` — a number is never synthesized (Q20)."""
    from strata.mcp.tools import verify_market_claim

    registry = _load_registry_or_exit(data_dir)
    out = verify_market_claim(registry, claim=claim, asserted_value=value)

    typer.echo(f"Claim: {claim}")
    typer.echo(f"Verdict: {out['verdict']}")
    rng = out.get("strata_range")
    if rng is None:
        typer.echo(f"  {out.get('message', 'no sourced range')}")
        return
    typer.echo(
        f"  Sourced range: {rng['low']:,.0f} - {rng['high']:,.0f} "
        f"(mid {rng['mid']:,.0f}, spread {out.get('spread_x', 0):.1f}×)"
    )
    typer.echo(
        f"  Method families: {out.get('method_families', [])}  "
        f"independence {out.get('independence_score', 0):.2f}"
    )
    inputs = out.get("inputs", [])
    if inputs:
        typer.echo("  Cited inputs:")
        seen: set[str] = set()
        for inp in inputs:
            slug = inp["primitive"]
            if slug in seen:
                continue
            seen.add(slug)
            typer.echo(f"    ← {slug} (snapshot {inp['snapshot_sha256'][:12]}…)")


# ── Database sub-commands ────────────────────────────────────────────


def _player_from_spec(spec: str) -> Player:
    """Parse a --player spec, resolving an ``edgar:TICKER`` revenue token to a
    SOURCED revenue via SEC EDGAR (live HTTP). Any other revenue token is an
    analyst estimate parsed offline."""
    parts = [p.strip() for p in spec.split("|")]
    if len(parts) >= 3 and parts[1].lower().startswith("edgar:"):
        ticker = parts[1].split(":", 1)[1].strip()
        if not ticker:
            raise SenseCheckError(f"empty EDGAR ticker in {spec!r}")
        if os.environ.get("STRATA_OFFLINE") == "1":
            raise SenseCheckError(f"{spec!r} needs a live EDGAR lookup but STRATA_OFFLINE=1")
        try:
            share = normalize_share(float(parts[2]))
        except ValueError as exc:
            raise SenseCheckError(f"could not parse share {parts[2]!r} in {spec!r}") from exc
        try:
            rr = resolve_revenue(ticker)
        except RevenueLookupError as exc:
            raise SenseCheckError(str(exc)) from exc
        typer.echo(
            f"  resolved {parts[0]} revenue ${rr.revenue:,.0f} "
            f"(EDGAR {rr.concept} FY{rr.fiscal_year}, {rr.entity_name})"
        )
        return Player(name=parts[0], revenue=rr.revenue, market_share=share, revenue_sourced=True)
    return parse_player(spec)


def _collect_players(specs: list[str], players_file: Path | None) -> list[Player]:
    players = [_player_from_spec(s) for s in specs]
    if players_file is not None:
        with players_file.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                name = (row.get("name") or "").strip()
                if not name:
                    continue
                rev = (row.get("revenue") or "").strip()
                share = (row.get("market_share") or "").strip()
                players.append(_player_from_spec(f"{name}|{rev}|{share}"))
    return players


@app.command("sense-check")
def sense_check_cmd(
    player: list[str] = _SC_PLAYER_OPT,
    players_file: Path | None = _SC_FILE_OPT,
    concept: str | None = _SC_CONCEPT_OPT,
    data_dir: Path = _DATA_DIR_OPT,
) -> None:
    """Market-share-implied TAM cross-check: sum(top-player revenue) / sum(market share).

    A sense check, not a sourced number — market shares are analyst estimates, so
    the implied TAM is MODELED and never persisted (Q20). With --concept, the
    implied TAM is compared head-to-head with the curated market's sourced
    scenario range (within / above / below).
    """
    try:
        players = _collect_players(player, players_file)
    except SenseCheckError as exc:
        typer.echo(f"ERROR {exc}", err=True)
        raise typer.Exit(code=2) from exc

    sourced_scenarios: tuple[float, ...] | None = None
    if concept:
        try:
            reg = Registry.from_loaded(load_data_dir(data_dir))
            tam = size_concept(reg, concept)
        except (LoaderError, EvaluatorError, RegistryError) as exc:
            typer.echo(f"ERROR could not size concept {concept!r}: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        sourced_scenarios = tuple(s.value for s in tam.scenarios)

    try:
        result = sense_check(players, sourced_scenarios=sourced_scenarios)
    except SenseCheckError as exc:
        typer.echo(f"ERROR {exc}", err=True)
        raise typer.Exit(code=2) from exc
    _render_sense_check(result, concept)


def _render_sense_check(r: SenseCheckResult, concept: str | None) -> None:
    typer.echo("Market-share-implied TAM (comparable-revenue sense-check)")
    typer.echo(
        f"  implied TAM     ${r.implied_tam:,.0f}   "
        f"(= revenue ${r.revenue_floor:,.0f} / share {r.combined_share:.0%})"
    )
    typer.echo(
        f"  sensitivity     ${r.implied_low:,.0f} - ${r.implied_high:,.0f}   "
        f"(shares +/-{r.share_tolerance:.0%})"
    )
    typer.echo(f"  revenue floor   ${r.revenue_floor:,.0f}   (a TAM cannot be below this)")
    typer.echo(
        f"  leverage        {r.leverage:.1f}x   "
        f"(implied TAM is {r.leverage:.1f}x captured revenue; 1 / {r.combined_share:.0%} share)"
    )
    typer.echo(
        f"  residual        ${r.residual:,.0f}   (revenue attributed to players outside the set)"
    )
    typer.echo(
        f"  per-player spread {r.spread_ratio:.1f}x   ({r.n_sourced}/{r.n_players} revenues sourced)"
    )
    for pi in r.per_player:
        tag = "" if pi.revenue_sourced else "  (est.)"
        typer.echo(
            f"    {pi.name:24} ${pi.revenue:,.0f} @ {pi.market_share:.0%}"
            f"  -> implied ${pi.implied_tam:,.0f}{tag}"
        )
    if concept and r.verdict is not None:
        typer.echo(
            f"\n  cross-check vs {concept}: sourced range "
            f"${r.sourced_low:,.0f} - ${r.sourced_high:,.0f} (mid ${r.sourced_mid:,.0f})"
        )
        verdict_label = {
            "within": "AGREES - implied TAM lands inside the sourced range",
            "above": "implied TAM is ABOVE the sourced range",
            "below": "implied TAM is BELOW the sourced range",
        }[r.verdict]
        ratio = f" ({r.vs_mid_ratio:.1f}x the sourced midpoint)" if r.vs_mid_ratio else ""
        typer.echo(f"  verdict: {verdict_label}{ratio}")
    typer.echo("\n  Assumptions (the implied TAM holds only if):")
    for a in r.assumptions:
        typer.echo(f"   - {a}")
    if r.warnings:
        typer.echo("")
    for w in r.warnings:
        typer.echo(f"  WARN {w}")


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


@app.command("embed")
def embed_command() -> None:
    """Populate pgvector embeddings for all concepts/primitives (flow 39).

    Recomputes the deterministic feature-hashing embedding for every concept and
    primitive in Postgres and writes it to the ``embedding`` column. Powers the
    resolver's semantic NN fallback (``match_concept_semantic``). Requires
    migration 010 (pgvector + embedding columns) — if the extension is not
    installed the DB error is surfaced (BLOCKED until a superuser runs
    ``CREATE EXTENSION vector``)."""
    import asyncio

    from strata.db.embed_populate import populate_embeddings

    typer.echo("Computing embeddings → Postgres ...")
    try:
        counts = asyncio.run(populate_embeddings())
    except Exception as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        typer.echo(
            "If this mentions the 'vector' type, pgvector is not provisioned: "
            "a superuser must run `CREATE EXTENSION vector;` and `alembic upgrade head`.",
            err=True,
        )
        raise typer.Exit(code=1) from exc
    for table, count in counts.items():
        typer.echo(f"  {table:20} {count:>6} embedded")
    typer.echo("Done.")


# ── Ingest orchestrator sub-commands ────────────────────────────────

ingest_app = typer.Typer(
    name="ingest",
    help="Declarative data-bank ingest from data/ingest-manifest.yaml.",
    no_args_is_help=True,
)
app.add_typer(ingest_app)

_INGEST_MANIFEST_OPT = typer.Option(
    Path("../data/ingest-manifest.yaml"),
    "--manifest",
    "-m",
    help="Path to the ingest manifest YAML.",
)
_INGEST_CONNECTOR_OPT = typer.Option(
    None, "--connector", help="Only ingest this connector (e.g. fred)."
)
_INGEST_TIER_OPT = typer.Option(
    None, "--tier", help="Only ingest connectors of this source tier (e.g. regulator)."
)
_REFRESH_TIER_OPT = typer.Option(
    None, "--tier", help="Only refresh connectors of this source tier."
)
_REFRESH_OLDER_THAN_OPT = typer.Option(
    None,
    "--older-than",
    help="Only refresh primitives whose as_of is older than this many days.",
)


@ingest_app.command("run")
def ingest_run(
    manifest: Path = _INGEST_MANIFEST_OPT,
    connector: str | None = _INGEST_CONNECTOR_OPT,
    tier: str | None = _INGEST_TIER_OPT,
) -> None:
    """Walk the manifest and ingest each connector method into the data bank.

    Connectors whose ``STRATA_<X>_API_KEY`` is unset are logged and skipped —
    a missing key never aborts the batch. Writes land in the auto-primitives
    staging dir (``~/.strata/auto-primitives/``); promote with `strata promote`.
    """
    from strata.ingest import run_ingest

    try:
        report = run_ingest(manifest_path=manifest, tier=tier, connector=connector)
    except FileNotFoundError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except ValueError as exc:
        typer.echo(f"ERROR malformed manifest: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(f"Ingest complete: {report.written} written, {report.failed} failed.")
    if report.skipped_connectors:
        typer.echo(f"  skipped (no API key): {', '.join(sorted(report.skipped_connectors))}")


@ingest_app.command("status")
def ingest_status_cmd() -> None:
    """List every previously-ingested auto-primitive with its source pin."""
    from strata.ingest import ingest_status

    rows = ingest_status()
    if not rows:
        typer.echo("No ingested auto-primitives yet. Run `strata ingest run`.")
        return
    typer.echo(f"Ingested auto-primitives ({len(rows)}):")
    for row in rows:
        typer.echo(
            f"  {row.slug:40} {row.connector}.{row.method:24} "
            f"as_of={row.as_of}  snapshot={row.snapshot_sha256[:12]}…"
        )


@ingest_app.command("refresh")
def ingest_refresh(
    manifest: Path = _INGEST_MANIFEST_OPT,
    tier: str | None = _REFRESH_TIER_OPT,
    older_than: int | None = _REFRESH_OLDER_THAN_OPT,
) -> None:
    """Re-fetch manifest targets, rewriting a primitive only when its
    ``snapshot_sha256`` changed (unchanged rows are left untouched)."""
    from strata.ingest import refresh

    try:
        report = refresh(manifest_path=manifest, tier=tier, older_than=older_than)
    except FileNotFoundError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except ValueError as exc:
        typer.echo(f"ERROR malformed manifest: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(f"Refresh complete: {report.refreshed} rewritten, {report.unchanged} unchanged.")
    if report.skipped_connectors:
        typer.echo(f"  skipped (no API key): {', '.join(sorted(report.skipped_connectors))}")


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
    typer.echo(f"  {'sizing-grade primitives':24} {len(reg.atomic):>6}")
    typer.echo(f"  {'signals (non-sizing)':24} {len(reg.signals):>6}")
    typer.echo(f"  {'concepts':24} {len(reg.concepts):>6}")
    typer.echo(f"  {'frameworks':24} {len(reg.frameworks):>6}")
    typer.echo(f"  {'sources':24} {len(records.source_registries):>6}")
    typer.echo(f"  {'annotations':24} {len(reg.annotations):>6}")

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

    # Phase 4 — sourced vs modeled (the soft-data fence). provenance_class is
    # derived from source.tier so this can never drift from the tier breakdown.
    from strata.models.primitive import ProvenanceClass

    sourced = sum(1 for p in reg.atomic.values() if p.provenance_class is ProvenanceClass.SOURCED)
    modeled = sum(1 for p in reg.atomic.values() if p.provenance_class is ProvenanceClass.MODELED)
    queued = sum(1 for p in reg.atomic.values() if p.needs_resourcing)
    typer.echo("\nProvenance:")
    typer.echo(f"  {'sourced':24} {sourced:>6}")
    typer.echo(f"  {'modeled':24} {modeled:>6}")
    typer.echo(f"  {'queued for re-sourcing':24} {queued:>6}")


@app.command("resource-status")
def resource_status(data_dir: Path = _DATA_DIR_OPT) -> None:
    """Report re-sourcing progress over the fenced (modeled) primitives:
    how many carry a candidate connector target vs. are honest gaps."""
    from strata.loader import load_data_dir
    from strata.models.primitive import ProvenanceClass
    from strata.registry import Registry

    try:
        records = load_data_dir(data_dir)
    except LoaderError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    reg = Registry.from_loaded(records)
    modeled = [p for p in reg.atomic.values() if p.provenance_class is ProvenanceClass.MODELED]
    with_target = [p for p in modeled if p.resource_target]
    unmapped = [p for p in modeled if not p.resource_target]
    typer.echo("Re-sourcing queue (modeled primitives):")
    typer.echo(f"  {'total modeled':28} {len(modeled):>6}")
    typer.echo(f"  {'mapped to a connector target':28} {len(with_target):>6}")
    # resource_target=None means "not yet mapped" — NOT necessarily an honest gap.
    # Classifying each unmapped primitive as resourceable vs honest-gap is the
    # re-source-execution follow-up (§6); until then they are simply unmapped.
    typer.echo(f"  {'unmapped (target TBD)':28} {len(unmapped):>6}")
    for p in sorted(with_target, key=lambda x: x.slug):
        typer.echo(f"    → {p.slug}  ⇒  {p.resource_target}")


@app.command("verify-integrity")
def verify_integrity(data_dir: Path = _DATA_DIR_OPT) -> None:
    """Verify stored source snapshots hash to their declared sha256 (AC1.3)."""
    from strata.integrity import verify_snapshot_store

    report = verify_snapshot_store(data_dir / "snapshots")
    typer.echo(f"Verified {report.verified} snapshot(s).")
    if not report.ok:
        for failure in report.failures:
            typer.echo(f"  INTEGRITY FAILURE: {failure}", err=True)
        raise typer.Exit(code=1)
    typer.echo("All stored snapshots intact.")


# ── Connector smoke tests ───────────────────────────────────────────

_CONNECTORS_LIVE_OPT = typer.Option(
    False, "--live", help="Also smoke-test the keyless government APIs (network)."
)


@app.command("test-connectors")
def test_connectors(
    live: bool = _CONNECTORS_LIVE_OPT,
) -> None:
    """Enumerate all 23 typed connectors with honest readiness.

    By default this is OFFLINE: it reports each connector's tier, whether its
    required API key is present, and whether it is capability-only (no committed
    ingest yet) — never silently claiming a connector works. Keyed connectors
    with a missing key are reported BLOCKED, not failed: the gap is a credential,
    not a code defect. Pass ``--live`` to additionally hit the keyless/govt APIs
    that need no credential (a small smoke set), reporting real failures.
    """
    from strata.config import get_settings
    from strata.connectors._capability import all_capabilities

    settings = get_settings()

    # Honest per-connector descriptors. `key_attr` names the Settings field that
    # must be set for a LIVE call; None means the connector works keyless (govt /
    # public APIs, often rate-limited without a key). `blocked` connectors REQUIRE
    # a key and raise without one — they are surfaced as BLOCKED, not broken.
    @dataclass(frozen=True, slots=True)
    class _ConnDesc:
        tier: str
        key_attr: str | None
        note: str
        requires_key: bool = False  # raises / unusable without the key (BLOCKED)
        capability_only: bool = False  # typed client exists; no committed ingest

    descriptors: dict[str, _ConnDesc] = {
        "bls": _ConnDesc("regulator", "bls_api_key", "employment/wages/CPI (keyless OK)"),
        "fred": _ConnDesc("regulator", "fred_api_key", "GDP/rates (keyless OK)"),
        "census": _ConnDesc("regulator", "census_api_key", "NAICS industry stats (keyless OK)"),
        "edgar": _ConnDesc("regulator", None, "SEC XBRL financials (keyless)"),
        "worldbank": _ConnDesc("aggregator", None, "global GDP/population (keyless)"),
        "oecd": _ConnDesc("aggregator", None, "38-country SDMX (keyless)"),
        "eurostat": _ConnDesc("regulator", None, "EU sector stats (keyless)"),
        "comtrade": _ConnDesc(
            "aggregator", "comtrade_api_key", "bilateral trade; world-aggregate needs paid key"
        ),
        "fdic": _ConnDesc("regulator", None, "bank financials (keyless)"),
        "cms": _ConnDesc("regulator", None, "Medicare/Medicaid (keyless)"),
        "eia": _ConnDesc("regulator", "eia_api_key", "energy (keyless OK)"),
        "usda_nass": _ConnDesc("regulator", "usda_nass_api_key", "crop/livestock (keyless OK)"),
        "faa": _ConnDesc("regulator", None, "aviation; enplanements Excel-only (capability)"),
        "openfda": _ConnDesc("regulator", "openfda_api_key", "drugs/devices (keyless OK)"),
        "kalshi": _ConnDesc(
            "prediction_market", None, "event probabilities — QUARANTINED, never a TAM input"
        ),
        "alpha_vantage": _ConnDesc(
            "aggregator", "alpha_vantage_api_key", "equities/FX; 25 req/day free", requires_key=True
        ),
        "nasdaq_data_link": _ConnDesc(
            "aggregator",
            "nasdaq_data_link_api_key",
            "economic/commodity series; premium gated",
            requires_key=True,
        ),
        "dune": _ConnDesc(
            "onchain",
            "dune_api_key",
            "on-chain queries; reference-only (plan limits)",
            requires_key=True,
            capability_only=True,
        ),
        "yfinance": _ConnDesc(
            "analyst", None, "unofficial Yahoo scraper — fragile", capability_only=True
        ),
        "github": _ConnDesc(
            "community",
            "github_token",
            "stars/forks — community signal, QUARANTINED (token raises limits)",
        ),
        "reddit": _ConnDesc(
            "community",
            "reddit_client_id",
            "subscribers — community signal, QUARANTINED",
            requires_key=True,
        ),
        "stack_exchange": _ConnDesc(
            "community", "stack_exchange_key", "tag counts — community signal, QUARANTINED"
        ),
        "twitter": _ConnDesc(
            "analyst",
            "twitter_bearer_token",
            "X v2 free tier only — fragile",
            requires_key=True,
        ),
    }

    # The capability manifest is the live list of router-visible connectors. Cross
    # check it against the descriptor table so neither can silently drift.
    manifest_connectors = {spec.connector for spec in all_capabilities()}
    described = set(descriptors)
    if manifest_connectors - described:
        typer.echo(
            f"  ! manifest connectors with no descriptor: "
            f"{sorted(manifest_connectors - described)}",
            err=True,
        )

    typer.echo(f"Connector readiness ({len(descriptors)} typed connectors)\n")
    ready = blocked = capability = 0
    for name in sorted(descriptors):
        d = descriptors[name]
        key_present = d.key_attr is None or bool(getattr(settings, d.key_attr, None))
        if d.requires_key and not key_present:
            # `requires_key` implies key_attr is set, and key_present is only
            # False when key_attr is not None — narrow for the type checker.
            key_attr = d.key_attr or "api_key"
            status, mark = "BLOCKED", "⊘"
            reason = f"missing {key_attr} — set STRATA_{key_attr.upper()}"
            blocked += 1
        elif d.capability_only:
            status, mark = "CAPABILITY", "○"
            reason = d.note
            capability += 1
        else:
            status, mark = "READY", "✓"
            reason = d.note if key_present else f"{d.note} (no key — rate-limited)"
            ready += 1
        typer.echo(f"  {mark} {name:18} [{d.tier:17}] {status:11} — {reason}")

    typer.echo(
        f"\n{ready} ready · {blocked} blocked (API key) · {capability} capability-only "
        f"of {len(descriptors)} connectors."
    )

    if not live:
        typer.echo("(offline readiness only; pass --live to smoke-test keyless govt APIs)")
        return

    typer.echo("\nLive smoke test (keyless government APIs):")
    live_failed = 0
    try:
        from strata.connectors.fred import FREDClient

        with FREDClient(api_key=settings.fred_api_key) as client:
            resp = client.get_observations("GDP", limit=3, sort_order="desc")
            assert resp.observations, "No observations"
            typer.echo(f"  ✓ FRED    — GDP latest={resp.observations[0].value}")
    except Exception as exc:
        typer.echo(f"  ✗ FRED    — {exc}", err=True)
        live_failed += 1
    try:
        from strata.connectors.worldbank import WorldBankClient

        with WorldBankClient() as client:
            resp = client.get_indicator("SP.POP.TOTL", country="US", date_range="2023:2023")
            assert resp.values, "No values"
            typer.echo(f"  ✓ WBank   — US population={resp.values[0].value:,.0f}")
    except Exception as exc:
        typer.echo(f"  ✗ WBank   — {exc}", err=True)
        live_failed += 1
    if live_failed:
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

_PROMOTE_SLUG_ARG = typer.Argument(
    None, help="Slug of the auto-primitive to promote (omit with --from-ingest)."
)
_PROMOTE_DATA_DIR_OPT = typer.Option(
    Path("data"), "--data-dir", "-d", help="Target data directory."
)
_PROMOTE_FROM_INGEST_OPT = typer.Option(
    False,
    "--from-ingest",
    help="Promote EVERY not-yet-committed auto-primitive (bulk ingest campaign).",
)
_PROMOTE_VALIDATE_ONLY_OPT = typer.Option(
    False,
    "--validate-only",
    help="With --from-ingest: stage + validate but roll everything back (dry run).",
)


def _stage_auto_primitive(src: Path, dst: Path) -> None:
    """Copy an auto-primitive into the committed tree, stripping its ingest-only
    ``metadata`` block (is_auto / connector / args hash) which the committed
    AtomicPrimitive schema forbids — provenance is already pinned in
    ``source.snapshot_sha256``."""
    import yaml

    record = yaml.safe_load(src.read_text())
    if isinstance(record, dict):
        record.pop("metadata", None)
    dst.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True))


def _promote_subdir(src: Path) -> str:
    """Pick the committed-tree subdir for a staged auto-primitive by its tier.

    Non-sizing tiers (prediction-market / community-social, NON_SIZING_TIERS)
    land in ``data/signals/`` so the loader quarantines them as read-only
    signals; everything else lands in ``data/primitives/``. The destination is
    derived from the RECORD's tier — the same constant the loader and the DB
    path use — so a community/social primitive can never be promoted into the
    sizing bank by virtue of the directory the promote command writes to."""
    import yaml
    from pydantic import TypeAdapter

    from strata.models import NON_SIZING_TIERS
    from strata.models.primitive import AtomicPrimitive

    record = yaml.safe_load(src.read_text())
    if isinstance(record, dict):
        record = dict(record)
        record.pop("metadata", None)
    try:
        prim = TypeAdapter(AtomicPrimitive).validate_python(record)
    except Exception:
        return "primitives"  # let the normal validator surface a shape error
    return "signals" if prim.source.tier in NON_SIZING_TIERS else "primitives"


def _is_modeled_candidate(src: Path) -> bool:
    """Phase 4 (G2) — is this staged auto-primitive a MODELED/soft-data number?
    The committed bank's modeled primitives are hand-authored on purpose; the
    *promote* path is for connector-sourced output, so a modeled candidate
    reaching it is refused. provenance_class is derived from source.tier."""
    import yaml
    from pydantic import TypeAdapter

    from strata.models.primitive import AtomicPrimitive, ProvenanceClass

    record = yaml.safe_load(src.read_text())
    if isinstance(record, dict):
        record = dict(record)
        record.pop("metadata", None)
    try:
        prim = TypeAdapter(AtomicPrimitive).validate_python(record)
    except Exception:
        return False  # let the normal validator surface a shape error
    return prim.provenance_class is ProvenanceClass.MODELED


def _attribute_errors(errors: list[ValidationFinding], staged: set[str]) -> set[str]:
    """Map validator errors back to the staged slug(s) that caused them.

    Semantic/cross-record findings carry ``slug`` directly; structural findings
    (e.g. duplicate slug) leave it blank but name the slug in ``message``. We try
    the exact ``slug`` field first and only fall back to a message scan when no
    error attributes cleanly — that keeps over-rollback to a minimum.
    """
    exact = {f.slug for f in errors if f.slug in staged}
    if exact:
        return exact
    # Fall back to a message scan ONLY for errors that carry no staged slug of
    # their own — otherwise a pre-existing tree error that merely mentions a
    # staged slug name would wrongly eject a good primitive (over-rollback).
    unattributed = [f for f in errors if f.slug not in staged]
    return {s for s in staged for f in unattributed if s in f.message}


def _first_error_for(errors: list[ValidationFinding], slug: str) -> str:
    for f in errors:
        if f.slug == slug or slug in f.message:
            return f"{f.code}: {f.message}"
    return "rejected by validator"


def _promote_from_ingest(data_dir: Path, *, validate_only: bool) -> None:
    """Bulk-promote every staged auto-primitive, validating once and rolling back
    only the offenders so the committed tree is *never* left in a broken state.

    Unlike the single-slug path this does not re-validate per file (O(n²) on a
    few-hundred-primitive campaign): it stages the whole batch, validates once,
    drops the slug(s) the validator blames, and re-validates until clean.
    """
    from strata.resolver import AUTO_PRIMITIVES_DIR

    if not AUTO_PRIMITIVES_DIR.exists():
        typer.echo("No auto-primitives staged. Run `strata ingest run` first.")
        return

    primitives_dir = data_dir / "primitives"
    signals_dir = data_dir / "signals"
    primitives_dir.mkdir(parents=True, exist_ok=True)

    staged: dict[str, Path] = {}  # slug -> committed dst path (pending)
    src_of: dict[str, Path] = {}  # slug -> staging src path
    rejected_modeled: list[str] = []  # Phase 4 — soft-data candidates, never promoted
    already = 0
    for src in sorted(AUTO_PRIMITIVES_DIR.glob("*.yaml")):
        slug = src.stem
        # Route by the record's tier: non-sizing tiers go to data/signals/ so the
        # loader quarantines them; an already-promoted slug under EITHER dir is a
        # no-op (a primitive never silently splits across both trees).
        if _promote_subdir(src) == "signals":
            signals_dir.mkdir(parents=True, exist_ok=True)
            target_dir = signals_dir
        else:
            target_dir = primitives_dir
        dst = target_dir / f"{slug}.yaml"
        if dst.exists() or (primitives_dir / f"{slug}.yaml").exists():
            already += 1
            continue
        if _is_modeled_candidate(src):
            rejected_modeled.append(slug)
            continue
        _stage_auto_primitive(src, dst)
        staged[slug] = dst
        src_of[slug] = src

    if not staged:
        typer.echo(f"Nothing to promote ({already} already committed).")
        return

    rejected: dict[str, str] = {}
    while staged:
        report = run_validate(data_dir)
        if report.ok:
            break
        offenders = _attribute_errors(report.errors, set(staged))
        removed_any = False
        for slug in offenders:
            if slug not in staged:  # defensive: keep the loop crash-free
                continue
            rejected[slug] = _first_error_for(report.errors, slug)
            staged.pop(slug).unlink(missing_ok=True)
            removed_any = True
        if not removed_any:
            # Errors persist but no staged primitive can be blamed — roll the
            # whole remaining batch back so the tree stays loadable (guarantees
            # termination), then surface the errors.
            for slug, dst in staged.items():
                dst.unlink(missing_ok=True)
                rejected[slug] = "rolled back: unattributable validation error"
            staged.clear()
            typer.echo(
                "ERROR: validation errors not attributable to one primitive — "
                "rolled the batch back:",
                err=True,
            )
            for f in report.errors[:5]:
                typer.echo(f"  • {f.code}: {f.message}", err=True)
            break

    committed = sorted(staged)
    if validate_only:
        for dst in staged.values():
            dst.unlink(missing_ok=True)
        typer.echo(
            f"[validate-only] {len(committed)} would promote · "
            f"{len(rejected)} rejected · {already} already committed."
        )
    else:
        for slug in committed:
            src_of[slug].unlink(missing_ok=True)
        typer.echo(
            f"✓ Promoted {len(committed)} record(s) → {primitives_dir} / {signals_dir} "
            f"({len(rejected)} rejected · {already} already committed)."
        )
    for slug, reason in sorted(rejected.items()):
        typer.echo(f"  ✗ {slug}: {reason}", err=True)
    for slug in sorted(rejected_modeled):
        typer.echo(
            f"  ⊘ {slug}: refused — MODELED/soft-data, not promotable (Phase 4 fence)", err=True
        )
    if (rejected or rejected_modeled) and not committed:
        raise typer.Exit(code=1)


@app.command("promote")
def promote(
    slug: str | None = _PROMOTE_SLUG_ARG,
    data_dir: Path = _PROMOTE_DATA_DIR_OPT,
    from_ingest: bool = _PROMOTE_FROM_INGEST_OPT,
    validate_only: bool = _PROMOTE_VALIDATE_ONLY_OPT,
) -> None:
    """Move ~/.strata/auto-primitives/{slug}.yaml → data/primitives/{slug}.yaml.

    Refuses promotion if the validator rejects (mirrors v0.5 contribution flow).
    Idempotent: re-running on an already-promoted slug is a no-op. Pass
    ``--from-ingest`` to promote the whole staged batch at once.
    """
    if from_ingest:
        _promote_from_ingest(data_dir, validate_only=validate_only)
        return

    if slug is None:
        typer.echo("ERROR: provide a slug, or use --from-ingest to bulk-promote.", err=True)
        raise typer.Exit(code=2)

    from strata.resolver import AUTO_PRIMITIVES_DIR

    src = AUTO_PRIMITIVES_DIR / f"{slug}.yaml"
    if not src.exists():
        typer.echo(
            f"ERROR: {src} does not exist. Run `strata goal` first to mint an auto-primitive.",
            err=True,
        )
        raise typer.Exit(code=2)

    target_dir = data_dir / _promote_subdir(src)
    target_dir.mkdir(parents=True, exist_ok=True)
    dst = target_dir / f"{slug}.yaml"
    # Idempotent across BOTH trees: a slug already promoted to primitives/ OR
    # signals/ is a no-op, so a tier flip can never silently fork it into both.
    if dst.exists() or (data_dir / "primitives" / f"{slug}.yaml").exists():
        typer.echo(f"{slug} is already promoted — no-op.")
        return

    # Phase 4 (G2): the promote path is for sourced connector output; refuse a
    # MODELED/soft-data candidate before it can enter the committed bank.
    if _is_modeled_candidate(src):
        typer.echo(
            f"ERROR: refusing to promote {slug} — it is MODELED/soft-data, not a "
            f"sourced measurement (Phase 4 fence).",
            err=True,
        )
        raise typer.Exit(code=1)

    # Stage, then run the validator on data_dir. Roll back on reject.
    _stage_auto_primitive(src, dst)
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


# --------------------------------------------------------------------------- #
# Feedback loop (Phase F) — flag → triage → apply the fix into the data layer. #
# --------------------------------------------------------------------------- #

feedback_app = typer.Typer(
    name="feedback",
    help="Flag bad assumptions / failed queries / corrections; triage and apply them.",
    no_args_is_help=True,
)
app.add_typer(feedback_app)

# Org scope is required: feedback_events is RLS-scoped, so every CLI verb runs
# inside org_session_scope(org) exactly like the HTTP routes. Operator passes the
# tenant explicitly (the CLI has no Clerk session to derive it from).
_FB_ORG_OPT = typer.Option(..., "--org", help="Org id to scope the operation to (RLS tenant).")
_FB_KIND_OPT = typer.Option(
    "general",
    "--kind",
    help="bad_assumption | failed_query | primitive_correction | missing_data | general.",
)
_FB_TARGET_OPT = typer.Option(
    "query", "--target", help="tam | primitive | concept | framework | query | report."
)
_FB_BODY_OPT = typer.Option(..., "--body", help="What's wrong / what you observed.")
_FB_TARGET_ID_OPT = typer.Option(None, "--target-id", help="The flagged target (hash or slug).")
_FB_STATUS_OPT = typer.Option(None, "--status", help="Filter by status (open/triaged/...).")
_FB_APPLY_OPT = typer.Option(
    False, "--apply", help="Also apply the correction (create an org-private primitive)."
)
_FB_RESOLUTION_OPT = typer.Option(None, "--resolution", help="Resolution note when resolving.")
_FB_ID_ARG = typer.Argument(..., help="Feedback row id.")


@feedback_app.command("submit")
def feedback_submit(
    org: str = _FB_ORG_OPT,
    body: str = _FB_BODY_OPT,
    kind: str = _FB_KIND_OPT,
    target: str = _FB_TARGET_OPT,
    target_id: str | None = _FB_TARGET_ID_OPT,
) -> None:
    """Flag a bad assumption / failed query / correction (org-scoped, RLS)."""
    import asyncio

    from strata.db.engine import org_session_scope
    from strata.db.feedback import record_feedback
    from strata.models.feedback import FeedbackKind, TargetType

    async def _run() -> int:
        async with org_session_scope(org) as session:
            event = await record_feedback(
                session,
                org_id=org,
                user_id=None,
                kind=FeedbackKind(kind),
                target_type=TargetType(target),
                body=body,
                target_id=target_id,
            )
            return event.id

    try:
        fid = asyncio.run(_run())
    except ValueError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"ERROR writing feedback: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"✓ Flag {fid} submitted ({kind} on {target}).")


@feedback_app.command("list")
def feedback_list(org: str = _FB_ORG_OPT, status: str | None = _FB_STATUS_OPT) -> None:
    """List the org's flags newest-first, optionally filtered by status."""
    import asyncio

    from strata.db.engine import org_session_scope
    from strata.db.feedback import list_feedback
    from strata.models.feedback import FeedbackEvent, FeedbackStatus

    status_filter = FeedbackStatus(status) if status else None

    async def _run() -> list[FeedbackEvent]:
        async with org_session_scope(org) as session:
            return await list_feedback(session, org_id=org, status=status_filter, limit=100)

    try:
        rows = asyncio.run(_run())
    except ValueError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"ERROR listing feedback: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if not rows:
        typer.echo("No feedback for this org.")
        return
    for r in rows:
        tgt = f"{r.target_type.value}:{r.target_id}" if r.target_id else r.target_type.value
        typer.echo(f"  #{r.id:<5} [{r.status.value:<8}] {r.kind.value:<22} {tgt}  — {r.body[:60]}")


@feedback_app.command("resolve")
def feedback_resolve(
    feedback_id: int = _FB_ID_ARG,
    org: str = _FB_ORG_OPT,
    apply_correction: bool = _FB_APPLY_OPT,
    resolution: str | None = _FB_RESOLUTION_OPT,
) -> None:
    """Resolve a flag. With ``--apply`` the correction is written into the data
    layer (creates an org-private primitive from the flag's suggested_value through
    the same MODELED fence as the HTTP/MCP paths); otherwise it just marks the row
    resolved."""
    import asyncio

    from strata.db.engine import org_session_scope
    from strata.db.feedback import (
        FeedbackNotApplicableError,
        apply_feedback_correction,
        update_feedback,
    )
    from strata.db.user_primitives import ModeledFenceError
    from strata.models.feedback import FeedbackStatus

    async def _run() -> str:
        async with org_session_scope(org) as session:
            if apply_correction:
                _event, prim = await apply_feedback_correction(
                    session, feedback_id, org_id=org, primitive_payload=None
                )
                return f"applied → org-private primitive {prim.slug!r} (id={prim.id})"
            updated = await update_feedback(
                session,
                feedback_id,
                org_id=org,
                status=FeedbackStatus.RESOLVED,
                resolution=resolution,
            )
            if updated is None:
                raise FeedbackNotApplicableError(f"no feedback {feedback_id} visible to this org")
            return "resolved"

    try:
        outcome = asyncio.run(_run())
    except (FeedbackNotApplicableError, ModeledFenceError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"ERROR resolving feedback: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"✓ Flag {feedback_id} {outcome}.")


gaps_app = typer.Typer(
    name="gaps",
    help="The demand-ranked sourcing backlog: queries/roles we had no sourced number "
    "for, ranked by how often they were asked.",
    no_args_is_help=True,
)
app.add_typer(gaps_app)

_GAPS_STATUS_OPT = typer.Option(None, "--status", help="Filter by status (open/sourced/wontfix).")
_GAPS_ALL_OPT = typer.Option(False, "--all", help="Every workspace, ranked platform-wide (admin).")
_GAPS_ORG_OPT = typer.Option(None, "--org", help="Narrow to a single workspace (with --all).")
_GAPS_LIMIT_OPT = typer.Option(20, "--top", help="Max rows (most-demanded first).")


@gaps_app.command("list")
def gaps_list(
    status: str | None = _GAPS_STATUS_OPT,
    all_orgs: bool = _GAPS_ALL_OPT,
    org: str | None = _GAPS_ORG_OPT,
    limit: int = _GAPS_LIMIT_OPT,
) -> None:
    """List sourcing gaps, most-demanded first. ``--all`` ranks every workspace's
    gaps platform-wide (the connector-build backlog ordered by real demand)."""
    import asyncio

    from strata.db.engine import admin_session_scope, org_session_scope
    from strata.db.sourcing_gaps import admin_list_gaps, list_gaps
    from strata.models.sourcing_gap import GapStatus, SourcingGap

    status_filter = GapStatus(status) if status else None

    async def _run() -> list[SourcingGap]:
        if all_orgs:
            async with admin_session_scope(_ADMIN_ORG) as session:
                return await admin_list_gaps(session, status=status_filter, org_id=org, limit=limit)
        # Org scope requires an explicit tenant when not --all.
        if org is None:
            raise ValueError("pass --org <workspace> (or --all for the platform queue)")
        async with org_session_scope(org) as session:
            return await list_gaps(session, org_id=org, status=status_filter, limit=limit)

    try:
        rows = asyncio.run(_run())
    except ValueError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"ERROR listing gaps: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if not rows:
        typer.echo("No sourcing gaps recorded.")
        return
    for r in rows:
        tgt = r.resource_target or (r.query_text or "")
        scope = f"{r.org_id:<24} " if all_orgs else ""
        typer.echo(f"  ×{r.hit_count:<4} [{r.status.value:<7}] {scope}{tgt[:64]}")


@gaps_app.command("record")
def gaps_record(
    org: str = typer.Option(..., "--org", help="Workspace to attribute the gap to."),
    query: str | None = typer.Option(None, "--query", help="The market that had no answer."),
    resource_target: str | None = typer.Option(
        None, "--target", help="connector:method that would fill it."
    ),
) -> None:
    """Manually log a sourcing gap (de-duplicated; a repeat bumps its hit count)."""
    import asyncio

    from strata.db.engine import org_session_scope
    from strata.db.sourcing_gaps import record_gap
    from strata.models.sourcing_gap import GapSource

    if not query and not resource_target:
        typer.echo("ERROR: pass --query or --target", err=True)
        raise typer.Exit(code=1)

    async def _run() -> int:
        async with org_session_scope(org) as session:
            gap = await record_gap(
                session,
                org_id=org,
                source=GapSource.MANUAL,
                query_text=query,
                resource_target=resource_target,
            )
            return gap.hit_count

    try:
        hits = asyncio.run(_run())
    except Exception as exc:
        typer.echo(f"ERROR recording gap: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"✓ Gap recorded (hit_count={hits}).")


@gaps_app.command("resolve")
def gaps_resolve(
    gap_id: int = typer.Argument(..., help="Sourcing-gap row id to close."),
    org: str = typer.Option(..., "--org", help="Workspace the gap belongs to (RLS tenant)."),
    primitive_id: int | None = typer.Option(
        None, "--primitive-id", help="The org-private primitive that now sources it."
    ),
    note: str | None = typer.Option(None, "--note", help="How it was sourced."),
) -> None:
    """Close a gap once its number is sourced — flips status to ``sourced`` and
    optionally links the primitive that filled it."""
    import asyncio

    from strata.db.engine import org_session_scope
    from strata.db.sourcing_gaps import mark_gap_sourced

    async def _run() -> bool:
        async with org_session_scope(org) as session:
            closed = await mark_gap_sourced(
                session, gap_id, org_id=org, resolved_primitive_id=primitive_id, note=note
            )
            return closed is not None

    try:
        ok = asyncio.run(_run())
    except Exception as exc:
        typer.echo(f"ERROR resolving gap: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if not ok:
        typer.echo(f"No gap {gap_id} visible to {org}.", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"✓ Gap {gap_id} marked sourced.")


admin_app = typer.Typer(
    name="admin",
    help="Cross-org governance: read every tenant's feedback, promote a correction "
    "into the shared bank. Local-trust (operator has repo access).",
    no_args_is_help=True,
)
app.add_typer(admin_app)

# The CLI is local-trust, so it sets the admin GUC directly (the STRATA_ADMIN_ORGS
# allowlist gates the *network* MCP path). app.org_id is set to a stable sentinel
# inside admin_session_scope; the cross-org reads key on app.is_admin, not the org.
_ADMIN_ORG = "cli-admin"
_ADMIN_STATUS_OPT = typer.Option(None, "--status", help="Filter by status (open/triaged/...).")
_ADMIN_KIND_OPT = typer.Option(None, "--kind", help="Filter by flag kind.")
_ADMIN_FILTER_ORG_OPT = typer.Option(None, "--org", help="Narrow to a single tenant's queue.")
_ADMIN_PROMOTE_ORG_OPT = typer.Option(
    None, "--org", help="The originating org of the flag (for the audit note)."
)
_ADMIN_VALIDATE_ONLY_OPT = typer.Option(
    False, "--validate-only", help="Validate + print the shared YAML but don't write/resolve."
)
_ADMIN_ID_ARG = typer.Argument(..., help="Feedback row id to promote.")


@admin_app.command("feedback")
def admin_feedback(
    status: str | None = _ADMIN_STATUS_OPT,
    kind: str | None = _ADMIN_KIND_OPT,
    org: str | None = _ADMIN_FILTER_ORG_OPT,
) -> None:
    """List feedback across EVERY org's queue (newest-first), with org attribution."""
    import asyncio

    from strata.db.engine import admin_session_scope
    from strata.db.feedback import admin_list_feedback
    from strata.models.feedback import FeedbackEvent, FeedbackKind, FeedbackStatus

    status_filter = FeedbackStatus(status) if status else None
    kind_filter = FeedbackKind(kind) if kind else None

    async def _run() -> list[FeedbackEvent]:
        async with admin_session_scope(_ADMIN_ORG) as session:
            return await admin_list_feedback(
                session, status=status_filter, kind=kind_filter, org_id=org, limit=200
            )

    try:
        rows = asyncio.run(_run())
    except ValueError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"ERROR listing feedback: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if not rows:
        typer.echo("No feedback across any org.")
        return
    for r in rows:
        tgt = f"{r.target_type.value}:{r.target_id}" if r.target_id else r.target_type.value
        typer.echo(
            f"  #{r.id:<5} [{r.status.value:<8}] {r.org_id:<28} {r.kind.value:<22} "
            f"{tgt}  — {r.body[:50]}"
        )


@admin_app.command("promote")
def admin_promote(
    feedback_id: int = _ADMIN_ID_ARG,
    org: str | None = _ADMIN_PROMOTE_ORG_OPT,
    data_dir: Path = _DATA_DIR_OPT,
    validate_only: bool = _ADMIN_VALIDATE_ONLY_OPT,
) -> None:
    """Promote an org-private correction into the SHARED bank: re-validate through
    the shared-bank fence (a modeled / analyst-tier number is refused — Q20), write
    ``data/primitives/<slug>.yaml``, and mark the flag resolved cross-org."""
    import asyncio

    import yaml

    from strata.db.engine import admin_session_scope
    from strata.db.feedback import FeedbackNotApplicableError, admin_promote_payload
    from strata.guards.fence import ModeledFenceError

    async def _run() -> dict[str, Any]:
        # The read → fence → resolve sequence lives in admin_promote_payload so the
        # CLI and the MCP tool can't drift; validate_only maps to resolve=False.
        async with admin_session_scope(_ADMIN_ORG) as session:
            shared, _ = await admin_promote_payload(session, feedback_id, resolve=not validate_only)
            return shared

    try:
        shared = asyncio.run(_run())
    except (FeedbackNotApplicableError, ModeledFenceError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"ERROR promoting correction: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    slug = str(shared["slug"])
    if validate_only:
        typer.echo(f"✓ Validated (not written). Shared YAML for {slug!r}:\n")
        typer.echo(yaml.safe_dump(shared, sort_keys=False))
        return
    dest = data_dir / "primitives" / f"{slug}.yaml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.safe_dump(shared, sort_keys=False), encoding="utf-8")
    origin = f" (from {org})" if org else ""
    typer.echo(f"✓ Promoted flag {feedback_id}{origin} → {dest}")
    typer.echo("  Validate + seed: `strata validate` then `strata db seed`.")


traces_app = typer.Typer(
    name="traces",
    help="MCP session traces: list captured sessions, inspect ordered calls, export "
    "golden fixtures, replay against current code to surface regressions, or purge "
    "old captures. Gated on STRATA_TRACE_CAPTURE=1 at capture time (safe to read "
    "when the gate was ever on).",
    no_args_is_help=True,
)
app.add_typer(traces_app)

# Module-level Option singletons (B008 — never put typer.Option(...) in a function
# default; Typer reads them at definition time; these mirror the gaps_app pattern).
_TRACES_ORG_OPT = typer.Option(None, "--org", help="Workspace (org_id) to scope reads to.")
_TRACES_ALL_OPT = typer.Option(
    False, "--all", help="Read across every workspace (admin scope — local-trust only)."
)
_TRACES_OUTCOME_OPT = typer.Option(
    None,
    "--outcome",
    help="Filter by agent-submitted outcome (ok/unsourced/unverifiable/error/flagged).",
)
_TRACES_TOP_OPT = typer.Option(50, "--top", help="Max sessions to return (most-recent first).")
_TRACES_OUT_OPT = typer.Option(
    None, "--out", help="Destination path for the exported fixture JSON."
)
_TRACES_FIXTURE_OPT = typer.Option(
    None, "--fixture", help="Path to a JSON fixture written by 'traces export'."
)
_TRACES_INCLUDE_WRITES_OPT = typer.Option(
    False,
    "--include-writes",
    help="Replay [WRITE] tools too (DANGEROUS: mutates real org data; use a sandboxed DB).",
)
_TRACES_BEFORE_OPT = typer.Option(
    None,
    "--before",
    help="ISO-8601 datetime; purge sessions whose last_seen_at is older than this.",
)
_TRACES_SESSION_OPT = typer.Option(
    None, "--session", help="Purge exactly this one session_id (overrides --before)."
)


@traces_app.command("list")
def traces_list(
    org: str | None = _TRACES_ORG_OPT,
    all_orgs: bool = _TRACES_ALL_OPT,
    outcome: str | None = _TRACES_OUTCOME_OPT,
    limit: int = _TRACES_TOP_OPT,
) -> None:
    """List captured MCP sessions, most-recently-active first.

    Use ``--all`` for the platform-wide admin view; ``--org`` for a single workspace."""
    import asyncio

    from strata.db.engine import admin_session_scope, org_session_scope
    from strata.db.traces import admin_list_sessions, list_sessions
    from strata.models.trace import TraceSession

    async def _run() -> list[TraceSession]:
        if all_orgs:
            async with admin_session_scope(_ADMIN_ORG) as session:
                return await admin_list_sessions(session, org_id=org, outcome=outcome, limit=limit)
        if org is None:
            raise ValueError("pass --org <workspace> or --all for the platform view")
        async with org_session_scope(org) as session:
            return await list_sessions(session, outcome=outcome, limit=limit, offset=0)

    try:
        rows = asyncio.run(_run())
    except ValueError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"ERROR listing sessions: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if not rows:
        typer.echo("No trace sessions found.")
        return
    for r in rows:
        outcome_tag = r.outcome or "-"
        last = r.last_seen_at.strftime("%Y-%m-%dT%H:%M")
        typer.echo(
            f"  {r.session_id[:16]}…  calls={r.call_count:<4}  outcome={outcome_tag:<14}  {last}"
        )


@traces_app.command("show")
def traces_show(
    session_id: str = typer.Argument(..., help="The session_id to inspect."),
    org: str | None = _TRACES_ORG_OPT,
    all_orgs: bool = _TRACES_ALL_OPT,
) -> None:
    """Print the ordered tool calls for a session and its agent-submitted reasoning."""
    import asyncio

    from strata.db.engine import admin_session_scope, org_session_scope
    from strata.db.traces import (
        admin_get_session_calls,
        admin_list_sessions,
        get_session_calls,
        list_sessions,
    )
    from strata.models.trace import ToolCall, TraceSession

    async def _run() -> tuple[TraceSession | None, list[ToolCall]]:
        if all_orgs:
            async with admin_session_scope(_ADMIN_ORG) as session:
                sessions = await admin_list_sessions(session, org_id=org, limit=1000)
                sess = next((s for s in sessions if s.session_id == session_id), None)
                calls = await admin_get_session_calls(session, session_id=session_id, org_id=org)
            return sess, calls
        if org is None:
            raise ValueError("pass --org <workspace> or --all")
        async with org_session_scope(org) as session:
            sessions = await list_sessions(session, limit=1000)
            sess = next((s for s in sessions if s.session_id == session_id), None)
            calls = await get_session_calls(session, session_id=session_id)
        return sess, calls

    try:
        sess, calls = asyncio.run(_run())
    except ValueError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"ERROR fetching session: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if not calls:
        typer.echo(f"No calls found for session {session_id!r}.", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Session {session_id}")
    if sess:
        typer.echo(
            f"  calls={sess.call_count}  outcome={sess.outcome or '-'}  "
            f"last={sess.last_seen_at.strftime('%Y-%m-%dT%H:%M')}"
        )
    typer.echo("")
    typer.echo(f"  {'seq':<5} {'tool':<34} {'status':<7} {'ms':>6}")
    typer.echo(f"  {'-' * 5} {'-' * 34} {'-' * 7} {'-' * 6}")
    for c in calls:
        typer.echo(f"  {c.seq:<5} {c.tool:<34} {c.status.value:<7} {c.duration_ms:>6}")

    if sess and sess.reasoning:
        typer.echo("\n--- reasoning ---")
        typer.echo(sess.reasoning)


@traces_app.command("export")
def traces_export(
    session_id: str = typer.Argument(..., help="Session to export."),
    org: str | None = _TRACES_ORG_OPT,
    all_orgs: bool = _TRACES_ALL_OPT,
    out: Path | None = _TRACES_OUT_OPT,
) -> None:
    """Export a captured session to a versioned JSON fixture for replay in CI.

    Writes to ``--out`` or ``tests/fixtures/traces/<session_id>.json`` by default."""
    import asyncio
    import json as _json
    from datetime import datetime

    from strata.db.engine import admin_session_scope, org_session_scope
    from strata.db.traces import (
        admin_get_session_calls,
        admin_list_sessions,
        get_session_calls,
        list_sessions,
    )
    from strata.models.trace import ToolCall, TraceSession

    async def _run() -> tuple[TraceSession | None, list[ToolCall]]:
        if all_orgs:
            async with admin_session_scope(_ADMIN_ORG) as session:
                sessions = await admin_list_sessions(session, org_id=org, limit=1000)
                sess = next((s for s in sessions if s.session_id == session_id), None)
                calls = await admin_get_session_calls(session, session_id=session_id, org_id=org)
            return sess, calls
        if org is None:
            raise ValueError("pass --org <workspace> or --all")
        async with org_session_scope(org) as session:
            sessions = await list_sessions(session, limit=1000)
            sess = next((s for s in sessions if s.session_id == session_id), None)
            calls = await get_session_calls(session, session_id=session_id)
        return sess, calls

    try:
        sess, calls = asyncio.run(_run())
    except ValueError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"ERROR fetching session: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if not calls:
        typer.echo(f"No calls found for session {session_id!r}.", err=True)
        raise typer.Exit(code=1)

    # Resolve output path — default to tests/fixtures/traces/ next to the
    # backend package root so the fixture is version-controllable alongside tests.
    if out is None:
        here = Path(__file__).resolve().parent
        # cli.py lives at backend/src/strata/cli.py → parents[2] == backend/
        fixtures_dir = here.parents[2] / "tests" / "fixtures" / "traces"
        fixtures_dir.mkdir(parents=True, exist_ok=True)
        out = fixtures_dir / f"{session_id}.json"

    # Fixture JSON shape (documented in traces/replay.py module docstring).
    fixture: dict[str, object] = {
        "schema_version": 1,
        "session_id": session_id,
        "org_id": sess.org_id if sess else (org or "unknown"),
        "reasoning": sess.reasoning if sess else None,
        "exported_at": datetime.now(UTC).isoformat(),
        "calls": [
            _json.loads(c.model_dump_json())
            for c in sorted(calls, key=lambda c: (c.seq, c.created_at))
        ],
    }

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json.dumps(fixture, indent=2, default=str), encoding="utf-8")
    typer.echo(f"✓ Exported {len(calls)} call(s) → {out}")


@traces_app.command("replay")
def traces_replay(
    session_id: str | None = typer.Argument(
        None,
        help="Session to replay from the DB (requires --org or --all).",
    ),
    org: str | None = _TRACES_ORG_OPT,
    all_orgs: bool = _TRACES_ALL_OPT,
    fixture: Path | None = _TRACES_FIXTURE_OPT,
    include_writes: bool = _TRACES_INCLUDE_WRITES_OPT,
) -> None:
    """Replay a captured session against current code and report hash divergences.

    Exits non-zero when any call produces a 'diff' or 'error' — usable as a CI
    regression gate.  Write tools are skipped by default (pass --include-writes
    only against a sandboxed DB)."""
    # ── load calls ──────────────────────────────────────────────────────────────
    from strata.models.trace import ToolCall
    from strata.traces.replay import load_session_from_fixture, replay_session

    if fixture is not None:
        try:
            calls = load_session_from_fixture(fixture)
        except Exception as exc:
            typer.echo(f"ERROR loading fixture {fixture}: {exc}", err=True)
            raise typer.Exit(code=1) from exc
    elif session_id is not None:
        import asyncio as _asyncio

        from strata.db.engine import admin_session_scope, org_session_scope
        from strata.db.traces import admin_get_session_calls, get_session_calls

        async def _load() -> list[ToolCall]:
            if all_orgs:
                async with admin_session_scope(_ADMIN_ORG) as session:
                    return await admin_get_session_calls(session, session_id=session_id, org_id=org)
            if org is None:
                raise ValueError("pass --org <workspace> or --all (or use --fixture)")
            async with org_session_scope(org) as session:
                return await get_session_calls(session, session_id=session_id)

        try:
            calls = _asyncio.run(_load())
        except ValueError as exc:
            typer.echo(f"ERROR: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        except Exception as exc:
            typer.echo(f"ERROR loading session: {exc}", err=True)
            raise typer.Exit(code=1) from exc
    else:
        typer.echo("ERROR: provide a session_id argument or --fixture path.", err=True)
        raise typer.Exit(code=1)

    if not calls:
        typer.echo("No calls to replay.", err=True)
        raise typer.Exit(code=1)

    # ── build offline registry ───────────────────────────────────────────────────
    # Replay is registry-first + YAML-only so no live DB connector path runs.
    # server.load_registry() uses a short TTL cache and reads from the configured
    # data_dir — the same source of truth as the capture path.
    try:
        from strata.mcp.server import load_registry

        reg = load_registry()
    except Exception as exc:
        typer.echo(f"ERROR building registry: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    # ── run replay ──────────────────────────────────────────────────────────────
    report = replay_session(reg, calls, include_writes=include_writes)

    # ── print report ────────────────────────────────────────────────────────────
    status_symbols = {"match": "✓", "diff": "✗", "skipped": "~", "error": "!"}
    typer.echo(f"Replay — session {report.session_id or 'fixture'} — {len(report.calls)} call(s)")
    typer.echo("")
    for cr in report.calls:
        sym = status_symbols.get(cr.status, "?")
        line = f"  {sym} seq={cr.seq:<4} {cr.tool:<34} {cr.status}"
        if cr.status == "diff":
            line += f"\n      captured={cr.captured_hash[:16]}…  fresh={cr.fresh_hash[:16] if cr.fresh_hash else 'N/A'}…"
        elif cr.status == "error":
            line += f"\n      {cr.error}"
        typer.echo(line)

    typer.echo("")
    if report.passed:
        typer.echo("PASS — no regressions detected.")
    else:
        typer.echo("FAIL — regression(s) detected (see diff/error rows above).", err=True)
        raise typer.Exit(code=1)


@traces_app.command("purge")
def traces_purge(
    org: str = typer.Option(..., "--org", help="Workspace to purge traces for."),
    before: str | None = _TRACES_BEFORE_OPT,
    session: str | None = _TRACES_SESSION_OPT,
) -> None:
    """Delete captured sessions for a workspace.  Use ``--before`` for date-based
    cleanup or ``--session`` to delete exactly one session."""
    import asyncio
    from datetime import datetime

    from strata.db.engine import org_session_scope
    from strata.db.traces import purge_sessions

    before_dt: datetime | None = None
    if before is not None:
        try:
            before_dt = datetime.fromisoformat(before)
            if before_dt.tzinfo is None:
                # Treat a naive ISO string as UTC so --before=2026-01-01 is unambiguous.
                before_dt = before_dt.replace(tzinfo=UTC)
        except ValueError as exc:
            typer.echo(f"ERROR: --before must be an ISO-8601 datetime: {exc}", err=True)
            raise typer.Exit(code=1) from exc

    async def _run() -> int:
        async with org_session_scope(org) as db_session:
            return await purge_sessions(db_session, before=before_dt, session_id=session)

    try:
        deleted = asyncio.run(_run())
    except Exception as exc:
        typer.echo(f"ERROR purging traces: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if deleted == 0:
        typer.echo("No sessions matched the filter.")
    else:
        typer.echo(f"✓ Purged {deleted} session(s) from {org}.")


if __name__ == "__main__":
    app()
