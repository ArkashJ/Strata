# Connectors — Data Bank Ingest Layer

## Vision

Strata is building a **data bank** — a self-hosted, version-controlled store
of market-sizing primitives sourced from government, industry, and community
data. The connectors module is the ingest pipeline that populates this bank.

**End state:** All TAM sizing runs against the local data bank (YAML on disk
at v0.2, Postgres at v0.3+). Live API calls are a **fallback** for niche data
not yet ingested — not the primary path. Every number in the bank is pinned
by `snapshot_sha256` and traceable to a source URL.

```
Live API (BLS, FRED, EDGAR, Census, ...)
        │
        ▼  connector fetches + caches raw JSON
┌─ CONNECTOR ──────────────────────────────────┐
│  BLSClient / FREDClient / ...                │
│  → typed response (dataclasses)              │
│  → disk cache (~/.strata/cache/)             │
└──────────────┬───────────────────────────────┘
               │  series_to_primitive_yaml()
               ▼
┌─ DATA BANK ──────────────────────────────────┐
│  data/primitives/*.yaml   (AtomicPrimitive)  │
│  data/sources/*.yaml      (SourceRegistry)   │
│  → loader.py → Registry → API / Evaluator   │
└──────────────────────────────────────────────┘
```

## What's here

| File | Purpose |
|------|---------|
| `__init__.py` | Re-exports key types from all 15 connectors |
| `bls.py` | BLS Public Data API v2 — employment, wages, CPI, JOLTS |
| `fred.py` | FRED API — GDP, rates, money supply, consumption |
| `census.py` | Census Bureau API — industry stats by NAICS (CBP/SUSB) |
| `edgar.py` | SEC EDGAR XBRL — company financials, frames |
| `worldbank.py` | World Bank Indicators API v2 — global GDP, population |
| `kalshi.py` | Kalshi prediction markets — event contracts, probabilities |
| `oecd.py` | OECD SDMX REST API — 38 countries, GDP/labour/trade/health/R&D |
| `eurostat.py` | Eurostat JSON-stat — EU sector stats, demographics |
| `comtrade.py` | UN Comtrade — bilateral trade flows by HS code |
| `fdic.py` | FDIC BankFind — bank financials, institutions, failures |
| `cms.py` | CMS Open Data — Medicare/Medicaid enrollment, spending, NHE |
| `eia.py` | EIA API v2 — electricity, petroleum, gas, coal, renewables |
| `usda_nass.py` | USDA NASS QuickStats — crop/livestock production, prices |
| `faa.py` | FAA aviation — airports, passengers, status |
| `openfda.py` | openFDA — drug events, device 510k/PMA, recalls |
| `alpha_vantage.py` | Alpha Vantage — equities fundamentals + FX/crypto; aggregator/fragile (25 req/day free) |
| `nasdaq_data_link.py` | Nasdaq Data Link — economic / commodity time series; aggregator, premium gated |
| `yfinance.py` | yfinance — unofficial Yahoo Finance scraper; analyst/fragile |
| `reddit.py` | Reddit OAuth — subscribers, active users; community |
| `github.py` | GitHub REST v3 — stars, forks, issues; community |
| `stack_exchange.py` | Stack Exchange API 2.3 — tag question counts; community |
| `twitter.py` | X v2 — only the 2 free-tier endpoints (`user_lookup_by_username` + `user_timeline`); analyst/fragile |
| `_capability.py` | `CapabilitySpec` schema + `all_capabilities()` walker (router input) |

## Capability manifest (v0.3, PR-A)

Every connector exposes a module-level `capabilities()` returning a
`list[CapabilitySpec]`. The router (`backend/src/strata/router.py`) serializes
the union of all 22 manifests as a cached Anthropic system block and asks
Claude to choose one connector method for a given free-form query.

Adding a new method that should be router-visible:

1. Implement the method on `<Connector>Client`.
2. Append a `CapabilitySpec(...)` entry to the connector's `capabilities()`.
3. `tests/test_capability_manifest.py` asserts the method actually exists on
   the client class. If you forget step 1 or mistype `method=...`, that test
   fails.

Demotion flags on the spec:
  - `is_fragile=True` — router demotes unless the query explicitly asks
    (e.g. yfinance scraper, Alpha Vantage rate-limited methods).
  - `requires_paid_tier=True` — router refuses to pick on a free-tier setup
    (e.g. Nasdaq premium datasets, X paid endpoints).

## Adding a new connector

Follow the BLS pattern:

1. **Enums** for API constants (survey codes, period types, status codes).
2. **TypedDicts** for raw API response shapes (documentation + type checking).
3. **Frozen dataclasses** for validated internal models (`@dataclass(frozen=True, slots=True)`).
4. **Standard return type** — a single response dataclass wrapping status, data, cache metadata.
5. **Disk cache** — JSON files under `~/.strata/cache/{connector}/`, configurable TTL.
6. **Client class** — context-manager (`with`), one method per API endpoint, auto-chunking for batch.
7. **Strata converters** — `series_to_primitive_yaml()` / `series_to_source_yaml()` emit dicts ready for `yaml.dump()` that conform to the AtomicPrimitive / Source schemas.

