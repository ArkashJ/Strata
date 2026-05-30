# Strata — YC Execution Spec (technical, testable)

> Executable companion to [`16-adversarial-yc-readiness-review.md`](16-adversarial-yc-readiness-review.md)
> (the 116-rec backlog) and [`17-yc-remediation-plan.md`](17-yc-remediation-plan.md) (the wave
> sequencing). This file is the **implementation contract**: per wave — an **End Goal**, **Acceptance
> Criteria** (each a runnable/observable assertion), a **Technical Design** (files, signatures, schemas,
> API/MCP/DB contracts), and a **TODO** checklist. An item is "done" only when its acceptance criteria
> pass under the global gate.

## Global definition of done (every wave)

```
uv run pytest                # green, no skips added to dodge failures
uv run pyright               # 0 errors (strict)
uv run ruff check . && uv run ruff format --check .
cd web && bun run build      # (or npm run build) — prod build green
cd web && bun run typecheck  # tsc --noEmit clean
```

- Each wave opens **one PR**, bumps `VERSION`, adds a `CHANGELOG.md [Unreleased]` block.
- No CLAUDE.md hard-rule violations: no invented figures; no LLM-projected primitives (Q20);
  composites = same-unit set-ops only (Q3); frameworks have no scalar defaults (Q15); annotations
  never affect math (E1); citations are sha256-pinned (Q5); don't rename the project; confirm before
  changing `web/` tooling.
- **Adversarial verify**: after building a wave, run the relevant audit lens(es) from doc 16 as a
  subagent and confirm the targeted findings flip from FAIL→PASS.

## Score targets (re-audit gate)

| Milestone | Overall YC score | Gating waves |
|---|---|---|
| Current | 42 | — |
| Demo-ready | 65 | 0, 1, 5A, 5C-viz |
| Diligence-ready | 80 | + 2, 3, 4 |
| Moat-proven | 88 | + 5B, 5C-live |

---

## WAVE 0 — Demo-blockers (make the thesis TRUE on clicked surfaces)

### End goal
A first-time VC can type a market → get a **triangulated** scenario-tree TAM with real source spread →
edit an assumption → recompute live → open a **share link that resolves and renders** — with zero
surface that contradicts "TAMs are scenario trees, sourced and reproducible."

### Acceptance criteria
- **AC0.1** `GET /tam/<hash>` returns 200 for any hash minted by `GET /build/{slug}` or
  `POST /build/recompute` (persist evaluated TAMs into `reg.tam_outputs`, FIFO-capped). Assert
  `test_recomputed_tam_permalink_resolves`, `test_built_tam_permalink_resolves`.
- **AC0.2** `POST /resolve` for a query that matches a curated concept returns `via="concept"` and a
  scenario tree with **≥2 scenarios from ≥2 distinct frameworks/methods** (not a single point). Assert in
  a new `test_resolve_concept_returns_tree`.
- **AC0.3** `POST /resolve` for a novel query returns `estimate_kind="single_method"` AND a non-null
  honesty `banner`; it never emits a `point`-labeled scalar dressed as a TAM.
- **AC0.4** `grep -r "strata.internal" backend/ ` returns **0** citation URLs in any emitted payload
  (covered fully in Wave 1, stub here: resolver must not synthesize citation hosts).
- **AC0.5** `data/signals/` exists; `data/primitives/` contains **0** files with `tier: prediction_market`;
  `strata stats` reports a "sizing-grade primitives" count that excludes signals. Assert
  `test_no_prediction_market_in_primitives`.
- **AC0.6** ≥5 concepts have non-empty `competing_concepts` with ≥2 independently-sourced measurements
  whose values differ by ≥10%; the `/c/<slug>` disagreement bar renders >1 bar. Assert
  `test_demo_concepts_are_triangulated` (iterate the curated demo set).
- **AC0.7** A built TAM's `independence_score > 0` for the ≥5 demo concepts (≥2 method families).
- **AC0.8** `/tam/<hash>` page emits OpenGraph tags (`og:title`, `og:description`, `og:image`) and is
  server-rendered (view-source shows the TAM headline, not an empty `#root`). Playwright asserts
  `meta[property="og:image"]` present and TAM value in initial HTML.

