# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Corrected 24-company TAM pipeline** (`scripts/tam_77_pipeline.py`) — replaces the v1
  hardcoded-multiplier approach with a Claude-driven classification pipeline that
  threads through Strata's actual primitive/framework/evaluator DAG. Per company:
  (1) Claude (claude-opus-4-7) classifies onto one of the 5 existing frameworks
  via tool-use, returning concept definition + 2 input primitives with
  geo/unit/source-tier metadata; (2) connector hints are best-effort enriched
  against live BLS / Census / FRED / openFDA / World Bank APIs with response-body
  SHA256 pinning; (3) concept YAML, primitive YAMLs (with deterministic SHA256
  for analyst-paraphrase / community-modeled values), and framework variants are
  written into `data/`; (4) the registry is reloaded and `size_concept(slug)`
  produces a real `TAMOutput` with permanent state-hash. Outputs:
  `backend/tam_77_results_v2.json` + `docs/tam-77-corrected.md`.
- **3 hand-crafted worked-example concepts** wired into the DAG:
  - `yotta-india-cloud` — India-only sovereign cloud (top-down-revenue-capture). TAM $4.0B India, $0 intl.
  - `voice-ai-infra-global` — infra-stack take-rate over $108B voice-AI application stack (throughput-take-rate). TAM $13.5B global.
  - `piramidal-eeg-multi-geo` — multi-jurisdiction (FDA / CE / CDSCO / ANVISA / APAC) EEG foundation model, sized as throughput-take-rate.
- **12 methodology corrections** to the original 77-query estimates, documented
  per company in `docs/tam-77-corrected.md`: geographic over-scaling fixed for
  Yotta + 7 US-only-regulated companies; TAM ceilings vs SAM corrected for
  Endeavor / Zero RFI / Minerva by embedding addressability % into primitive
  values rather than the framework formula (Q15); infra layers (MetaVoice,
  Supermemory, Sieve) re-sized as application-stack × infra share rather than
  nascent API ARR.
- **77-query TAM estimation suite v1 baseline** — historical script (`scripts/tam_77_estimates.py`)
  that pulls real data from 15 connectors and computes TAM estimates for 24
  portfolio companies across 4 geographies (NA, Europe, APAC, RoW). Source
  attribution per estimate (S1/S2/S3 confidence tiers). Geographic scaling
  via World Bank GDP ratios. Kept on disk as the pre-correction reference;
  superseded by the v2 pipeline above. Original results in `docs/tam-77-results.md`.
- **19 TAM coverage tests** (`tests/test_tam_query_coverage.py`) — maps all
  77 queries to connector data sources, verifies disambiguation pairs produce
  distinct TAMs, validates all 14 client classes importable.
- **9 new data connectors** (15 total) — typed API clients with disk caching
  and Strata YAML converters for international, financial, energy, agriculture,
  aviation, healthcare, and regulatory data:
  - **OECD** — SDMX REST API, 22 query methods covering GDP, labour, trade,
    health spending, R&D, education, productivity across 38 OECD member
    countries. Source tier: aggregator. 1,187 lines.
  - **Eurostat** — JSON-stat API, 17 methods for EU sector statistics,
    national accounts, trade, demographic data for all EU member states.
    Source tier: regulator. 957 lines.
  - **UN Comtrade** — 16 methods for bilateral trade flows by HS commodity
    code, 200+ countries, exports/imports breakdowns. Source tier:
    aggregator. 1,050 lines.
  - **FDIC BankFind** — 16 methods for bank financials, institutions,
    failures, locations, historical summaries. Source tier: regulator.
    1,208 lines.
  - **CMS Open Data** — 16 methods for Medicare/Medicaid enrollment,
    spending, drug costs, providers, national health expenditure. Source
    tier: regulator. 1,229 lines.
  - **EIA** — API v2, 20 methods for electricity prices/sales/generation,
    petroleum, natural gas, coal, renewables, STEO forecasts, international
    energy. Source tier: regulator. 1,187 lines.
  - **USDA NASS QuickStats** — 16 methods for crop/livestock production,
    acreage, yield, prices, farm income/expenses. Source tier: regulator.
    1,145 lines.
  - **FAA** — 15 methods for airports, passengers, status, state summaries,
    proximity search. Source tier: regulator. 994 lines.
  - **openFDA** — 20 methods for drug adverse events, drug labels, device
    510(k)/PMA clearances, device/food recalls, enforcement actions. Source
    tier: regulator. 1,218 lines.
  All follow the established 6-layer pattern. 10,175 lines of new connector
  code (15,437 total across 15 connectors, ~170 query methods).
