# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — rigorous market definition, sub-project 1
- **`MarketScope` value object** (`strata.models.scope`) — the structured,
  checkable definition of *which* market a number sizes: `vertical` (NAICS),
  `persona` (SOC), `segment` (firm-size band), `geo_supply`/`geo_demand` (ISO,
  the Q8 two-geo shape), plus free-text `product`/`include`/`exclude`. Added as
  an optional `scope:` field on both `Concept` (declared/canonical) and
  `AtomicPrimitive` (the primitive's *true* scope), defaulting empty so existing
  YAML loads unchanged.
- **The scope guard** (`strata.scope.guard.classify_scope`) — pure,
  deterministic (no network/LLM, mirrors the verbatim guard). Compares declared
  vs actual scope per dimension into a `Relationship`
  (exact/narrower/broader/partial/disjoint/unknown) and returns a `ScopeMatch`
  whose `displayed` scope is **always the primitive's actual scope**
  (snap-to-truth) plus mismatch warnings. NAICS/SOC compared by significant-
  prefix hierarchy (a minor group like SOC 41-4000 correctly contains detailed
  41-4012); geo by ISO-set with `global` wildcard; segment by employee-range
  containment. Catches the reviewed failures: a wholesale/mfg-only headcount
  (SOC 41-4012) under an "all B2B reps" market reads as NARROWER and names the
  services group (41-3000) it excludes entirely; an unrestricted occupation
  count under a mid-market band reads as BROADER. 24 adversarial tests
  (`tests/test_scope_guard.py`).
  Spec: `docs/superpowers/specs/2026-05-31-rigorous-market-definition-design.md`.
- **Showcase data backfilled.** `demo-ai-sales-ops-us` + its 5 primitives now
  declare real scope, so the guard reproduces the reviewed failures on live data:
  the concept's two methods (bottoms-up $2.0B via the wholesale-only SOC 41-4012
  headcount, top-down $31.2B via mid-market-only firms) diverge *because* of the
  scope mismatches — the headcount reads NARROWER (excludes services reps), both
  mid-market inputs read NARROWER on segment.