### Technical design
- **Resolver registry-first** — replace `_http_slug` (resolve.py:66) so it attempts
  `registry.match_concept(query)` (exact slug → fuzzy ≥ threshold) and returns
  `ResolverIntent.CONCEPT` on hit. On concept hit, call `size_concept(reg, slug)` and map the
  `TAMOutput.scenarios` into the SSE `scenarios` array (label per `framework_variant`/`expansion_stage`).
  Keep NOVEL fallback for misses. New: `resolver/match.py::match_concept(reg, query) -> str | None`.
- **Tree on novel path** — `ResolverResult` gains `scenarios: list[ScenarioLite]` where
  `ScenarioLite = {label, value, method, framework, triangulated: bool}`. Novel path emits a single
  `triangulated=False` scenario; concept path emits the full set. Update `events.py` + `render.py` + the
  SSE `result` payload. Frontend `ResolveResultChart.tsx` already consumes `{label,value}` — extend to
  show the honesty banner when `triangulated=false`.
- **Kalshi quarantine** — move 202 `tier: prediction_market` YAMLs from `data/primitives/` →
  `data/signals/`. Loader: `load_data_dir` skips `signals/` for the primitive registry but exposes a
  `registry.signals` dict (read-only, never feeds frameworks). Update `strata stats` to print both
  counts. Migration: a one-shot `scripts/quarantine_signals.py` (idempotent, git-mv based) + update
  any test fixtures referencing those slugs.
- **Triangulated demo concepts** — author 5–8 concepts each with `competing_concepts: [...]` and ≥2
  atomic primitives from **independent sources** measuring the same quantity (e.g. US software-engineer
  headcount: BLS OEWS vs Census CBP). Add a second framework variant per concept so
  `method_families_used` ≥ 2 → `independence_score > 0`. Validate with `strata validate`.
- **OG + SSR for `/tam/<hash>`** — convert the route to a Next.js Server Component that fetches the TAM
  server-side and exports `generateMetadata()`; add an OG image route
  (`web/src/app/tam/[hash]/opengraph-image.tsx`) rendering value + concept + tier ring via
  `next/og` `ImageResponse`.

### TODO
- [ ] `resolver/match.py::match_concept` + unit tests (exact + fuzzy + miss).
- [ ] Wire registry-first into `resolve.py`; concept hit → `size_concept` → tree.
- [ ] `ResolverResult.scenarios` + SSE `result.scenarios` (multi-scenario); update `render.py`.
- [ ] `test_resolve_concept_returns_tree`, `test_resolve_novel_single_method`.
- [ ] `scripts/quarantine_signals.py`; move 202 files; `registry.signals`; loader skip.
- [ ] `strata stats` dual count; `test_no_prediction_market_in_primitives`.
- [ ] Author 5–8 triangulated demo concepts + 2nd variants; `competing_concepts` wired.
- [ ] `test_demo_concepts_are_triangulated`, `test_demo_concepts_independence_positive`.
- [ ] `/tam/[hash]` → Server Component + `generateMetadata` + `opengraph-image.tsx`.
- [ ] Playwright: share-link renders TAM + OG tags present.

---

## WAVE 1 — AI defensibility + data rigor (the credibility core)

### End goal
Every number Strata emits is grounded in a real, snapshotted, hash-verified source; the resolver cannot
fabricate a citation or a tier; resolver quality is measured by a regression eval, not vibes.

### Acceptance criteria
- **AC1.1** No emitted citation URL has a host not present in an allowlist of real source domains; a
  fabricated/`strata.internal` URL fails CI. Assert `test_no_synthetic_citation_hosts` (scans resolver
  output for novel hosts).
- **AC1.2** Source tier is **never** assigned by the LLM. The resolver derives tier from the matched
  connector/source record; a unit test feeds an LLM response claiming `tier: regulator` and asserts the
  emitted tier comes from the source registry, not the model.
- **AC1.3** Every primitive load verifies `sha256(snapshot_bytes) == snapshot_sha256`; a tampered
  snapshot raises `IntegrityError`. Assert `test_snapshot_integrity_enforced`.
- **AC1.4** A verifier/critic pass runs on every novel resolve: it re-checks unit compatibility and
  flags any input whose value is >Nσ from the source's plausible range; flagged results carry a
  `dark_estimate` banner. Assert `test_resolver_verifier_flags_outlier`.
- **AC1.5** A resolver eval harness (`backend/evals/resolver_eval.py`) runs ≥20 golden queries with
  expected concept/lens/order-of-magnitude and reports pass-rate; CI fails if pass-rate < baseline.
  `uv run python -m strata.evals.resolver_eval --assert-baseline 0.8`.
