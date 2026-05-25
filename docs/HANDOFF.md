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
| API routes | **Done** | 10 endpoints: `/healthz`, `/c`, `/c/{slug}`, `/p`, `/p/{slug}`, `/f`, `/f/{slug}`, `/build/{concept_slug}`, `/tam/{state_hash}`, `POST /resolve` (dynamic SSE) |
| CLI (`strata`) | **Partial** | `strata version`, `strata validate`, `strata size` wired; other commands stubbed |
| Tests | **110 passing** | Models, validator, evaluator, e2e sizing, API integration, all-concepts, enrichment, data validation |
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
| Concepts | **6** | 6 | 0 — all 6 lenses covered |
| Primitives (atomic) | **14** | ~50 | ~36 missing (need real API connectors) |
| Composites | **0** | ~10 | ~10 missing |
| Frameworks | **5** | 6 | 1 missing (L3 latent_demand) |
| Sources | **15** | ~50 | ~35 missing |
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

<!-- FIXED 2026-05-24 session: items 1-3 resolved -->
1. ~~**Primitive cards in ScenarioGraph** show role names instead of values/units~~ — FIXED: InputUsed enriched with value/name/unit from evaluator
2. ~~**Build page heading** shows concept slug instead of full name~~ — FIXED: TAMTarget.concept_name populated by evaluator
3. ~~**No range display** in build header~~ — FIXED: min-max range shown under midpoint
4. **Lineage graph modal** opens on scroll interaction unexpectedly — needs proper trigger wiring
5. **CORS** hardcoded to localhost:3000 + 3001 — production deploy needs env-driven origins
6. **structlog** had a crash with `add_logger_name` + `PrintLoggerFactory` — fixed but not tested with `log_json=True`
7. **Dynamic resolve** works but uses only one framework per query — no triangulation yet (independence always 0.0)
8. **Snapshot hashes** are still placeholders — no actual source document downloads yet

---

## What to do next — MVP launch critical path

<!-- Updated 2026-05-24. Phase strategy: Approach C (progressive decentralization).
     MVP = internal tool for Arkash + friend to build TAMs.
     Phase 2 (paid) and Phase 3 (contribution) come after MVP proves value. -->

### Sprint 1: Real data connectors (replaces seed YAML)

The dynamic `/resolve` endpoint proves the concept — now build proper connectors.
See `docs/11-api-catalog.md` for full API list with auth/limits/SDKs.

1. **FRED API connector** (`fredapi`) — 800K macro series, free key
2. **BLS API connector** — occupation headcounts + wages by SOC, free
3. **SEC EDGAR XBRL connector** — public company financials, no auth needed
4. **Census Bureau connector** (`census`) — business counts by NAICS
5. Replace placeholder `snapshot_sha256` with real downloaded snapshots

### Sprint 2: MVP workhorse UI

The current build page is read-only. The MVP needs an interactive wiring view.
Design spec from deep-research session (not a separate doc — kept here):

- **Three-panel layout**: (left) concept + AI lens recommender, (center) formula wiring with sliders, (right) live scenario tree + provenance
- **Lens recommender**: rules engine from Q1-Q5 decision tree, not LLM. Presents recommended lens + confidence + modifiers. "Help me choose" wizard, "Override" dropdown.
- **Inline primitive discovery**: click empty wiring slot → search panel → existing library + "Search the web" (Exa) → draft primitive → validate → wire
- **Scenario tree from variation points**: each wired primitive gets a slider range. Bear/base/bull generated automatically from combinations.

### Sprint 3: Deploy + multi-framework triangulation

6. Deploy backend to Railway, frontend to Vercel
7. Multi-framework triangulation in `/resolve` (search for primitives matching 2-3 lenses, independence > 0)
8. Export: Copy URL + PDF/Markdown stubs

### Later (not MVP)

- Prediction market connectors (Polymarket, Kalshi) — Phase 1 stretch
- Pyramid three-axis constraint picker — v0.3
- Contribution flow + auth — Phase 2
- Chain-portable schema fields (contributor_id, content_hash, usage_count) — Phase 3
- On-chain anchoring (Base/Solana) — Phase 4

---

## The honest bottom line (updated 2026-05-24)

**The pipeline works end-to-end. Data is expanding but still seed-quality.**

We now have: 6 concepts across all 6 lenses, 14 primitives (2 Exa-verified against BLS), 5 frameworks, 110 passing tests, dynamic query resolution (Claude + Exa + SSE streaming), and a working ReactFlow build page showing real values.

What's still missing for MVP: real API connectors (FRED/BLS/EDGAR/Census) replacing seed YAML, interactive wiring UI with sliders, multi-framework triangulation, and deployment. The `/resolve` endpoint is a prototype of the dynamic pipeline — it needs to become the primary data path, not a fallback.