- **Scope report on every sized TAM** (`strata.scope.build_scope_report`). The
  evaluator attaches an optional `ScopeReport` to `TAMOutput`: the declared
  market scope plus, per consumed primitive, its snap-to-truth `displayed` scope
  and definite mismatch warnings (`UNKNOWN` suppressed, so a per-seat price with
  no persona isn't nagged). Derived — not part of the state hash, JSONB-stored,
  `None` on TAMs persisted before scope landed. Flows through `GET /build/{slug}`,
  `POST /build/recompute`, and `GET /tam/{hash}`. 6 tests (`tests/test_scope_report.py`).
- **Scope on the `/tam` artifact** (`web/.../tam/ScopeCheck.tsx`). A read-only
  **Market** chip strip under the headline shows the declared scope; a **Scope
  check** section (after the convergence banner) lists each off-scope input with
  its snap-to-truth scope and the narrower/broader reason — the legible "why the
  methods disagree"; a right-rail summary gives the at-a-glance ok/off-scope
  count. `scope` added to the web `tamOutputSchema` (zod). 5 component tests;
  typecheck + biome clean on changed files.
- **Scope persisted through Postgres** (migration `007`). `scope` JSONB columns
  on `primitives` + `concepts` (nullable); `Registry.from_db` round-trips it
  (NULL → empty scope for rows seeded before scope landed), and the seed upsert
  writes/updates it (complete on-conflict set, per the prior re-seed bug). Without
  this the guard worked on the YAML/in-memory path but scope was dropped on the
  PG-backed deploy path. Verified end-to-end against live Postgres.

### Changed — honest sourced-gap upgrade for unsizable crypto companies
- **Corrected two wrong `unsizable` reasons.** 0xPass and 3Blocks were labelled
  unsizable due to the Q20 quarantine — but that conflates two different things:
  the quarantine forbids feeding `prediction_market`/onchain signal *values* into
  a framework, not sizing a crypto *company*. Onchain-tier values are in fact
  framework-legal (`registry.py` quarantines only `prediction_market`). The real
  gap is sourcing: the demand-side count is sourceable, the spend-per-unit is not.
- **Seeded the real, pinnable demand-side primitive** `web3-monthly-active-developers-2024`
  (23,613 monthly-active OSS devs, Electric Capital Developer Report 2024,
  `tier: aggregator`, snapshot-pinned) + two intentionally framework-less concepts
  (`web3-wallet-infrastructure`, `onchain-analytics-software`) that carry it as a
  measurement — the navigable, honest shape of "unsizable".
- **Rewrote the two reasons** to state the true sourced-gap (count sourced; no
  primary source for spend-per-developer / seat price; refusing to reproduce the
  analyst ~$2B / ~$3.4B market reports as a TAM, Q26) and linked each demo card to
  its concept. No framework, no TAM, nothing community-modeled dressed as sourced.
  Spec: `docs/superpowers/specs/2026-05-31-honest-sourced-gap-upgrade-design.md`.

### Added — portfolio sizing + company layer (P1)
- **The verbatim guard (`strata.sizing.guard`)** — the Q20 wall, productized. Two
  gates in series: a *semantic magnitude match* ($4.2B ≡ 4.2 billion ≡
  4,200,000,000 ≡ USD 4.2bn) with **clause-bounded role locality** (a revenue
  value matched against a "market cap" sentence is rejected), then
  **corroboration** (≥2 independent role-matched spans, or a 2nd source). Verdicts
  gate eligibility: only `verbatim_corroborated` is public-eligible;
  `verbatim_single` is org-private only. 24 adversarial tests.
- **`strata.sizing` service** — `size_company(reg, company, opts)`, productized
  from `scripts/tam_77_pipeline.py`. Registry-first and **offline-safe by
  default**: with no live flags it matches a curated market or returns an honest
  `unsizable` — it never calls an LLM/Exa on a render path (F3). Analyst-sourced
  inputs persist **org-private first** (F2); public promotion is gated on ≥2
  corroborating sources or review.
- **`companies` table** (migration 006, org-scoped + RLS) + `CompanyRecord` model,
  behind `STRATA_PORTFOLIO_ENABLED` (F6 — table created always, write surfaces
  ship dark). Idempotent JSON-backed `CompanyStore` for the local/CLI path.
- **Surfaces:** `strata portfolio import|size|list|gaps` CLI; three **write-capable
  MCP tools** (`import_portfolio`/`size_company`/`list_portfolio`, flag-gated,
  offline-safe sizing); `GET /portfolio`; a thin read-only **`/portfolio`** page
  (sized rows link to `/build/<market>`, "unsizable" rows shown as honesty).
- **Deterministic cached demo (F3/F5):** a curated 25-company subset
  (`portfolios/portfolio_demo_subset.yaml`) pre-sized **offline** by
  `scripts/presize_demo.py` into a baked `portfolio_demo.json` (20 sized · 5
  honestly unsizable). The demo renders entirely from cache — zero live LLM/Exa.
- 582 backend tests (40 new), pyright/ruff clean on `src`; web typecheck/biome clean.
- Spec: `docs/superpowers/specs/2026-05-31-portfolio-sizing-company-layer-design.md` (§12).

### Fixed — prod data integrity: re-seed now actually repairs stale rows
- **Root cause of the prod `/build` failures ("no applicable framework variants")
  and the "cannot fetch enough market data" errors:** every Postgres upsert in
  `db/sync.py` had an **incomplete `on_conflict_do_update` set**, so an idempotent
  re-seed silently skipped the omitted columns. Framework `variants` (the
  concept → primitive bindings) were never updated after the first seed, stranding
  every framework at `variants=[]` in prod and 422-ing every `/build`, `/tam`, and
  the resolver's registry-first path. Concepts also dropped `competing_concepts`;
  primitives dropped half their columns; sources dropped snapshot/accessed. Now
  **every upsert updates every non-key column**, so `STRATA_SEED_ON_BOOT` repairs
  stale prod data on the next deploy.
- **Composite primitives were never seeded to Postgres** (`Registry.from_db` had no
  composite path), so any concept consuming one 422'd ("neither a known atomic nor
  composite primitive") — e.g. `ai-coding-assistants-us` via
  `us-software-engineering-workforce`. Each same-unit `union` composite is now
  seeded as a **resolved row** whose value is `math.fsum` of its already-sourced
  member atomics (no invented figures; Census CBP regulator provenance preserved).

  ```
  YAML seed ──► sync_yaml_to_db ──► Postgres
     atomics ───────────────────────►  primitives (all columns updated on conflict)
     composites ─(union = Σ members)─►  primitives (resolved row, real value)
     frameworks ─(variants included)─►  frameworks  ──► /build works ──► /tam persists
  ```

### Added — portfolio → sourced-market map
- **`scripts/map_companies_to_markets.py` + `portfolios/cos-list-market-map.csv`:**
  maps the 4,918-company portfolio onto the curated sourced markets (by industry
  vertical + the six-lens taxonomy). 61% inherit a defensible market TAM; the
  uncovered verticals (ESG, Web3, Marketplaces, Logistics, Edtech, …) are flagged
  honestly as "no curated market yet" rather than fabricated.

### Added — connector explorer (answers "how do connectors come into play")
- **`GET /connectors` + `/connectors` page (sidebar link):** the ingest catalog.
  Lists all 22 typed connectors from the capability registry, and cross-references
  the live data bank by source host so each shows a **real** `primitives_in_bank`
  count + a sample primitive you can open (census 38 · bls 27 · fred 22 ·
  worldbank 21 · edgar 16 = 124 sourced primitives). Capability-only connectors
  are listed honestly as "wired, not yet ingested" (0, no fabricated sample). The
  page draws the pipeline — `API → typed client → snapshot pin → atomic primitive
  → framework → TAM` — so a partner sees why every number is defensible. Read-only,
  no live API calls in the request path; sample is slug-sorted for determinism.
  Kalshi is deliberately excluded (its data is the quarantined `/signals`). 5
  backend + 3 e2e tests; pyright/ruff/typecheck/biome clean.

### Added — forwardable market-sizing report (tournament finalist · P2.4)
- **`/tam/<hash>/report`:** a clean, print-first **one-page report** generated from
  any TAM — the document a partner forwards. Letterhead + permalink, an executive
  KPI strip (triangulated TAM · range · methods · independence), the convergence
  cross-check, a **"how it was sized"** breakdown showing each method's equation
  (`A × B × … = TAM`), a sensitivity tornado ("what moves the answer"), a
  **Sources & provenance** table (every input with tier + SHA-256 snapshot), and
  honest footnotes (modeled/paraphrase banners). "Print / Save as PDF" via a
  scoped print stylesheet; reachable from the TAM Export rail ("Generate report").
  All derived from the existing artifact — no new number. 4 Playwright e2e tests;
  verified live (PDF export confirmed).

### Added — convergence cross-check + downloadable graphs (tournament champion)
- **Bottoms-up vs tops-down convergence (MV2):** when a concept is sized by ≥2
  independent method families, the evaluator emits a `convergence` object
  (`engine.py` `_convergence` → `TAMOutput.convergence`) and the `/tam/<hash>`
  page leads with an **animated agreement banner** — "lower estimate $X · higher
  estimate $Y · spread N×", graded tight/broad/wide. This is the triangulation a
  VC assembles by hand; pure synthesis of already-sourced scenario values, never a
  fabricated second method. Renders **only** for multi-family concepts (single
  method → `null`, no banner). Refuses to compare across mismatched units. Honesty
  framing throughout: "method agreement", never "confidence". (e.g. doc-gen-pc:
  bottoms-up $155M / top-down $470M / 3.0×.)
- **Downloadable graphs:** every result chart (sensitivity tornado, TAM-over-time)
  gets a **PNG / SVG** export (`lib/chart-export.ts` inlines computed styles so
  CSS-var theming survives the detached SVG; `ChartDownload` button). Client-side
  only, no new data — the forwardable image for a deck or memo.
- Tests: 2 convergence backend tests (multi-family present, single-method null);
  537 pytest pass, pyright/ruff clean on `src`, web typecheck + biome clean.
  Verified live via Playwright against a real `/tam/<hash>`.

### Added — prediction-market signals surface (docs/22 T1)
- **`GET /signals` + `/signals` page:** the 202 `prediction_market` primitives
  quarantined to `data/signals/` (Q20) now have a read-only surface. The backend
  route (`api/routes/signals.py`) lists each signal's value, source URL, tier, and
  SHA256 snapshot pin; the web page (`/signals`, sidebar link with a live count)
  groups them by concept behind a loud banner that states they **never feed a TAM**.
  A differentiator a general LLM can't reproduce — live Kalshi event probabilities
  next to a sized number, with the quarantine made explicit. 4 backend tests
  (incl. a `/p`-leak invariant) + 4 Playwright e2e tests; full gate green
  (534 pytest pass, pyright/ruff clean, web typecheck clean).

### Fixed — full-app QA + adversarial-tournament P0 remediation
- **Local dev unblocked:** dev/non-prod CORS now auto-allows any `localhost:*`
  origin, so `next dev` works on whatever port it grabs (was hard-coded
  3000/3001 → every API fetch CORS-blocked → empty UI). Prod stays locked.
- **Citations surfaced:** the resolver now threads `source_tier`/`source_url`/
  `snapshot_sha256` through `primitives_used`, so the build/TAM result shows a
  tier badge + clickable source per input (composites correctly show none).
- **Shareable permalink made durable (tournament blocker #1):** TAMs persist to
  Postgres (`tam_outputs`, migration 005); `GET /tam/<hash>` falls back to the DB
  and survives an API restart; homepage Featured TAMs link to `/tam/<hash>`, not
  the old `/build?q=` workaround. Verified end-to-end across a real restart.
- **Credibility fixes:** removed the fabricated `j.vega · verified · 27 contribs`
  sidebar user (now real Clerk user / Sign-in / honest Guest); footer GitHub link
  points at the real repo; the resolve hero suppresses the independence donut for
  single-method estimates (shows a muted "single method" chip instead).
- **Docs:** `docs/qa/TEST_PLAN.md` (audit), `docs/20-adversarial-teardown.md`
  (108-agent tournament, 46/100), `docs/21-teardown-remediation.md` (P0/P1/P2 plan).

### Added — P1 defensibility made visible (docs/21)
- **Show the math (P1.1):** the resolve/build result renders the explicit
  equation — `Multiplies to 3M people × 300/per-seat-year = $900M` — plus the
  source tier in each bar's tooltip. The receipt an LLM can't produce.
- **Defensibility on cards (P1.2):** Featured TAM cards show a compact
  independence ring + a method badge (green `△ N methods` when triangulated
  across ≥2 method families, muted `single method` otherwise), so a defensible
  TAM looks different from a one-source guess. `IndependenceDonut` gains a
  `showLabel` ring-only mode.
- **Audit graceful degrade (P1.4):** `GET /audit` serves a read-only capped feed
  to anonymous callers in non-prod instead of a hard 401, so the dashboard trust
  trail isn't a broken box in a keyless demo; prod stays auth-gated.
- **Modeled-input honesty (P1.5):** results containing `community-modeled` /
  `strata.internal` figures show a loud banner so the headline TAM is never
  mistaken for a fully externally-sourced number.
- **Per-input source-tier mix on the TAM artifact (P2.4):** the evaluator now
  threads each input's source tier onto `InputUsed` (composite → members' shared
  tier or `mixed`); the `/tam/<hash>` artifact renders a real provenance
  breakdown (e.g. `analyst-paraphrase 1/2 · community-modeled 1/2`) in place of
  the old "not yet exposed" placeholder — the "where every number came from" a
  partner needs before forwarding. (The sensitivity tornado already ships on the
  artifact via `TornadoChart`.)

### Added — client guides + simple login
- **Guides (`/guides`):** a screenshot-driven, business-language platform
  walkthrough behind a sidebar "Guides" link — every surface (home → build/
  equation → sourced primitive → concept disagreement → pyramid → shareable
  artifact → dashboard → integrations → browse), led by a "why this beats an LLM
  answer" value table, with a live-vs-coming-soon honesty section and a page
  sitemap. 9 screenshots captured from the live app (`web/public/guides/`).
  Companion handbook `docs/guides/CLIENT_PLATFORM_GUIDE.md` with a regeneration
  recipe (built via the playwright-doc-generator + playwright-cli skills).
- **Simple login:** a zero-config local identity (name/org, persisted) so the
  keyless deploy has a working sign-in (sidebar footer) instead of a bare
  "Guest" — coexists with Clerk, which remains the real-auth path when keyed.
  Not a security boundary; a single-user demo identity for attribution.
- **Favorites:** a star on each saved-build row pins a TAM to a Favorites
  section on the dashboard (persisted, survives the visit-history cap). Each
  star subscribes only to its own key for correct cross-row reactivity.
- **Engineering handoff** (`docs/22-handoff.md`): current state + verification
  gate, session gotchas, four maximum-value functions with specs, concrete
  TODOs with file pointers, nice-to-haves, and a value-spec table.

### Changed — re-audit hardening (flip existential Risks 2 & 5)
- **Substrate wired at runtime (Risk 5).** `set_org_scope`/`org_session_scope`/
  `get_org_session` activate the Wave-3 Postgres RLS per request (parametrized,
  transaction-local `app.org_id`); `GET /audit` is now auth-only; rate-limiting
  covers `/build/recompute`, `/build/{slug}/promote`, and `/contribute` (was
  `/resolve` only).
- **Moat intake persisted (Risk 2).** Migration 004 `contributions` table;
  `POST /contribute` persists durably (attributed to `org_id`) and
  `GET /contributions` is an auth-guarded review queue.

### Added — YC remediation Wave 4 (GTM, moat & narrative)
- **Growth loop.** Promoted TAMs (`TAMOutput.is_promoted`, `POST /build/{slug}/promote`,
  `GET /browse`) feed a Next `sitemap.ts` + `robots.ts` so shareable, SSR'd
  `/tam/<hash>` pages are crawlable and indexable. An **embeddable widget**
  (`/embed/tam/<hash>`) renders a compact iframe-able TAM card (CSP
  `frame-ancestors *` on `/embed` only). A validator-gated **`POST /contribute`**
  accepts proposed primitives/annotations (regulator/first-party auto-accept,
  low-tier → needs-review, malformed → rejected; annotations never auto-applied
  to math, E1). A **doc-count CI check** (`scripts/check_doc_counts.py`) fails the
  build when `VERSION` ≠ `pyproject` or a tag runs ahead. Promoted TAMs are exempt
  from FIFO eviction.

### Added — YC remediation Wave 5B/5C (private OAuth data + integrations gallery)
- **Connect-your-data (the network-effect moat).** A generic inbound OAuth
  connector framework (`connectors/saas/`): a fund connects its SaaS (HubSpot
  pilot + a second stub provider proving genericity) and the data becomes
  **private, org-scoped, first-party primitives** that sharpen only its TAMs.
  OAuth tokens are **Fernet-encrypted** and org-scoped; private primitives are
  org-namespaced and isolated (cross-tenant read = 0, mirrors Wave-3 RLS); they
  feed the **same evaluator** and carry a `private` banner; disconnecting purges
  tokens + tombstones the data. OAuth flow has single-use CSRF state + auth-only
  routes. `AtomicPrimitive` gains `visibility`/`org_id`.

```
connect ─> OAuth (CSRF state) ─> encrypted org token ─> sync ─> private primitive
        ─> org_scoped_registry ─> same evaluator ─> TAM (private banner)
disconnect ─> purge token + tombstone primitives
```

- **`/integrations` gallery (Wave 5C).** `simple-icons` `BrandIcon` (monogram
  fallback for gov/unknown, never crashes), three groups (Inbound / Outbound /
  Public data bank), an old-vs-new comparison, and a reduced-motion-safe
  animated pipeline flow. Linked in the sidebar nav.

### Added — YC remediation Wave 3 (architecture, trust & ops)
- **Company substrate.** API-key auth (`api/auth.py`, hashed `X-API-Key` →
  `Principal{org_id}`; 401 when required) on the LLM/compute routes; a per-org
  **token-bucket rate limit** (`api/ratelimit.py`, 429 + `Retry-After`);
  **usage metering** (`api/metering.py` + `GET /usage`) and a `/metrics`
  Prometheus endpoint; a request-id + structured-timing middleware
  (`X-Request-Id` on every response); **CORS fails closed in prod** (no
  wildcard). Tenancy: migration 003 adds `api_keys`, `usage_events`, and a
  `tenant_data` table with **Postgres row-level security** (policy keyed on
  `current_setting('app.org_id')`, `FORCE RLS`) — cross-tenant reads return 0
  rows (verified against a live PG). This is the hard prerequisite for the
  Wave-5B private OAuth data.

### Added — YC remediation Wave 1 (AI defensibility & data rigor)
- **Every emitted number is grounded.** A citation-host allowlist
  (`resolver/citations.py`) rejects fabricated / `strata.internal` hosts; the
  novel resolver keeps only Exa-returned URLs and derives **source tier from the
  host class, never the LLM** (AC1.1/AC1.2). A **unit guard** blocks
  dimensionally-invalid TAM multiplies (money² / no-currency) (AC1.6). A
  **verifier/critic pass** stamps a `dark_estimate` banner on flagged synthesis
  (AC1.4). **Snapshot integrity** (`strata verify-integrity`, `IntegrityError`)
  verifies stored snapshots hash to their sha256 (AC1.3). A **resolver eval
  harness** (`strata.evals.resolver_eval`, 30 golden cases) gates CI at ≥0.8
  pass-rate (AC1.5). **Staleness**: `Source.freshness_sla_days` + a `StaleChip`
  flag primitives past their freshness SLA (AC1.7).

### Added — YC remediation Wave 2 (motion & visual craft)
- **Recompute payoff + live pyramid.** New motion primitives (`CountUp` rAF
  count-up, `Pulse`, `useHoverIntent`) wire a count-up + pulse into the TAM
  headline. The pyramid gains a **right-click context menu** (Expand children /
  Suggest framework / Annotate) and a **250ms hover-intent ghost card**. A new
  **sensitivity tornado** (`GET /build/{slug}/sensitivity` → `TornadoChart`)
  shows which assumption moves the TAM most, sorted by |impact|. All motion is
  gated by `prefers-reduced-motion`. Tests: motion (4), tornado sort (2),
  pyramid overlays (2), sensitivity endpoint (3); e2e specs for count-up + CLS.

### Added — YC remediation Wave 5A (Strata MCP server)
- **Strata in Claude via MCP.** A read-only MCP server (`strata.mcp`) exposes the
  curated data bank + evaluator as five tools — `search_concepts`, `get_primitive`,
  `list_frameworks`, `size_tam`, `resolve_market` — over **stdio**
  (`strata-mcp --stdio`) and a **streamable-HTTP** transport mounted at `/mcp`.
  Every numeric payload is sourced: `source_url` + `source_tier` +
  `snapshot_sha256`; the internal `strata.internal` host is scrubbed to `null`
  (modeled numbers carry no external citation, pre-staging Wave 1's allowlist).
  `resolve_market` is registry-first and LLM-free, so an agent can never get an
  unsourced number. No tool mutates the registry. `claude mcp add` snippet in
  both READMEs.

### Added — YC remediation Wave 0 (demo-blockers)
- **`/tam/<hash>` is server-rendered with OpenGraph (AC0.8).** The artifact route
  is now a Next.js Server Component that fetches the TAM server-side and seeds the
  client view via tanstack `initialData`, so a shared link's initial HTML carries
  the headline value (crawlers + previews see it, not an empty root).
  `generateMetadata` emits `og:title`/`og:description`; a `next/og`
  `opengraph-image.tsx` renders value + concept + a triangulation ring. e2e spec
  `tam-share-og.spec.ts` asserts SSR value + OG tags.
- **5 triangulated demo concepts (AC0.6/AC0.7).** Seeded `demo-ai-dev-tooling-us`,
  `demo-ai-insurance-claims-us`, `demo-ai-sales-ops-us`, `demo-ai-clinical-docs-us`,
  `demo-ai-legal-research-us` — each sized two independent ways (bottoms-up persona
  × cost, top-down firms × spend) so its TAM spans 2 method families
  (`independence_score=1.0`), and each carries ≥2 independently-sourced same-quantity
  measurements differing ≥10% (a regulator headcount vs an aggregator estimate) so the
  `/c/<slug>` disagreement bar shows real spread. Generated by
  `backend/scripts/seed_demo_concepts.py` from real public figures (soft ACV/spend
  figures are `analyst-paraphrase` tier with verify-against-source banners).
- **Resolver is registry-first and tree-shaped (AC0.2/AC0.3).** `POST /resolve`
  now matches the query against curated concepts first (`resolver/match.py`,
  pure-Python exact + fuzzy, no LLM). A concept hit returns the full
  **multi-scenario tree** with `estimate_kind="triangulated"` when it spans ≥2
  method families; a novel query falls through to single-method synthesis with
  `estimate_kind="single_method"` and a mandatory honesty banner — a point is
  never dressed up as a triangulated TAM. The SSE `result` event now carries
  `scenarios[]` (`{label,value,method,framework,triangulated}`) + `estimate_kind`.
- **Prediction-market primitives quarantined as signals (AC0.5).** The 202
  Kalshi event-contract probabilities moved from `data/primitives/` →
  `data/signals/`; the loader routes anything under `signals/` into a read-only
  `registry.signals` dict that the evaluator and frameworks never touch (Q20).
  `strata stats` now prints "sizing-grade primitives" and "signals" separately.
  One-shot idempotent migration: `backend/scripts/quarantine_signals.py`.
- **Built/recomputed TAMs now persist (AC0.1).** `GET /build/{slug}` and
  `POST /build/recompute` remember their evaluated `TAMOutput` in the registry
  (FIFO-capped), so a copied `/tam/<hash>` share-link resolves within the
  session instead of 404-ing. `reg.remember_tam` is idempotent on `state_hash`.

### Added
- **Interactive edit → recompute on `/build` (the core loop).** Click a primitive
  node on the graph to open an override panel and either (a) type/slide a
  **what-if value** or (b) **swap in a different sourced primitive**. The TAM
  recomputes live — headline, graph, and charts update, and what-if scenarios are
  flagged so no unsourced number is ever passed off as sourced.

  ```
  click node -> override panel -> /build/<hash>?s=  -> POST /build/recompute
                                                          (override-aware evaluator)
                                                       -> new TAM (what-if banner)
  ```

  - Backend: `POST /build/recompute` takes per-input overrides, checks each
    override's unit against the framework input, and returns a freshly hashed TAM.
    What-if values are never written to the data bank (Q20); they live in the URL
    only and carry a `user_override` banner into exports.
- **Result charts.** A method-comparison chart and an input-composition chart
  (shadcn / recharts) render on every sized TAM.
- **Dashboard + sign-in (optional).** A `/dashboard` page shows live library
  counts, your recently built TAMs, and an activity (audit) feed. Sign-in uses
  Clerk and is **off by default** — with no Clerk keys the app runs exactly as
  before; add keys to turn it on.
- **Activity log.** An `audit_events` table plus `GET /audit` records resolve and
  recompute events; the dashboard reads this feed.
- **Animated landing page** with a live query box; the live "Featured TAMs" are
  unchanged (still sized from real data, no invented figures).

### Changed / Ops
- **Live answers in production.** The Railway backend now runs the paid Anthropic
  path (`STRATA_LLM_BACKEND=anthropic` + funded key + Exa key); `GET /healthz/llm`
  reports `{"backend":"anthropic-sdk","available":true}`. `docker-compose` is wired
  the same way for local runs (keys read from the gitignored `.env`).
- Fixed a corrupt production API URL (a stray newline in `NEXT_PUBLIC_API_URL`)
  that would have broken every frontend request.
- **Preview deploys can reach the backend.** Added a configurable
  `STRATA_CORS_ORIGIN_REGEX` so Vercel preview URLs (whose subdomain carries a
  per-deploy hash) are allowed by CORS — the cause of "Failed to fetch" on a
  preview link. Off by default; no change to existing behaviour.

### Fixed
- **Graph nodes are now clickable.** A browser walkthrough found that the editable
  primitive nodes on `/build` could not be clicked — ReactFlow turns off pointer
  events on non-draggable nodes, so the override panel never opened for real
  users. The edit number now re-enables clicks on itself.
- **Dynamic resolution now answers real TAM questions off the Claude Code
  subscription.** The headless `claude -p` subprocess inherited a dead/low-credit
  `ANTHROPIC_API_KEY` and failed with "Credit balance is too low" — the root
  cause of the resolver "feeling mock". `resolver/llm._complete_cli` now scrubs
  the key so completion uses subscription auth. `resolver/slug.py` and
  `router.py` no longer call the Anthropic SDK directly — both route through
  `llm.complete()` (backend switch + env scrub). Concept-hit queries return the
  full composed TAM (value + attached primitives + lens), not just the name.

### Added
- **Composites are first-class in TAM math.** The evaluator and cross-record
  validator resolve a framework input bound to a composite primitive — `union`
  sums same-unit members; unit-crossing math stays in the framework (Q3). A
  community-modeled input now surfaces a `MODELED` banner.
- **Two worked, connector-sourced TAM questions:** `ai-coding-assistants-us`
  (composite persona `us-software-engineering-workforce` = Census CBP 5112 + 5415
  employees -> ~$900M) and `ai-legal-assistants-us` (Census CBP 5411 -> ~$947M),
  both sized via the existing cost-efficiency framework.
- **shadcn charts.** Installed shadcn (`components.json` + `ui/chart`); a resolved
  query now renders an interactive composition chart (`ResolveResultChart`) bound
  to the live payload, themed to the app tokens (light/dark).
- **`GET /healthz/llm`** backend probe; the `strata` CLI now auto-loads `.env`.
- **ast-grep rules** (`sgconfig.yml` + `rules/`) forbidding direct Anthropic SDK
  use anywhere in `backend/src` except `resolver/llm.py`.
- **Current-UI Playwright smoke** (`web/e2e/sp1-real-tam.spec.ts`). NOTE: the 16
  legacy e2e specs predate the v0.42 UI (assert the removed Contribute nav) and
  are stale — a tracked follow-up.

## [0.4.0] - 2026-05-28

### Changed
- **Removed all "Contribute" surfaces from the web app.** The `/contribute` route,
  the top-bar Contribute button, and the sidebar COMMUNITY group (Pull requests /
  Annotations / Activity / Starred) are gone — the contribution flow lands with
  the v0.5 expert layer, so the placeholders no longer dead-end.
- **Relicensed from Apache-2.0 to proprietary (all rights reserved).** Strata is
  not open-source software. `LICENSE` replaced with a proprietary notice;
  `pyproject` license set to `LicenseRef-Proprietary` with a
  `Private :: Do Not Upload` classifier; README license badge + thesis wording
  updated to drop the open-source/"free" framing.

### Added
- **v0.42 web frontend (PR #54).** Rebuilt the web app to the v0.42 design and
  wired it entirely to the live backend (30 concepts, 355 primitives, 5
  frameworks) — the mock data is gone. New shell with a left sidebar, a ⌘K
  command palette, and live library counts; new pages for concept / primitive /
  framework detail (including the concept "disagreement view"), the
  `/tam/<hash>` artifact page (export to link / Markdown / PDF), and a real
  browse registry. How a user moves through it:

  ```
  Home  (search · popular concepts)
    │  pick a concept, or type a market in plain English
    ▼
  /c · /p · /f detail  ──►  /build  (size it)  ──►  /tam/<hash>  (cite it)
    │                                                export: URL · Markdown · PDF
    └──►  /graph  (pyramid explorer)
  ```
- **Plain-English resolver runs on Claude Code.** Free-form market queries are
  parsed and sourced through the local Claude Code subscription, so no paid
  Anthropic API key is required (the API key path still works if one is set).
- **TAM-over-time trajectory** (`GET /build/{concept}/trajectory`). Re-evaluates
  a concept's frameworks at each date its sourced numbers were published, so the
  app can chart how a TAM estimate has moved as evidence arrived (current vs
  previous). Shows a single-snapshot state until a concept has numbers from more
  than one date.
- **Related-entities network view.** A force-directed bubble graph (opened from a
  concept or TAM page) showing what connects to what — concepts sharing a lens,
  a source, or a measurement, and the frameworks that size them.
- **Modern, on-brand motion.** Reusable entrance / stagger / hover animations
  tied to the brand-kit timing tokens, and they respect "reduce motion".
- **Working light / dark theme.** A real theme toggle (the old sun-glyph button
  was inert) flips a `html.dark` token set via `useSyncExternalStore`, with a
  no-flash bootstrap script and `color-scheme`. Light stays the default; the
  choice persists under `strata-theme`.
- **Home "Featured TAMs" are computed live.** The landing page now sizes the
  first few real concepts through `/build` and shows their actual ranges (and
  live library counts) instead of hardcoded placeholder figures.

### Fixed
- **Honest dynamic-resolution failure.** When the LLM backend is unreachable
  (no API key / exhausted credits) the `/build` resolver now says so plainly and
  always offers a curated-concept fallback, instead of a misleading "failed to
  parse AI response". The CLI layer surfaces the real cause (e.g. "Credit
  balance is too low") instead of an empty error.
- **Hydration mismatch on the library list pages** (`/c` `/p` `/f`) — the SSR
  skeleton no longer disagrees with the hydrated cards (gated via
  `useHasMounted`/`useSyncExternalStore`).
- **`strata promote` now works for ingested primitives** — it strips the
  ingest-only `metadata` block (provenance already lives in the pinned source),
  so `ingest → promote → seed` completes end-to-end. Added 3 connector-sourced
  primitives (EDGAR ×2, World Bank) to the data bank (358 total).

## [0.3.0] - 2026-05-28

### v0.3 release — connector dispatch, live ingest, graph renderer, deploy hardening (PRs #46–#50)

Closes the loop from a free-form question to a sourced number on a deployable,
self-refreshing service — and ships the read-only pyramid graph.

```
question / portfolio ─► router / manifest ─► call_and_convert ─► data bank
                                                   │
  /graph (pyramid UI) ◄─ registry ◄─ upsert_primitive ┘   ─► Postgres (deploy + seed)
```

#### Added
- **Connector dispatch** (`connectors/_dispatch.py`, PR #46) — `CONNECTOR_DISPATCH`
  maps every router-visible `(connector, method)` to a client factory + YAML
  converter; `call_and_convert(...)` builds the client (passing
  `STRATA_*_API_KEY` when the ctor accepts it), calls the method, fills the
  converter's positionals by matching the response shape, and returns a
  validated `AtomicPrimitive`. Coverage is pinned to `all_capabilities()`.
- **Live connector step in the resolver** (`resolver/pipeline.py`, PR #49) —
  step 3 now runs `router.choose → call_and_convert → writer.upsert_primitive`,
  emits CONNECTOR_CALL + WROTE_PRIMITIVE, honors `--expansion-budget` (parallel
  dispatch via asyncio), and falls through to fallback on failure.
- **Ingest orchestrator + freshness CLI** (`strata/ingest/`, `cli.py`, PR #50) —
  `strata ingest run|status|refresh`, driven by a declarative
  `ingest-manifest.yaml` (repo root). De-dups by `auto_args_hash`, skips
  key-less connectors (logged, non-fatal); `refresh` rewrites only when
  `snapshot_sha256` changed.
- **Read-only pyramid graph** (`web/src/app/graph/`, PR #48) — `/graph` renders
  the 3-axis pyramid (Qualitative · Quantitative · Industry) with geo/time
  filter chips, click-to-narrow sibling greying, and a compatible-frameworks
  side panel. Built on the existing ReactFlow + Tailwind 4 + TanStack/Zod
  stack; no new dependencies.
- **Deploy + CI + refresh cron** (PR #47) — `backend/entrypoint.sh`
  (migrate → seed → serve), `.github/workflows/ci.yml` (PR gate),
  `.github/workflows/refresh.yml` (weekly `strata ingest refresh` → auto-PR),
  explicit SQLAlchemy pool settings in `config.py`, every `STRATA_*` var
  documented in `.env.example`, and a Railway `[deploy] startCommand`.

#### Changed
- **`/resolve` SSE** (`api/routes/resolve.py`, PR #49) — now drives
  `resolver.pipeline.run()` via `asyncio.to_thread` and emits only the 6 frozen
  wire events (+ legacy step/done); CLI-only event kinds no longer leak.
  Removed `FRAMEWORK_TEMPLATES` / `_select_framework`.
- **CI type/lint gate scoped to `src/`** at zero errors; `db/models.py` JSONB
  columns parameterized (`Mapped[dict[str, Any]]` / `Mapped[list[Any]]`) so
  `pyright src` is clean. The pre-existing `tests/` strict-mode debt is tracked
  as a follow-up rather than gated.
- **`VERSION` → 0.3.0** — promoted out of alpha.

#### Tests
- 400 backend tests passing (adds dispatch 12, goal-SSE 5, ingest-CLI 16).

---

### v0.3 — `strata goal` CLI + 7 connectors + manifest-LLM router (PR #45)

Adds free-form TAM queries on the CLI and the connector + router scaffolding
behind them. Closes the "I don't know the slug" gap so any VC or operator can
type a question and get a sourced TAM back.

```
strata goal "<query>"
        │
        ▼  4-step resolver: cheap path first, LLM last
   ┌────────────────────────────────────────────────┐
   │ pre. slug resolver  Claude → ResolvedQuery     │
   │ 1.   concept hit    registry → ready TAM       │
   │ 2.   primitive hit  registry → sourced value   │
   │ 3.   connector live router → API → write to    │
   │                       ~/.strata/auto-primitives │
   │ 4.   fallback       Claude+Exa → ephemeral TAM │
   └────────────────────────────────────────────────┘
```

### Added
- **`strata goal "<query>"` CLI** — free-form TAM queries through a 4-step
  hybrid resolver (concept → primitive → connector → fallback). Output modes:
  compact (default), `--stream` (chain-of-thought), `--json`. Flags:
  `--no-live`, `--no-fallback`, `--primitive-only`, `--expansion-budget`.
  Env: `STRATA_OFFLINE=1` short-circuits steps 3 + 4 (CI-friendly). Full
  spec at `docs/superpowers/specs/2026-05-27-strata-goal-cli-and-connectors-design.md`,
  user howto at `docs/13-strata-goal-cli.md`.
- **`strata promote <slug>` CLI** — moves an auto-primitive from
  `~/.strata/auto-primitives/{slug}.yaml` into the committed
  `data/primitives/{slug}.yaml` after running the full validator pipeline.
  Idempotent.
- **`strata.resolver` module** — extracted Claude+Exa pipeline from
  `api/routes/resolve.py` so the new `goal` CLI and existing `/resolve` HTTP
  surface share one implementation. New submodules: `slug.py` (single Claude
  call mapping query → ResolvedQuery, cached system block), `parse.py`,
  `search.py`, `writer.py` (writes auto-primitives, validates against
  AtomicPrimitive schema, idempotent dedup via `auto_args_hash` metadata),
  `pipeline.py`, `render.py`, `events.py` (PipelineEventKind frozen wire
  contract enum).
- **`strata.router`** — manifest+LLM router with all 22 connector
  capabilities serialized into a cached system block (5-min Anthropic prompt
  cache). Returns `RoutingDecision | None`. Demotes `is_fragile` and
  `requires_paid_tier` capabilities unless explicitly opted in.
- **CapabilitySpec manifest schema** on all 22 connectors. Each connector
  exposes a `capabilities()` module function returning a list of
  `CapabilitySpec` (connector / method / args / source_tier / is_fragile /
  requires_paid_tier). `strata.connectors.all_capabilities()` walks every
  module and concatenates them — this is the router's input.
- **7 new connectors** (`backend/src/strata/connectors/`):
  alpha_vantage (aggregator, fragile — free tier 25 req/day),
  nasdaq_data_link (aggregator; premium gated by `requires_paid_tier`),
  yfinance (analyst, fragile — unofficial Yahoo scraper),
  reddit (community — subscribers as count primitives),
  github (community — stars/forks/issues as count primitives),
  stack_exchange (community — question count per tag),
  twitter (analyst, fragile — only the 2 free-tier endpoints
  `user_lookup_by_username` + `user_timeline`; paid-only endpoints
  intentionally not stubbed per audit fix F).
- **Frontend resolver bindings** (`web/src/lib/`): Zod schemas mirroring
  every backend resolver/router Pydantic model (`resolver-schemas.ts`),
  streaming SSE consumer for `POST /resolve` (`resolver-client.ts`),
  TanStack mutation hook (`resolver-queries.ts`), plus a `PipelineTrace`
  component for rendering `--stream` events in the right rail.
- **`STRATA_OFFLINE` env var** — CI shorthand for `--no-live --no-fallback`.
- **7 new env-var entries in `.env.example`** for the new connectors,
  matching fields added to `Settings` in `backend/src/strata/config.py`.

### Changed
- **`api/routes/resolve.py` refactor** — internal Claude+Exa helpers
  (`_parse_query_with_claude`, `_search_primitive_with_exa`) replaced by
  imports from `strata.resolver.{parse,search}`. The §9.1 SSE wire contract
  is **frozen**: `parsing` / `searching` / `framework_selected` /
  `evaluating` / `result` / `error`. Legacy `step` + `done` events kept for
  the existing frontend. A regression test
  (`tests/test_sse_event_contract.py`) ties the frozen wire set to the
  `PipelineEventKind` enum so renames break compilation. Downstream code
  that imported the old `_parse_query_with_claude` directly must move to
  `strata.resolver.parse.parse_query`.

### Tests
- 367 backend tests passing (310 → 338 → 354 → 367 across PR-A and PR-B).
- 10 frontend Vitest tests covering the resolver Zod schemas + SSE parser.

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

[Unreleased]: https://github.com/ArkashJ/Strata/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/ArkashJ/Strata/compare/v0.1.0...v0.3.0
[0.1.0]: https://github.com/ArkashJ/Strata/releases/tag/v0.1.0