- **AC1.6** Resolver responses are unit-checked end-to-end: multiplying inputs with incompatible
  `Unit` signatures raises before emit (no silent scalar multiply). Assert `test_resolve_unit_guard`.
- **AC1.7** Staleness: any primitive whose `as_of` (data period, not ingest date) is older than its
  source's freshness SLA renders a `stale` chip in `/c` and `/build`; assert in component test.

### Technical design
- **Citation allowlist** — `resolver/citations.py::SOURCE_HOSTS: frozenset[str]` derived from
  `data/sources/*.yaml` `url` hosts + connector base URLs. `assert_real_host(url)` raises on miss.
  Replace any resolver-synthesized URL with the matched source record's real URL or `None`.
- **Tier from source, not model** — in `resolver/pipeline.py` step 2/3, tier is read from the
  `Source` record (`source.tier`) keyed by the primitive's `source_id`; strip any `tier` field the LLM
  returns. Add `parse.py` schema that forbids `tier` in the model's JSON (extra="forbid").
- **Integrity** — `loader.py` (or `connectors/writer.py`) computes sha256 over the stored snapshot and
  compares to `snapshot_sha256`; new `strata.errors.IntegrityError`. CLI `strata verify-integrity`.
- **Verifier agent** — `resolver/verify.py::verify(result, reg) -> list[Flag]`. Cheap deterministic
  checks first (unit compat, range bounds from `source.plausible_range` if present); optional LLM critic
  behind a flag. Flags → `ScenarioBanner(kind=dark_estimate)`.
- **Eval harness** — `backend/src/strata/evals/resolver_eval.py` + `evals/golden.yaml` (query →
  expected concept_slug | lens | magnitude_bucket). Runner prints a table, returns nonzero on regression.
  Wire into a CI job `evals` (allowed to use `STRATA_OFFLINE=1` with recorded fixtures).
- **Staleness** — add `freshness_sla_days` to `Source`; evaluator/`/c` compute `is_stale`; web
  `TierBadge`/new `StaleChip`.

### TODO
- [ ] `resolver/citations.py` allowlist + `assert_real_host`; purge synthetic URLs.
- [ ] `test_no_synthetic_citation_hosts`.
- [ ] Strip LLM-supplied `tier`; derive from `Source`; `test_tier_from_source_not_model`.
- [ ] sha256 verification in load path; `IntegrityError`; `strata verify-integrity`; test.
- [ ] `resolver/verify.py` + `dark_estimate` banner wiring; outlier test.
- [ ] `evals/resolver_eval.py` + `golden.yaml` (≥20) + CI job + baseline assert.
- [ ] End-to-end unit guard on resolve; `test_resolve_unit_guard`.
- [ ] `freshness_sla_days` on Source; `is_stale`; `StaleChip` + component test.

---

## WAVE 2 — Motion & visual craft (the "expensive" feel)

### End goal
The product *feels* like Linear/Vercel: the recompute has a satisfying payoff animation, the pyramid is
a live interactive instrument (not a diagram), and numbers/charts animate in with intent — all
respecting `prefers-reduced-motion`.

### Acceptance criteria
- **AC2.1** On recompute, the changed TAM value animates (count-up from old→new) and affected graph
  nodes pulse; verified by a Playwright trace asserting the value cell text changes over ≥3 frames.
- **AC2.2** Pyramid node **right-click** opens a context menu (Expand children / Suggest framework /
  Annotate); **hover** shows a ghost card after **250ms** with value+source+snapshot. Playwright asserts
  `contextmenu` opens a menu and hover-delay card appears.
- **AC2.3** A sensitivity **tornado chart** renders per TAM showing each input's swing on the output;
  component test asserts bars sorted by |impact|.
- **AC2.4** All entrance/transition motion is gated by `prefers-reduced-motion`; with it set, no
  transform/opacity animations run (assert via `motion.tsx` honoring the media query — existing
  `useReducedMotion` path covered by test).
- **AC2.5** Lighthouse "Cumulative Layout Shift" < 0.1 on `/build` and `/`; skeleton→content uses
  matched dimensions (no jump).

### Technical design
- Extend `web/src/components/ui/motion.tsx` with `CountUp` (rAF-based, reduced-motion → instant) and
  `Pulse`. Wire `CountUp` into the TAM value cells and `ScenarioBarChart`.
