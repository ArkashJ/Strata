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

from ..evaluator import size_concept
from ..evaluator.engine import EvaluatorError
from ..registry import Registry
from ..sizing.revenue_lookup import RevenueLookupError, resolve_revenue
from ..sizing.sense_check import (
    Player,
    SenseCheckError,
    normalize_share,
)
from ..sizing.sense_check import (
    sense_check as run_sense_check,
)
from .errors import (
    CODE_CONCEPT_NOT_FOUND,
    CODE_EVALUATOR_ERROR,
    CODE_INVALID_INPUT,
    CODE_LIVE_DISABLED,
    ToolError,
)

# The unconditional Q20 label every payload carries, machine-readably.
MODELED_LABEL = (
    "MODELED (Q20): market shares are analyst estimates, so the implied TAM is a "
    "modeled cross-check — never a sourced number, never persisted"
)


def _player_from_row(row: dict[str, Any], live_enabled: bool) -> Player:
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

    ticker = str(row.get("edgar_ticker") or "").strip()
    revenue = row.get("revenue")
    if ticker and revenue is not None:
        raise ToolError(
            f"player {name!r}: provide 'revenue' OR 'edgar_ticker', not both",
            code=CODE_INVALID_INPUT,
        )
    if ticker:
        if not live_enabled:
            raise ToolError(
                f"player {name!r}: resolving 'edgar_ticker' is a live SEC EDGAR call, "
                "which is disabled; set STRATA_MCP_LIVE_CONNECTORS=1 on the server, or "
                "pass a numeric 'revenue' instead (offline).",
                code=CODE_LIVE_DISABLED,
                remediation="set STRATA_MCP_LIVE_CONNECTORS=1 or supply revenue directly",
            )
        try:
            rr = resolve_revenue(ticker)
        except RevenueLookupError as exc:
            raise ToolError(str(exc), code=CODE_INVALID_INPUT, retriable=True) from exc
        return Player(
            name=name,
            revenue=rr.revenue,
            market_share=share,
            revenue_sourced=True,
            # EDGAR revenue is whole-company, never silently an in-market figure.
            revenue_note="filing, total-co",
        )
    if not isinstance(revenue, (int, float)) or isinstance(revenue, bool):
        raise ToolError(
            f"player {name!r}: provide a numeric 'revenue' or an 'edgar_ticker'",
            code=CODE_INVALID_INPUT,
        )
    return Player(name=name, revenue=float(revenue), market_share=share)


def sense_check_tool(
    reg: Registry, *, players: list[dict[str, Any]], concept_slug: str | None = None
) -> dict[str, Any]:
    live_enabled = os.getenv("STRATA_MCP_LIVE_CONNECTORS") == "1"
    parsed = [_player_from_row(dict(row), live_enabled) for row in players]

    sourced_scenarios: tuple[float, ...] | None = None
    if concept_slug:
        if concept_slug not in reg.concepts:
            raise ToolError(
                f"concept {concept_slug!r} not found",
                code=CODE_CONCEPT_NOT_FOUND,
                remediation="search_concepts to find a matching slug",
            )
        try:
            tam = size_concept(reg, concept_slug)
        except EvaluatorError as exc:
            raise ToolError(str(exc), code=CODE_EVALUATOR_ERROR) from exc
        sourced_scenarios = tuple(s.value for s in tam.scenarios)

    try:
        r = run_sense_check(parsed, sourced_scenarios=sourced_scenarios)
    except SenseCheckError as exc:
        raise ToolError(str(exc), code=CODE_INVALID_INPUT) from exc

    caveats = [
        f"{p.name}: EDGAR figure is TOTAL company revenue — confirm it equals "
        f"in-market revenue or use a segment figure"
        for p in parsed
        if p.revenue_note == "filing, total-co"
    ]
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
            }
            for p in r.per_player
        ],
        "warnings": list(r.warnings) + caveats,
        "assumptions": list(r.assumptions),
        "concept": concept_slug,
        "sourced_range": sourced_range,
        "vs_mid_ratio": r.vs_mid_ratio,
        "verdict": r.verdict,
    }
