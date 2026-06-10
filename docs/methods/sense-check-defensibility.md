# Sense-check defensibility — surviving the 10 arguments

The market-share-implied TAM (`strata sense-check`) is a **cross-check**, not a
primary sourced number. This memo is the adversarial review: the ten arguments a
TAM expert raises against the market-share method, and exactly how the tool
answers each — by code, by a surfaced warning, by an explicit assumption, or by
an honest stated limitation. Nothing is hidden; the implied TAM only claims to be
valid if the assumptions hold, and it shows its own uncertainty.

The method:

    implied TAM = Σ(player revenue) / Σ(player market share)
    revenue floor = Σ(player revenue)        # a TAM can't be below this
    per-player    = revenueᵢ / shareᵢ        # must all agree
    residual      = implied − floor          # revenue attributed to everyone else
    leverage      = 1 / Σshare               # error multiplier
    band          = implied at shares ±25%   # the estimate is a range, not a point

---

## The 10 arguments

| # | Expert argument | How the check answers it |
|---|---|---|
| 1 | **"Reported revenue isn't in-market revenue"** — a vendor's total revenue spans adjacent products. | Assumption #1 is stated on every run ("each revenue is the player's revenue IN THIS MARKET"). The tool can't detect this, so it makes the requirement explicit and tags every non-filing revenue `(est.)`. An `edgar:` revenue is tagged `(filing, total-co)` and resolution prints an inline caveat ("EDGAR figure is TOTAL company revenue — confirm it equals in-market revenue or use a segment figure") — a sourced total never passes as an unmarked in-market figure. |
| 2 | **"Share of *what*?"** — revenue share ≠ unit/seat/logo/mindshare. | Assumption #2 ("market shares are revenue shares OF THIS SAME MARKET"). The math is only coherent for revenue shares; the assumption names it so a seats-share input is caught by the reviewer, not silently divided. |
| 3 | **"A small combined share explodes the error."** | The `leverage = 1/Σshare` factor is printed, and a **warning fires when combined share ≤ 25%** (matching `LEVERAGE_WARN_SHARE` with `<=` in code: "the implied TAM is Nx the captured revenue … widen the player set"). The **sensitivity band** (shares ±25%) shows how far the answer moves. |
| 4 | **"Your shares overlap / sum past 100%."** | Detected and warned ("combined market share is N% (> 100%) … only the revenue floor is defensible"). When Σshare ≥ 100% the band, leverage, and residual are **suppressed entirely** — a band derived from overlapping shares would exclude its own point estimate, so only the revenue floor and the warning are emitted. Never rendered as if clean. |
| 5 | **"Your share estimates are internally inconsistent."** | The **per-player spread** (`max(revᵢ/shareᵢ) / min(...)`) is computed; a spread beyond 2× warns. If every player implies a different TAM, the reviewer sees it immediately. |
| 6 | **"Currencies don't match."** | Assumption #3 ("one currency"). The tool is unit-agnostic by design; the assumption is load-bearing and shown. |
| 7 | **"Periods don't match"** — TTM vs FY, mixed years. | Assumption #3 ("one period, e.g. TTM"). Same treatment: explicit, not silent. |
| 8 | **"Geography mismatch"** — global revenue against a US market. | Assumption #3 ("same geography as the market"). This ties to Strata's first-class `MarketScope` (geo_supply/geo_demand); a future increment can bind the players' geo to the concept's declared scope and auto-flag a mismatch. |
| 9 | **"Private-company revenue is itself a guess — this is circular."** | Each revenue carries a `revenue_sourced` flag; the output shows `n/N revenues sourced` and tags estimates `(est.)`. The **MODELED label is unconditional**: market shares are always analyst estimates, so the implied TAM is labelled **MODELED (Q20)** even when every revenue is a sourced filing, and is **never persisted as a sourced primitive** — it can only agree or disagree with the sourced number, never become one. |
| 10 | **"This market isn't revenue-defined yet"** — pre-revenue / latent demand. | Assumption #4 ("the market is revenue-defined today, not pre-revenue / latent"). For a `latent_demand` market the method is the wrong tool, and the assumption says so — the reviewer uses the adoption-curve lens instead. |

## Two more failure modes — validated in practice (AI coding tools)

Both surfaced when the method was applied for real to the AI-coding-tools market
(prod MCP feedback, feedback event #6). Both are **warnings, never silent
corrections** — the tool stays honest, not clever.

| # | Failure mode | How the check answers it |
|---|---|---|
| 11 | **"Your revenue and your share aren't from the same moment."** Dividing Cursor's Feb-2026 $2B ARR by its mid-2025 ~18% share inflates the implied market roughly 2× — the share was measured before the revenue grew into it. | Optional `revenue_as_of` / `share_as_of` dates (`YYYY[-MM[-DD]]`) on every player, via the `--player` DSL (`rev_date=2026-02\|share_date=2025-06`), the CSV columns, and the MCP row schema. When both dates are present and more than ~6 months apart (`TIME_MATCH_WARN_MONTHS`), a per-player warning fires ("pairing a current revenue with a stale share inflates/deflates the implied TAM; time-match the inputs"). When dates are absent, the assumptions block adds the softer line "revenue and share assumed time-matched — un-dated inputs". An `edgar:` revenue threads its filing's own fiscal-period end into `revenue_as_of` automatically — and rejects a conflicting caller-supplied date rather than silently overriding either. A bare year anchors to mid-year (June), staying honest about its own imprecision. |
| 12 | **"That's a seat share, not a revenue share."** GitHub Copilot's ~42% share of AI-coding *seats* is far above its revenue share; dividing market revenue by a usage/seat share understates the implied market. | Optional `share_basis` per player: `revenue` \| `usage` \| unspecified (DSL `share_basis=usage`, CSV column, MCP enum). `usage` fires a strong per-player warning ("denominator must be a REVENUE share — usage/seat share understates the implied market"); unspecified adds the assumptions line "shares assumed to be revenue shares". Any other token is rejected, never coerced. |

These sharpen arguments #2 and #7 above from stated assumptions into checkable,
per-player guardrails — when the analyst supplies the metadata, the tool checks
it; when they don't, the output says exactly what was assumed.

### Bonus: "comparing to one number hides the real spread"
When `--concept` is given, the implied TAM is compared to the curated market's
**full sourced scenario range** (`within / above / below`), not a single point —
honoring Strata's rule that TAMs are scenario trees, never scalars. The verdict
also reports the ratio to the sourced midpoint.

---

## What "defensible" means here

1. **Every number shows its derivation** — revenue floor, per-player implied,
   residual, leverage, and the ±25% band are all printed; nothing is a black box.
2. **The estimate is a range, not a point** — the band is the headline a careful
   reviewer trusts.
3. **The assumptions are printed every run** — the five conditions above are the
   reasoning a TAM expert audits first; they are explicit, not implied.
4. **It fails honest** — overlap, inconsistency, fragility, and modeled inputs all
   produce warnings; a miss is never dressed up as a sourced fact (Q20).

## Known limitations (stated, not hidden)
- Cannot verify that a revenue is in-market, same-currency, same-period, or
  same-geography — it asserts the assumption and tags estimates; the analyst owns
  the inputs.
- `MarketScope`-aware geo/period binding (argument 8) is a future increment.
- `edgar:TICKER` pulls a sourced annual revenue from SEC EDGAR (US-listed filers
  only), selected by the fact's own period end — but it is TOTAL company revenue,
  tagged `(filing, total-co)` with an inline caveat; segment figures stay manual.