- `PyramidGraph.tsx`: add `onNodeContextMenu` → `<NodeContextMenu/>`; add a 250ms hover-intent hook
  `useHoverIntent(delay)` → `<GhostCard/>` (value/source/snapshot). OR semantics for shift-click made
  visible (selected siblings highlight).
- New `web/src/components/charts/TornadoChart.tsx` fed by an evaluator endpoint
  `GET /build/{slug}/sensitivity` returning per-input low/high swing (compute by ±x% perturbation
  through `size_concept`).
- Recompute payoff: optimistic UI → on response, `CountUp` old→new + node `Pulse`.

### TODO
- [ ] `CountUp`, `Pulse`, `useHoverIntent` in motion layer (+ reduced-motion tests).
- [ ] `NodeContextMenu`, `GhostCard`; wire into `PyramidGraph`.
- [ ] `GET /build/{slug}/sensitivity` + `TornadoChart`.
- [ ] Recompute payoff animation; Playwright trace test.
- [ ] CLS audit + skeleton dimension matching.

---

## WAVE 3 — Architecture, trust & ops (company substrate)

### End goal
Strata is a multi-tenant product with authenticated, metered, rate-limited APIs, real observability, and
a CI that gates regressions — ready to take paying customers and (Wave 5C) private data.

### Acceptance criteria
- **AC3.1** API key auth on all write/compute + LLM routes; missing/invalid key → 401. `test_auth_required`.
- **AC3.2** `/resolve` (and other LLM routes) rate-limited per key (token bucket); exceeding → 429 with
  `Retry-After`. `test_rate_limit_429`.
- **AC3.3** Per-key usage metering persisted (`usage_events`); `GET /usage` returns counts. `test_metering`.
- **AC3.4** CORS is **not** wildcard in prod; allowed origins from config. `test_cors_not_wildcard_prod`.
- **AC3.5** Structured request logging + a `/metrics` (Prometheus) or OTel exporter; a trace id on every
  response header. `test_request_id_header`.
- **AC3.6** Tenancy substrate: `org_id` on requests, Postgres RLS policies present (verified by a
  migration test that cross-tenant reads return 0 rows).

### Technical design
- `api/auth.py` dependency: API key → `Principal{org_id, key_id, scopes}`; stored hashed in
  `api_keys` table. `api/ratelimit.py` token-bucket (in-proc + Redis-ready interface).
  `db/models.py`: `ApiKey`, `UsageEvent`. Alembic migration. `config.py`: `allowed_origins`,
  `rate_limit_rpm`. Middleware: request-id + structured log + timing. OTel optional behind env.
- RLS: migration adds `org_id` columns + `ENABLE ROW LEVEL SECURITY` + policies keyed on
  `current_setting('app.org_id')`; session sets it from the Principal.

### TODO
- [ ] `api/auth.py` + `api_keys` table + migration; `test_auth_required`.
- [ ] `api/ratelimit.py` token bucket; `test_rate_limit_429`.
- [ ] `usage_events` + `GET /usage` metering; `test_metering`.
- [ ] CORS prod-tighten via config; `test_cors_not_wildcard_prod`.
- [ ] Request-id + structured logging middleware + `/metrics`/OTel; header test.
- [ ] `org_id` + RLS migration; cross-tenant isolation test.

---

## WAVE 4 — GTM, moat & narrative

### End goal
Strata has a working growth loop (shareable, indexable TAM pages + embeddable widget), a thin
contribution path, and a coherent, non-self-contradicting story.

### Acceptance criteria
- **AC4.1** `/browse` lists promoted TAMs; each `/tam/<hash>` is SSR + in `sitemap.xml`; a crawler
  (curl) sees the headline in HTML. `test_sitemap_lists_promoted_tams`.
- **AC4.2** An embeddable widget (`/embed/tam/<hash>`) renders a compact TAM card in an iframe with
  `X-Frame-Options`/CSP allowing embed; snapshot test.
- **AC4.3** A contribution endpoint accepts a proposed primitive/annotation as a PR-shaped payload, runs
  the validator, and returns accept/reject with reasons (no auto-publish of low-tier). `test_contribute_validates`.
- **AC4.4** Docs consistency: a CI check asserts `VERSION` == `pyproject` == latest tag prefix, README
  connector/test counts match `strata stats`/`pytest --collect-only -q | wc -l`. `test_docs_counts_match`.

