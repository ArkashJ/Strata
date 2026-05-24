# Strata Handoff Document

**Date:** 2026-05-24
**Author:** Arkash Jain + Claude Opus 4.7
**Branch:** `ArkashJ/spec/execution_foundation` (merged to main)

---

## What exists today

### Backend (Python — `backend/`)

| Component | Status | Notes |
|-----------|--------|-------|
| Pydantic v2 models | **Done** | All 6 record types + Unit, Geo, Source DU, Annotation |
| YAML loader | **Done** | Globs `data/**/*.yaml`, dispatches on `kind` |
| Slug registry | **Done** | In-memory dict keyed by `(type, slug)` |
| Validator pipeline | **Done** | Structural + semantic + cross-record (dangling refs, cycles, unit compat) |
| Evaluator engine | **Done** | Multiplicative framework evaluation, independence scoring |
| Content-hash minter | **Done** | `sha256(canonical_json(payload))` for `/tam/{hash}` URLs |
| API routes | **Done** | 9 endpoints: `/healthz`, `/c`, `/c/{slug}`, `/p`, `/p/{slug}`, `/f`, `/f/{slug}`, `/build/{concept_slug}`, `/tam/{state_hash}` |
| CLI (`strata`) | **Partial** | `strata version`, `strata validate`, `strata size` wired; other commands stubbed |
| Tests | **45 passing** | Models, validator, evaluator, e2e sizing, API integration |
| Type checking | **0 pyright errors** | Strict mode, 14 warnings (all in Typer/TypeAdapter edge cases) |
| Lint | **Clean** | ruff 100-char, py312 rule set |

### Frontend (Next.js 16 — `web/`)

| Component | Status | Notes |
|-----------|--------|-------|
| Landing page (`/`) | **Done** | Search box, suggestion chips, Strata branding |
| Build page (`/build?q=`) | **Done** | TanStack Query → real API → ScenarioGraph |
| ScenarioGraph | **Done** | ReactFlow workflow canvas (Harvey style), Target → Frameworks → Primitives |
| Right rail | **Partial** | Frameworks accordion + Independence score. Missing: Scenarios, Lineage modal, Banners, Export |
| Data page (`/data`) | **Done** | JSON explorer + charts for raw API data |
| Lineage graph | **Done** | Force-directed network (vis-network style) |
| Zod schemas | **Done** | Runtime-validated types mirroring all backend responses |
| TanStack Query hooks | **Done** | `queries.ts` with Zod validation per endpoint |
| Zustand store | **Scaffolded** | UI state only (right rail open/tab) |
| Design system | **Done** | CSS variables from brand-kit, Geist + Instrument Serif fonts |
| `vercel.json` | **Done** | Configured for bun build + API proxy rewrite |

### Data (`data/`)

| Record type | Count | v0.2 target | Gap |
|-------------|-------|-------------|-----|
| Concepts | **1** | 6 | 5 missing |
| Primitives (atomic) | **4** | ~50 | ~46 missing |
| Composites | **0** | ~10 | ~10 missing |
| Frameworks | **2** | 6 | 4 missing |
| Sources | **5** | ~50 | ~45 missing |
| Annotations | **0** | ~5 | ~5 missing |
| TAM outputs | **0** | ~3 | ~3 missing |

---

## What the data actually is

### Honest assessment

**The 4 primitives are real-ish sourced numbers, but the source snapshots are fabricated hashes.** The values reference real datasets (BLS OES, NAIC annual reports, Gartner P&C software spend) and the magnitudes are plausible, but:

1. **No actual API connectors exist.** The roadmap calls for BLS/FRED/EDGAR/NAIC direct-API ingestion. Zero connectors are built.
2. **Source `snapshot_sha256` values are placeholder hashes.** The spec (Q5) requires content-hash-pinned snapshots of the actual source documents. These don't exist — the hashes are 64-char hex strings that don't point to real snapshots.
3. **Source URLs point to real landing pages** (bls.gov, naic.org) but are not deep-linked to the specific data tables the values claim to come from.
4. **No source snapshot storage exists.** The spec requires downloaded copies of source documents stored sha256-named. This infrastructure doesn't exist.
5. **Values have not been independently verified.** They're plausible estimates that would pass a smell test, but nobody has opened the BLS OES tables and confirmed "yes, 331,200 claims adjusters" or cross-referenced the NAIC annual report for "2,541 active P&C carriers."

### What exists by vertical

