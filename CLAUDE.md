# CLAUDE.md

Notes for AI assistants (and future-me) working in this repo.

---

## What this project is

Codename **Strata**. Open-source, community-curated market-sizing engine for
VCs and operators. Replaces IBISWorld / Statista / Gartner-lite reports by
exposing the **primitives** (atomic sourced numbers) and the **frameworks**
(parameterized recipes that combine them into TAM) — plus an **expert layer**
for community correction. Audience wants defensible numbers fast, not academic
rigor.

Full thesis: [`docs/00-vision.md`](docs/00-vision.md).

---

## Repo state (as of 2026-05-30)

- **Version:** `0.4.0` (beta). `VERSION` + `pyproject` pinned; tags follow
  `vX.Y.Z`. v0.4 = frontend v0.42 parity + light/dark theme + live home TAMs +
  honest resolver fallback (PR #54).
- **In flight (PR #55 — "Strata Live"):** the `/build` page is now **interactive**.
  Clicking a primitive graph node opens an override panel to set a **what-if value**
  or **swap a sourced primitive**; the TAM recomputes live via `POST /build/recompute`
  (override-aware evaluator — `EvalOverrides` threaded through `size_concept`; unit-
  checked; what-if scenarios carry a `user_override` banner and never persist as
  primitives, Q20). Adds result charts (method-comparison + composition), an optional
  **Clerk** sign-in + `/dashboard` (graceful no-op without keys — prod build stays
  green), an `audit_events` table + `GET /audit`, and an animated landing page.
  **Prod resolver is live on the paid Anthropic SDK** (`STRATA_LLM_BACKEND=anthropic`
  on Railway; `/healthz/llm` → `anthropic-sdk`, available). 453 backend tests pass.
- **Phase:** Schemas locked, **backend fully functional**, frontend PoC working,
  dynamic query resolution proven end-to-end. **v0.3 shipped (PRs #46–#50):**
  connector dispatch (`connectors/_dispatch.py` — `call_and_convert` turns a
  router decision into a validated primitive), the resolver's live connector
  step wired (`resolver/pipeline.py` step 3 → dispatch → `writer.upsert_primitive`),
  the ingest orchestrator + freshness CLI (`strata/ingest/`, `strata ingest
  run|status|refresh`, manifest at repo-root `ingest-manifest.yaml`), the
  read-only pyramid graph (`web/src/app/graph/`), and deploy hardening
  (entrypoint, CI gate, weekly refresh cron, DB pool config). 400 backend
  tests; CI type/lint gate scoped to `src/` (zero errors there; `tests/`
  strict-mode debt tracked as a follow-up).
- **Backend (`backend/src/strata/`):** All business logic implemented —
  models, loader, registry, validators, evaluator, scoring, 10 API routes
  (including `POST /resolve` for dynamic TAM resolution via Claude + Exa),
  plus the **connectors** ingest layer (15 connectors: BLS, FRED, Census,
  EDGAR, World Bank, Kalshi, **OECD, Eurostat, UN Comtrade, FDIC, CMS,
  EIA, USDA NASS, FAA, openFDA** — all typed clients, disk cache, Strata
  YAML converters, ~170 query methods). 167+ tests passing, pyright strict
  clean, ruff clean.
  `/resolve` hardened: async event loop (asyncio.to_thread), no internal
  error leaks, JSON parse safety, client singletons, specific exception
  handling.
- **Frontend (`web/`):** Next.js 16 + React 19, rebuilt to **v0.42 parity**
  (PR #54) and wired 100% to the live backend — mock data removed. A persistent
  app shell (left sidebar + ⌘K command palette + live library counts) wraps
  every route: home (Featured TAMs sized live from `/build`, no invented
  figures), `/c` `/p` `/f` list + detail (the concept "disagreement view"),
  `/build` workhorse, `/tam/<hash>` artifact (export URL/Markdown/PDF),
  `/graph` pyramid, `/browse`. **Contribute surfaces removed** (route + top-bar
  button + COMMUNITY sidebar group) — they land with the v0.5 expert layer.
  **Working light/dark theme** via `ThemeToggle` (`useSyncExternalStore` theme
  store + `html.dark` tokens + no-flash script; light default, persisted under
  `strata-theme`). `ResolveView` streams the resolver's chain-of-thought; when
  the LLM backend is unavailable it fails honestly and offers curated concepts.
  Backed by **Claude Code** (SDK only on `STRATA_LLM_BACKEND=anthropic`).
- **Data (`data/`):** **30 concepts** (6 originals + 3 hand-crafted worked
  examples + 21 portfolio-pipeline-generated), **350+ atomic primitives**
  from 5 connector APIs + Exa-sourced analyst-paraphrase + community-modeled
  multipliers, 5 frameworks with 30 variants, 87 sources. All validate clean.
- **Portfolios (`portfolios/`):** sibling directory to `data/` holding
  portfolio catalogs the TAM pipeline consumes. One file at v0.2
  (`portfolios/tam-77-sample.yaml`); add a new YAML here per fund / strategy
  desk. Kept outside `data/` so the registry loader does not try to parse
  them as records.
- **TAM-77 pipeline:** `backend/scripts/tam_77_pipeline.py` is the
  portfolio-agnostic Claude-driven classifier that threads each company
  through the primitive/framework/evaluator DAG and writes YAML artifacts.
  Pattern documented in `docs/12-portfolio-tam-pipeline-howto.md`; outputs
  for the TAM-77 sample portfolio in `docs/tam-77-corrected.md`.
- **Tests:** 310 passing in `backend/tests/` (including 6 v2 acceptance
  tests in `test_tam_v2_acceptance.py`, 7 /resolve SSE tests, 168
  connector tests).
- **Design spec:** `docs/superpowers/specs/2026-05-25-strata-platform-evolution-design.md`
  covers 5 gaps (interactive wiring, ingest pipeline, auth, contribution schema,
  data connectors) across 6 sprints. Critic-reviewed and corrected.
- License: Apache-2.0.

### Architecture flow

```
User types market query
        │
        ▼
┌─ FRONTEND (Next.js 16) ────────────────────────────┐
│  Landing (/) → Build (/build?q=)                    │
│  If concept in registry → static ReactFlow graph    │
│  If not → ResolveView streams SSE from /resolve     │
└────────────────────────┬────────────────────────────┘
                         │ HTTP / SSE
┌─ BACKEND (FastAPI) ────┴────────────────────────────┐
│  /c /p /f /build/{slug}  → Registry → Evaluator    │
│  POST /resolve           → Claude parse → Exa search│
│                            → evaluate → SSE stream  │
│  Evaluator: multiply all inputs → scenario tree     │
└────────────────────────┬────────────────────────────┘
                         │
┌─ DATA STORE ────────────────────────────────────────┐
│  Production: Postgres (primary, GIN+B-tree indexed) │
│  Local dev:  YAML on disk → `strata db seed` → PG  │
│  6 concepts · 307 primitives · 5 frameworks         │
│  Each primitive: value + unit + source + sha256 pin │
└────────────────────────┬────────────────────────────┘
                         │ populated by
┌─ CONNECTORS (ingest) ──┴────────────────────────────┐
│  BLSClient · FREDClient · CensusClient              │
│  EDGARClient · WorldBankClient · KalshiClient       │
│  OECDClient · EurostatClient · ComtradeClient       │
│  FDICClient · CMSClient · EIAClient                 │
│  NASSClient · FAAClient · OpenFDAClient             │
│  Each: typed → disk-cached → SHA256-pinned → DB     │
└─────────────────────────────────────────────────────┘
```

### Six analysis lenses (Q39)

| Lens | Math shape | Example |
|------|-----------|---------|
| L1 `cost_efficiency` | persona × cost | Harvey, Glean |
| L2 `revenue_generation` | segment × spend | Brex, Rippling |
| L3 `latent_demand` | population × adoption × WTP | Uber (not built yet) |
| L4 `platform_throughput` | volume × take_rate | Stripe, Visa |
| L5 `bundle_consolidation` | total_spend × consolidation | Notion, Linear |
| L6 `productivity_uplift` | personas × value_split | Copilot, Cursor |

### Phase strategy (Approach C — progressive decentralization)

```
Phase 1 (now):  Internal tool — CLI + API + ingest (FRED/BLS/EDGAR)
Phase 2:        Paid product — API keys + metering + subscriptions
Phase 3:        Community — contributor profiles + attribution + royalties
Phase 4:        Optional chain anchor — Base/Solana hash anchoring
```

---

## Stack

### Backend (Python)
- **Python 3.12** + **uv** package manager.
- **Pydantic v2** for schemas; **pyright strict** mode (zero errors required).
- **FastAPI** for HTTP; **Typer** for CLI (`strata` entry point).
- **ruff** (100-char lines, py312, E/W/F/I/B/UP/SIM/RUF) for lint/format.
- **pytest** + **httpx** + **pytest-asyncio** for tests.
- **YAML files on disk** are the source of truth at v0.2 (no DB yet; Postgres
  mirror lands at v0.3 per `docs/07-data-layer-brainstorm.md` Q27).
- **Connectors** (`connectors/`) — typed API clients that ingest external data
  into the data bank. All follow a 6-layer pattern: enums → TypedDicts →
  frozen dataclasses → unified response → disk cache → client + YAML converters.
  | Connector | Lines | Source Tier | Key Data |
  |-----------|-------|-------------|----------|
  | BLS | 747 | regulator | Employment, wages, CPI, JOLTS |
  | FRED | 752 | regulator | GDP, rates, money supply, consumption |
  | Census | 789 | regulator | Industry stats by NAICS (CBP/SUSB) |
  | EDGAR | 856 | regulator | Company financials, XBRL frames |
  | World Bank | 613 | aggregator | Global GDP, population, adoption |
  | Kalshi | 995 | prediction_market | Event contracts, probabilities |
  | OECD | 1187 | aggregator | 38-country GDP, labour, trade, health, R&D |
  | Eurostat | 957 | regulator | EU sector stats, demographics, energy |
  | UN Comtrade | 1050 | aggregator | Bilateral trade flows by HS code |
  | FDIC | 1208 | regulator | Bank financials, institutions, failures |
  | CMS | 1229 | regulator | Medicare/Medicaid enrollment, spending |
  | EIA | 1187 | regulator | Electricity, petroleum, gas, coal, renewables |
  | USDA NASS | 1145 | regulator | Crop/livestock production, prices |
  | FAA | 994 | regulator | Airports, passengers, aviation data |
  | openFDA | 1218 | regulator | Drug events, device 510k/PMA, recalls |
  See `backend/src/strata/connectors/CLAUDE.md`.

### Frontend (`web/`)
- **Next.js 16.2.6** + **React 19.2.4**.
- **Tailwind CSS 4** with CSS-variable design tokens (`--bg-0`, `--fg-1`,
  `--accent`, ...) wired in `globals.css` / `layout.tsx`.
- **ReactFlow** for the pyramid network graph + scenario tree visualization.
- Geist Sans/Mono + Instrument Serif fonts.
- **Note:** user's long-term preferred web stack (per memory) is bun + biome +
  knip + tanstack + zod + zustand — current scaffold predates that direction;
  confirm before introducing tooling changes.

---

## The five-layer data model

Locked across `docs/07-data-layer-brainstorm.md` (Q1–Q38). Layers:

```
Concept                  (Q9, Q10)   — curated identity object, narrow-scope
  ↓ measured-by
Atomic Primitive         (Q2)        — one source, one number, reproducible
  ↓ bundled-into
Composite Primitive      (Q2, Q3)    — same-unit set ops (union/filter/restrict)
  ↓ consumed-by
Framework                (Q3, Q15–Q18) — unit-crossing arithmetic, no scalar defaults
  ↓ emits
TAM Output               (Q1, Q38)   — scenario tree, permanent URL, hash-pinned
```

Canonical YAML shapes for each record (atomic/composite primitive, framework,
concept, marketplace_concept, company_concept, tam_output, annotation) live in
`docs/07-data-layer-brainstorm.md` §"Final design" and
`docs/09-expert-layer-brainstorm.md`. Don't redesign these without revisiting
the brainstorms — every field is load-bearing.

### Load-bearing schema rules (don't drift)

- **TAMs are scenario trees**, never scalars + error bars (Q1).
- **Units are structured** (`kind`, `dimension`, `denominator`, `currency`,
  `basis`); frameworks declare unit signatures; validator statically rejects
  bad wiring (Q4).
- **Currency stored nominal**, normalized at query time (Q4).
- **Composites = same-unit set ops only.** Frameworks = all unit-crossing math
  (Q3). Hard line — don't blur it.
- **Frameworks have NO scalar defaults** — every input is a primitive slug
  (Q15). Variants attach pointers, not values (Q17).
- **Citations are content-hash pinned** (`snapshot_sha256`). Source snapshots
  mandatory at ingest. Sensitivity-aware change notifications (Q5).
- **Geo has two parallel fields:** `geo_supply` + `geo_demand`. Sub-national
  is first-class. ISO 3166 (Q8).
- **Concepts are first-class** — multiple competing measurements attach to one
  concept; disagreement gets a page, not a footnote (Q9, Q10).
- **Source tiers:** `first_party | regulator | aggregator | analyst |
  community | onchain | prediction_market | community-modeled` (Q26, Q37).
  Last three were added in the brainstorm — extends the original five.
- **No LLM-projected primitives**, ever (Q20). Synthetic atomics allowed only
  with hard guards (range mandatory, 12-mo expiry, banner downstream).
- **Annotations are pure commentary** — text-only, never auto-applied to math.
  The user reads and decides (`docs/09-expert-layer-brainstorm.md` E1).

---

## Product surface

Locked across `docs/08-product-surface-brainstorm.md` (U1–U12).

### Three pillars (axes)
**Qualitative · Quantitative · Industry** — the pyramid's three sides.
**Geo + Time are filter chips above the graph**, not pillars (Q12 / U1).
Promoting them to pillars tetrahedralizes the cognitive load.

### Pyramid graph
Always-on centerpiece (U1). Click node → adds constraint, greys incompatible
siblings. Shift-click → OR within pillar/tier. Right-click → context menu.
Hover → 250ms ghost-card preview. Three node types coexist: **taxonomy stub**
(navigation-only), **concept-bearing leaf** (data attached), **saved-query
node** (dynamic, pinnable, shareable) — see Q11.

### URL / page model (U5, U6, U11)
- `/` — search landing (single centered query box, LLM parses to constraints — U3)
- `/?q=<query>` — multi-interpretation cards before pyramid loads (U4)
- `/build/<state-hash>` — workhorse view, auto-minted on every meaningful state
  change (constraint add/remove, framework toggle, assumption tweak). Pan/zoom/
  hover do **not** mint
- `/tam/<hash>` — frozen artifact; read-only + Fork button; all edits create a
  new `/build/<state-hash>`
- `/c/<slug>` `/p/<slug>` `/f/<slug>` — concept/primitive/framework detail pages
- `/browse` — public registry of promoted TAMs (`is_promoted` flag separate
  from auto-mint hash)
- `/contribute` — contribution splash

State is canonicalized (sorted keys) before sha256 hashing so equivalent
states collide.

### Right-rail accordion (U2)
Frameworks + Scenarios expanded · Independence + Lineage chips collapsed ·
Banners + Export pinned bottom.

### Annotations (U8)
**Red dots in context only** (next to annotated names / graph nodes / scenario
rows). Hover → snippet · click → inline expand sorted by contributor weight.
**Never aggregated in a rail section.**

### Export (U10)
"Copy URL" / "Download PDF" / "Download Markdown". Banners (synthetic, modeled,
subsidy, regulated, dark-estimate) become footnotes in exports.

---

## Docs index (read these to orient)

Numbered for reading order. Cross-link liberally with relative paths.

| File | Purpose |
|---|---|
| `docs/00-vision.md` | Thesis: why a community market-sizing engine wins |
| `docs/01-primer.md` | Conceptual on-ramp: three layers + five-layer data model + pyramid graph |
| `docs/04-user-journey.md` | Sarah's P&C doc-gen TAM golden path |
| `docs/05-roadmap.md` | v0.2 → v1.0 milestones |
| `docs/06-glossary.md` | Domain terms — update in same change that introduces a term |
| `docs/07-data-layer-brainstorm.md` | **Decision record** Q1–Q40: full data-layer schema lock |
| `docs/08-product-surface-brainstorm.md` | **Decision record** U1–U12: UX surface lock |
| `docs/09-expert-layer-brainstorm.md` | **Decision record** E1–E5: annotation schema (ops deferred to v0.5) |
| `docs/10-v0.2-backend-spec.md` | Executable v0.2 backend spec — the implementation blueprint |
| `docs/design/` | Brand kit tokens + component catalog + mockup screenshots |
| `docs/plans/` | In-flight implementation plans |

The three brainstorm decision records (07/08/09) plus the backend spec (10)
are the **load-bearing** docs for current work. `01-primer.md` is the
conceptual on-ramp — read it first if you've never seen the project.

---

## Build sequence (v0.2 → v1.0)

| Milestone | Scope |
|---|---|
| **v0.2** — seed library + schema lock | All record schemas (atomic, composite, framework, concept, output, annotation), unit type system, geo type, extended source tiers, validator L1+L2, seed concept library (~100 concepts), ~50 primitives, 5 frameworks across 2 verticals exercising marketplace + multi-product + subsidy paths |
| **v0.3** — graph renderer | Pyramid topology with 3 axes + geo/time overlays; three node types; Postgres mirror rebuilt on merge; full-text + faceted search; annotation display per U8 |
| **v0.4** — calculator + export | Scenario-tree TAM outputs; content-hash pinning; permanent `/tam/<hash>` URLs; PDF/markdown export; method-family / independence scoring surfaced in UI |
| **v0.5** — contribution flow | PR-based contribution + full validator pipeline; LLM PR review (Claude Code-style); LLM auto-publish for high-tier sources; web form for annotations; **expert-layer ops land here** (credentialing, reputation, moderation, COI rules, adversarial defenses) |
| **v1.0** — public beta | Semantic embeddings search; 250+ primitives, 25+ frameworks, 5+ verticals; concept promotion flow; intersection-concept auto-promotion |

Verification scenarios for the v0.2 schema (from `docs/07` §Verification plan):
P&C doc-gen TAM · AI agents marketplace 2027 · Stripe TAM (two-sided + embedded)
· EV charging 2026 (subsidy) · Hedge-fund tech (power-law) · Polymarket-implied
private valuation. If any needs a schema exception, the schema isn't done.

---

## Conventions

### Versioning
- SemVer: `MAJOR.MINOR.PATCH`. Pre-1.0: minor bumps for spec/schema change,
  patch for docs-only.
- `git tag -a vX.Y.Z -m "..."`; update `VERSION` + `CHANGELOG.md` in the same
  commit as the tag.
- `CHANGELOG.md` is Keep-a-Changelog format. Every notable change goes under
  `[Unreleased]`.

### Docs
- Live under `docs/`, numbered `NN-title.md` so they sort in reading order.
- Plain Markdown. ASCII diagrams over Mermaid for small diagrams (no toolchain).
- Cross-link with relative paths.

### Naming
- Project codename **Strata** — provisional, user-chosen, do NOT rename without
  an explicit request.
- New domain terms → add to `docs/06-glossary.md` in the same change.

### Data (when YAML lands)
- One entity per file, slug-keyed kebab-case.
- `data/primitives/` · `data/composites/` · `data/frameworks/` · `data/concepts/`
  · `data/sources/` · `data/annotations/` · `data/tam_outputs/`.
- Records declare `schema_version` (Q30); migrations run atomically on bumps.
- Content-addressed source snapshots stored sha256-named.

### Running things
- All `uv run` commands must be invoked from `backend/` (where `pyproject.toml` lives).
- Tests live at `backend/tests/`; the orphaned root `/tests/` is not picked up by `testpaths`.
- `data/` lives at the repo root — pass `--data-dir ../data` when running `strata` commands from `backend/`.
- Verification suite: `uv run pytest && uv run pyright && uv run ruff check . && uv run ruff format --check .`

### Database commands (from `backend/`)
- `uv run alembic upgrade head` — create/migrate Postgres tables.
- `uv run strata db seed -d ../data` — upsert all YAML into Postgres (idempotent).
- `uv run strata db stats` — show Postgres row counts.
- `uv run strata test-connectors` — live smoke test all 5 APIs.
- `uv run strata stats -d ../data` — show YAML data bank counts.

### Free-form TAM queries (`strata goal`, v0.3)
- `uv run strata goal "<query>"` — runs the 4-step resolver (concept → primitive
  → connector → fallback). `--stream` / `--json` / `--no-live` / `--no-fallback`
  / `--primitive-only` / `--expansion-budget N`. `STRATA_OFFLINE=1` for CI.
- `uv run strata promote <slug>` — moves `~/.strata/auto-primitives/{slug}.yaml`
  into the committed `data/primitives/` tree (validator-gated, idempotent).
- Full howto: `docs/13-strata-goal-cli.md`. Spec:
  `docs/superpowers/specs/2026-05-27-strata-goal-cli-and-connectors-design.md`.

### Data storage architecture
- **Production (Railway):** Postgres is the primary store. YAML files are baked
  into the Docker image as seed data. Run `strata db seed` once after deploy.
- **Local dev:** YAML on disk → `strata db seed` → local Postgres. Or just use
  YAML directly via the in-memory Registry (no DB required for dev).
- **CI/tests:** Tests use YAML loader directly; no Postgres needed.
- **Connectors write to disk cache** (`~/.strata/cache/{connector}/`) then to
  YAML via converter functions. The `strata db seed` command loads YAML → DB.
  Future: connectors will write directly to DB, skipping YAML entirely.

### Pydantic v2
- Discriminated unions (e.g. `Source = Annotated[Union, Field(discriminator=...)]`) are typing constructs, not models — validate with `TypeAdapter(Source).validate_python(...)`, not `.model_validate(...)`.
- Trust `uv run pyright` over the IDE's streaming diagnostics on newly-written files (the latter shows phantom "Import could not be resolved" errors that resolve themselves).

### Known schema drift (deferred to v0.3)
- **Q8 geo** — at v0.2 primitives carry a single `geo: Geo` + `geo_perspective` enum, not the two-parallel-fields design Q8 mandates. Restoration tracked for v0.3 when a primitive needs to declare both supply and demand geos.
- **Q20 synthetic primitives** — no `synthetic: bool` marker or required `expiry`/`uncertainty` yet. Lands when the first synthetic primitive is seeded (v0.3 community-modeled sliders).

---

## What NOT to do

- **Don't invent figures.** Every claimed real number needs a source. Illustrative
  examples must be labelled "illustrative" or use obviously fake values (`$X`, `N`).
- **Don't blur the composite/framework line.** Composites are same-unit set ops
  only; any unit-crossing math belongs in a framework (Q3).
- **Don't add scalar defaults to frameworks.** Every input is a citable
  primitive slug (Q15).
- **Don't add LLM-projected primitives** (Q20). LLM hallucination becoming
  citable is the worst-case outcome.
- **Don't make annotations affect math.** Pure commentary only (E1).
- **Don't rename the project** without an explicit request.
- **Don't pick new tooling** for `web/` without confirming — there's tension
  between the current Next.js scaffold and the user's long-term stack
  preference (bun/biome/tanstack/zustand).
- **Don't run `cat`, `head`, `tail`, `sed`, `awk`** in Bash — use Read/Edit.
  Bash is for git/mkdir/rm/mv/navigation only (context-mode policy).
- **Don't put `typer.Argument(...)` or `typer.Option(...)` in function defaults** (ruff B008) — create them as module-level singletons and reference them. Python evaluates function defaults once at definition time, which is exactly what Typer expects.

---

## When you start a new session

1. Read `README.md`, this file, `docs/01-primer.md`, and `docs/05-roadmap.md` to orient.
2. Skim the three brainstorm decision records (`07`, `08`, `09`) and the v0.2
   backend spec (`10`) — they are load-bearing.
3. Check `git log --oneline -10` and `[Unreleased]` in `CHANGELOG.md` for
   in-flight work.
4. Tags are the source of truth for released versions:
   `git tag --sort=-v:refname`.

---

## User context

- User is **Arkash Jain** (`arkash@benmore.tech`).
- Working from `/Users/arkashjain/Desktop/work/VC_stuff`.
- Audience for this product is **VCs and operators doing TAM work** — write
  docs and UI copy for that reader (defensible numbers fast, not academic
  rigor).
