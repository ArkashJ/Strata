# Strata

> **Provisional codename.** A community-curated, open-source library of market-sizing
> primitives, frameworks, and expert annotations — rendered as an interactive pyramid
> graph that lets VCs and operators build credible TAMs without buying a $20k report.

[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen)](https://strata-pied-three.vercel.app)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
![Version](https://img.shields.io/badge/version-0.2.0a0-informational)
![Status](https://img.shields.io/badge/status-pre--alpha-orange)

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
both free, sourced, and community-curated, and you eat the bottom 80% of the
IBISWorld / Statista / Gartner-lite use case.

## What this is

A tool for VCs (and operators) to **cut through the noise**:

1. Pick a segment in a clickable **pyramid graph** — Qualitative ↓ Quantitative ↓ Industry.
2. The graph surfaces **frameworks** that fit the segment.
3. Each framework is pre-populated with **primitives** from the library.
4. Adjust assumptions, see the range, export the build with a full source trail.
5. Optionally read **expert annotations** that flag blind spots.

See [`docs/00-vision.md`](docs/00-vision.md) for the full thesis.

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

**Pre-alpha — v0.2.0a0.** Schemas locked, scaffolding in place, no business
logic implemented yet. v0.1.0 was a thesis + spec snapshot; v0.2 wires the
backend + frontend skeletons. See [`docs/05-roadmap.md`](docs/05-roadmap.md)
for phasing.

## Deployment

**Frontend:** [strata-pied-three.vercel.app](https://strata-pied-three.vercel.app) (Vercel, auto-deploys from `main`)

The frontend deploys as a static Next.js app. The backend API is not yet deployed — pages that fetch data will show loading states until a backend is available. Set `NEXT_PUBLIC_API_URL` in Vercel environment variables when the API goes live.

To deploy manually:

```sh
cd web
vercel deploy --prod --scope arkashjs-projects
```

## Stack

### 🐍 Backend — `backend/`
- **Python 3.12** managed by **uv**.
- **FastAPI** + **Pydantic v2** + **pydantic-settings** for HTTP and config.
- **SQLAlchemy 2.0** (async) + **asyncpg** + **Alembic** migrations.
  *(Postgres mirror lands at v0.3 per `docs/07-data-layer-brainstorm.md` Q27;
  infra is wired so the cutover is just adding models.)*
- **structlog** for structured logs (JSON in prod, console in dev).
- **OpenAPI** docs at `/docs` (Swagger) and `/redoc`, schema at `/openapi.json`.
- **pyright strict** + **ruff** lint/format; **pytest** + **httpx** for tests.
- **Typer** CLI exposed as the `strata` entry point.

### ⚛️ Frontend — `web/`
- **Next.js 16** + **React 19** + **TypeScript 5**, managed by **bun**.
- **Tailwind CSS 4** with CSS-variable design tokens.
- **TanStack Query** (server state) + **Zustand** (client UI state) +
  **Zod** (validation + env).
- **ReactFlow** for the pyramid network graph.
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

Migrations (still from `backend/`):

```sh
uv run alembic revision --autogenerate -m "init"
uv run alembic upgrade head
```

Tests + checks:

```sh
uv run pytest
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
├── 📄 README.md · CHANGELOG.md · CLAUDE.md · LICENSE · VERSION
├── 🐳 docker-compose.yml         Postgres + api + web
├── 🔐 .env.example               STRATA_* env documentation
│
├── 🐍 backend/                   Python service (run `uv` from here)
│   ├── pyproject.toml            uv-managed, pyright strict, ruff
│   ├── uv.lock
│   ├── alembic.ini · alembic/    migration config + env + versions
│   ├── Dockerfile                uv-based, layered, healthcheck'd
│   └── src/strata/
│       ├── api/                  FastAPI app + routes (/healthz live)
│       ├── config.py             pydantic-settings (STRATA_* env)
│       ├── logging.py            structlog
│       ├── db/                   SQLAlchemy 2.0 async engine + Base
│       ├── models/ validator/ evaluator/ scoring/   (v0.3 work)
│       └── cli.py                `strata` Typer entry point
│
├── ⚛️  web/                       Next.js 16 + React 19 + bun
│   ├── biome.json                lint + format (JS/TS)
│   ├── eslint.config.mjs         next/core-web-vitals only
│   ├── .prettierrc.json          md/css/yaml only
│   ├── knip.json                 dead-code detection
│   ├── vitest.config.ts          unit/component tests
│   ├── Dockerfile                bun build → node runtime
│   └── src/
│       ├── app/                  App Router pages
│       ├── components/           UI components
│       ├── stores/               Zustand client state
│       └── lib/                  env, query-client, api-client, providers
│
├── 📊 data/                       YAML records (primitives/frameworks/concepts/...)
└── 📚 docs/                       design docs + decision records
```

## License

Apache License 2.0 — see [`LICENSE`](LICENSE). Choice of license is deliberate:
patent-grant + permissive, so research orgs, funds, and vendors can adopt the
schema and seed the library without fear of relicensing traps.

## Contributing

Not yet open for external contributions — schema is still landing. Once v0.2.0
ships the primitive schema, contribution guidelines will follow.
