# Connector Layer — Handoff & Next Steps

## Current State (2026-05-25)

### What Exists

```
backend/src/strata/connectors/
├── __init__.py        — re-exports all connector types
├── bls.py             — BLS Public Data API v2 (24.8K, 7 endpoints)
├── fred.py            — Federal Reserve Economic Data (24.4K, 6 endpoints)
├── census.py          — US Census Bureau SUSB (25.8K, firm + industry data)
├── edgar.py           — SEC EDGAR filings (28K, company financials)
├── worldbank.py       — World Bank Open Data (21K, global indicators)
├── kalshi.py          — Kalshi prediction markets (35.4K, 5 endpoints + auth)
├── CLAUDE.md          — connector layer conventions + patterns
├── KALSHI_REFERENCE.md — curl commands, TAM tickers, ingest workflow
└── DUNE_REFERENCE.md  — SQL queries, table catalog, blocked by plan tier
```

### Data Bank

```
data/primitives/    308 files (202 from Kalshi, rest from BLS/FRED/Census/EDGAR/WB)
data/sources/        89 files
data/concepts/        6 files
data/frameworks/      5 files
```

### Keys Available (in .env + shell)

| Service | Key Location | Status |
|---------|-------------|--------|
| BLS | `STRATA_BLS_API_KEY` | Working |
| FRED | `STRATA_FRED_API_KEY` | Working |
| Census | `STRATA_CENSUS_API_KEY` | Working |
| EDGAR | No key needed (public) | Working |
| World Bank | No key needed (public) | Working |
| Kalshi | `STRATA_KALSHI_API_KEY` + `~/.kalshi/private_key.pem` | Working |
| Dune | `DUNE_API_KEY` in .env | MCP works, execution blocked by community plan |

### Tests

167 passing. All connectors have typed models validated by pyright strict. Every primitive
in the data bank passes the Pydantic schema loader (AtomicPrimitive model).

---

## The Pattern (How to Build a New Connector)

Every connector follows the same structure. Copy `bls.py` and adapt:

```
1. ENUMS          — API-specific constants (status codes, categories, periods)
2. TYPEDDICTS     — Raw JSON response shapes (for type checking + documentation)
3. DATACLASSES    — Frozen internal models (@dataclass(frozen=True, slots=True))
4. RESPONSE TYPE  — Single return type wrapping status + data + cache metadata
5. PARSERS        — _parse_xxx() functions: raw dict → dataclass
6. DISK CACHE     — _DiskCache class: JSON files under ~/.strata/cache/{name}/
7. CLIENT CLASS   — Context manager, one method per endpoint, auto-pagination
8. CONVERTERS     — Standalone functions: dataclass → Strata YAML dict
```

### Key Conventions

- **Pyright strict + ruff clean** — non-negotiable
- **Frozen dataclasses** — all internal models are immutable
- **Disk cache** — every connector caches raw responses (24h for gov data, 1h for markets)
- **Converters are standalone functions** — not methods, so they compose freely
- **Source slugs** — must match `^[a-z0-9][a-z0-9-]*$` (no dots, underscores, uppercase)
- **snapshot_sha256** — hash the response payload at ingest time, proves provenance
- **No invented figures** — every `value` must trace to an API response
- **Config** — add `{name}_api_key: str | None = None` to `config.py`, prefix `STRATA_`

### Schema Constraints (valid enum values for primitives)

```
unit.kind:       stock | flow | intensive | dimensionless
unit.dimension:  people | currency | transactions | events | percent |
                 tokens | impressions | organizations | seats
source.tier:     first_party | regulator | aggregator | analyst |
                 analyst-paraphrase | community | onchain |
                 prediction_market | community-modeled
```

---

## Next Connectors to Build (Priority Order)

### P0: Dune Analytics (onchain tier)

**Why:** Largest untapped data source. DEX volume, protocol revenue, stablecoin flows,
active wallets — all feed crypto TAM models directly.

**Blocker:** Community plan can't execute queries on Spellbook tables (cross-chain).
Need Plus plan ($350/mo) or use only canonical tables.

**Architecture:**
```
DuneClient
├── create_query(sql) → query_id
├── execute_query(query_id) → execution_id
├── poll_execution(execution_id) → status
├── get_results(execution_id) → rows
├── get_latest_results(query_id) → rows (cached)
└── search_tables(query) → table metadata
```

**Key difference from other connectors:** Dune is query-based, not endpoint-based.
You write SQL, execute it, poll for completion, then fetch results. The client needs
a poll loop with exponential backoff.

**SQL queries ready** (in `DUNE_REFERENCE.md`):
1. Monthly DEX volume all chains
2. Top DEX protocols by volume
3. Stablecoin daily transfer volume
4. Monthly active wallets
5. Protocol revenue via fees

**Primitive mapping:**
- `unit.kind: flow`, `unit.dimension: currency` for USD volumes
- `unit.kind: stock`, `unit.dimension: people` for unique wallets (approximation)
- `source.tier: onchain`

**Estimated effort:** 1 day for client, 1 day for canned queries + converters.

