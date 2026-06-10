"""MCP `sense_check` tool — the market-share-implied TAM cross-check (agent parity
with `strata sense-check`).

The payload mirrors the CLI result structurally (implied TAM, band, floor,
leverage, residual, per-player rows, warnings, assumptions) and ALWAYS carries
the machine-readable MODELED marker: market shares are analyst estimates, so the
implied TAM is a modeled cross-check even when every revenue is a sourced filing
(Q20) — it never becomes a sourced number.

`edgar_ticker` resolution is a live SEC call, gated behind the same
``STRATA_MCP_LIVE_CONNECTORS=1`` env gate as ``get_connector_data`` so the
default MCP surface stays offline-safe.
"""

from __future__ import annotations

import os
from typing import Any

from ..connectors.edgar import EDGARClient
from ..evaluator.engine import EvaluatorError
from ..registry import Registry, RegistryError
from ..sizing.revenue_lookup import RevenueLookupError, resolve_revenue, to_player
from ..sizing.sense_check import (
    MODELED_LABEL,
    Player,
    SenseCheckError,
    normalize_share,
    parse_as_of,
    parse_share_basis,
)
from ..sizing.sense_check import (
    sense_check as run_sense_check,
)
from ..sizing.service import sourced_scenarios
from .errors import (
    CODE_CONCEPT_NOT_FOUND,
    CODE_EVALUATOR_ERROR,
    CODE_INVALID_INPUT,
    CODE_LIVE_DISABLED,
    ToolError,
)


def _player_from_row(row: dict[str, Any], live_enabled: bool, client: EDGARClient) -> Player:
    name = str(row.get("name") or "").strip()
    if not name:
        raise ToolError("each player needs a non-empty 'name'", code=CODE_INVALID_INPUT)
    raw_share = row.get("market_share")
    if not isinstance(raw_share, (int, float)) or isinstance(raw_share, bool):
        raise ToolError(
            f"player {name!r}: 'market_share' must be a number (fraction 0.15 or percent 15)",
            code=CODE_INVALID_INPUT,
        )
    share = normalize_share(float(raw_share))

    # The guardrail inputs are validated at the door so a bad token is an honest
    # CODE_INVALID_INPUT, not a deep engine error.
    raw_rev_as_of = str(row.get("revenue_as_of") or "").strip()
    raw_share_as_of = str(row.get("share_as_of") or "").strip()
    try:
        revenue_as_of = parse_as_of(raw_rev_as_of) if raw_rev_as_of else ""
        share_as_of = parse_as_of(raw_share_as_of) if raw_share_as_of else ""
        share_basis = parse_share_basis(str(row.get("share_basis") or ""))
    except SenseCheckError as exc:
        raise ToolError(f"player {name!r}: {exc}", code=CODE_INVALID_INPUT) from exc

    ticker = str(row.get("edgar_ticker") or "").strip()
    revenue = row.get("revenue")
    if ticker and revenue is not None:
        raise ToolError(
            f"player {name!r}: provide 'revenue' OR 'edgar_ticker', not both",
            code=CODE_INVALID_INPUT,
        )
    if ticker:
        if revenue_as_of:
            raise ToolError(
                f"player {name!r}: 'revenue_as_of' conflicts with 'edgar_ticker' — the "
                f"filing's fiscal-period end fills revenue_as_of automatically",
                code=CODE_INVALID_INPUT,
            )
        if not live_enabled:
            raise ToolError(
                f"player {name!r}: resolving 'edgar_ticker' is a live SEC EDGAR call, "
                "which is disabled; set STRATA_MCP_LIVE_CONNECTORS=1 on the server, or "
                "pass a numeric 'revenue' instead (offline).",
                code=CODE_LIVE_DISABLED,
                remediation="set STRATA_MCP_LIVE_CONNECTORS=1 or supply revenue directly",
            )
        try:
            rr = resolve_revenue(ticker, client=client)
        except RevenueLookupError as exc:
            raise ToolError(str(exc), code=CODE_INVALID_INPUT, retriable=True) from exc
        return to_player(name, share, rr, share_as_of=share_as_of, share_basis=share_basis)
    if not isinstance(revenue, (int, float)) or isinstance(revenue, bool):
        raise ToolError(
            f"player {name!r}: provide a numeric 'revenue' or an 'edgar_ticker'",
            code=CODE_INVALID_INPUT,
        )
    return Player(
        name=name,
        revenue=float(revenue),
        market_share=share,
        revenue_as_of=revenue_as_of,
        share_as_of=share_as_of,
        share_basis=share_basis,
    )


def sense_check_tool(
    reg: Registry, *, players: list[dict[str, Any]], concept_slug: str | None = None
) -> dict[str, Any]:
    live_enabled = os.getenv("STRATA_MCP_LIVE_CONNECTORS") == "1"
    # Construction is cheap and no-network; one client serves every edgar: row.
    with EDGARClient() as client:
        parsed = [_player_from_row(row, live_enabled, client) for row in players]

    scenarios: tuple[float, ...] | None = None
    if concept_slug:
        try:
            scenarios = sourced_scenarios(reg, concept_slug)
        except RegistryError as exc:
            raise ToolError(
                f"concept {concept_slug!r} not found",
                code=CODE_CONCEPT_NOT_FOUND,
                remediation="search_concepts to find a matching slug",
            ) from exc
        except EvaluatorError as exc:
            raise ToolError(str(exc), code=CODE_EVALUATOR_ERROR) from exc

    try:
        r = run_sense_check(parsed, sourced_scenarios=scenarios)
    except SenseCheckError as exc:
        raise ToolError(str(exc), code=CODE_INVALID_INPUT) from exc

    sourced_range = None
    if r.sourced_low is not None and r.sourced_high is not None:
        sourced_range = {"low": r.sourced_low, "mid": r.sourced_mid, "high": r.sourced_high}
    return {
        # Unconditional Q20 marker — machine-readable, never gated on sourcing.
        "modeled": True,
        "modeled_label": MODELED_LABEL,
        "implied_tam": r.implied_tam,
        # Band/leverage/residual are null when Σshare ≥ 100% (a band that would
        # exclude its own point estimate is suppressed, never emitted).
        "implied_low": r.implied_low,
        "implied_high": r.implied_high,
        "share_tolerance": r.share_tolerance,
        "revenue_floor": r.revenue_floor,
        "combined_share": r.combined_share,
        "leverage": r.leverage,
        "residual": r.residual,
        "spread_ratio": r.spread_ratio,
        "n_players": r.n_players,
        "n_sourced": r.n_sourced,
        "all_revenue_sourced": r.all_revenue_sourced,
        "per_player": [
            {
                "name": p.name,
                "revenue": p.revenue,
                "market_share": p.market_share,
                "implied_tam": p.implied_tam,
                "revenue_sourced": p.revenue_sourced,
                "revenue_note": p.revenue_note or None,
                "revenue_as_of": p.revenue_as_of or None,
                "share_as_of": p.share_as_of or None,
                "share_basis": p.share_basis or None,
            }
            for p in r.per_player
        ],
        # The total-company caveat now arrives as an engine warning (set by the
        # typed marker), so no surface re-derives it from prose.
        "warnings": list(r.warnings),
        "assumptions": list(r.assumptions),
        "concept": concept_slug,
        "sourced_range": sourced_range,
        "vs_mid_ratio": r.vs_mid_ratio,
        "verdict": r.verdict,
    }
