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
# Combined share ≤ 25% makes the 1/Σshare multiplier large → fragile estimate
# (the threshold docs/methods/sense-check-defensibility.md states; keep in sync).
LEVERAGE_WARN_SHARE = 0.25

# Tokens an optional 4th --player field / CSV `sourced` column may use to flag
# a filing-backed revenue — one list shared by every parsing surface.
SOURCED_TOKENS = ("sourced", "filing", "true", "1", "yes")

# The unconditional Q20 label every surface renders/ships, machine-readably:
# shares are ALWAYS analyst estimates, so the implied TAM stays modeled even
# when every revenue is a sourced filing.
MODELED_LABEL = (
    "MODELED (Q20): market shares are analyst estimates, so the implied TAM is a "
    "modeled cross-check — never a sourced number, never persisted"
)

# Typed marker for an EDGAR-resolved revenue: a whole-company filing figure,
# not an in-market one. Lives here (not revenue_lookup) so the engine can emit
# the caveat without importing the lookup module (which imports Player from us).
REVENUE_NOTE_FILING_TOTAL_CO = "filing, total-co"
# The caveat sentence, stated ONCE — sense_check() emits it as a per-player
# warning whenever the marker is set, so every surface renders it uniformly.
EDGAR_TOTAL_CO_CAVEAT = (
    "EDGAR figure is TOTAL company revenue — confirm it equals in-market revenue "
    "or use a segment figure"
)

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
    # Display tag for the revenue's basis, e.g. "filing, total-co" for an EDGAR
    # figure (whole-company revenue, not in-market) — rendered next to the line
    # so a sourced-but-total figure is never an unmarked sourced line.
    revenue_note: str = ""


@dataclass(frozen=True, slots=True)
class PlayerImplied:
    name: str
    revenue: float
    market_share: float
    implied_tam: float  # revenue / market_share
    revenue_sourced: bool = False
    revenue_note: str = ""


@dataclass(frozen=True, slots=True)
class SenseCheckResult:
    implied_tam: float  # combined Σrevenue / Σshare
    # Band/leverage/residual are None when Σshare ≥ 100%: a band derived from
    # overlapping shares would exclude its own point estimate, leverage < 1 is
    # meaningless, and the residual goes negative — suppressed, never emitted.
    implied_low: float | None  # at shares scaled up by share_tolerance (more share → less TAM)
    implied_high: float | None  # at shares scaled down by share_tolerance (less share → more TAM)
    share_tolerance: float
    revenue_floor: float  # Σrevenue
    combined_share: float  # Σshare
    leverage: float | None  # 1 / Σshare — how much the estimate multiplies the captured revenue
    residual: float | None  # implied_tam - revenue_floor (revenue attributed outside the set)
    per_player: tuple[PlayerImplied, ...]
    spread_ratio: float  # max per-player implied / min (1.0 == perfect agreement)
    n_sourced: int  # how many revenues are sourced filings
    warnings: tuple[str, ...] = ()
    # Cross-check against a curated concept's sourced scenario range (when given).
    sourced_low: float | None = None
    sourced_high: float | None = None
    sourced_mid: float | None = None
    vs_mid_ratio: float | None = None  # implied_tam / sourced_mid
    verdict: str | None = None  # within | above | below | None (no sourced market)
    assumptions: tuple[str, ...] = field(default=ASSUMPTIONS)

    # Derivable state stays derived — per_player is the single source of truth.
    @property
    def n_players(self) -> int:
        return len(self.per_player)

    @property
    def all_revenue_sourced(self) -> bool:
        return self.n_sourced == self.n_players


def normalize_share(raw: float) -> float:
    """Accept a share as a fraction (``0.15``) or a percent (``15``). A value > 1
    is read as a percent, so ``15`` → ``0.15``. (A genuine share never exceeds 1,
    so this is unambiguous in practice.)"""
    return raw / 100.0 if raw > 1.0 else raw


def share_token_warning(token: str, share: float) -> str | None:
    """The ``1`` trap: a bare integer token parses to a 100% share (fractions ≤ 1
    pass through :func:`normalize_share`), but a user may have meant 1%. Warn when
    a token without a decimal point or percent sign lands on exactly 100%."""
    t = token.strip()
    if share == 1.0 and "." not in t and "%" not in t:
        return (
            f"share token {token!r} parsed as 100% — if you meant 1%, "
            f"write '0.01' or '1.0' for an unambiguous fraction"
        )
    return None


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


