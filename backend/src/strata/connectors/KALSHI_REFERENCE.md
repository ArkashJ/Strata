# Kalshi Connector — Reference & Curl Commands

## Quick Start

```python
from strata.connectors import KalshiClient, market_to_primitive_yaml

client = KalshiClient(
    api_key="950da0f3-a026-4533-a91f-d555d3902add",
    private_key_path=Path("~/.kalshi/private_key.pem"),
)

# List active markets with volume
resp = client.get_markets(status="open", limit=1000)
active = [m for m in resp.markets if m.volume > 0]

# Get a specific event with nested markets
resp = client.get_event("KXRECSSNBER-26")
event = resp.events[0]

# Convert to Strata primitive
prim = market_to_primitive_yaml(
    event.markets[0],
    concept_slug="us-economic-cycle-2026",
    primitive_slug="kalshi-recession-2026-probability",
    name="Probability: US recession in 2026 (Kalshi NBER)",
    description="...",
)
```

## Curl Commands

### List markets (no auth required for public data)

```bash
# All open markets (paginated, max 1000)
curl -s "https://external-api.kalshi.com/trade-api/v2/markets?limit=200&status=open" | jq '.markets[:3]'

# Markets for a specific event
curl -s "https://external-api.kalshi.com/trade-api/v2/markets?event_ticker=KXRECSSNBER-26" | jq .

# Specific market by ticker
curl -s "https://external-api.kalshi.com/trade-api/v2/markets/KXRECSSNBER-26" | jq .market
```

### List events

```bash
# All events (paginated)
curl -s "https://external-api.kalshi.com/trade-api/v2/events?limit=200&with_nested_markets=true" | jq '.events[:3]'

# Single event with markets
curl -s "https://external-api.kalshi.com/trade-api/v2/events/KXLAYOFFSYINFO-26?with_nested_markets=true" | jq .
```

### Orderbook

```bash
curl -s "https://external-api.kalshi.com/trade-api/v2/markets/KXRECSSNBER-26/orderbook" | jq .orderbook
```

### Trades

```bash
curl -s "https://external-api.kalshi.com/trade-api/v2/markets/trades?ticker=KXRECSSNBER-26&limit=20" | jq '.trades[:5]'
```

### Authenticated request (Python — needed for portfolio/trading)

```python
import time, base64, requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

key_id = "950da0f3-a026-4533-a91f-d555d3902add"
private_key = serialization.load_pem_private_key(
    open("~/.kalshi/private_key.pem", "rb").read(), password=None
)
ts = str(int(time.time() * 1000))
method, path = "GET", "/trade-api/v2/portfolio/balance"
msg = f"{ts}{method}{path}"
sig = base64.b64encode(private_key.sign(
    msg.encode(),
    padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
    hashes.SHA256(),
)).decode()

resp = requests.get(
    f"https://external-api.kalshi.com{path}",
    headers={
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "KALSHI-ACCESS-SIGNATURE": sig,
    }
)
```

## TAM-Relevant Event Tickers (Curated)

### Economics & Macro (highest TAM signal)

| Ticker | Title | Why it matters |
|--------|-------|----------------|
| `KXRECSSNBER-26` | Recession this year? | Macro scenario gate — 16.5% probability weights all TAM downside scenarios |
| `KXLAYOFFSYINFO-26` | More tech layoffs in 2026 than 2025? | 90.5% prob — tech labor contraction signal, affects all SaaS TAMs |
| `KXIPOSPACEX` | When will SpaceX announce IPO? | Space industry capital formation signal |
| `KXFEDCHAIRCONFIRM` | Who will be confirmed as Fed chair? | Monetary policy direction signal |

### Companies & M&A

| Ticker | Title | Why it matters |
|--------|-------|----------------|
| `KXTAKEOVERACQWB-27JUN30` | Who will take over Warner Brothers? | Media consolidation TAM signal |

### Categories Available on Kalshi

| Category | TAM Use Case |
|----------|-------------|
| Economics | Recession/growth priors, labor market signals |
| Financials | Rate expectations, market regime changes |
| Science and Technology | Adoption probability for tech categories |
| Companies | IPO/M&A timing, company-specific events |
| Crypto | Token/protocol adoption probability |
| Climate and Weather | Energy/EV TAM sensitivity |
| Transportation | Autonomous driving, EV adoption timing |
| Health | Healthcare/pharma approval signals |

## How Kalshi Data Maps to Strata Primitives

### Probability primitives (source tier: prediction_market)

Market midpoint → `value` (0-1 scale)
Bid-ask spread → `uncertainty.range` [bid, ask]
Useful for: scenario weighting, adoption probability, event timing

### Volume/OI primitives (source tier: prediction_market)

Cumulative volume → `value` (contracts traded)
Useful for: market attention proxy, conviction signal, demand estimation

### Schema mapping

```yaml
# Probability primitive
kind: atomic_primitive
unit: {kind: probability, dimension: ratio}
uncertainty:
  range: [yes_bid, yes_ask]   # 0-1 dollar scale
  basis: "Kalshi bid-ask spread ({ticker})"
source:
  tier: prediction_market

# Volume primitive  
kind: atomic_primitive
unit: {kind: flow, dimension: contracts, denominator: cumulative}
distribution_shape: power_law
source:
  tier: prediction_market
```

## Ingest Workflow

```bash
# From backend/ directory
uv run python -c "
from strata.connectors import KalshiClient, market_to_primitive_yaml
import yaml, os
from pathlib import Path

client = KalshiClient(
    api_key=os.environ['KALSHI_API_KEY_ID'],
    private_key_path=Path(os.environ['KALSHI_PRIVATE_KEY_PATH']),
)

resp = client.get_event('KXRECSSNBER-26')
market = resp.events[0].markets[0]

prim = market_to_primitive_yaml(
    market,
    concept_slug='us-economic-cycle-2026',
    primitive_slug='kalshi-recession-2026-probability',
    name='Probability: US recession in 2026 (Kalshi NBER)',
    description='...',
)

Path('../data/primitives/kalshi-recession-2026-probability.yaml').write_text(
    yaml.dump(prim, default_flow_style=False, sort_keys=False)
)
"
```
