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
| `__init__.py` | Re-exports key types from all connectors |
| `bls.py` | BLS Public Data API v2 — all 7 signatures, typed models, cache, Strata converters |

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

| Connector | Source tier | Priority | Status |
|-----------|-----------|----------|--------|
| BLS (OES, CPI, LAUS, JOLTS) | `regulator` | P0 | Done |
| FRED (Federal Reserve) | `regulator` | P0 | Done |
| Census / SUSB | `regulator` | P1 | Done |
| SEC / EDGAR | `regulator` | P1 | Done |
| World Bank Open Data | `aggregator` | P2 | Done |
| **Kalshi (prediction markets)** | `prediction_market` | P1 | **Done** |
| Dune Analytics (onchain) | `onchain` | P1 | Reference only (plan limits) |
| Eurostat | `regulator` | P2 | Planned |
| Polymarket | `prediction_market` | P2 | Planned |

## Conventions

- Pyright strict, ruff clean — same as the rest of `strata/`.
- Sources from government APIs are tier `regulator`.
- `snapshot_sha256` is computed from the response payload, not the source document.
- Cache TTL defaults to 24 hours; BLS data changes monthly at most.
- Converter functions are standalone (not methods) so they compose freely.
- Don't invent figures — every value in the data bank must trace to an API response.