---

### P1: Polymarket (prediction_market tier)

**Why:** Deeper liquidity than Kalshi on crypto/tech topics. Different market structure
(AMM-based vs order book) gives complementary price signals.

**API:** REST at `https://gamma-api.polymarket.com/`
- `GET /markets` — list markets
- `GET /markets/{id}` — single market
- No auth needed for public data (read-only)

**Key difference from Kalshi:** Polymarket prices are 0-1 directly (no dollar conversion).
Markets use CLOB (Central Limit Order Book) now, not AMM. Condition IDs are on-chain.

**Primitive mapping:** Same as Kalshi — probability + volume. But Polymarket has
richer resolution criteria metadata (on-chain settlement).

**Auth:** Public read is unauthenticated. Trading requires wallet signature.

**Estimated effort:** 0.5 day (simpler than Kalshi — no RSA auth, similar response shape).

---

### P1: CoinGecko / CoinMarketCap (onchain tier)

**Why:** Token prices + market caps are inputs to crypto TAM models. "What's the total
crypto market cap?" is a primitive. Token-specific prices feed protocol valuation.

**Endpoints needed:**
- `/coins/markets` — top N tokens by market cap
- `/coins/{id}` — single token detail
- `/global` — total crypto market cap, BTC dominance

**Primitive mapping:**
- Market cap → `unit.kind: stock`, `unit.dimension: currency`
- Volume → `unit.kind: flow`, `unit.dimension: currency`
- `source.tier: aggregator`

**Rate limits:** CoinGecko free tier = 10-30 calls/min. Cache aggressively (1h for prices).

**Estimated effort:** 0.5 day.

---

### P2: Eurostat (regulator tier)

**Why:** EU market sizing needs EU data. Eurostat has employment, GDP, trade stats
for 27 EU countries at NUTS-2 granularity.

**API:** REST at `https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/`
- SDMX format (XML by default, JSON available)
- Hierarchical datasets with dimensions (geo, time, indicator)

**Key challenge:** SDMX is complex — multi-dimensional datasets with codified dimensions.
Need a dimension mapper.

**Primitive mapping:**
- Employment → `unit.kind: stock`, `unit.dimension: people`
- GDP → `unit.kind: flow`, `unit.dimension: currency`
- `source.tier: regulator`
- `geo.level: country` or `subnational` (NUTS codes map to ISO 3166-2)

**Estimated effort:** 1.5 days (SDMX parsing is non-trivial).

---

### P2: Crunchbase / PitchBook (aggregator tier)

**Why:** Company count by segment, funding rounds, headcount — all feed TAM models.
"How many Series A+ AI companies exist?" is a primitive.

**Access:** API keys are expensive ($5k+/yr). Consider scraping alternatives or
using Exa search as a proxy until budget allows.

**Primitive mapping:**
- Company count → `unit.kind: stock`, `unit.dimension: organizations`
- Funding volume → `unit.kind: flow`, `unit.dimension: currency`
- `source.tier: aggregator`

**Estimated effort:** 1 day if API access exists, otherwise defer.

---

### P2: Glassdoor / LinkedIn Economic Graph (aggregator tier)

**Why:** Job postings by category = real-time labor demand signal. "How many open
ML engineer roles?" feeds the developer tools TAM directly.

**Access:** LinkedIn Economic Graph requires partnership. Glassdoor has a limited API.
Alternative: use BLS JOLTS data (already have via BLS connector) + Indeed/Glassdoor
scraped signals.

**Estimated effort:** Defer until API access secured.

---

### P3: Stripe Atlas / Commerce Data (first_party tier)

**Why:** If Stripe ever opens their macro commerce data (aggregate payment volume
by category), it's the single best real-time TAM signal for any commerce-adjacent market.

**Status:** Not publicly available. Monitor Stripe's data partnerships program.

---

## Dune Upgrade Path

### What $350/mo Gets You

- Execute queries on ALL Spellbook tables (cross-chain)
- `dex.trades` — DEX volume across 50+ chains
- `stablecoins_*.transfers` — stablecoin flows
- `nft.trades` — NFT marketplace data
- `lending.borrow` — DeFi lending
- 2500 → 25000 monthly credits

### Implementation Plan (Once Upgraded)

```
1. Build DuneClient following pattern:
   - __init__(api_key, cache_dir, cache_ttl)
   - execute_sql(sql) → ExecutionResult (handles create + poll + fetch)
   - get_cached_results(query_id) → rows (if recent execution exists)
   - _poll_with_backoff(execution_id) → wait for completion

2. Create 5 "canned query" functions:
   - get_monthly_dex_volume(months_back=12) → list[MonthlyVolume]
   - get_protocol_revenue(protocol, months_back=6) → list[Revenue]
   - get_stablecoin_flows(chain, days_back=30) → list[DailyFlow]
   - get_active_wallets(chain, months_back=12) → list[MonthlyWallets]
   - get_tvl_by_protocol(top_n=20) → list[ProtocolTVL]

3. Converters:
   - volume_to_primitive_yaml() — monthly USD volume → flow/currency
   - wallets_to_primitive_yaml() — monthly unique → stock/people
   - revenue_to_primitive_yaml() — protocol fees → flow/currency

4. Ingest script:
   - Run monthly via cron or CLI command
   - Produces ~50 new primitives per run (5 queries × top 10 protocols)
```

