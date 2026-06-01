# Honest sourced-gap upgrade — 0xPass & 3Blocks (2026-05-31)

## Problem

Two of the five `unsizable` demo companies carry **wrong** reasons that conflate
Q20's quarantine with un-sizability:

- **0xPass** — "token & prediction-market pricing is quarantined (Q20)". But
  wallet-*infra* spend is not a token price; the quarantine never bound here.
- **3Blocks** — "onchain-tier signals are read-only and never feed a framework".
  But onchain-tier *values are framework-legal* (`registry.py:64-76` quarantines
  only `prediction_market`, not `onchain`). The analytics *SaaS* market is not an
  onchain signal value.

The reasons should state the **true** gap, backed by real seeded numbers.

## Sourcing reality (web search, 2026-05-31)

| Leg | 0xPass | 3Blocks | Pinnable? |
|---|---|---|---|
| demand-side **count** | web3 devs 23,613 (Electric Capital '24) | same | ✅ aggregator, corroborated CoinDesk/Blockworks |
| **spend / price** per unit | none | none | ❌ no primary source |
| adoption / capture | none | none | ❌ no primary source |
| ready-made "market size" | $2B WaaS | $3.4B analytics | ⛔ analyst-tier → cite-only (Q26), forbidden as TAM output |

**Conclusion:** the count side is sourceable; the value side is not. A bottoms-up
framework would need 3-of-4 inputs invented → that is the fabrication the Q20 wall
exists to refuse. **No framework, no TAM.**

### Price hunt (Dune MCP) — recorded outcome

Attempted to source an on-chain *value* leg (ERC-4337 account-abstraction UserOps
volume + paymaster gas spend) to replace the modeled multiplier. Blocked in this
environment: the MCP key is read-only (cannot author a query) and the reputable
public query (`theblockcrypto` #2479120) times out on the free tier. **More
fundamentally**, on-chain data yields *volume* (UserOps / gas), not
*spend-per-customer / take-rate* — so even a successful run would not close the
gap to a defensible TAM. Recorded as a proven gap, not a fabrication. A future
L4 platform_throughput floor remains a candidate **iff** a take-rate source appears.

## What ships

1. **New primitive** `data/primitives/web3-monthly-active-developers-2024.yaml`
   — value 23613, `stock/people`, global, `source.tier: aggregator`, Electric
   Capital Developer Report 2024, snapshot hash over the verbatim claim.
2. **New concepts** (declared lens, real measurement, **no framework** → honest
   unsizable):
   - `data/concepts/web3-wallet-infrastructure.yaml` (lens `revenue_generation`)
   - `data/concepts/onchain-analytics-software.yaml` (lens `cost_efficiency`)
   Both list the dev-count primitive in `measurements`.
3. **Reason rewrite + link** in `portfolios/portfolio_demo_subset.yaml`: replace
   the two wrong reasons with precise sourced-gap text; add `market:` so each card
   links to its concept (navigable honesty).
4. **`scripts/presize_demo.py`**: pass `market_concept_slug` for `unsizable` rows
   too, so the baked JSON carries the concept link while keeping the curated reason.
5. Re-run `presize_demo.py` → `portfolio_demo.json` (still 20 sized · 5 unsizable).

## Won't do

No framework, no TAM, no `community-modeled` multiplier dressed as sourced, no
reproduction of the analyst $2B / $3.4B market reports.

## Verification

`uv run pytest && uv run pyright && uv run ruff check . && uv run ruff format --check .`
(new YAML must validate clean via the auto-glob loader) + confirm `portfolio_demo.json`
shows the two upgraded reasons and the concept links.
