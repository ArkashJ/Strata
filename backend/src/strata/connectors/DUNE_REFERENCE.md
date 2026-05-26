# Dune Connector — Reference & Queries (Planned)

## Status

- **API Key:** `IzD2Zq5AmKjgfsJ5EHg2a2Z3AvvgEyxT` (community_fluid_engine_v2)
- **Credits:** 2500/month
- **Limitation:** Community plan cannot execute queries on cross-chain spell tables
  (dataset 4). Upgrade to Plus/Premium for `dex.trades`, `stablecoins_*.transfers`, etc.
- **MCP available:** Yes — `mcp__dune__*` tools for search, query management, dashboards.
- **Connector:** Not yet built — waiting on execution access. When ready, follow BLS pattern.

## Key Tables for TAM Research

### DEX / DeFi (tier: onchain)

| Table | Description | TAM Use Case |
|-------|-------------|-------------|
| `dex.trades` | All DEX trades across 50+ EVM chains | DEX volume TAM, take-rate models (L4 lens) |
| `dex.pools` | DEX liquidity pool metadata | DeFi infrastructure sizing |
| `stablecoins_{chain}.transfers` | Stablecoin transfer events per chain | Remittance/payments TAM, stablecoin velocity |
| `stablecoins_{chain}.balances` | Daily stablecoin balances per address | AUM proxy, demand-side signal |

### Protocol Revenue

| Table | Description | TAM Use Case |
|-------|-------------|-------------|
| `dex_aggregator.trades` | Aggregator (1inch, Paraswap) trades | Aggregator take-rate TAM |
| `nft.trades` | NFT marketplace trades | Digital collectibles TAM |
| `lending.borrow` | Lending protocol borrows | DeFi lending TAM |

### Wallet Activity

| Table | Description | TAM Use Case |
|-------|-------------|-------------|
| `ethereum.transactions` | All ETH transactions | Active user base sizing |
| `tokens.transfers` | ERC20 token transfers | Token economy velocity |

## SQL Queries Ready to Execute (when plan allows)

### Q1: Monthly DEX Volume (All Chains)

```sql
SELECT
    DATE_TRUNC('month', block_date) AS month,
    blockchain,
    SUM(amount_usd) AS volume_usd,
    COUNT(*) AS trade_count,
    COUNT(DISTINCT taker) AS unique_traders
FROM dex.trades
WHERE block_date >= DATE '2024-01-01'
    AND block_date < CURRENT_DATE
    AND amount_usd IS NOT NULL
    AND amount_usd > 0
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC
```

**Primitive mapping:**
- `value` = monthly volume_usd per chain
- `unit` = {kind: flow, dimension: currency, currency: USD, denominator: per-month}
- `source.tier` = onchain

### Q2: Top DEX Protocols by Volume (Monthly)

```sql
SELECT
    DATE_TRUNC('month', block_date) AS month,
    project,
    blockchain,
    SUM(amount_usd) AS volume_usd,
    COUNT(DISTINCT taker) AS unique_users
FROM dex.trades
WHERE block_date >= CURRENT_DATE - INTERVAL '90' DAY
    AND amount_usd > 0
GROUP BY 1, 2, 3
HAVING SUM(amount_usd) > 1000000
ORDER BY 4 DESC
```

**Use case:** Protocol-level take-rate TAM (L4 lens).
Uniswap volume * fee tier = protocol revenue.

### Q3: Stablecoin Daily Transfer Volume

```sql
SELECT
    block_date,
    token_symbol,
    SUM(amount_usd) AS transfer_volume_usd,
    COUNT(*) AS transfer_count,
    COUNT(DISTINCT "from") AS unique_senders
FROM stablecoins_ethereum.transfers
WHERE block_date >= CURRENT_DATE - INTERVAL '30' DAY
    AND amount_usd > 0
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC
```

**Use case:** Payments/remittance TAM. USDT on Tron = largest remittance rail.

### Q4: Active Wallets (Monthly Unique)

```sql
SELECT
    DATE_TRUNC('month', block_date) AS month,
    blockchain,
    COUNT(DISTINCT taker) AS monthly_active_traders
FROM dex.trades
WHERE block_date >= DATE '2024-01-01'
GROUP BY 1, 2
ORDER BY 1 DESC
```

**Use case:** Total addressable users for DeFi products.

### Q5: Protocol Revenue via DEX Fees

```sql
SELECT
    DATE_TRUNC('month', block_date) AS month,
    project,
    SUM(amount_usd * 0.003) AS estimated_fee_revenue_usd  -- 30bps average
FROM dex.trades
WHERE block_date >= DATE '2024-01-01'
    AND blockchain = 'ethereum'
    AND amount_usd > 0
GROUP BY 1, 2
ORDER BY 3 DESC
```

**Use case:** L4 platform throughput lens (volume * take_rate).

## Curl Commands

```bash
# Search tables
curl -s -H "X-Dune-API-Key: IzD2Zq5AmKjgfsJ5EHg2a2Z3AvvgEyxT" \
  "https://api.dune.com/api/v1/table/search?query=dex+trades&limit=5" | jq .

# Get query metadata
curl -s -H "X-Dune-API-Key: IzD2Zq5AmKjgfsJ5EHg2a2Z3AvvgEyxT" \
  "https://api.dune.com/api/v3/queries/649046" | jq .

# Execute a query (requires paid plan for spell tables)
curl -s -X POST -H "X-Dune-API-Key: IzD2Zq5AmKjgfsJ5EHg2a2Z3AvvgEyxT" \
  -H "Content-Type: application/json" \
  "https://api.dune.com/api/v1/query/649046/execute" \
  -d '{"performance": "medium"}' | jq .

# Get latest results (if cached)
curl -s -H "X-Dune-API-Key: IzD2Zq5AmKjgfsJ5EHg2a2Z3AvvgEyxT" \
  "https://api.dune.com/api/v1/query/649046/results" | jq .

# Check usage
curl -s -X POST -H "X-Dune-API-Key: IzD2Zq5AmKjgfsJ5EHg2a2Z3AvvgEyxT" \
  "https://api.dune.com/api/v1/billing/usage" | jq .
```

## Connector Design (for when execution access is available)

```python
# Future: backend/src/strata/connectors/dune.py
# Follow BLS flat-client pattern:
# - DuneClient(api_key=..., cache_dir=..., cache_ttl=...)
# - Client manages: create query, execute, poll, get results
# - query_to_primitive_yaml() converter
# - query_to_source_yaml() converter
# - Disk cache keyed by query_id + params hash
# - Source tier: "onchain"
```

## TAM-Relevant Topics to Query

### Crypto-Native TAMs (tier: onchain)
1. **DEX total market** — $X/month volume * take-rate = revenue TAM
2. **Stablecoin market** — total supply, velocity, cross-border flows
3. **NFT market** — monthly volume, unique buyers, marketplace fees
4. **Lending/Borrowing** — total borrows, protocol revenue
5. **L2 ecosystem** — Base/Arbitrum/Optimism tx volume + fees
6. **MEV market** — sandwich volume, arbitrage revenue

### Crypto-as-Signal for TradFi TAMs
1. **Stablecoin velocity → remittance market** (Tron USDT = biggest rail)
2. **Tokenized assets (RWA) → AUM proxy**
3. **DEX volume growth rate → fintech disruption signal**
4. **Active wallet growth → crypto adoption curve**
5. **Protocol revenue multiples → SaaS comparable metrics**