---

## Operational Notes

### Cache Locations

```
~/.strata/cache/
├── bls/         — 24h TTL (data changes monthly)
├── fred/        — 24h TTL
├── census/      — 24h TTL
├── edgar/       — 24h TTL
├── worldbank/   — 24h TTL
├── kalshi/      — 1h TTL (market prices change continuously)
└── dune/        — 6h TTL (blockchain data updates every block but we don't need live)
```

### API Key Rotation

All keys live in `.env` with `STRATA_` prefix. Shell also exports some without prefix
(for ad-hoc curl). When rotating:
1. Update `.env`
2. Update shell env (fish: `set -Ux STRATA_KALSHI_API_KEY new-value`)
3. Clear relevant cache dir: `rm -rf ~/.strata/cache/kalshi/`

### Running Ingest

```bash
cd backend

# Single connector test
uv run python -c "
from strata.connectors import KalshiClient
import os
from pathlib import Path
client = KalshiClient(
    api_key=os.environ['KALSHI_API_KEY_ID'],
    private_key_path=Path(os.environ['KALSHI_PRIVATE_KEY_PATH']),
)
resp = client.get_markets(limit=5)
print(resp.markets[0].ticker, resp.markets[0].midpoint)
client.close()
"

# Full test suite (verifies all primitives validate against schema)
uv run pytest tests/ -q

# Type check connector changes
uv run pyright src/strata/connectors/new_connector.py

# Lint
uv run ruff check src/strata/connectors/ && uv run ruff format --check src/strata/connectors/
```

### Common Pitfalls

1. **Source slug validation** — must be `^[a-z0-9][a-z0-9-]*$`. Sanitize tickers that contain dots/underscores.
2. **Unit enum values** — only the exact enum values are valid (see Schema Constraints above). Don't invent new ones.
3. **`total=False` TypedDicts** — raw API responses have optional fields. Use `.get()` with defaults everywhere.
4. **Ruff RUF022** — `__all__` must be sorted. Run `ruff check --unsafe-fixes --fix` if it complains.
5. **Ruff B008** — don't put mutable defaults in function signatures. Use module-level singletons.
6. **Cache key determinism** — sort JSON keys in cache key construction so same params always hit same cache.

---

## Quick Reference: Connector API Summary

| Connector | Base URL | Auth | Rate Limit | Cache TTL |
|-----------|----------|------|-----------|-----------|
| BLS | api.bls.gov/publicAPI/v2 | API key in payload | 500/day | 24h |
| FRED | api.stlouisfed.org/fred | API key query param | 120/min | 24h |
| Census | api.census.gov/data | API key query param | None stated | 24h |
| EDGAR | data.sec.gov/api | User-Agent header | 10/sec | 24h |
| World Bank | api.worldbank.org/v2 | None | None stated | 24h |
| Kalshi | external-api.kalshi.com/trade-api/v2 | RSA-PSS signed headers | Undocumented | 1h |
| Dune | api.dune.com/api/v1 | X-Dune-API-Key header | Credit-based | 6h |
| Polymarket | gamma-api.polymarket.com | None (public read) | Undocumented | 1h |
| CoinGecko | api.coingecko.com/api/v3 | API key header | 10-30/min | 1h |

---

## The Big Picture

```
                        ┌─────────────────────────────────────┐
                        │         STRATA DATA BANK            │
                        │  (308 primitives, growing weekly)    │
                        └────────────────┬────────────────────┘
                                         │
              ┌──────────────────────────┼──────────────────────────┐
              │                          │                          │
    ┌─────────┴─────────┐    ┌──────────┴──────────┐    ┌─────────┴─────────┐
    │   GOVERNMENT      │    │   PREDICTION MKTS   │    │   BLOCKCHAIN      │
    │   (regulator)     │    │   (prediction_mkt)  │    │   (onchain)       │
    │                   │    │                     │    │                   │
    │ BLS  ✓ headcount  │    │ Kalshi ✓ 202 prims │    │ Dune  ◌ blocked  │
    │ FRED ✓ macro data │    │ Polymarket ◌ next  │    │ CoinGecko ◌ next │
    │ Census ✓ firms    │    │                     │    │                   │
    │ EDGAR ✓ filings   │    │                     │    │                   │
    │ World Bank ✓ intl │    │                     │    │                   │
    │ Eurostat ◌ EU     │    │                     │    │                   │
    └───────────────────┘    └─────────────────────┘    └───────────────────┘

    ✓ = done and ingesting       ◌ = designed, not yet built
```

The goal: every number in a TAM model traces to a real API response,
content-hash pinned, with a clickable source URL. No analyst guesses,
no made-up figures, no stale quarterly reports.