### Technical design
- `sitemap.ts` route generating entries for `is_promoted` TAMs; `robots.txt`. `web/src/app/embed/tam/[hash]`
  minimal renderer + relaxed frame policy on that path only. `POST /contribute` → reuse
  `strata.validators` L1/L2; persist proposals to a `contributions` table with status. A
  `scripts/check_doc_counts.py` invoked in CI.

### TODO
- [ ] `sitemap.xml` + `robots.txt` for promoted TAMs; crawler test.
- [ ] `/embed/tam/[hash]` + frame policy; snapshot.
- [ ] `POST /contribute` + validator gate + `contributions` table; test.
- [ ] `check_doc_counts.py` + CI; fix existing drift.

---

## WAVE 5 — Integrations, MCP & the data-pipeline moat

### End goal
(1) Anyone can add Strata to Claude as an MCP server and get **sourced, hash-pinned** market numbers
inside their agent. (2) A fund can OAuth-connect its own SaaS data (HubSpot/Stripe/Salesforce/…), which
becomes **private first-party primitives** that sharpen its TAMs and never leak — the data network
effect. (3) A polished `/integrations` surface (brand icons + pipeline viz) sells it.

### 5A — Strata MCP server ("Connect to Claude")

#### Acceptance criteria
- **AC5A.1** `strata-mcp` starts via stdio and over a hosted HTTP/SSE transport; `mcp` inspector lists
  the tools. Smoke: `uv run python -m strata.mcp.server --stdio` responds to `tools/list`.
- **AC5A.2** Tools exposed with typed JSON Schemas: `search_concepts(query, limit)`,
  `get_primitive(slug)`, `list_frameworks()`, `size_tam(concept_slug | query)`,
  `resolve_market(query)`. Each returns sourced payloads **with citations + snapshot_sha256**; a tool
  result never contains a fabricated host (reuses Wave-1 allowlist). `test_mcp_tools_sourced`.
- **AC5A.3** Read-only: no MCP tool mutates the registry or writes primitives. `test_mcp_readonly`.
- **AC5A.4** Auth: hosted endpoint requires the Wave-3 API key; stdio mode is local-trust.
- **AC5A.5** A `claude mcp add strata …` snippet in README works against the hosted URL (manual-verified;
  documented).

#### Technical design
- `backend/src/strata/mcp/server.py` using the official `mcp` Python SDK (`Server`, `@server.list_tools`,
  `@server.call_tool`). Tool handlers call the **existing** registry/evaluator/resolver — no logic fork.
  `mcp/schemas.py` holds the input JSON Schemas. Transports: stdio (local) + ASGI mount at
  `/mcp` on the FastAPI app for remote (auth-gated). Package entry: `pyproject` script `strata-mcp`.
  Tool outputs are the same Pydantic models serialized with citations.

#### TODO
- [ ] Add `mcp` dep; `mcp/server.py` + `mcp/schemas.py`; 5 tools over existing engine.
- [ ] stdio entrypoint + `/mcp` ASGI mount (auth-gated in prod).
- [ ] `test_mcp_tools_sourced`, `test_mcp_readonly`.
- [ ] README `claude mcp add` snippet + hosted URL.

### 5B/5C-live — Inbound OAuth data connectors (private primitives)

#### Acceptance criteria
- **AC5B.1** OAuth handshake completes for the pilot connector (HubSpot **or** Stripe); tokens stored
  encrypted, scoped to `org_id`. `test_oauth_token_scoped_encrypted` (mocked provider).
- **AC5B.2** A fetch→normalize→primitive step produces a `tier: first_party`, `banner: private`
  primitive in the org namespace; it is **excluded** from `/browse`, public seed, and other tenants'
  registries. `test_private_primitive_isolated` (cross-tenant read = 0).
- **AC5B.3** A private primitive feeds `size_concept` exactly like a public one (same evaluator), and the
  resulting TAM carries a `private` banner. `test_private_primitive_feeds_evaluator`.
- **AC5B.4** Disconnecting a source purges its tokens and tombstones its private primitives
  (no orphan data). `test_disconnect_purges`.
- **AC5B.5** Connector framework is generic: adding a second provider requires only a
  `SaaSConnector` subclass + object→role mapping (no core changes). Demonstrated by a second stub provider.

