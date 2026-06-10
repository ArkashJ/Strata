"""Market-share-implied TAM sense-check (the comparable-revenue cross-check).

Given the top players in a market — each with a revenue and an estimated market
share — derive an implied TAM and (optionally) cross-check it against a sourced
bottoms-up TAM. This is the ``COMPARABLE_REVENUE`` method run as an analyst
sense-check rather than a curated framework:

    implied_tam   = Σ player_revenue / Σ player_market_share     (the headline)
    revenue_floor = Σ player_revenue            (a TAM can't be below the revenue
                                                 already booked inside it)
    per-player    = revenue_i / share_i         (each should agree; a wide spread
                                                 means the share estimates are
                                                 internally inconsistent)
    residual      = implied_tam - revenue_floor (revenue the estimate attributes
                                                 to everyone outside the named set)

It is built to be **defensible**, which means it surfaces its own uncertainty and
assumptions instead of emitting one confident number (see
``docs/methods/sense-check-defensibility.md``):

* a **sensitivity band** — recompute the implied TAM with shares ±``share_tolerance``
  so the output is a range, the way a TAM expert would sanity-check it;
* a **leverage factor** (``1 / Σshare``) — a small combined share multiplies every
  error, so the check warns when the estimate is fragile;
* the load-bearing **assumptions** the caller renders, so the reasoning is explicit.

**Honesty (Q20).** Market shares are analyst *estimates*, so the implied TAM is a
MODELED cross-check — never written back as a sourced primitive. It exists to
agree or disagree with the sourced number, surfacing a spread the same way the
evaluator's ``convergence`` does for two genuinely sourced method families.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

# Default agreement band: estimates within this multiple of each other "agree";
# beyond it, the check flags a disagreement (the whole point of a sense-check).
DEFAULT_AGREE_BAND = 2.0
# Default relative tolerance applied to shares for the sensitivity band.
DEFAULT_SHARE_TOLERANCE = 0.25
# Combined share below this makes the 1/Σshare multiplier large → fragile estimate.
LEVERAGE_WARN_SHARE = 0.25

# The load-bearing assumptions the implied TAM rests on. Rendered with every
# result so a reviewer sees exactly what must hold — these are the conditions a
# TAM expert checks first, made explicit rather than buried.
ASSUMPTIONS: tuple[str, ...] = (
    "each revenue is the player's revenue IN THIS MARKET (not total company revenue)",
    "market shares are revenue shares OF THIS SAME MARKET (not seats / logos / mindshare)",
    "all revenues share one currency, period (e.g. TTM), and geography as the market",
    "the market is revenue-defined today (not a pre-revenue / latent market)",
    "the named players don't double-count each other's revenue (no channel pass-through)",
)


class SenseCheckError(ValueError):
    """Bad sense-check input (no players, non-positive revenue, share out of range,
    or an unparseable ``--player`` / money / share token)."""


@dataclass(frozen=True, slots=True)
class Player:
    name: str
    revenue: float  # currency/year, in the market's unit
    market_share: float  # fraction in (0, 1]
    revenue_sourced: bool = False  # True only if revenue is a sourced filing (EDGAR/regulator)


@dataclass(frozen=True, slots=True)
class PlayerImplied:
    name: str
    revenue: float
    market_share: float
    implied_tam: float  # revenue / market_share
    revenue_sourced: bool = False


@dataclass(frozen=True, slots=True)
class SenseCheckResult:
    implied_tam: float  # combined Σrevenue / Σshare
    implied_low: float  # at shares scaled up by share_tolerance (more share → less TAM)
    implied_high: float  # at shares scaled down by share_tolerance (less share → more TAM)
    share_tolerance: float
    revenue_floor: float  # Σrevenue
    combined_share: float  # Σshare
    leverage: float  # 1 / Σshare — how much the estimate multiplies the captured revenue
    residual: float  # implied_tam - revenue_floor (revenue attributed outside the named set)
    per_player: tuple[PlayerImplied, ...]
    spread_ratio: float  # max per-player implied / min (1.0 == perfect agreement)
    n_players: int
    n_sourced: int  # how many revenues are sourced filings
    all_revenue_sourced: bool
    warnings: tuple[str, ...] = ()
    # Cross-check against a curated concept's sourced scenario range (when given).
    sourced_low: float | None = None
    sourced_high: float | None = None
    sourced_mid: float | None = None
    vs_mid_ratio: float | None = None  # implied_tam / sourced_mid
    verdict: str | None = None  # within | above | below | None (no sourced market)
    assumptions: tuple[str, ...] = field(default=ASSUMPTIONS)


def normalize_share(raw: float) -> float:
    """Accept a share as a fraction (``0.15``) or a percent (``15``). A value > 1
    is read as a percent, so ``15`` → ``0.15``. (A genuine share never exceeds 1,
    so this is unambiguous in practice.)"""
    return raw / 100.0 if raw > 1.0 else raw


def parse_money(raw: str) -> float:
    """Parse a money token: ``31e9`` / ``31000000000`` / ``3.1b`` / ``950m`` /
    ``$1.2B`` / ``12,000``. Suffixes k/m/b/t scale by 1e3/1e6/1e9/1e12."""
    s = raw.strip().lower().replace("$", "").replace(",", "").replace("_", "")
    if not s:
        raise SenseCheckError(f"empty money token: {raw!r}")
    mult = 1.0
    suffixes = {"t": 1e12, "b": 1e9, "m": 1e6, "k": 1e3}
    if s[-1] in suffixes:
        mult = suffixes[s[-1]]
        s = s[:-1]
    try:
        return float(s) * mult
    except ValueError as exc:
        raise SenseCheckError(f"could not parse money value {raw!r}") from exc


def parse_player(spec: str) -> Player:
    """Parse a CLI ``--player`` spec ``'Name|revenue|share'`` (optional 4th field
    ``sourced`` flags a revenue that comes from a filing). Revenue uses
    :func:`parse_money`; share uses :func:`normalize_share`."""
    parts = [p.strip() for p in spec.split("|")]
    if len(parts) not in (3, 4):
        raise SenseCheckError(f"--player must be 'Name|revenue|share[|sourced]', got {spec!r}")
    name, rev_s, share_s = parts[0], parts[1], parts[2]
    if not name:
        raise SenseCheckError(f"player name is empty in {spec!r}")
    try:
        share = normalize_share(float(share_s))
    except ValueError as exc:
        raise SenseCheckError(f"could not parse share {share_s!r} in {spec!r}") from exc
    sourced = len(parts) == 4 and parts[3].lower() in ("sourced", "filing", "true", "1", "yes")
    return Player(
        name=name, revenue=parse_money(rev_s), market_share=share, revenue_sourced=sourced
    )


def sense_check(
    players: list[Player],
    *,
    sourced_scenarios: tuple[float, ...] | None = None,
    agree_band: float = DEFAULT_AGREE_BAND,
    share_tolerance: float = DEFAULT_SHARE_TOLERANCE,
) -> SenseCheckResult:
    """Compute the market-share-implied TAM, its sensitivity band, and (optionally)
    compare it to a curated concept's sourced scenario values. Pure and
    deterministic — no I/O, no LLM, no persistence."""
    if not players:
        raise SenseCheckError("no players provided — add at least one (name, revenue, share)")
    if not 0 <= share_tolerance < 1:
        raise SenseCheckError(f"share_tolerance must be in [0, 1) (got {share_tolerance})")

    for p in players:
        if p.revenue <= 0:
            raise SenseCheckError(f"{p.name}: revenue must be > 0 (got {p.revenue})")
        if not 0 < p.market_share <= 1:
            raise SenseCheckError(
                f"{p.name}: market_share must be in (0, 1] (got {p.market_share})"
            )

    warnings: list[str] = []
    total_rev = sum(p.revenue for p in players)
    total_share = sum(p.market_share for p in players)
    if total_share > 1.0:
        warnings.append(
            f"combined market share is {total_share:.0%} (> 100%) — the shares overlap "
            f"or are overstated; treat the implied TAM as a floor"
        )

    implied = total_rev / total_share
    leverage = 1.0 / total_share
    # Sensitivity band: a share that is x% too low/high moves the TAM the other way.
    # Cap the upper share at 1.0 (a combined share can't exceed 100%).
    share_hi = min(total_share * (1.0 + share_tolerance), 1.0)
    share_lo = total_share * (1.0 - share_tolerance)
    implied_low = total_rev / share_hi
    implied_high = total_rev / share_lo if share_lo > 0 else float("inf")
    residual = implied - total_rev

    if total_share < LEVERAGE_WARN_SHARE:
        warnings.append(
            f"combined share is only {total_share:.0%}, so the implied TAM is {leverage:.0f}x the "
            f"captured revenue — it is highly leveraged on the share estimate; widen the player set"
        )

    per = tuple(
        PlayerImplied(
            p.name, p.revenue, p.market_share, p.revenue / p.market_share, p.revenue_sourced
        )
        for p in players
    )
    implied_vals = [pi.implied_tam for pi in per]
    spread = max(implied_vals) / min(implied_vals)
    if spread > agree_band:
        warnings.append(
            f"per-player implied TAMs disagree {spread:.1f}x — the share estimates are "
            f"internally inconsistent (each revenue/share should imply the same TAM)"
        )

    n_sourced = sum(1 for p in players if p.revenue_sourced)
    all_sourced = n_sourced == len(players)
    if not all_sourced:
        warnings.append(
            f"{len(players) - n_sourced}/{len(players)} revenues are estimates, not sourced "
            f"filings — the implied TAM is MODELED, a cross-check only, never a sourced number (Q20)"
        )

    sourced_low = sourced_high = sourced_mid = vs_mid = None
    verdict: str | None = None
    if sourced_scenarios:
        sourced_low = min(sourced_scenarios)
        sourced_high = max(sourced_scenarios)
        sourced_mid = statistics.median(sourced_scenarios)
        if sourced_mid > 0:
            vs_mid = implied / sourced_mid
        if implied < sourced_low:
            verdict = "below"
        elif implied > sourced_high:
            verdict = "above"
        else:
            verdict = "within"

    return SenseCheckResult(
        implied_tam=implied,
        implied_low=implied_low,
        implied_high=implied_high,
        share_tolerance=share_tolerance,
        revenue_floor=total_rev,
        combined_share=total_share,
        leverage=leverage,
        residual=residual,
        per_player=per,
        spread_ratio=spread,
        n_players=len(players),
        n_sourced=n_sourced,
        all_revenue_sourced=all_sourced,
        warnings=tuple(warnings),
        sourced_low=sourced_low,
        sourced_high=sourced_high,
        sourced_mid=sourced_mid,
        vs_mid_ratio=vs_mid,
        verdict=verdict,
    )