- **118 new connector tests** (168 total) — parsing, client init, cache
  roundtrip, YAML converter output shape, edge cases, cross-connector
  consistency for all 9 new connectors.
- **4 new API key settings** in config.py — `STRATA_EIA_API_KEY`,
  `STRATA_USDA_NASS_API_KEY`, `STRATA_OPENFDA_API_KEY`,
  `STRATA_COMTRADE_API_KEY`.
- **GitHub issues #35–#43** — tracking issues for all 9 new connectors.
- **5 data connectors** (original 6) — typed API clients with disk caching and
  Strata YAML converters for all major US government data sources:
  - **BLS** (Bureau of Labor Statistics) — 7 API v2 signatures, OES employment
    + wage data, CPI, JOLTS, QCEW. 748 lines.
  - **FRED** (Federal Reserve Economic Data) — 7 endpoints, GDP, employment,
    interest rates, money supply, consumption. 753 lines.
  - **Census Bureau** — CBP (County Business Patterns) + SUSB (Statistics of
    US Businesses), establishment/employee/payroll by NAICS. 790 lines.
  - **SEC EDGAR** — XBRL company financials, 5 endpoints (submissions, facts,
    concept, frames, tickers), ticker-to-CIK resolver. 856 lines.
  - **World Bank** — Indicators API, auto-pagination, 11 pre-defined indicator
    codes, income-level + region filtering. 614 lines.
  All follow a 6-layer pattern: enums → TypedDicts → frozen dataclasses →
  unified response → disk cache → client + YAML converters. 3,700+ lines of
  typed, pyright-strict connector code.
- **307 atomic primitives** populated from live API queries across all six
  TAM analysis lenses:
  - L1 cost_efficiency: BLS employment (software devs, managers), FRED wages
  - L2 revenue_generation: EDGAR company revenue (AAPL/MSFT/GOOGL/AMZN/META +
    V/MA/PYPL), FRED GDP/PCE/retail, Census industry payroll
  - L3 latent_demand: World Bank population (337M), internet (93.5%),
    mobile (109/100), FRED prime-age employed (105M)
  - L4 platform_throughput: EDGAR payment companies, Census banking,
    World Bank FDI ($362B)
  - L5 bundle_consolidation: Census professional services (legal/accounting),
    EDGAR SaaS platforms (NOW/WDAY)
  - L6 productivity_uplift: BLS CES software/data employment, Census R&D,
    EDGAR total US R&D spend ($600B)
  - Cross-lens: 6 major economy GDPs, world population/labor force, inflation
- **87 source records** — all SHA256-pinned, traceable to API responses.
- **50 connector tests** — parsing, caching, converters, cross-connector
  consistency. Test suite: 117 → 167 tests.
- **Population scripts** (`backend/scripts/`) — `populate_data_bank.py` for
  initial seeding, `populate_lens_primitives.py` for lens-aligned expansion.
- **Dune connector context prompt** — `docs/dune-connector-context-prompt.md`
  for building the Dune Analytics connector in a separate session.
- **Config expansion** — `STRATA_FRED_API_KEY`, `STRATA_CENSUS_API_KEY` added
  to pydantic-settings config and `.env.example`.

