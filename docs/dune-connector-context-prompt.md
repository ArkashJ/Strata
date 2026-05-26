# Dune Analytics Connector — Context Prompt for Separate Session

Use this prompt when working in a separate Claude session with the Dune MCP server
to build the Dune connector for Strata.

---

## Context Prompt

You are building a **Dune Analytics connector** for the Strata market-sizing engine.
The project is at `/Users/arkashjain/Desktop/work/VC_stuff` and you have the Dune MCP
server available.

### What Strata is

Strata is a community-curated market-sizing engine for VCs. It stores **atomic primitives**
(one source, one number, SHA256-pinned) in a YAML data bank and combines them via
**frameworks** into TAM estimates. The connectors module ingests data from external APIs
into this data bank.

### What's already built

Four connectors exist at `backend/src/strata/connectors/`:
- `bls.py` (748 lines) — Bureau of Labor Statistics, the template
- `fred.py` (~750 lines) — Federal Reserve Economic Data
- `census.py` (~790 lines) — US Census Bureau (CBP, SUSB)
- `edgar.py` (~855 lines) — SEC EDGAR XBRL filings
- `worldbank.py` (~614 lines) — World Bank Open Data

All follow the same 6-layer pattern. **Read `bls.py` first** to understand the exact
architecture you must replicate.

### The 6-layer pattern (mandatory)

```
Layer 1: Enums (StrEnum)          — API constants, query types
Layer 2: TypedDicts               — raw API response shapes (documentation + type safety)
Layer 3: Frozen dataclasses       — validated internal models (@dataclass(frozen=True, slots=True))
Layer 4: Unified Response type    — single return dataclass with cache metadata
Layer 5: _DiskCache               — JSON-on-disk cache with SHA256 keys and configurable TTL
Layer 6: Client class             — context-manager, one method per endpoint, auto-pagination
Layer 7: Strata YAML converters   — series_to_primitive_yaml() / series_to_source_yaml()
```

### Your task: build `backend/src/strata/connectors/dune.py`

#### Dune API endpoints to implement (use the Dune MCP for reference):
1. **Execute query** — Run a Dune query by ID and get results
2. **Get query results** — Fetch results of a previously executed query
3. **Get latest results** — Get cached results without re-executing
4. **Cancel execution** — Cancel a running query
5. **Search queries** — Search public Dune queries by keyword

#### Key Dune queries for market sizing:
- DEX trading volumes (Uniswap, etc.)
- DeFi TVL (Total Value Locked) by protocol
- NFT marketplace volumes
- L2 transaction counts and fees
- Stablecoin supply and transfers
- Active wallet counts by chain
- Token holder distributions
- Bridge volumes between chains

#### Dune-specific considerations:
- **API key**: Required. Add `dune_api_key: str | None = None` to `config.py` Settings,
  reads from `STRATA_DUNE_API_KEY`. The user already has `DUNE_API_KEY=IzD2Zq5AmKjgfsJ5EHg2a2Z3AvvgEyxT`.
- **Async execution**: Dune queries are async — you submit, then poll for results.
  The client should handle the poll loop internally.
- **Rate limits**: Free tier: 2,500 credits/month, ~10 req/min
- **Source tier**: `"community"` (Dune queries are community-contributed SQL on blockchain data)
- **Cache TTL**: 3600 (1 hour — blockchain data changes frequently)
- **Cache prefix**: `dune_`
- **Error class**: `DuneClientError(RuntimeError)`

#### Enums to define:
```python
class DuneStatus(StrEnum):
    PENDING = "QUERY_STATE_PENDING"
    EXECUTING = "QUERY_STATE_EXECUTING"
    COMPLETED = "QUERY_STATE_COMPLETED"
    FAILED = "QUERY_STATE_FAILED"
    CANCELLED = "QUERY_STATE_CANCELLED"
    EXPIRED = "QUERY_STATE_EXPIRED"

class DuneChain(StrEnum):
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    BASE = "base"
    SOLANA = "solana"
    AVALANCHE = "avalanche_c"
    BNB = "bnb"
```

#### Dataclasses:
```python
@dataclass(frozen=True, slots=True)
class DuneColumn:
    name: str
    type: str  # "varchar", "double", "bigint", "date", "timestamp", etc.

@dataclass(frozen=True, slots=True)
class DuneResult:
    execution_id: str
    query_id: int
    status: DuneStatus
    columns: tuple[DuneColumn, ...]
    rows: tuple[dict[str, Any], ...]  # each row is a dict of column_name → value
    total_row_count: int
    execution_started_at: str
    execution_ended_at: str

@dataclass(frozen=True, slots=True)
class DuneResponse:
    result: DuneResult | None = None
    cached: bool = False
    cache_age_seconds: float = 0.0
```

#### Client class:
```python
class DuneClient:
    def __init__(self, api_key: str | None = None, cache_dir: Path | None = None,
                 cache_ttl: int = 3600, timeout: float = 120.0,
                 poll_interval: float = 2.0, max_poll: int = 300) -> None: ...
    
    def execute_query(self, query_id: int, params: dict[str, Any] | None = None) -> DuneResponse:
        """Execute a query and wait for results (polls internally)."""
    
    def get_latest_results(self, query_id: int) -> DuneResponse:
        """Get cached results without re-executing."""
    
    def get_results(self, execution_id: str) -> DuneResponse:
        """Get results of a specific execution."""
    
    def cancel_execution(self, execution_id: str) -> None:
        """Cancel a running query execution."""
    
    def clear_cache(self) -> int:
```

#### Strata converters:
```python
def query_to_primitive_yaml(
    result: DuneResult,
    *,
    concept_slug: str,
    primitive_slug: str,
    name: str,
    description: str,
    source_url: str,  # e.g. "https://dune.com/queries/12345"
    value_column: str,  # which column to extract the value from
    row_index: int = 0,  # which row (for single-value queries, usually 0)
    # ... same geo/unit params as other connectors
) -> dict[str, Any]: ...

def query_to_source_yaml(
    result: DuneResult,
    *,
    source_url: str,
    description: str = "",
) -> dict[str, Any]: ...
```

### Style requirements
- `from __future__ import annotations` at the top
- All dataclasses: `@dataclass(frozen=True, slots=True)`
- ruff: 100-char lines, py312 target
- pyright strict: no Any leaks in public signatures
- No comments unless WHY is non-obvious
- Section headers using `# ═══...` separators
- Source tier: `"community"` (Dune is community-contributed)
- All slugs must match `^[a-z0-9][a-z0-9-]*$`

### After writing the connector:
1. Update `backend/src/strata/connectors/__init__.py` to re-export Dune types
2. Add `dune_api_key: str | None = None` to `backend/src/strata/config.py`
3. Add `STRATA_DUNE_API_KEY=` to `.env.example`
4. Run `uv run pyright src/strata/connectors/dune.py` — must be 0 errors
5. Run `uv run ruff check src/strata/connectors/dune.py` — must pass
6. Run `uv run pytest` — all 167+ tests must still pass
7. Write tests in `backend/tests/test_connectors.py` (add a TestDuneParsing class)
8. Try executing some real queries via the MCP and save the results to `data/primitives/`

### Useful Dune query IDs for market sizing:
- Query 2030664: Uniswap daily volume
- Query 1847756: DeFi TVL by protocol
- Query 2461024: NFT marketplace volume
- Query 2296418: L2 transaction counts
- Query 767782: Active addresses by chain

Use the Dune MCP to discover more queries relevant to market sizing.
