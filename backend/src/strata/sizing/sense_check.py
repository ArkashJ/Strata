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

import re
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

# Time-match guardrail: a revenue and a share dated more than this many months
# apart get a per-player warning — pairing a current revenue with a stale share
# inflates/deflates the implied TAM (validated in practice: Cursor's Feb-2026
# ARR over its mid-2025 share inflated the implied market ~2x).
TIME_MATCH_WARN_MONTHS = 6
# The only declarable share bases. 'usage' triggers a strong warning: dividing
# revenue by a seat/usage share understates the implied market (a high-priced
# player's revenue share exceeds its seat share, and vice versa).
SHARE_BASIS_VALUES = ("revenue", "usage")
# Conditional assumptions-block lines — softer than warnings, still explicit.
NOTE_UNDATED = "revenue and share assumed time-matched — un-dated inputs"
NOTE_BASIS_UNSPECIFIED = "shares assumed to be revenue shares"

# An as-of token: 'YYYY', 'YYYY-MM', or 'YYYY-MM-DD' (ISO order so strings sort).
_AS_OF_RE = re.compile(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$")

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
    # When the revenue / the share estimate were measured ('YYYY[-MM[-DD]]').
    # Optional: absent dates only soften the output (assumptions note), present
    # dates that disagree past TIME_MATCH_WARN_MONTHS warn — never auto-corrected.
    revenue_as_of: str = ""
    share_as_of: str = ""
    # 'revenue' | 'usage' | '' (unspecified). 'usage' warns: the method's
    # denominator must be a revenue share, never seats/usage.
    share_basis: str = ""


@dataclass(frozen=True, slots=True)
class PlayerImplied:
    name: str
    revenue: float
    market_share: float
    implied_tam: float  # revenue / market_share
    revenue_sourced: bool = False
    revenue_note: str = ""
    revenue_as_of: str = ""
    share_as_of: str = ""
    share_basis: str = ""


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


def parse_as_of(raw: str) -> str:
    """Validate an as-of token: ``'2026'``, ``'2026-02'``, or ``'2026-02-15'``.
    Returns the token unchanged (ISO order already sorts/compares correctly)."""
    s = raw.strip()
    m = _AS_OF_RE.match(s)
    if not m or (m.group(2) and not 1 <= int(m.group(2)) <= 12):
        raise SenseCheckError(
            f"could not parse as-of date {raw!r} (use YYYY, YYYY-MM, or YYYY-MM-DD)"
        )
    return s


def _as_of_month_index(value: str) -> int:
    """A validated as-of token as a month count. A bare year is honest about its
    imprecision — anchor it mid-year (June) so the comparison stays unbiased."""
    m = _AS_OF_RE.match(value)
    assert m is not None  # callers validate via parse_as_of / sense_check
    return int(m.group(1)) * 12 + (int(m.group(2)) if m.group(2) else 6)


def parse_share_basis(raw: str) -> str:
    """Validate a share-basis token: ``'revenue'``, ``'usage'``, or empty
    (unspecified). Anything else is rejected — never silently coerced."""
    s = raw.strip().lower()
    if s and s not in SHARE_BASIS_VALUES:
        raise SenseCheckError(f"share_basis must be one of {SHARE_BASIS_VALUES} (got {raw!r})")
    return s


@dataclass(frozen=True, slots=True)
class PlayerSpec:
    """A parsed ``--player`` mini-DSL spec, before money/share token parsing
    (the edgar: branch needs the raw revenue token)."""

    name: str
    revenue_token: str
    share_token: str
    sourced: bool = False
    revenue_as_of: str = ""
    share_as_of: str = ""
    share_basis: str = ""


# The optional key=value suffix keys the --player DSL accepts (after the three
# positional fields and the optional 'sourced' flag).
_SPEC_KEYS = ("rev_date", "share_date", "share_basis")
_SPEC_SHAPE = "'Name|revenue|share[|sourced][|key=value ...]'"


def split_player_spec(spec: str) -> PlayerSpec:
    """Split a ``--player`` spec into its fields. The field-count and empty-name
    guards live HERE only, so every spec branch (plain / edgar) fails the same way.

    Backward-compatible shape: three positional fields, an optional ``sourced``
    flag, then optional ``key=value`` suffix tokens (``rev_date`` / ``share_date``
    / ``share_basis``) — a token with no ``=`` is only ever the sourced flag."""
    parts = [p.strip() for p in spec.split("|")]
    if len(parts) < 3:
        raise SenseCheckError(f"--player must be {_SPEC_SHAPE}, got {spec!r}")
    if not parts[0]:
        raise SenseCheckError(f"player name is empty in {spec!r}")
    sourced = False
    kv: dict[str, str] = {}
    for i, token in enumerate(parts[3:]):
        key, eq, value = token.partition("=")
        if eq:
            key = key.strip().lower()
            if key not in _SPEC_KEYS:
                raise SenseCheckError(
                    f"unknown key {key!r} in {spec!r} (expected one of {_SPEC_KEYS})"
                )
            if key in kv:
                raise SenseCheckError(f"duplicate key {key!r} in {spec!r}")
            kv[key] = value.strip()
        elif i == 0 and token.lower() in SOURCED_TOKENS:
            sourced = True
        else:
            raise SenseCheckError(f"--player must be {_SPEC_SHAPE}, got {spec!r}")
    return PlayerSpec(
        name=parts[0],
        revenue_token=parts[1],
        share_token=parts[2],
        sourced=sourced,
        revenue_as_of=parse_as_of(kv["rev_date"]) if kv.get("rev_date") else "",
        share_as_of=parse_as_of(kv["share_date"]) if kv.get("share_date") else "",
        share_basis=parse_share_basis(kv.get("share_basis", "")),
    )


def parse_player(spec: str) -> Player:
    """Parse a CLI ``--player`` spec ``'Name|revenue|share'`` (optional 4th field
    ``sourced`` flags a revenue that comes from a filing; optional ``key=value``
    suffixes set ``rev_date`` / ``share_date`` / ``share_basis``). Revenue uses
    :func:`parse_money`; share uses :func:`normalize_share`."""
    ps = split_player_spec(spec)
    try:
        share = normalize_share(float(ps.share_token))
    except ValueError as exc:
        raise SenseCheckError(f"could not parse share {ps.share_token!r} in {spec!r}") from exc
    return Player(
        name=ps.name,
        revenue=parse_money(ps.revenue_token),
        market_share=share,
        revenue_sourced=ps.sourced,
        revenue_as_of=ps.revenue_as_of,
        share_as_of=ps.share_as_of,
        share_basis=ps.share_basis,
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
        # Players can be constructed directly (MCP rows, library callers), so
        # the as-of / basis tokens are re-validated here, not just at the DSL.
        if p.revenue_as_of:
            parse_as_of(p.revenue_as_of)
        if p.share_as_of:
            parse_as_of(p.share_as_of)
        parse_share_basis(p.share_basis)

    warnings: list[str] = []
    for p in players:
        # Time-match guardrail: warn, never auto-correct — the analyst owns the
        # inputs; the tool's job is to make the mismatch impossible to miss.
        if p.revenue_as_of and p.share_as_of:
            delta = abs(_as_of_month_index(p.revenue_as_of) - _as_of_month_index(p.share_as_of))
            if delta > TIME_MATCH_WARN_MONTHS:
                warnings.append(
                    f"{p.name}: revenue is as of {p.revenue_as_of} but the share is as of "
                    f"{p.share_as_of} (~{delta} months apart) — pairing a current revenue "
                    f"with a stale share inflates/deflates the implied TAM; time-match the inputs"
                )
        if p.share_basis == "usage":
            warnings.append(
                f"{p.name}: share_basis is 'usage' — the denominator must be a REVENUE "
                f"share; usage/seat share understates the implied market"
            )
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
            p.revenue_as_of,
            p.share_as_of,
            p.share_basis,
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

    # Conditional assumptions: softer than warnings — un-dated or basis-less
    # inputs are not errors, but what the implied TAM silently assumes about
    # them must be on the record.
    assumptions = list(ASSUMPTIONS)
    if any(not (p.revenue_as_of and p.share_as_of) for p in players):
        assumptions.append(NOTE_UNDATED)
    if any(not p.share_basis for p in players):
        assumptions.append(NOTE_BASIS_UNSPECIFIED)

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
        assumptions=tuple(assumptions),
    )