#### Technical design
- `connectors/saas/base.py::SaaSConnector` (abstract: `authorize_url`, `exchange_code`, `fetch`,
  `to_private_primitives`). Concrete `connectors/saas/hubspot.py` (or `stripe.py`). Reuse
  `connectors/_dispatch.py` convert pattern. `db/models.py`: `OAuthCredential` (encrypted, `org_id`),
  `PrivatePrimitive` (or reuse primitive table + `org_id` + `visibility=private` + RLS). Routes:
  `GET /integrations/{provider}/authorize`, `GET /integrations/{provider}/callback`,
  `POST /integrations/{provider}/sync`, `DELETE /integrations/{provider}`. Encryption via app KMS/env
  key (`cryptography.fernet`). Object→primitive mapping config per provider (`mapping.yaml`).
  **Gate:** depends on Wave-3 auth + RLS (hard prerequisite before any real customer data).

#### TODO
- [ ] `SaaSConnector` base + pilot provider (HubSpot/Stripe) end-to-end.
- [ ] `OAuthCredential` (encrypted, scoped) + migration; `test_oauth_token_scoped_encrypted`.
- [ ] Private-primitive namespace + RLS + evaluator feed; isolation + feed tests.
- [ ] authorize/callback/sync/disconnect routes; disconnect purge test.
- [ ] Object→role mapping config; second stub provider proves genericity.

### 5C-viz / 5D — `/integrations` gallery, brand icons, pipeline viz

#### Acceptance criteria
- **AC5C.1** `<BrandIcon name=…/>` renders SVG marks for all vendors (GitHub, Slack, Gmail, Notion, Jira,
  Linear, Teams, Salesforce, HubSpot, Snowflake, Stripe, QuickBooks, Google Sheets, Segment, Airtable,
  Anthropic/Claude) + the 15 gov sources; unknown name → fallback glyph, never a crash. `BrandIcon.test.tsx`.
- **AC5C.2** `/integrations` renders three groups (Inbound / Outbound / Public data bank) of cards
  `[icon · name · status · CTA]` with statuses `connected | available | coming-soon`; reduced-motion safe.
- **AC5C.3** "Old way vs new way" comparison card renders (red broken / green working) with icon clusters,
  matching the reference layout.
- **AC5C.4** Animated pipeline flow (`sources → Strata engine: Documents/Web/Data-Analysis → verifier
  review → outputs: TAM/Report/API/MCP`) using ReactFlow + existing motion; nodes + edges animate;
  honors reduced-motion. Snapshot/interaction test.
- **AC5C.5** `web build` + `typecheck` green; no new lint.

#### Technical design
- `web/src/components/icons/brands/` — one component backed by `simple-icons` SVG paths + a small
  hand-traced set for marks not in simple-icons; `brand-registry.ts` maps `name → {path, hex}`; render
  in a circular chip with a source-tier ring (`TierBadge` color tokens). `web/src/app/integrations/page.tsx`
  (Server Component) reads a static `integrations.ts` catalog (provider, group, status). `IntegrationCard`,
  `OldVsNewCard`, `PipelineFlow` (ReactFlow graph mirroring `network/` patterns + `motion.tsx` edges).
  Connect buttons deep-link to the Wave-5B authorize routes (disabled with "coming soon" until live).

#### TODO
- [ ] `simple-icons` dep (confirm web-tooling change with user first) **or** vendored SVGs; `BrandIcon` + registry + test.
- [ ] `integrations.ts` catalog + `/integrations` page + `IntegrationCard`.
- [ ] `OldVsNewCard` (reference image 1).
- [ ] `PipelineFlow` animated viz (reference images 2 & 3).
- [ ] lucide UI icons replace text-only markers; status dots; MCP "live" pulse.

---

## Cross-wave end-state checklist (the "are we YC-ready" gate)

- [ ] Live demo: query → triangulated tree → edit → recompute → share link renders (Wave 0).
- [ ] Every number sourced, hash-verified, no fabricated citations; resolver eval ≥ baseline (Wave 1).
- [ ] Motion/interactions read as "expensive"; pyramid is a live instrument (Wave 2).
- [ ] Auth + metering + rate-limit + tenancy + observability (Wave 3).
- [ ] Indexable/shareable/embeddable growth loop + consistent docs (Wave 4).
- [ ] Strata-in-Claude via MCP **and** connect-your-CRM private primitives, sold by `/integrations` (Wave 5).
- [ ] Re-run the 11-lens audit (workflow); overall score ≥ 80; the five existential risks all flipped.