### Fixed
- Census connector: `follow_redirects=True` (302 on api.census.gov).
- EDGAR connector: correct company_tickers URL (`www.sec.gov` not `data.sec.gov`),
  `follow_redirects=True`, lowercase frame values in source slugs.
- World Bank connector: dots replaced with dashes in indicator IDs for valid slugs.
- Amazon EDGAR: uses `RevenueFromContractWithCustomerExcludingAssessedTax` tag.

- **Dynamic TAM resolution** (`POST /resolve`) — Claude parses natural
  language queries into lens + primitives, Exa deep-searches for real
  market data, evaluator computes TAM, streams SSE events showing chain
  of thought. Frontend `ResolveView` renders steps as they arrive.
- **5 new verticals** seeded: GTM ops ($2.1B), midmarket SaaS ($84B),
  P&C payments ($1B), workplace consolidation ($12.75B), software-eng
  productivity ($3.9B). 10 new primitives, 3 new frameworks (L4/L5/L6).
- **Exa data sourcing script** (`scripts/exa_source_lookup.py`) — verifies
  primitive values against real web sources. BLS headcounts corrected.
- **API catalog** (`docs/11-api-catalog.md`) — 50+ APIs researched across
  10 categories with auth, free tiers, Python SDKs, integration priority.
- **Comprehensive test suite** — 47 → 110 tests (all-concepts evaluation,
  enrichment verification, full API endpoint coverage, data validation).
