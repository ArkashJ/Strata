# Strata

> **Provisional codename.** A curated library of market-sizing primitives,
> frameworks, and expert annotations — rendered as an interactive pyramid
> graph that lets VCs and operators build credible TAMs without buying a $20k report.

[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen)](https://strata-pied-three.vercel.app)
[![License: Proprietary](https://img.shields.io/badge/license-proprietary-red.svg)](LICENSE)
![Version](https://img.shields.io/badge/version-0.7.0-informational)
![Status](https://img.shields.io/badge/status-beta-brightgreen)

![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-E92063?logo=pydantic&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?logo=sqlalchemy&logoColor=white)
![Postgres](https://img.shields.io/badge/Postgres-16-4169E1?logo=postgresql&logoColor=white)
![uv](https://img.shields.io/badge/uv-DE5FE9?logo=uv&logoColor=white)
&nbsp;
![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=next.js&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![TanStack Query](https://img.shields.io/badge/TanStack_Query-FF4154?logo=reactquery&logoColor=white)
![Zustand](https://img.shields.io/badge/Zustand-443E38)
![Zod](https://img.shields.io/badge/Zod-3068B7?logo=zod&logoColor=white)
![Biome](https://img.shields.io/badge/Biome-60A5FA?logo=biome&logoColor=white)
![bun](https://img.shields.io/badge/bun-FBF0DF?logo=bun&logoColor=black)
&nbsp;
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)

---

## The one-line thesis

Market sizing today is gated by expensive low-quality reports, when in reality the
underlying exercise is just **credible primitives + a transparent framework**. Make
both sourced, transparent, and rigorously curated, and you eat the bottom 80% of the
IBISWorld / Statista / Gartner-lite use case.

## What this is

A tool for VCs (and operators) to **cut through the noise**:

1. Pick a segment in a clickable **pyramid graph** — Qualitative ↓ Quantitative ↓ Industry.
2. The graph surfaces **frameworks** that fit the segment.
3. Each framework is pre-populated with **primitives** from the library.
4. Adjust assumptions, see the range, export the build with a full source trail.
5. Optionally read **expert annotations** that flag blind spots.

See [`docs/00-vision.md`](docs/00-vision.md) for the full thesis.

## Connect to Claude (MCP)

Strata ships a **read-only MCP server** so any agent (Claude Desktop, IDE
assistants) can pull **sourced, hash-pinned** market numbers — every figure
carries its source URL, tier, and `snapshot_sha256`. Five tools:
`search_concepts`, `get_primitive`, `list_frameworks`, `size_tam`,
`resolve_market`.

```sh
# local (stdio)
claude mcp add strata -- uv run --directory /ABS/PATH/backend strata-mcp --stdio
# hosted (HTTP, mounted at /mcp on the API)
claude mcp add --transport http strata https://<your-strata-host>/mcp
```

```
agent ── tools/call ──> Strata MCP ──> registry + evaluator (read-only)
                                   └──> sourced TAM tree (url · tier · sha256)
```

## The three product layers

| Layer | Name | What's in it |
|------:|------|--------------|
| 1 | **Primitives Library** | Atomic, sourced figures (e.g. "# of GTM professionals in N. America", "avg IT spend per SMB"). Each has a value, date, methodology, and credibility-tiered source. |
| 2 | **Framework Library** | Reusable, parameterized recipes for going primitives → TAM. Organized by function (Finance, GTM, Ops...) and approach (top-down, bottoms-up, comparable, analog). |
| 3 | **Expert Layer** | Comments, annotations, and alternative framings on top of figures and frameworks. Reputation-weighted. |

Full breakdown: [`docs/01-primer.md`](docs/01-primer.md).

## The pyramid graph

The Qualitative / Quantitative / Industry pyramid in the sketch:

```
                       ┌──────────────────────┐
                       │   TAM for GTM market │
                       └──────────┬───────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        ▼                         ▼                         ▼
   ┌─────────┐               ┌─────────┐               ┌─────────┐
   │ B2C/B2B │               │  Ent.   │               │   ...   │   ← top tier
   └────┬────┘               │ sales/  │               └────┬────┘
        │                    │ defense │                    │
   ┌────┴────┐               └────┬────┘                    │
   │ GTM for │               ┌────┴────┐                ┌───┴───┐
   │ engineers│              │Midmarket│                │       │  ← middle tier
   └────┬────┘               └────┬────┘                └───┬───┘
        │                         │                        │
   ┌────┴─────┐             ┌─────┴──────┐           ┌─────┴──────┐
   │ GTM for  │             │   SMB /    │           │  industry  │  ← base tier
   │ bio tools│             │  consumer  │           │   slices   │
   └──────────┘             └────────────┘           └────────────┘
     Qualitative              Quantitative              Industry
```

Each node is a **constraint** — clicking expands children, narrows the segment, and
re-suggests frameworks. Topology in [`docs/01-primer.md`](docs/01-primer.md);
full UX surface in [`docs/08-product-surface-brainstorm.md`](docs/08-product-surface-brainstorm.md).

## Status

**Beta — v0.3.0.** Question → sourced number → deployable, self-refreshing service, end to end.

```
┌─────────────────────────────────────────────────────────────┐
│                     HOW IT WORKS                             │
│                                                              │
│  1. You type a market     "AI code review tools TAM"        │
│                                    │                         │
│  2. AI parses the query    lens: productivity_uplift         │
│     into sizing params     need: developer count + tool cost │
│                                    │                         │
│  3. Exa searches the web   BLS: 28.7M developers            │
│     for real data           Cledara: $4,500/dev/yr           │
│                                    │                         │
│  4. Framework computes     28.7M × $4,500 = $129.2B TAM     │
│     the scenario tree      with every source cited           │
│                                    │                         │
│  5. Graph renders with     ReactFlow: Target → Frameworks   │
│     clickable sources               → Primitive cards       │
└─────────────────────────────────────────────────────────────┘
```

**What works today:**
- **Static builds** — 6 pre-seeded concepts across 5 of 6 TAM lenses, each with
  real values, enriched primitive cards, min-max range display
- **Dynamic queries** — type ANY market → Claude parses → Exa finds real data →
  evaluates framework → streams chain of thought via SSE
- **Edit and recompute (PR #55)** — on a sized TAM, click a number in the graph to
  set a **what-if value** or **swap in a different sourced figure**; the whole TAM
  recomputes live. What-if values are clearly flagged and never saved as sourced
  data. Result charts (method comparison + input composition) render alongside.

  ```
  click a number  ->  set what-if / swap source  ->  TAM recomputes  ->  share the link
                                                      (what-if flagged)
  ```
- **Dashboard + activity log (PR #55, optional sign-in)** — `/dashboard` shows
  library counts, your recent builds, and an audit feed. Sign-in (Clerk) is off
  until you add keys; the app runs the same without them.
- **22 data connectors** — BLS, FRED, Census, EDGAR, World Bank, Kalshi, OECD,
  Eurostat, UN Comtrade, FDIC, CMS, EIA, USDA NASS, FAA, openFDA, plus 7 added
  in v0.3 (Alpha Vantage, Nasdaq Data Link, yfinance, Reddit, GitHub, Stack
  Exchange, Twitter/X). All typed clients with disk caching, YAML converters,
  and a CapabilitySpec manifest so the router knows what each one can answer.
- **307 atomic primitives** from live API queries across all six lenses + 87 sources
- **`strata goal "<query>"` CLI** — ask free-form TAM questions from the terminal.
  Maps to known data first, then **live connector calls** (the router picks a
  connector method, `call_and_convert` fetches + writes a sourced primitive),
  then Claude+Exa fallback. See [`docs/13-strata-goal-cli.md`](docs/13-strata-goal-cli.md).
- **`strata ingest run|status|refresh`** — populate and refresh the data bank in
  bulk from a declarative `ingest-manifest.yaml`; key-less connectors are skipped,
  and `refresh` rewrites only numbers whose source snapshot changed.
- **Pyramid graph (`/graph`)** — read-only 3-axis explorer (Qualitative ·
  Quantitative · Industry) with geo/time filter chips and click-to-narrow.
- **Deploy-ready** — one-command boot (migrate → seed → serve), a PR CI gate,
  and a weekly cron that opens a PR with refreshed data.
- **400 backend tests** passing; type/lint clean on shipping code (`src/`) and
  enforced in CI; frontend build clean on bun.
- **50+ APIs cataloged** for integration ([`docs/11-api-catalog.md`](docs/11-api-catalog.md))

### v0.3 — ask in plain English, get a sourced TAM

The v0.3 push (PR #45) closes the "I don't know the slug" gap. Type a question,
the resolver tries the cheapest path first and only escalates when it has to.

```
┌──────────────────────────────────────────────────────────────────┐
│  strata goal "US bank deposit market size 2024"                  │
│                                                                  │
│  1. Slug resolver  — one Claude call. Matches the query to the   │
│     (free)           data bank's known concepts and primitives,  │
│                      or marks it "novel".                        │
│                                                                  │
│  2. Concept hit?   — return a ready TAM (no LLM, no network).    │
│                                                                  │
│  3. Primitive hit? — return the sourced value with a banner.     │
│                                                                  │
│  4. Connector live — router picks the right API (FDIC, EDGAR,    │
│     ($)              etc.), fetches the number, writes the       │
│                      result to ~/.strata/auto-primitives/.       │
│                                                                  │
│  5. Fallback       — Claude + Exa synthesize a TAM from web      │
│     ($$)             results. Always banner-flagged "do not      │
│                      cite without manual verification".          │
│                                                                  │
│  6. strata promote — move a curated auto-primitive into the      │
│                      committed data/primitives/ tree after the   │
│                      validator passes.                           │
└──────────────────────────────────────────────────────────────────┘
```

Why this shape:
- **Defensibility first** — registry hits never call an LLM. The expensive paths
  are last, not first.
- **No silent pollution** — auto-primitives land in your home folder, not the
  committed data bank. `strata promote` is the one path into the curated tree
  and it runs the full validator.
- **Cost-aware** — the slug resolver and router both use Anthropic's 5-minute
  prompt cache, so back-to-back queries cost ~10% of the first one.

### Data bank coverage by lens

| Lens | Primitives | Key Sources |
|------|-----------|-------------|
| L1 cost_efficiency | Employment headcounts, wages, CES industry data | BLS OES, FRED, Census CBP |
| L2 revenue_generation | Company revenues, GDP, retail sales, industry payroll | EDGAR, FRED, Census, World Bank |
| L3 latent_demand | Population (337M), internet (93.5%), mobile (109/100) | World Bank, FRED, Census |
| L4 platform_throughput | Payment co. revenues (V/MA/PYPL), banking establishments | EDGAR, Census, World Bank FDI |
| L5 bundle_consolidation | Professional services establishments, SaaS revenues | Census, EDGAR (NOW/WDAY) |
| L6 productivity_uplift | Developer counts, R&D spend ($600B), tech employment | BLS CES, Census, EDGAR frames |
| Cross-lens | 6 major GDPs, world population, inflation, unemployment | World Bank, FRED |

See [`docs/05-roadmap.md`](docs/05-roadmap.md) for phasing.

### The six TAM lenses

| # | Lens | Formula shape | Companies sized this way |
|---|------|---------------|-------------------------|
| L1 | Cost efficiency | persona × cost/persona | Harvey, Glean, Decagon |
| L2 | Revenue generation | segment × spend/segment | Brex, Rippling, Ramp |
| L3 | Latent demand | population × adoption × WTP | Uber, Duolingo (not yet built) |
| L4 | Platform throughput | volume × take rate | Stripe, Shopify, Visa |
| L5 | Bundle consolidation | total spend × consolidation rate | Notion, Linear, Monday |
| L6 | Productivity uplift | personas × gain × vendor share | GitHub Copilot, Cursor |

## Deployment

### Frontend — Vercel
[strata-pied-three.vercel.app](https://strata-pied-three.vercel.app) (auto-deploys from `main`)

Set `NEXT_PUBLIC_API_URL` in Vercel environment variables to point at the Railway API.

### Backend — Railway
Railway deploys the API + Postgres from docker-compose.yml.

**Service variables to set in Railway:**
```
STRATA_ENV=prod
STRATA_LOG_JSON=true
STRATA_DATABASE_URL=${{Postgres.DATABASE_URL}}
STRATA_CORS_ORIGINS=["https://strata-pied-three.vercel.app"]
STRATA_BLS_API_KEY=<your key>
STRATA_FRED_API_KEY=<your key>
STRATA_CENSUS_API_KEY=<your key>
```

**After first deploy, seed the database:**
```sh
# Railway CLI or in the service shell
alembic upgrade head
python -m strata.cli db seed -d /app/data
```

The API auto-discovers data from Postgres. YAML files are baked into the
Docker image as seed data — `strata db seed` loads them once, then Postgres
is the source of truth for all reads.

### Architecture at scale (1K concurrent users)

```
Vercel (frontend CDN)
       │ HTTPS
       ▼
Railway (FastAPI + Postgres)
  ┌─ FastAPI ──────────────────┐
  │  Registry loads from DB    │  ← in-memory cache, TTL refresh
  │  Connectors refresh data   │  ← background jobs (planned)
  └────────────┬───────────────┘
               │ asyncpg
  ┌─ Postgres ─┴───────────────┐
  │  primitives (307+ rows)    │  GIN index on JSONB (unit, geo, source)
  │  sources (87+ rows)        │  B-tree on slug, concept_slug, as_of
  │  concepts (6 rows)         │  
  │  frameworks (5 rows)       │  
  └────────────────────────────┘
```

YAML files remain in the repo for:
- Version-controlled seed data
- Local development without Postgres
- CI test fixtures

## Stack

### 🐍 Backend — `backend/`
- **Python 3.12** managed by **uv**.
- **FastAPI** + **Pydantic v2** + **pydantic-settings** for HTTP and config.
- **SQLAlchemy 2.0** (async) + **asyncpg** + **Alembic** migrations.
  Postgres ORM models live in `db/models.py` — primitives, sources,
  concepts, frameworks with JSONB columns and GIN indexes.
- **structlog** for structured logs (JSON in prod, console in dev).
- **OpenAPI** docs at `/docs` (Swagger) and `/redoc`, schema at `/openapi.json`.
- **pyright strict** + **ruff** lint/format; **pytest** + **httpx** for tests.
- **Typer** CLI exposed as the `strata` entry point.

### ⚛️ Frontend — `web/`
- **Next.js 16** + **React 19** + **TypeScript 5**, managed by **bun**.
- **Tailwind CSS 4** with CSS-variable design tokens.
- **TanStack Query** (server state) + **Zustand** (client UI state) +
  **Zod** (validation + env).
- **ReactFlow** for the pyramid + scenario trees, **vis-network** for the
  related-entities modal, **Recharts** for TAM charts.
- **App shell** — a persistent left sidebar + ⌘K command palette wrap every
  route (`/`, `/c`, `/p`, `/f`, `/build`, `/tam`, `/graph`, `/browse`,
  `/contribute`), all reading live backend data (no mock).
- **openapi-typescript** generates a typed API client from the running
  FastAPI's `/openapi.json` (run `bun run gen:api`).
- **Biome** owns JS/TS lint + format. **ESLint** runs only `next/core-web-vitals`.
  **Prettier** formats md/css/yaml only. **Knip** finds dead code.
- **Vitest** + **Testing Library** for unit/component tests.

## 🚀 Quick start

### 🐳 With Docker (recommended)
Boots Postgres + API + web with one command from the repo root.

```sh
cp .env.example .env        # optional — compose injects its own env
docker compose up --build
```

Then seed the database and verify:

```sh
cd backend
uv run alembic upgrade head       # create tables
uv run strata db seed -d ../data  # load 307 primitives into Postgres
uv run strata db stats            # verify row counts
uv run strata test-connectors     # smoke-test all 5 APIs
```

Then visit:
- 🌐 web: <http://localhost:3000>
- 📖 API docs: <http://localhost:8000/docs>
- ❤️  health: <http://localhost:8000/healthz>

### 🛠 Local dev (no Docker)

**🐍 Backend** — needs Python 3.12 + [`uv`](https://docs.astral.sh/uv/).
Run every `uv` command from `backend/`; the venv lives at `backend/.venv/`.

```sh
cd backend
uv sync --extra dev
cp ../.env.example ../.env
# start Postgres however you like (brew, pg.app, docker); ensure the DSN matches
uv run uvicorn strata.api.app:app --reload --port 8000
```

Database setup (still from `backend/`):

```sh
uv run alembic revision --autogenerate -m "init"  # generate migration
uv run alembic upgrade head                        # create tables
uv run strata db seed -d ../data                   # load 307 primitives → Postgres
uv run strata db stats                             # verify: primitives 307, sources 87
```

CLI commands:

```sh
uv run strata stats -d ../data      # data bank counts (YAML)
uv run strata test-connectors       # live smoke test all 5 APIs
uv run strata validate ../data      # three-layer validator
uv run strata size doc-gen-pc-insurance -d ../data  # evaluate a concept
uv run strata goal "US bank deposits 2024" -d ../data  # v0.3 free-form TAM
uv run strata promote fdic-deposits-us-2024 -d ../data # curate auto-primitive
```

Tests + checks:

```sh
uv run pytest                # 167 tests (models, API, connectors, evaluator, resolve)
uv run ruff check .
uv run pyright
```

**⚛️ Frontend** — needs [`bun`](https://bun.com/):

```sh
cd web
bun install
bun run dev                 # http://localhost:3000
bun run gen:api             # regenerate TS types from running API
bun run check               # typecheck + biome + eslint + knip
bun run test
```

## 📁 Repository layout

```
.
├── README.md · CHANGELOG.md · CLAUDE.md · LICENSE · VERSION
├── docker-compose.yml            Postgres + api + web
├── .env.example                  STRATA_* env documentation
│
├── backend/                      Python 3.12 service (run `uv` from here)
│   ├── pyproject.toml            uv-managed, pyright strict, ruff
│   ├── src/strata/
│   │   ├── api/routes/           10 endpoints: healthz, concepts, primitives,
│   │   │                         frameworks, build, tam, resolve (SSE)
│   │   ├── connectors/           6 typed API clients (BLS, FRED, Census,
│   │   │                         EDGAR, World Bank, Kalshi) — 4,650+ lines
│   │   ├── db/models.py          ORM: PrimitiveRow, SourceRow, ConceptRow,
│   │   │                         FrameworkRow (JSONB + GIN indexes)
│   │   ├── db/sync.py            YAML → Postgres upsert (idempotent)
│   │   ├── models/               6 Pydantic record types + Unit, Geo, Source
│   │   ├── evaluator/engine.py   size_concept() → TAMOutput (multiplicative)
│   │   ├── validator/            structural + semantic + cross-record
│   │   ├── scoring/              independence + disagreement
│   │   ├── loader.py             YAML → Pydantic via kind discriminator
│   │   ├── registry.py           in-memory slug-keyed store
│   │   └── cli.py                strata: version, validate, size, stats,
│   │                             test-connectors, db seed, db stats
│   ├── scripts/
│   │   ├── populate_data_bank.py       initial 29-query seeding
│   │   └── populate_lens_primitives.py 86-query lens-aligned expansion
│   └── tests/                    167 tests (models, API, connectors, evaluator)
│
├── web/                          Next.js 16 + React 19 + bun
│   └── src/
│       ├── app/page.tsx          Landing — search box + suggestion chips
│       ├── app/build/            Build view — ReactFlow graph + right rail
│       ├── components/
│       │   ├── ScenarioGraph.tsx  Target → Framework → Primitive cards
│       │   ├── ResolveView.tsx   SSE streaming chain-of-thought
│       │   └── LineageGraph.tsx  Force-directed network
│       └── lib/
│           ├── schemas.ts        Zod schemas matching backend
│           ├── queries.ts        TanStack Query hooks per endpoint
│           └── format.ts         USD + compact number formatting
│
├── data/                         YAML seed data (syncs to Postgres)
│   ├── concepts/    30 files    (6 originals + 3 hand-crafted + 21 portfolio)
│   ├── primitives/ 350+ files   (regulator + analyst-paraphrase + community-modeled)
│   ├── frameworks/   5 files    (sizing formulas with per-portfolio variants)
│   └── sources/     87 files    (citation records, SHA256-pinned)
│
├── portfolios/                   Portfolio catalogs consumed by the TAM pipeline
│   └── tam-77-sample.yaml       (24-company sample portfolio; add yours alongside)
│
└── docs/                         Design docs + decision records
    ├── 07-data-layer-brainstorm  Q1-Q40 schema decisions (LOAD BEARING)
    ├── 08-product-surface        U1-U12 UX decisions (LOAD BEARING)
    ├── 11-api-catalog            50+ APIs for market sizing
    ├── 12-portfolio-tam-pipeline 5-step guide to sizing any portfolio
    ├── tam-77-corrected.md       Generated v2 TAMs for the 24-company sample
    ├── CLIENT_PLATFORM_GUIDE.md  Customer-facing platform walkthrough
    └── superpowers/specs/        Platform evolution + TAM methodology specs
```

## License

Proprietary — all rights reserved. See [`LICENSE`](LICENSE). This is not
open-source software: the source, schema, and data may not be used, copied,
modified, or distributed without prior written permission from the owner.

## Contributing

Not yet open for external contributions — schema is still landing. Once v0.2.0
ships the primitive schema, contribution guidelines will follow.