**P&C Insurance Doc-Gen (the only vertical):**
- 1 concept: `doc-gen-pc-insurance` (lens: cost_efficiency + revenue_generation)
- 4 primitives:
  - `bls-pc-claims-adjusters-headcount` — 331,200 (BLS OES, tier: regulator)
  - `naic-active-pc-carriers-2024` — 2,541 (NAIC, tier: regulator)
  - `pc-claims-adjuster-cost-per-seat` — $468.50/seat (BLS wages, tier: regulator)
  - `pc-saas-spend-per-carrier-2024` — $184,700/carrier/yr (Gartner, tier: analyst)
- 2 frameworks:
  - `bottoms-up-cost-efficiency` (lens: cost_efficiency, 4 inputs)
  - `top-down-revenue-capture` (lens: revenue_generation, 2 inputs)
- Evaluator output: $312M midpoint, 2 scenarios, independence 1.00

**Missing verticals (per v0.2 roadmap):**
- `gtm-ops-tooling-na` (L1 cost_efficiency)
- `midmarket-saas-spend-na` (L2 revenue_generation, analyst-paraphrase tier)
- `payments-throughput-pc-insurance` (L4 platform_throughput)
- `workplace-suite-consolidation` (L5 bundle_consolidation)
- `software-eng-productivity` (L6 productivity_uplift)

**Missing frameworks (per v0.2 roadmap):**
- `adoption_curve_latent_demand` (L3) — requires analog field
- `throughput_take_rate` (L4) — marketplace_concept consumer
- `consolidation_sum_then_discount` (L5)
- `productivity_uplift_value_split` (L6)

---

## Open-source data collection — what needs to happen

### The spec's vision (from `docs/plans/data-collection-strategy.md` + Q26/Q37)

Strata's value proposition is **reproducible, citable numbers from public sources.** The source tier hierarchy:

| Tier | Examples | v0.2 plan |
|------|----------|-----------|
| `first_party` | Company 10-Ks, S-1s | EDGAR API connector |
| `regulator` | BLS, Census, NAIC, FRED | Direct API connectors (BLS API, FRED API) |
| `aggregator` | Statista (public previews), OECD | Manual extraction + snapshot |
| `analyst` | Gartner (public press releases) | Manual extraction + snapshot |
| `analyst-paraphrase` | Paywalled reports (≤280 char paraphrase) | Manual with reviewer sign-off |
| `community` | Community-submitted estimates | Web form (v0.5) |
| `onchain` | Dune Analytics, on-chain data | API connector (later) |
| `prediction_market` | Polymarket, Metaculus | API connector (later) |
| `community-modeled` | Community regression models | Submission form (later) |

### What's actually needed for v0.2

**Minimum viable data collection:**

1. **BLS OES API** (`https://api.bls.gov/publicAPI/v2/`) — free, 500 req/day limit, no key needed for v1 API. This is the source for occupation headcounts and wages. One connector could populate 10+ primitives.

2. **FRED API** (`https://api.stlouisfed.org/fred/`) — free with API key. Macro-economic series (GDP, sector spend, employment). Needed for top-down frameworks.

3. **NAIC data** — No public API. Annual reports are PDFs. Requires manual extraction + snapshot. The "2,541 active P&C carriers" number needs to be verified from the actual NAIC annual statement database.

4. **EDGAR** (`https://efts.sec.gov/LATEST/`) — free, 10 req/sec. 10-K and S-1 filings for company-level revenue, headcount, segment breakdowns. Needed for `first_party` tier primitives.

5. **Manual extraction** — For Gartner press releases, analyst estimates, and paywalled sources (analyst-paraphrase tier). Human reads the source, creates a ≤280 char paraphrase, a reviewer signs off, and the paraphrase + metadata get sha256-hashed as the snapshot.

### Realistic work estimate

| Task | Effort | Produces |
|------|--------|----------|
| BLS API connector + 10 primitives | 1-2 days | ~10 verified primitives (headcounts, wages across occupations) |
| FRED API connector + 5 primitives | 1 day | ~5 macro primitives (sector GDP, IT spend ratios) |
| EDGAR scraper for 3 companies | 2 days | ~6 first_party primitives (revenue, headcount, segment) |
| Manual NAIC extraction | 0.5 day | ~3 primitives (carrier counts, premium volume) |
| Manual Gartner/analyst extraction | 1 day | ~5 analyst-tier primitives (market size estimates) |
| 4 remaining frameworks | 2 days | L3, L4, L5, L6 frameworks with input schemas |
| 5 remaining concepts | 1 day | One per lens, with measurements + modifiers |
| Snapshot storage infrastructure | 1 day | sha256-named files in `data/snapshots/` |
| **Total** | **~10 days** | **~50 primitives, 6 frameworks, 6 concepts** |

---

## Architecture & deployment

### How to run locally