- **Frontend deployed to Vercel** — live at
  [strata-pied-three.vercel.app](https://strata-pied-three.vercel.app).
  ReactQueryDevtools switched to `next/dynamic` with dev-only guard
  (`bundle-defer-third-party`).
- GitHub repo description, homepage URL, and topics updated.

### Fixed
- `InputUsed` enriched with `value`, `name`, `unit` from evaluator —
  primitive cards now show actual data instead of role names.
- `TAMTarget.concept_name` populated — build heading shows full name.
- Range display (min–max) added under triangulated midpoint.
- Target card in ScenarioGraph shows concept name, not slug.
- `.gitignore` `/build/` scoped to root — no longer ignores `web/src/app/build/`.
- LineageGraph React 19 refs-in-render lint errors fixed.

### Changed
- BLS software developer headcount corrected: 4.4M → 2.18M (Exa-verified).
- BLS sales rep headcount corrected: 4.6M → 1.46M (Exa-verified).

- **`feat(v0.2)`: lens-aware concept end-to-end on `doc-gen-pc-insurance`.**
  First vertical slice of the Strata data layer — Pydantic models (Unit, Geo,
  Source with the 9-tier enum incl. `analyst-paraphrase`, AtomicPrimitive,
  CompositePrimitive, Concept with Q39 `analysis_lens` + modifiers,
  Framework with `lens` tag + role-tagged inputs + variants, Annotation per
  E3, TAMOutput scenario tree) in `backend/src/strata/models/`. YAML loader +
  in-memory `Registry` (`backend/src/strata/{loader,registry}.py`). Three-layer
  validator pipeline (`backend/src/strata/validator/`): structural (slug
  uniqueness) → semantic (snapshot-hash format, `as_of` not in the future,
  Q15 no-scalar-defaults, Q40 paraphrase ≤ 280 chars / reviewer / publisher)
  → cross-record (concept↔primitive linkage, framework `applicable_to`,
  Q39 lens-tag agreement, 30%-overlap warning between primary/secondary
  scenarios). Multiplicative evaluator that mints TAMs with content-hash-pinned
  inputs (`backend/src/strata/{evaluator,hashing}.py`). CLI wired:
  `strata validate <data-dir>` and `strata size <concept-slug>`.
- `data/` seed YAML for concept #1 — `doc-gen-pc-insurance`
  (`analysis_lens.primary: cost_efficiency, secondary: revenue_generation`),
  four atomic primitives (`naic-active-pc-carriers-2024`,
  `bls-pc-claims-adjusters-headcount`, `pc-saas-spend-per-carrier-2024`
  exercising the new Q40 `analyst-paraphrase` tier, and
  `pc-claims-adjuster-cost-per-seat`), two canonical frameworks
  (`bottoms-up-cost-efficiency` lens=cost_efficiency,
  `top-down-revenue-capture` lens=revenue_generation), four source-registry
  records, and an empty `data/sources/opt_out.yaml` takedown stub.
- `backend/tests/` — 22 pytest cases covering each validator rule
  (paraphrase missing `original_publisher` / `paraphrase_reviewer` /
  `paraphrase_text`, `as_of` in future, framework scalar default, lens-tag
  mismatch, 30%-overlap warning) plus end-to-end `strata size
  doc-gen-pc-insurance` (two reproducible lens-tagged scenarios; both pin
  every input by `snapshot_sha256`; the analyst-paraphrase scenario carries
  the "verify against full text" banner).

### Changed
- `docs/`: consolidated early sketches (`01-product-layers.md`,
  `02-network-graph.md`, `03-data-model.md`) into a single new
  `docs/01-primer.md` as the conceptual on-ramp. Brainstorm decision records
  (07/08/09) preserved as the canonical schemas + decision rationale.
  Cross-links across CLAUDE.md, README.md, and the surviving docs repointed.

### Added
- `docs/07-data-layer-brainstorm.md` — decision record from the data-layer
  brainstorm (38 questions resolved, full record schemas, build sequence
  mapped to roadmap, verification plan).
- `docs/08-product-surface-brainstorm.md` — decision record from the
  product-surface brainstorm (12 UX decisions resolved, 9 surfaces specified,
  URL state model, cross-cutting interaction patterns, verification plan).
  Supersedes `02-network-graph.md` and `04-user-journey.md` for v0.3+.
- `docs/09-expert-layer-brainstorm.md` — partial decision record for the
  expert layer (5 schema decisions locked: pure-commentary annotations,
  three flat tiers, annotation field set, append-only lifecycle). All
  operational mechanics (verification, reputation algorithm, moderation,
  adversarial defenses) deliberately deferred to v0.5.
- `docs/design/brand-kit.md` — design tokens (color, type, spacing,
  radii, elevation, motion, layout) extracted verbatim from the v0.42
  standalone mockup, ready to drop into a future `tokens.css`.
- `docs/design/component-catalog.md` — annotated tour of every component
  in the v0.42 mockup (app shell, home, pyramid explorer, concept detail,
  TAM detail, ⌘K palette) with screenshot references and token bindings.
- `docs/design/captures/` — 19 screenshots of the mockup as rendered
  (full-page, per-section, per-route, modal states) used as the visual
  source of truth for the catalog.
- `docs/10-v0.2-backend-spec.md` — executable v0.2 backend roadmap
  mapping data-layer + product-surface decisions to numbered tasks,
  stack choices (Python 3.12 + uv + FastAPI + Pydantic v2 + pyright
  strict), file layout, conventions, and a verification scenario
  (P&C doc-gen TAM).

### Planned
- Primitives schema + JSON store (`data/primitives/`).
- Framework schema + first 3 reference recipes (bottoms-up GTM, top-down spend, analog/penetration).
- Network-graph prototype (pyramid layout: Qualitative / Quantitative / Industry).
- Source credibility tiering (1st-party / aggregator / analyst).

### Scaffolded (v0.2 production stack)
- **Backend ops layer:** `strata.config` (pydantic-settings, `STRATA_*` env),
  `strata.logging` (structlog), `strata.db` (SQLAlchemy 2.0 async engine +
  Base + naming convention + `session_scope` / `get_session`), `strata.api.app`
  (factory with lifespan, CORS, mounted routers), `/healthz` route.
- **Alembic** initialized (`alembic.ini` + async `env.py` reading
  `strata.config.settings.database_url` and `strata.db.base.Base.metadata`).
- **Postgres infra** wired (asyncpg driver). v0.2 data layer remains
  YAML-on-disk; Postgres mirror lands at v0.3 per Q27.
- **Frontend prod tooling:** TanStack Query (provider + sane defaults),
  Zustand (`stores/ui-store.ts`), Zod (`lib/env.ts`), Biome
  (`biome.json` — lint+format, JS/TS), ESLint slimmed to
  `next/core-web-vitals` only, Prettier scoped to md/css/yaml, Knip,
  Vitest + Testing Library + jsdom.
- **`lib/api-client.ts`** typed fetch wrapper + `ApiError`; `gen:api` script
  produces `src/lib/api-schema.d.ts` from FastAPI's `/openapi.json`.
- **Docker:** `backend/Dockerfile` (uv-based, layered, healthcheck'd) +
  `web/Dockerfile` (bun build → node runtime) + root `docker-compose.yml`
  (Postgres 16 + api + web, healthchecks, named volume).
- **`.env.example`** at repo root documenting all `STRATA_*` knobs.
- **README** Stack + Quick Start sections covering both Docker and local
  dev paths.
- **Layout: backend moved from repo root into `backend/`** for symmetry with
  `web/`. `pyproject.toml`, `uv.lock`, `src/strata/`, `alembic.ini`,
  `alembic/`, `Dockerfile` all relocated. `uv` commands now run from
  `backend/`; venv lives at `backend/.venv/`. `docker-compose.yml` build
  context updated.

### Scaffolded (v0.2 work-in-progress)
- `pyproject.toml` — Python 3.12, uv-managed, FastAPI + Pydantic v2 + Typer.
- `src/strata/` package layout (`models/`, `validator/`, `evaluator/`, `scoring/`, `api/`, `cli.py`).
- `tests/` with pytest configured, smoke test green.
- Pyright strict mode + Ruff lint/format wired in `pyproject.toml`.
- Empty `data/` directory tree (`concepts/`, `primitives/`, `composites/`, `frameworks/`, `sources/`, `annotations/`, `tams/`) staged for seed records.
- `web/` — Next.js 16 + React 19 + TS + Tailwind 4 + react-flow, bun-managed.
  Brand-kit tokens (`brand-kit.md`) dropped into `web/src/app/globals.css`,
  Geist + Geist Mono + Instrument Serif wired via `next/font`.
- Landing page (`/`) — Robinhood-density: single centered search box,
  editorial Instrument Serif headline, three try-me suggestion chips.
- Build page (`/build?q=…`) — Harvey AI-style workflow canvas:
  target → frameworks → primitives rendered with react-flow, smoothstep
  edges on a sage canvas, white canvas-cards with role chips, right-rail
  accordion (Frameworks · Independence · Lineage graph).
- `web/src/lib/api.ts` — in-memory mock API mirroring the planned FastAPI
  response shapes for the P&C doc-gen TAM. Swap point for real backend.
- `docs/design/captures/v0.3-prototype/` — playwright-cli screenshots of
  the landing and build pages for visual regression tracking.

## [0.1.0] - 2026-05-20

### Added
- Apache-2.0 license.
- Initial `README.md` with project thesis and product layers.
- `CLAUDE.md` with codebase conventions and current state.
- `docs/` tree:
  - `00-vision.md` — core thesis and why now.
  - `01-product-layers.md` — Primitives, Frameworks, Expert layer.
  - `02-network-graph.md` — interactive pyramid graph spec.
  - `03-data-model.md` — schemas for primitives, sources, frameworks, annotations.
  - `04-user-journey.md` — P&C doc-gen worked example.
  - `05-roadmap.md` — phases from v0.1 → v1.0.
  - `06-glossary.md` — TAM, primitive, framework, credibility tier, etc.
- `VERSION` file pinned to `0.1.0`.
- Empty `data/` directory reserved for primitives, frameworks, annotations.

[Unreleased]: https://github.com/ArkashJ/Strata/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ArkashJ/Strata/releases/tag/v0.1.0
