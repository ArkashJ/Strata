# Strata Backend Feature Status (v0.2 Alpha)

## For Client Walkthrough Documentation

Updated: 2026-05-25

---

## API Endpoints Status

| Feature | Endpoint/Component | Status | Client-Facing Impact |
|---------|-------------------|--------|---------------------|
| Health Check | `GET /healthz` | **Live** | Returns API status, environment, and version number. Used for deployment health monitoring. |
| Concept Lookup | `GET /c` (all) & `GET /c/{slug}` (detail) | **Live** | Returns all 6 concepts or a specific concept with full metadata. Powers concept detail pages. |
| Primitive Lookup | `GET /p` (all) & `GET /p/{slug}` (detail) | **Live** | Returns all 307 primitives or specific primitive with source/unit info. Currently 14 seeded; remaining are placeholders. |
| Framework Lookup | `GET /f` (all) & `GET /f/{slug}` (detail) | **Live** | Returns all 5 frameworks with multiplicative evaluation rules. All 6 lenses covered (1 placeholder). |
| TAM Calculation (Static) | `GET /build/{concept_slug}` | **Live** | Evaluates a concept into a scenario tree TAM output using seeded primitives. Returns JSON with min/mid/max ranges and method family. |
| TAM Archive Retrieval | `GET /tam/{state_hash}` | **Live** | Retrieves a frozen TAM output by content-hash. Read-only artifact storage for sharing and permanent links. |
| Dynamic Market Query | `POST /resolve` (SSE streaming) | **Live** | Accepts natural-language market query. Pipeline: Claude parses query → identifies lens and framework → Exa web search for primitives → Claude extracts numbers → evaluator calculates TAM scenario tree. Returns streaming SSE events with progress updates. |

---

## Data Connectors Status

| Connector | Lines | Coverage | Implementation | Client Impact |
|-----------|-------|----------|-----------------|----------------|
| BLS (Bureau of Labor Statistics) | 748 | Employment, wages, CPI, JOLTS | **Live but unused** | Fully typed client with disk caching. Ready to pull government employment + wage data. Not yet wired to ingest pipeline. |
| FRED (Federal Reserve Economic Data) | 753 | GDP, rates, money supply, consumption | **Live but unused** | Complete macro data client with pagination + search. Not connected to live pulls. |
| Census Bureau | 790 | Industry stats by NAICS (CBP/SUSB) | **Live but unused** | Geo-aware client (state/county level). Ready for business count lookups. Not called in pipeline. |
| EDGAR (SEC Financials) | 856 | Company financials, XBRL frames | **Live but unused** | Full 10-K extraction + company concept lookups. No integration yet. |
| World Bank | 614 | Global GDP, population, adoption rates | **Live but unused** | Country-level indicators fully typed. Not connected to data ingest. |
| Kalshi (Prediction Markets) | — | Event contracts, implied probabilities | **Live but unused** | Market-implied TAM estimates. Orderbook + trade history support. Not called. |

**Key Message:** All 6 connectors are production-ready code. They are not currently wired into the `strata db seed` ingest pipeline. v0.3 will connect them, allowing live API pulls to populate the 293 placeholder primitives.

---

## Data Bank Status

| Metric | Current | v0.2 Target | Gap |
|--------|---------|-------------|-----|
| Atomic Primitives | 14 seeded | ~50 | ~36 missing |
| Primitive Placeholders | 293 | — | Ready for connector backfill |
| Concepts | 6 (all lenses) | 6 | ✓ Complete |
| Frameworks | 5 | 6 | 1 placeholder (L3 latent_demand) |
| Sources | 15 seeded | ~50 | ~35 missing |
| Annotations | 0 | ~5 | Deferred to v0.5 |

**Data Verification:** 2 primitives verified against Exa; rest are seed/placeholder quality.

---

## Partial Features (Roadmap, Not MVP)