```bash
# Backend (from backend/)
uv run uvicorn strata.api.app:app --reload --port 8000

# Frontend (from web/)
NEXT_PUBLIC_API_URL=http://localhost:8000 bun dev --port 3001

# Full verification
cd backend && uv run pytest && uv run pyright && uv run ruff check .
```

### Deployment plan

| Layer | Platform | Config |
|-------|----------|--------|
| Frontend | **Vercel** | `web/vercel.json` — set `BACKEND_URL` env var |
| Backend | **Railway** or **Render** | Dockerfile ready, set `STRATA_CORS_ORIGINS`, `STRATA_DATA_DIR` |
| DB (v0.3) | **Neon** (serverless Postgres) | asyncpg compatible, free tier |

### Key files

```
backend/
  src/strata/
    api/app.py          — FastAPI factory, all routes mounted
    api/deps.py         — Registry DI (loads YAML on first request)
    api/routes/         — concepts, primitives, frameworks, build, healthz
    models/             — All Pydantic v2 models (frozen, extra=forbid)
    evaluator/engine.py — size_concept() → TAMOutput
    validator/          — structural + semantic + cross-record pipeline
    loader.py           — YAML → LoadedRecords
    registry.py         — slug-keyed in-memory store
    config.py           — pydantic-settings (STRATA_ prefix)
  tests/                — 45 tests (models, validator, evaluator, API)

web/
  src/
    app/page.tsx        — Landing
    app/build/          — Build view (TanStack Query → real API)
    components/         — ScenarioGraph, LineageGraph, charts
    lib/schemas.ts      — Zod schemas matching backend
    lib/queries.ts      — TanStack Query options per endpoint
    lib/format.ts       — USD, compact number formatting
    lib/api-client.ts   — Typed fetch wrapper with ApiError
    lib/env.ts          — Zod-validated env vars
    stores/ui-store.ts  — Zustand (right rail state)

data/
  concepts/             — 1 YAML (need 6)
  primitives/           — 4 YAML (need ~50)
  composites/           — 0 YAML (need ~10)
  frameworks/           — 2 YAML (need 6)
  sources/              — 5 YAML (need ~50)
  annotations/          — 0 YAML (need ~5)
  tams/                 — 0 YAML
```

---

## Known issues

1. **Primitive cards in ScenarioGraph** show role names instead of values/units — needs API enrichment or a lookup against the registry
2. **Build page heading** shows concept slug instead of full name — the `/build/{slug}` endpoint returns `target.concept` as a slug; need to join with concept record for the name
3. **No range display** in build header — evaluator computes individual scenario values but doesn't emit a triangulated range
4. **Lineage graph modal** opens on scroll interaction unexpectedly — needs proper trigger wiring
5. **CORS** hardcoded to localhost:3000 + 3001 — production deploy needs env-driven origins
6. **structlog** had a crash with `add_logger_name` + `PrintLoggerFactory` — fixed but not tested with `log_json=True`

---

## What to do next (priority order)

### Week 1: Data is the product

The entire value proposition is **defensible numbers with sources you can cite.** The code infrastructure is ~90% done for v0.2. The bottleneck is **real data from real sources.**

1. Build BLS API connector — verify the 4 existing primitives, add 10 more
2. Build FRED API connector — add macro primitives
3. Manually verify NAIC + Gartner values against actual source documents
4. Create proper source snapshots (download the actual pages, sha256 them)
5. Add the 4 remaining frameworks (L3-L6) with their input schemas
6. Add the 5 remaining concepts (one per lens)

### Week 2: Fix the build page + polish

7. Fix primitive cards to show name/value/unit from API
8. Fix concept name display (full name, not slug)
9. Add triangulated range to evaluator output + header display
10. Wire export (Copy URL works, add PDF/Markdown stubs)

### Week 3: Deploy + v0.3 planning

11. Deploy backend to Railway, frontend to Vercel
12. Decide graph library for pyramid (vis-network vs cytoscape.js)
13. Begin pyramid three-axis constraint picker component

---

## The honest bottom line

**The code is solid. The data is thin.**

We have a working end-to-end pipeline: YAML → Pydantic models → validator → evaluator → API → TanStack Query → ReactFlow graph. It's type-safe, tested, and deployable.

But the product is a **data product**, and right now we have 4 primitives in 1 vertical when the spec calls for ~50 across 6 concepts exercising all 6 lenses. The source URLs are real organizations but the specific values haven't been independently verified against the actual data tables. The snapshot hashes are placeholders.

The next person picking this up should spend 80% of their time on **data collection and verification**, not code. The infrastructure to validate, store, and serve the data is built. What's missing is the data itself.
