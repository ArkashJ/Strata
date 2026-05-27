# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `docs/sample-queries.md` — 77 realistic TAM test queries anchored to real
  diligence-pipeline companies (24 companies), tagged by sizing-framework family,
  with adjacent-market disambiguation cases. Intended as an end-to-end test set
  for framework selection and source attribution.

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