| Feature | Current State | Next Step | Timeline |
|---------|---------------|-----------|----------|
| Multi-Framework Triangulation | Independence always 0.0 in `/resolve` | Lens-intersection primitive search (2-3 lenses at once) | v0.3 |
| Source Snapshot Hashing | Placeholders only | Real document downloads + SHA256 pinning | v0.3 |
| Interactive Wiring UI | Concept detail page only | Sliders, framework selector, assumption tweaks on build page | v0.3 |
| Export (PDF/Markdown) | Stubs in frontend | Backend export formatting + download routes | v0.4 |
| Contribution Pipeline | No API endpoints | PR-based contributions + LLM review + web form | v0.5 |
| Annotation Expert Layer | Schema complete, no moderation | Credentialing, COI rules, flagging, reputation scoring | v0.5 |

---

## What's Live vs. Stubbed — Executive Summary

### ✓ What Works (Client Can Use Today)

1. **Natural-language TAM queries** — Ask "What's the market for AI-assisted code review?" and get a calculated scenario tree back (Claude + Exa + LLM extraction).
2. **Static TAM builds** — Click a concept and see a full evaluation with min/mid/max ranges, method family, and framework inputs.
3. **Concept/primitive/framework browsing** — All three dimensions are queryable and detail pages work.
4. **TAM sharing via URLs** — Each build gets a content-hash URL (`/tam/{hash}`) that freezes and preserves the calculation.
5. **Full validation & type safety** — All records are schema-validated; cross-record dependencies are checked (no broken refs, no unit mismatches).

### ✗ What's Not Ready (MVP Doesn't Require)

1. **Real data** — Only 14 of 307 primitives are seeded. The rest are placeholders. Connectors exist but aren't called. v0.3 wires them up.
2. **Multi-lens triangulation** — `/resolve` finds primitives for one framework at a time. v0.3 searches across lenses for independence > 0.
3. **Source pinning** — All snapshot hashes are dummy values. Real web document capture + SHA256 anchoring deferred.
4. **Exports** — PDF/Markdown download buttons exist in UI but backend doesn't generate them yet.
5. **Community contributions** — No PR pipeline or web form. Full flow is v0.5.

---

## When Building the Client Doc

**Headline:** "Strata calculates TAM scenarios end-to-end. Ask a market question in English, and get a defensible number in 10 seconds."

**Scope:** 
- Emphasize the **live dynamic query pipeline** (POST /resolve). This is the unique value.
- Show the **static builds** for seeded concepts (good for walkthrough screenshots).
- Acknowledge the **data limitation** honestly: "The platform currently indexes 14 real market data points; we're adding 293 more from government APIs. Today, you can use this for testing and framework validation."
- Note the **TAM-sharing URL** as a powerful artifact for stakeholder reviews.

**What NOT to Promise:**
- Interactive sliders or advanced framework mixing (v0.3).
- Triangulation across multiple frameworks (v0.3).
- PDF exports (v0.4).
- Community features or contrib flow (v0.5).

**Gotchas for Client Testing:**
1. If they query something too niche (e.g., "albatross biotech"), Exa may return 0 results → `/resolve` will show "no primitives found." This is expected; try broader queries.
2. Independence scores are always 0.0 (by design). Triangulation comes later.
3. Source hashes are placeholders. Don't click "view source" expecting a real snapshot.

---

## Reference

- **API routes:** `/backend/src/strata/api/routes/`
- **Evaluator:** `/backend/src/strata/evaluator/engine.py` (multiplicative TAM scoring)
- **Connectors:** `/backend/src/strata/connectors/` (6 clients, all production-ready)
- **Models:** `/backend/src/strata/models.py` (Pydantic v2 schemas)
- **Tests:** 167 passing in `/backend/tests/` (including 7 SSE tests, 50 connector tests)

---

## Status at Commit

This doc reflects the state at `778903d` (feat: Alembic migration + Railway deploy docs + updated README/CLAUDE.md).