API keys go in `config.py` as `{connector}_api_key: str | None = None`, read from `STRATA_{CONNECTOR}_API_KEY` env vars.

## BLS Client reference

```python
from strata.connectors import BLSClient, series_to_primitive_yaml

with BLSClient(api_key="...") as client:
    # All 7 API v2 signatures
    resp = client.get_series("CUUR0000SA0")                    # single series, 3 years
    resp = client.get_latest("CUUR0000SA0")                    # most recent point
    resp = client.get_multiple_series(["A", "B"], 2020, 2024)  # multi-series POST
    resp = client.get_series_with_options(                     # with catalog/calcs/aspects
        ["A"], 2020, 2024, catalog=True, calculations=True,
        annual_average=True, aspects=True,
    )
    resp = client.get_popular(survey="OE")                     # popular series IDs
    resp = client.get_all_surveys()                            # all BLS surveys
    resp = client.get_survey("OE")                             # single survey metadata
    resp = client.get_series_batch(ids, 2020, 2024)            # auto-chunks >50 series

    # Convert to Strata YAML
    prim = series_to_primitive_yaml(
        resp.series[0],
        concept_slug="software-eng-productivity",
        primitive_slug="bls-sw-devs-2024",
        name="US software developers (BLS OES 15-1252)",
        description="...",
        source_url="https://www.bls.gov/oes/current/oes151252.htm",
        year=2024,
        unit_kind="stock",
        unit_dimension="people",
    )
```

## BLS types summary

| Layer | Types |
|-------|-------|
| Enums | `BLSStatus`, `BLSPeriodKind`, `BLSSurvey` |
| TypedDicts (raw API) | `FootnoteRaw`, `DataPointRaw`, `CatalogRaw`, `SeriesRaw`, `SurveyRaw`, `SeriesRequestPayload` |
| Dataclasses (internal) | `Footnote`, `Aspect`, `DataPoint`, `Catalog`, `Series`, `SurveyInfo` |
| Return type | `BLSResponse` — status, series, surveys, popular_ids, cached, cache_age_seconds |
| Error | `BLSClientError` |

## Connectors

| Connector | Source tier | Priority | Status | Lines | Methods |
|-----------|-----------|----------|--------|-------|---------|
| BLS (OES, CPI, LAUS, JOLTS) | `regulator` | P0 | Done | 747 | 8 |
| FRED (Federal Reserve) | `regulator` | P0 | Done | 752 | 10 |
| Census / SUSB | `regulator` | P1 | Done | 789 | 8 |
| SEC / EDGAR | `regulator` | P1 | Done | 856 | 7 |
| World Bank Open Data | `aggregator` | P2 | Done | 613 | 6 |
| Kalshi (prediction markets) | `prediction_market` | P1 | Done | 995 | 12 |
| **OECD (SDMX)** | `aggregator` | P1 | **Done** | 1187 | 22 |
| **Eurostat (JSON-stat)** | `regulator` | P1 | **Done** | 957 | 17 |
| **UN Comtrade (trade flows)** | `aggregator` | P1 | **Done** | 1050 | 16 |
| **FDIC BankFind** | `regulator` | P2 | **Done** | 1208 | 16 |
| **CMS Open Data (Medicare)** | `regulator` | P2 | **Done** | 1229 | 16 |
| **EIA (energy)** | `regulator` | P2 | **Done** | 1187 | 20 |
| **USDA NASS QuickStats** | `regulator` | P3 | **Done** | 1145 | 16 |
| **FAA (aviation)** | `regulator` | P3 | **Done** | 994 | 15 |
| **openFDA (drugs/devices)** | `regulator` | P3 | **Done** | 1218 | 20 |
| Dune Analytics (onchain) | `onchain` | P1 | Reference only (plan limits) | — | — |
| Polymarket | `prediction_market` | P2 | Planned | — | — |

## Conventions

- Pyright strict, ruff clean — same as the rest of `strata/`.
- Sources from government APIs are tier `regulator`.
- `snapshot_sha256` is computed from the response payload, not the source document.
- Cache TTL defaults to 24 hours; BLS data changes monthly at most.
- Converter functions are standalone (not methods) so they compose freely.
- Don't invent figures — every value in the data bank must trace to an API response.

## `GET /connectors` attribution (API behaviour)

The `/connectors` endpoint (`api/routes/connectors.py`) returns **every** typed
connector in the catalog with a `primitives_in_bank` count. That count is
**host-attribution**: a primitive is attributed to a connector when its
`source.url` host appears in that connector's `_CONNECTOR_HOSTS` entry. Catalog
membership and the count are independent — a connector with no host map (or no
matching primitives) is still listed, with `primitives_in_bank = 0`.

Two load-bearing rules (PR 0):

- **Map a connector's hosts only when it is a real ingest.** `usda_nass` is
  mapped (`quickstats.nass.usda.gov`, `nass.usda.gov`) → 8 attributed primitives.
- **`github` is deliberately *not* host-mapped (honest-zero).** The only
  primitives citing `github.com` are hand-authored analyst/community citations
  (and `community-modeled` model-definition links), **not** github-connector
  ingests. Mapping it would print "github · N primitives" and imply an ingest
  that never happened — a provenance lie. It stays listed with a count of 0.