def split_player_spec(spec: str) -> list[str]:
    """Split a ``--player`` spec into its fields. The field-count and empty-name
    guards live HERE only, so every spec branch (plain / edgar) fails the same way."""
    parts = [p.strip() for p in spec.split("|")]
    if len(parts) not in (3, 4):
        raise SenseCheckError(f"--player must be 'Name|revenue|share[|sourced]', got {spec!r}")
    if not parts[0]:
        raise SenseCheckError(f"player name is empty in {spec!r}")
    return parts


def parse_player(spec: str) -> Player:
    """Parse a CLI ``--player`` spec ``'Name|revenue|share'`` (optional 4th field
    ``sourced`` flags a revenue that comes from a filing). Revenue uses
    :func:`parse_money`; share uses :func:`normalize_share`."""
    parts = split_player_spec(spec)
    share_s = parts[2]
    try:
        share = normalize_share(float(share_s))
    except ValueError as exc:
        raise SenseCheckError(f"could not parse share {share_s!r} in {spec!r}") from exc
    sourced = len(parts) == 4 and parts[3].lower() in SOURCED_TOKENS
    return Player(
        name=parts[0], revenue=parse_money(parts[1]), market_share=share, revenue_sourced=sourced
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

    implied = total_rev / total_share
    leverage: float | None
    implied_low: float | None
    implied_high: float | None
    residual: float | None
    if total_share >= 1.0:
        # Σshare ≥ 100%: capping the upper share at 1.0 would put the band's low
        # end ABOVE the point estimate (which itself falls below the revenue
        # floor). A band that excludes its own point estimate is never emitted —
        # only the floor and the overlap warning survive.
        leverage = implied_low = implied_high = residual = None
        if total_share > 1.0:
            warnings.append(
                f"combined market share is {total_share:.0%} (> 100%) — the shares overlap "
                f"or are overstated; only the revenue floor ${total_rev:,.0f} is defensible"
            )
    else:
        leverage = 1.0 / total_share
        # Sensitivity band: a share that is x% too low/high moves the TAM the
        # other way. Cap the upper share at 1.0 (a combined share can't exceed 100%).
        share_hi = min(total_share * (1.0 + share_tolerance), 1.0)
        share_lo = total_share * (1.0 - share_tolerance)
        implied_low = total_rev / share_hi
        implied_high = total_rev / share_lo if share_lo > 0 else float("inf")
        residual = implied - total_rev

    if total_share <= LEVERAGE_WARN_SHARE and leverage is not None:
        warnings.append(
            f"combined share is only {total_share:.0%}, so the implied TAM is {leverage:.0f}x the "
            f"captured revenue — it is highly leveraged on the share estimate; widen the player set"
        )

    per = tuple(
        PlayerImplied(
            p.name,
            p.revenue,
            p.market_share,
            p.revenue / p.market_share,
            p.revenue_sourced,
            p.revenue_note,
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
    # The MODELED label is UNCONDITIONAL: market shares are always analyst
    # estimates, so the implied TAM stays a modeled cross-check even when every
    # revenue is a sourced filing (Q20).
    if all_sourced:
        warnings.append(
            "revenues sourced; shares are analyst estimates — the implied TAM remains "
            "MODELED (Q20), a cross-check only, never a sourced number"
        )
    else:
        warnings.append(
            f"{len(players) - n_sourced}/{len(players)} revenues are estimates, not sourced "
            f"filings — the implied TAM is MODELED, a cross-check only, never a sourced number (Q20)"
        )
    # The engine owns the total-company caveat so every surface (CLI, MCP)
    # renders it the same way instead of re-deriving it from the note string.
    warnings.extend(
        f"{p.name}: {EDGAR_TOTAL_CO_CAVEAT}"
        for p in players
        if p.revenue_note == REVENUE_NOTE_FILING_TOTAL_CO
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
        n_sourced=n_sourced,
        warnings=tuple(warnings),
        sourced_low=sourced_low,
        sourced_high=sourced_high,
        sourced_mid=sourced_mid,
        vs_mid_ratio=vs_mid,
        verdict=verdict,
    )
