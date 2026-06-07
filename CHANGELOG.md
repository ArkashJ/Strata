# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — the MCP is now a report-building harness an AI agent drives (backend)

- **An agent connected to Strata can now build a sourced, defensible market
  report back-and-forth, not just read one number.** Each tool result is typed,
  carries one-click drill-down links to the source behind every figure, and
  suggests the next step the agent can take (drill down, challenge an assumption,
  assemble the report). Old text-only clients still work.
- **Verify an AI-generated market claim** — the new `verify_market_claim` tool
  takes a claim ("the X market is $Y by 2027") and returns a verdict
  (supported / partially supported / unsupported / unverifiable) against Strata's
  sourced range, with the named, dated, hash-pinned inputs behind it. A claim
  Strata has no sourced data for comes back **unverifiable** — it never makes a
  number up.
- **The report now matches the exact number on screen.** Previously the report
  re-sized the market from scratch, so a "what-if" you steered could disagree
  with the report. `get_report_for_tam(<hash>)` (and `GET /tam/<hash>/report`)
  now bind the report to that exact TAM — overrides included.
- **Browse the data as resources.** An agent can list and read Strata records by
  address (`strata://primitive/…`, `concept/…`, `framework/…`, `tam/…`,
  `report/…`, `chart/…`) — e.g. `@`-mention a primitive in Claude Code.
- **Charts the agent's app can render** — every sizing result now carries
  chart specs (Vega-Lite + Mermaid) built only from the sourced numbers.
- **Guided workflows** — `strata.size / verify / report / portfolio` prompts
  script the loop so the agent follows the analyst's method, not guesswork.
- **Trust hardening** — every figure shows a snapshot integrity status; one
  shared fence now guards both the website and the agent write paths so a
  modeled estimate can't slip in through either; every agent call is audited.

  ```
  ask ─▶ size_tam / verify_market_claim ─▶ sourced TAM (+ links, charts)
       ─▶ challenge (what-if) ─▶ new /tam/<hash>
       ─▶ get_report_for_tam(<hash>) ─▶ report bound to that exact number
  ```

### Added — market reports now look like a $1M consulting deck

- **The report at `/tam/<hash>/report` is now a Coatue/Gartner-grade
  presentation, not a plain one-pager.** It opens with a bold editorial headline
  stating the takeaway, an executive figure strip (the triangulated TAM, the
  range, how many independent methods agree, and an independence score), the
  top-down-vs-bottoms-up cross-check, a ranked comparison of every method, a
  "how the number builds" factor bridge coloured by source quality, the
  sensitivity view (which assumption to defend first), and a sources appendix
  where every figure is named, dated, tiered, and snapshot-pinned.
- **Honest by design.** Sections with no sourced data (a competitive set or an
  adoption curve we haven't sourced yet) say so plainly instead of inventing a
  number. A market with only one method shown is labelled as such — no fake
  second method.
- **Look and feel.** Numbers use tabular Geist Mono; charts carry a title, a
  unit, and a source footnote; light and dark both supported; motion respects a
  reader's reduced-motion setting; no gradients or glassmorphism. The colour rule
  is consistent: warm tier colours always mean source quality, cool colours
  always mean method — they never cross.
- The new building blocks are reusable across the app and were built in
  Storybook (the auth-free design loop) before wiring into the page. The classic
  print-first one-pager is unchanged and is still what "Save as PDF" produces.

```
TAM (sized, sourced) ─▶ /tam/<hash>/report
  headline ─▶ figure strip ─▶ cross-check ─▶ method comparison
           ─▶ how-it-builds ─▶ sensitivity ─▶ sources appendix
  (any section with no data → an honest "not sourced yet" note)
```

### Added — connect Strata to claude.ai and ChatGPT in one click (OAuth)

- **The hosted Strata connector now works in the claude.ai and ChatGPT websites,
  not just Claude Code and Claude Desktop.** Those websites only offer a
  one-click "sign in" connector — they have no field to paste a key — so until
  now you couldn't add Strata there. Strata now runs that sign-in itself: you
  paste the connector URL, sign in with your existing Strata (Google) account on
  a Strata "Allow access?" screen, approve, and the agent is connected to your
  organization's data — the same data your website session sees. Key-based
  connect (Claude Code / Claude Desktop) is unchanged.

  ```
  paste URL ─▶ agent starts OAuth ─▶ sign in (Google) ─▶ "Allow Claude/ChatGPT
            to access your Strata org?" ─▶ approve ─▶ connected (your org's data)
  ```

  Built as a standard OAuth 2.1 sign-in alongside the existing connector, so it
  is added on top of — never replacing — the key and session sign-ins already in
  place. It stays switched off until the deployment sets the connector's web
  address; see the pull request for the settings to flip it on in production.

### Fixed — a market query can no longer be sized as the wrong market

- **Free-form queries that didn't name a curated market were being matched to an
  unrelated one and shown as a real, sourced answer.** "Market research tools"
  came back as "AI legal research (US lawyers) — $3.7B"; "pet insurance" came
  back as "P&C insurance document generation" — each on the strength of a single
  shared word ("research", "insurance"). The matcher compared raw letters, so
  coincidental overlap looked like a match. It now compares **words**, and a lone
  shared generic word no longer carries a match. A query that doesn't clearly
  name a curated market now falls through to the honest "synthesized — verify
  before citing" path instead of a confident wrong number. This also fixes the
  builder mis-sizing arbitrary markets.

  ```
  query ─▶ match words (not letters) ─┬─ clear match  ─▶ curated, sourced TAM
                                      └─ weak / generic ─▶ synthesized (verify) banner
  ```

- **Architecture diagrams expanded 41 → 54** (`docs/architecture/DIAGRAMS.md`):
  the resolver match ladder, unit algebra, source-tier taxonomy, request
  lifecycle, route/CLI surfaces, connector layering, data stores, and the full
  resolve sequence — plus a rendering fix for three older diagrams.
### Added — connect Strata to Claude with a self-serve API key

- **Generate an API key on the website, paste it into Claude.** A signed-in user
  visits `/agents`, clicks Generate, and copies a key (shown once). Pasting it
  into Claude (Code, Desktop, or claude.ai) as a connector gives that user's
  Claude the Strata toolset — sourced market sizing, the data bank, frameworks —
  scoped to their own account.

  ```
  website /agents ─▶ Generate key ─▶ strata_sk_live_… (copy once)
        └─▶ paste into Claude as an MCP connector ─▶ Claude calls Strata tools
                                                     (authenticated as your org)
  ```

- **Keys are safe by construction.** Only a one-way hash is stored — the secret
  is never saved and never shown again. Keys can be listed (masked) and revoked
  any time; a revoked key stops working immediately. One account can never see
  or revoke another's keys.

- **The connector got sturdier.** A `whoami` check confirms the connection and
  shows how much data the bank holds; long lists page properly; and each tool is
  labelled read-only vs write so Claude treats it correctly.

### Added — deploy runbook + a smoke test that proves a deploy took

- **A one-command check that a deploy actually landed.** `scripts/deploy-smoke.sh`
  pings the live backend's health, a route only the newest code serves (the
  "stale image" detector), the cross-origin permission the website needs, and the
  website itself — and exits non-zero if any of them is wrong. Paired with a
  written runbook (`docs/24-deploy-runbook.md`) that explains, in plain terms,
  every deploy gotcha and the exact commands to recover.

  ```
  deploy ─▶ smoke test ─┬─ backend healthy?         ─┐
                        ├─ newest code live?         ├─ all pass ─▶ green
                        ├─ website allowed by API?   │
                        └─ website up?               ─┘ any fail ─▶ non-zero + what to fix
  ```

### Changed — accessibility, dark mode, and input safety

- **The report charts and key controls now work with screen readers and the
  keyboard.** The TAM range bar, the coverage bars, and the "where the bank is
  thin" grid previously conveyed meaning through color and position only; they
  now announce their values as text. The lineage pop-up, sidebar, and collapsible
  panels gained the labels assistive tech needs.
- **Dark mode fix.** Two number/string colors in the raw-data viewer were stuck
  at their light-theme values; they now follow the theme.
- **Safer inputs.** The market-resolve box, the sensitivity control, and the
  contributions filter now reject obviously bad input up front (empty/oversized
  query, out-of-range percentage, unknown status) instead of passing it deeper.
- **Link previews.** Pasting a Strata page into Slack/LinkedIn now resolves its
  preview image correctly (absolute URLs).

### Changed — frameworks are now 6 shapes, not 25

- **Honest framework count.** We described the engine as having "25 frameworks,"
  but they were really the **6 sizing shapes** (one per lens) repeated with small
  realism tweaks — a clamp here, an adoption curve there. They're now classified
  as **6 canonical shapes + 19 specializations (subframeworks)**, and a check
  refuses to let the count of distinct shapes quietly creep back up. No recipe was
  removed and no number changed — only how they're grouped and counted.

  ```
  6 lens shapes ─┬─ subframeworks (same shape: bounded · adoption-gated · …)
                 ├─ signals      (corroborate, never feed a TAM)
                 └─ perspectives (cross-checks/views on a computed TAM)
  ```

  Decision record: `docs/plans/2026-06-07-frameworks-taxonomy-reframe.md`.

### Changed — analyst-grade report redesign

- **The report now reads like a VC analyst deck, not a wall of text.** The top of
  every analysis report was three small donuts and a lot of empty space, then
  pages of text cards that reprinted the same five sources over and over. It is
  now a single executive summary a reader takes in at a glance: the headline TAM,
  a range bar showing how far the methods disagree (floor → midpoint → ceiling on
  a log scale), the trust signals (how many independent methods agree, how
  tightly), a coverage chart of which questions are answered, a map of where the
  data bank is thin, the mix of source types, and one clean table of every source
  behind the numbers. The per-question cards keep a compact source tag instead of
  repeating the full list.

  ```
  before: [donut][donut][donut] + whitespace ─▶ 15 pages of repeated text
  after:  headline TAM ─▶ range bar (methods disagree) ─▶ trust signals
          ─▶ coverage + gaps ─▶ source-type mix ─▶ one source ledger ─▶ tight Q&A
  ```

  Every number still comes only from a sourced figure or a reproducible
  calculation — nothing is invented. The dollar range chart shows same-unit
  figures only; mixed-unit measurements stay in the source table, never plotted
  as bars. The downloadable PDF reflects the same layout.

### Fixed — report charts, multi-page PDF, dynamic TAM unblock

- **The deployed site shows data again.** The live frontend
  (`stratabank.vercel.app`) looked empty ("No concepts loaded yet") even though
  the API had data: the production server wasn't allowing the website's address,
  so the browser blocked every data request. Production now allows the Strata
  website (and its preview links) by default, so the bank, concepts, and
  featured TAMs load. Other sites are still blocked.

  ```
  browser (stratabank.vercel.app) ─▶ API  ─ before: no allow-origin → blocked → empty
                                          └─ after:  allow-origin set → data loads
  ```
- **Size any market straight from /build.** Bare `/build` used to lock onto one
  default market ("Accrual") with no way to change it — so it looked like nothing
  worked. There's now a "Size a different market" box at the top of Build: type
  any market and it pins a curated one or resolves a new one live.
- **Report charts now print correctly.** The donuts were drawing as half-finished
  arcs in the PDF because their entry animation hadn't finished when the page was
  captured. Charts now render fully (animation off) in the report.
- **Analysis report now has charts.** Three charts at the top of every report,
  all built only from numbers already in the report (no new figures invented):
  an answered-vs-gaps donut, a coverage-by-category radar, and a source-tier
  mix donut.
- **"Print / Save as PDF" now spans the whole report.** It used to stop after
  one page because the app frame was locked to one screen height. Print now
  drops the sidebar/top bar, unlocks the scroll frame, and lets the report flow
  across pages (a sample report prints as 13 pages).
- **Dynamic TAM answers any market again (config).** Typing a market that isn't
  pre-built returned "Could not find enough market data" because the live
  fallback was switched off on the server. With it on, the fallback finds real
  sourced numbers and computes a TAM, clearly banner-marked "synthesized via
  fallback — do not cite without manual verification".

  ```
  query ─▶ in the bank?  ─yes─▶ sourced TAM
            └─no─▶ STRATA_ALLOW_EXA_FALLBACK on? ─yes─▶ Exa-sourced TAM (banner)
                                                  └─no──▶ "not enough data" (old behavior)
  ```
- **Dynamic TAM finds an answer far more often.** When a market isn't pre-built,
  the live search used to throw away any source that didn't return a highlighted
  snippet — so it often came up one number short and said "not enough data". It
  now also reads each source's summary, so real sources stop being discarded
  (e.g. "robotic lawn mowers in France" now returns a TAM where it previously
  failed). Numbers still come only from real, host-verified sources.

### Added — breadth to v1.0 (v1.0 program · PR 5)

The final PR of the program — frameworks, the missing lens, the quarantine fix,
semantic search, and concept promotion. **No fabricated numbers** (Q20): every new
primitive is live-sourced or honestly `community-modeled` with a MODELED banner,
a real range, and a resolvable anchor.

- **Frameworks 5 → 25** — all six lenses, each a structurally distinct math shape,
  validator-gated (no scalar defaults; every role binds a primitive slug). Includes
  the **`latent_demand` lens** (was 0 frameworks / 0 concepts):
  `latent-demand-adoption-curve` + `-saturating-curve` (`addressable_population *
  logistic(adoption_rate_curve) * willingness_to_pay`) with 2 sourced L3 concepts
  (India consumer digital lending, US senior digital health) backed by real World
  Bank population primitives. The new L3 concepts **size a real TAM**.
- **Fixed the community-quarantine bug (#102):** quarantine is now a property of the
  record via one shared non-sizing-tier constant imported by **both** the YAML loader
  and `Registry.from_db` — community/social data can no longer feed `reg.atomic` on
  the prod DB path. New `test_quarantine_paths.py` asserts the invariant on both
  paths.
- **`strata test-connectors`** rewritten — enumerates all 23 typed connectors with
  honest skip reasons; keyed connectors (alpha_vantage/reddit/twitter/nasdaq) flagged
  BLOCKED on API keys.
- **Semantic-embeddings search** (migration `010_pgvector`, `strata embed`, NN
  fallback in `match_concept`; registry-first stays primary) and **concept-promotion
  / intersection-auto-promotion** (validator-gated through the existing `/contribute`
  queue — never a direct public write).
- **Verified:** `strata validate ../data` 0 errors; pyright src 0; ruff clean;
  quarantine invariant test green on both paths; `latent_demand` concepts size a TAM.
  **BLOCKED:** live pgvector embedding population + keyed connectors (no extension /
  API keys here — code + migration ship inert).

### Added — dashboards + Gartner charts + real PDF export (v1.0 program · PR 3)

- **Gartner chart contract** (`ChartFrame` + `chart-colors`): a shared frame —
  axis titles + units, on-chart annotations, a title/subtitle/**source-footnote**
  ("source: BLS OEWS, 2024"), consistent margins, tier-ramp series. `ResolveResultChart`'s
  hardcoded hex `LENS_COLORS` is **tokenized** to the cool lens-family CSS vars
  (a colour means one thing).
- **Real PDF export:** every "Download PDF" now opens the clean
  `/tam/<hash>/report?print=1` (auto-prints the one-pager) instead of `window.print()`
  on the dense interactive workspace — build workspace, `/tam` rail, export menu.
- **Markdown provenance:** `tamToMarkdown` gains a Sources & provenance section
  (input · tier · source link · honest snapshot — "not pinned (demo)" for
  placeholders, never a fabricated hash).
- **Dashboards:** `/dashboard` is a board surface again (library counts, saved
  builds, audit feed); degrades gracefully signed-out. Board persistence is gated on
  live Clerk (BLOCKED locally, same as PR 1's `/me`).
- **Verified:** web tsc + biome clean; 188 web unit tests. (Server-side Playwright
  print-to-PDF remains the longer-term target — the clean-report print path ships now.)

### Added — Build Studio: live, steerable TAM tree (v1.0 program · PR 2)

Type a market, **watch the sourced tree assemble node-by-node**, and steer any
branch — over a single `/build/recompute` payload (no fake streaming; the program's
honesty principle forbids theater).

- **`/build?mode=studio`** — `BuildStudioView` reveals the apex TAM then each role
  leaf in turn, with a live count-up headline (`aria-live`) and a "BUILDING N/N"
  ledger rail. `deriveBuildSteps(tam, lens, state)` (pure, 14 unit tests) sequences
  the reveal; `prefers-reduced-motion` (and any existing override) renders the whole
  tree instantly — never a forced animation.
- **Source at every node** (#107): each role card shows its tier dot
  (provenance ramp), a clickable `source ↗`, and honest snapshot state
  ("not pinned (demo)" when unpinned) — the steerable tree carries its provenance.
- **Steer it:** reuses `OverridePanel` (swap / what-if → `/build/recompute` →
  re-mints `/build/<hash>`); editing resumes the reveal at the changed role. The
  steered tree rides the URL — sharing the link reproduces exactly what you see.
- **`LensPicker`** auto-suggests the concept's primary lens (pre-selected,
  confirmable), gated to lenses with ≥1 applicable framework variant (cool lens
  family, never the tier ramp).
- Reuses `ScenarioGraph`'s module-scope node types (the React Flow `nodeTypes`
  warning is a pre-existing React-Flow-v11 + React-19-StrictMode dev-only artifact —
  0 in a production build; not a regression).
- **Verified:** web tsc + biome clean; 188 web unit tests (incl. 14 build-studio);
  authed Playwright shows the studio rendering with source-at-node + honesty labels.

### Added — real multi-tenant per-user workspace (v1.0 program · PR 1)

Saved research, audit history, and personal primitives become real, server-backed,
and tenant-isolated — the foundation the dashboards (PR 3) build on.

- **Clerk → backend bridge** (`api/clerk_auth.py`): verifies the Clerk session JWT
  against JWKS (cached, kid-refresh), fail-open in dev / fail-closed in prod, never
  500s, and **inert when `STRATA_CLERK_*` is unset** (keyless degradation preserved —
  anonymous `/tam/<hash>` permalinks still resolve, no 401 storm). `Principal` gains
  `user_id`; a Bearer branch resolves before the API-key branch.
- **Dual-purpose RLS on `tam_outputs`** (migration 008): `USING/WITH CHECK (org_id IS
  NULL OR org_id = current_setting('app.org_id', true))` — anonymous content-addressed
  permalinks stay world-readable while tenant saves isolate; the single
  `UNIQUE(state_hash)` is split into two partial unique indexes (public vs per-org).
  `audit_events` + the new `user_primitives` / `boards` / `board_items` tables
  (migration 009) use the strict closed policy.
- **Personal workspace endpoints:** `/me/primitives` CRUD (forces `visibility=private`
  + `org_id` server-side, enforces the MODELED fence; `promote` routes to the
  `/contribute` review queue, never a direct public write), `/me/tams/save` +
  `/me/tams` + `/me/audit`, and `GET /lineage/{id}` (server-side DAG). The frontend
  injects the Clerk bearer token and reads real `/me/*` data (localStorage favorites
  migrate to the server on first login).
- **Verified:** 922 backend tests incl. **cross-tenant RLS isolation** (org A ⊥ org B
  across tams/primitives/boards/audit; anon sees only `org_id IS NULL`); migrations
  008/009 up/down round-trip clean; pyright src 0; ruff + `strata validate` + web tsc
  clean. **BLOCKED:** live-prod Clerk JWKS verification (kept inert on unset keys; the
  stubbed-keypair RS256 path is tested).

### Docs — strategic adversarial review

- [`docs/STRATEGY-REVIEW-2026-06-06.md`](docs/STRATEGY-REVIEW-2026-06-06.md): a
  four-lens long-term/value-prop review → 16 tracked issues (#93–#108). Headline
  reframe: lead with the **verification layer for AI market claims** (MCP), make the
  MODELED fence **graded not binary**, invest in frameworks over connectors.

### Added — curated question → sourced-only report engine (v1.0 program · PR 4)

Ask analytical TAM/market questions and get them answered **only** from the data
bank — a sourced primitive, a concept-measurement spread, or a triangulated
TAM-field synthesis — or an honest "no data in bank" gap. **Never an LLM-projected
number, never an external citation.**

- **New record kind `analysis_question`** (`models/question.py`): an `AnswerSpec`
  discriminated union (`primitive_role | concept_measurement | tam_field |
  qualitative`) that can *only* bind registry objects — a literal number is
  structurally impossible. Wired into the loader + registry.
- **Report assembler** (`report/assembler.py`, pure — no LLM, no network):
  `assemble_report(reg, concept) → MarketReport`. `ResolvedAnswer` has a validator
  that forbids a numeric value without provenance or synthesis. A new
  `cross_record` check **rejects** any question that would resolve to a
  quarantined `reg.signals` entry (Q20 fence) and warns on questions authored
  ahead of their data (those carry honest `gap_text`).
- **Surfaces:** `GET /report/{concept_slug}`, `strata report <concept>` CLI, and
  the `/c/<slug>/questions` page (Sourced-Ledger styling, KPI strip, per-category
  answers, reproducible `/tam/<hash>` links, honest gaps).
- **109 curated questions** across all 10 categories (market_size, growth_rate,
  segmentation, geography, competition_share, regulation, adoption,
  unit_economics, risks, methodology). On the flagship concept the report answers
  27 questions from sourced primitives and shows 37 honest gaps — zero external
  citations.
- **Verified:** `strata validate` 0 errors (84 by-design "authored-ahead-of-data"
  warnings); 871 backend tests (incl. a provenance-fence test asserting every
  numeric answer has provenance/synthesis, and a signal-rejection test); pyright
  src 0; web tsc + biome clean; live `/report` endpoint sourced-only.
- Architecture: 41-diagram mermaid set added at `docs/architecture/DIAGRAMS.md`.

### Fixed — trust quick-wins + doc/architecture recovery (v1.0 program · PR 0)

First of the 6 sequenced v1.0 PRs (`docs/TODO_june6.md`). Stops "fake sources" on
first contact and restores the deleted ground-truth docs. Guiding rule: **honesty
over a fake green check** — fix the lie where it is displayed, never fake the data.

- **Killed placeholder provenance.** The 12 `community-modeled` primitives that
  cited the non-resolvable `strata.internal` host now cite their open-repo
  model-definition file (`github.com/ArkashJ/Strata/blob/main/data/primitives/<slug>.yaml`)
  — for a community model, the documented model *is* the real source — while each
  primitive's description still names its real-world anchor (Copilot pricing, SaaS
  precedents, etc.) for the reader. Tier stays `community-modeled`; the soft-data
  fence is tier-keyed, so the MODELED banner and `source_url=None` display are
  untouched. Zero `strata.internal` references remain in `data/`.
- **Demo snapshots render honestly.** The 25 `demo-*` primitives carry a
  placeholder `d3d3…d3` snapshot (never content-pinned). New `isPlaceholderSnapshot`
  / `formatSnapshot` helpers (`web/src/lib/format.ts`) render "not pinned (demo)"
  instead of a fake hash on the report's Sources table and the primitive detail
  page; the report's reproducibility footnote downgrades to its qualified form
  whenever a displayed row is unpinned. **Data unchanged — the display no longer
  lies.** (We do not manufacture a snapshot, which would forge reproducibility we
  don't have.)
- **Homepage featured concepts are deterministic + sourced-forward.** The blind
  `concepts.slice(0,3)` is replaced by a curated allowlist
  (`web/src/lib/featured.ts`) of the three concepts with the highest
  regulator/aggregator-input ratio (`kyber-pc-doc-gen`,
  `effective-ai-insurance-knowledge`, `doc-gen-pc-insurance`), with graceful
  fallback — so first contact leads with genuinely sourced numbers.
- **Connector host-map.** `usda_nass` is host-mapped → `/connectors` now shows
  `usda_nass = 8`. `github` is deliberately **not** mapped (honest-zero): its
  primitives are hand-authored citations, not ingests, so attributing a count
  would imply an ingest that never happened.
- **Deleted dead charts** `WaterfallChart.tsx` + `ScenarioBarChart.tsx` (zero imports).
- **Doc recovery.** Restored `00-vision`, `05-roadmap`, `07-data-layer-brainstorm`,
  `08-product-surface-brainstorm`, `10-v0.2-backend-spec` and 13 more
  referenced-but-deleted docs byte-faithfully from history (`0e2787b^`), so every
  `docs/*.md` reference in `CLAUDE.md`/`README.md` resolves again. Added
  `docs/architecture/` (as-built diagrams) and `docs/questions/` (PR 4 question-bank
  spec) to the docs index.
- **Verified:** 867 backend tests · `pyright src` 0 · `ruff check/format src` clean ·
  `strata validate ../data` 0 errors · `verify-integrity` passes · resolver-eval
  baseline · doc-count consistent · web `tsc` clean · 172 web unit tests (incl. new
  `format`/`featured` helpers). Learnings + issues recorded in
  [`docs/solutions/2026-06-06-pr0-trust-honesty-fences.md`](docs/solutions/2026-06-06-pr0-trust-honesty-fences.md).
- **Known/flagged (follow-ups):** two pre-existing `community-modeled` citations
  point at a wrong-org, now-deleted methodology doc (broken links — outside PR 0's
  12); CI gates the backend only, so the repo's pre-existing web `biome` debt in
  unmodified files is untouched here.

### Added — deeper data bank (Track B, Phase 1 · PR #86)
- Grew the sourced bank **214 → 279 primitives (+65)** by activating/deepening **9
  regulator + aggregator connectors** that were only 0–2 primitives deep: OECD,
  Eurostat, EIA, FDIC, CMS, FAA, openFDA, UN Comtrade, and USDA NASS (activated from
  zero). Producing connectors rose from 13 to ~17.
- Each new number is read live from the source API and pinned to a SHA-256 snapshot —
  national GDP figures, energy and commodity prices, trade flows, Medicare enrollment,
  drug/device counts, airport counts. Nothing is invented.
- Added **57 market concepts** so the new numbers attach to a named market.
- Pipeline (unchanged, no new code):

  ```
  ingest-manifest.yaml  ──►  ingest run (live APIs)  ──►  promote (validator-gated)
       (+67 targets)              (0 failures)                 (0 rejected → +65)
  ```

- Market-data and social-signal connectors (Alpha Vantage, Nasdaq, yfinance, GitHub,
  Stack Exchange, Reddit, Twitter, Dune) remain inactive pending a separate
  connector-plumbing fix — see `docs/plans/OVERNIGHT-LOG.md`.

### Changed — real formula engine (Track B, Phase 2)
- Framework recipes now compute from a real, **checkable formula** instead of a
  hard-coded "multiply everything" rule. Each framework's `formula` (e.g.
  `tools_displaced * consolidation_rate * (1 - pricing_discount)`) is parsed into
  a small, **closed** expression and evaluated over the sourced inputs — so the
  written recipe and the math can no longer disagree.
- The math is safe by construction: the engine never runs arbitrary code (no
  `eval`), only `+ − ×`, a few named functions (`min`, `max`, `clamp`, and bounded
  adoption curves), and the inputs the framework declares. A nonsense or
  tampered formula is rejected the moment a framework loads.
- **Nothing existing moved:** the five shipped frameworks produce byte-for-byte
  identical TAM numbers and permalinks — a frozen regression check fails the build
  on any drift.

  ```
  Framework.formula (text)  ──parse──▶  closed expression  ──walk over inputs──▶  TAM value
       (now load-bearing)                 (no eval, unit-checked at load)
  ```

- Groundwork for richer recipes (sum-then-discount, adoption S-curves, min/max
  blends, the `latent_demand` lens) is in place; the new framework catalog itself
  lands once the data bank holds the primitives those recipes need.

### Changed — soft-data fence (Track B, Phase 4)
- Honest labeling of estimates. About a third of the bank's numbers are
  hand-modeled estimates (capture rates, paraphrased figures) rather than numbers
  read live from a regulator. They are now **flagged "MODELED, not sourced"**
  everywhere they feed a TAM — including a tier that was previously silent — so a
  reader always knows which figures are estimates. Nothing is deleted; the policy
  is **fence + re-source**, not hide.
- A real number can no longer wear a fake source. Twelve estimates cited a
  fabricated internal address that slipped past the connector-side guard because
  they were hand-written. A new check **rejects any committed number citing the
  internal address unless it is honestly marked modeled** — and a test enforces it
  on every build, not just on demand.
- The AI web-search fallback is now **off by default**. The resolver only reaches
  for an AI-synthesized number when an operator explicitly opts in
  (`STRATA_ALLOW_EXA_FALLBACK=1`); otherwise an unresolved query honestly says "no
  curated result." A synthesized number can never be promoted, persisted, or
  written into the bank.

  ```
  committed number ─┬─ cites internal address & not "modeled" ─▶ BUILD FAILS
                    └─ modeled estimate ─▶ kept + loud "MODELED" banner everywhere
  AI fallback ─ off unless opted in ─ result is ephemeral, never enters the bank
  ```

- `strata stats` now shows a sourced / modeled / queued breakdown; new
  `strata resource-status` lists the estimates queued for re-sourcing.

### Security — the agent API now requires a key (Track B, Phase 3 · Workstream A)
- The hosted MCP endpoint (`/mcp`) — how an external AI agent talks to Strata —
  was open to anyone. It now **requires an API key** on every request, with the
  same per-tenant rate limiting and usage metering as the rest of the API. A
  missing or wrong key gets a clean 401; over-limit gets a 429. A malformed
  request can't run up the usage meter.
- The local desktop connection (`claude mcp add strata`) is **unchanged** — it
  stays local-trust and needs no key.

  ```
  external agent ─ X-API-Key ─▶ /mcp ─┬─ no/bad key ─▶ 401
                                      ├─ over limit  ─▶ 429
                                      └─ ok ─▶ tools (metered once)
  local stdio ─ no key needed ─▶ tools (local-trust)
  ```

- Groundwork only: letting agents *compose and save* a TAM, and a generated
  client library, are the remaining parts of this phase.

### Fixed — design system: lens vs source-tier colors (PR #84)
- The method-comparison chart colored each lens with a source-tier hue, so a
  "revenue generation" bar showed up in the same green that means "regulator
  source" everywhere else. Lenses now use their own cool color family (indigo,
  cyan, violet, rose); the warm/earth tier colors stay reserved for source
  provenance, so a color always means one thing.

  ```
  before:  lens color === tier color   (green = regulator AND revenue_generation)
  after:   methods = cool family   ·   sources = warm/earth tier hues
  ```

### Changed — frontend navigation consolidated (PR #85)
- The left navigation went from 16 flat items to 8, grouped into four sections
  so the core path (size a market, get a defensible number) stops drowning. The
  groups map to a simple idea: your work, your data, the shared bank, and where
  data comes from.

  ```
  WORK         Home · Build · Portfolio
  MY DATA      My Bank · Agents
  STRATA BANK  Explore
  SOURCES      Connectors · Integrations
  ```

- **Explore** is one place to browse the shared Strata bank (concepts,
  primitives, frameworks, signals, the pyramid, and TAMs) as tabs. The old
  separate pages still work — they forward to the new tabs.
- **My Bank** replaces the old Dashboard: your saved builds and favorites, plus
  a "my primitives" table — the private side of the two-tier model (your own
  data vs the shared bank). The old Dashboard link forwards here.
- **Build** now hosts the graph composer as a mode of the same page instead of a
  separate "Build a graph" route.
- **Agents** now shows an activity log of agent/CLI calls.
- Guides and Contribute moved to the footer; an unused data page was removed.

### Changed — modeled numbers are loudly flagged in the UI (Track B, Phase 4 · frontend)
- When a TAM leans on a hand-modeled estimate (rather than a number read live from
  a source), the report now shows a **loud, can't-miss "MODELED — NOT SOURCED"
  note** listing each estimated input — on both the `/build` workshop and the
  shared `/tam` page. Previously some estimates (notably one tier) were flagged
  only in the backend and stayed invisible to the reader.
- The note is non-dismissable and accessible: the warning is spelled out in words,
  never signalled by colour alone.

### Added — contribution flow (PR B, Phase 5)
- **`/contribute`** page (sidebar link) — re-adds the contribution surface (removed for
  the v0.5 expert layer) on top of the existing `POST /contribute` route: a form submits a
  proposed primitive, the backend runs the SAME validator the committed bank uses (schema +
  unit signature + real source URL + SHA-256), and returns accepted / needs-review / rejected
  with reasons. Regulator / first-party auto-accept org-private; everything else queues for
  human review — an unsourced number can never auto-publish into a TAM.

### Added — user-generated graph builder (PR B, Phase 4)
- **`/build/graph`** (sidebar link) — compose your own TAM from the bank: pick a market,
  then re-bind any framework input to a different sourced primitive (swaps are kept
  unit-compatible). The TAM recomputes live via `POST /build/recompute` and the minted
  `state_hash` is the shareable artifact (Open & share → `/tam/<hash>`, or edit in the
  workhorse). No fabricated numbers — every binding is an existing hash-pinned primitive;
  what-if wiring is never persisted as a primitive.

### Added — connector marketplace (PR B, Phase 3)
- `/connectors` now shows **13 producing connectors** (was 5): the route's
  `_CONNECTOR_HOSTS` map was stale and only counted the original four hosts, so the
  newly-ingested connectors (OECD, Eurostat, EIA, CMS, FDIC, FAA, openFDA, Comtrade)
  reported 0 despite having committed primitives. Mapped their source hosts.
- Made the catalog's header search functional (was a no-op) — filter connectors by
  name, tier, or what they return.

### Added — MCP agent harness (PR B, Phase 2)
- **`/agents` page** (`web/src/app/agents/`) — first-class harness surface (sidebar
  link + icon): the 12-tool catalog (read/write/live badges), an agent-flow ASCII
  diagram, stdio + streamable-HTTP connect snippets, and the "frameworks are
  harnesses" explainer. Promotes MCP off the single `/integrations` card.
- Four new MCP tools on the read-only Strata server (`mcp/tools.py`, now 12 total),
  every payload keeping the `source_url`+`tier`+`snapshot_sha256` contract:
  - **`list_primitives`** — paginated, filterable (tier/dimension/query) inventory of
    the sourced data bank.
  - **`build_tam`** — what-if sizing: swap a primitive's value (the unit is inherited
    from the primitive it replaces, so the framework signature still validates) or
    re-point a framework input; never persisted (`user_override` banner).
  - **`list_connectors`** — the typed-connector supply side (connector · tier · methods).
  - **`get_connector_data`** — `[LIVE]` run one connector method → validated, hash-pinned
    primitive; gated by `STRATA_MCP_LIVE_CONNECTORS=1` so the default surface is offline-safe.
  +9 MCP tests. This is the "research harness for agents" wedge.
- **Ingest orchestrator** now treats `cms`/`fdic`/`openfda` as keyless (their ctors take
  no key) so they run offline instead of being wrongly skipped.

### Fixed — unit-scale correctness (PR A, from code review)
- Government financial APIs report scaled figures — FDIC BankFind in **thousands**,
  OECD/Eurostat GDP in **millions** — but the primitives stored the raw number labelled
  as base currency, so a consuming framework would be 1000×/1,000,000× off. Added a
  `value_scale` converter param (`financial_/oecd_observation_/observation_to_primitive_yaml`)
  set per-arg-set in the manifest (FDIC ×1000, OECD/Eurostat GDP ×1e6). Largest US bank
  now stores **$3.46T** (was $3.46B), DEU GDP **€3.99T**, DE GDP **€4.22T**. Also gated
  those converters' currency stamp on `unit_dimension == "currency"` (matching FRED/WB).

### Fixed — eight more connectors made ingest-ready (PR A, "test all the APIs")
- A parallel audit fixed real bugs that meant most connectors had **never** produced
  a valid primitive. Bank → **214**. Each fix verified live through `call_and_convert`:
  - **EIA**: facet keys must be lowercase (`stateid`/`sectorid`) + value lives under the
    column key (`sales`), not `value`. → US electricity 4.06M GWh.
  - **CMS**: dataset addressed by UUID (not slug) + uppercase filter fields
    (`YEAR`/`BENE_STATE_ABRVTN`) + `TOT_BENES`. → CA Medicare 6.6M beneficiaries.
  - **OECD**: served **SDMX-JSON 2.0** but the parser read 1.0; wrong dataflow ID and a
    2-field key against a 12-dimension DSD. → DEU GDP €3.99T.
  - **Comtrade**: the keyless preview rejects combined-flow (`MX`) → single flow `M`.
    → US imports HS85 $463B, US–China trade $448B.
  - **Census SUSB** has no Data API → switched `get_susb` to the Annual Business Survey
    Company Summary (`abscs FIRMPDEMP`). → 123,842 computer-systems-design firms.
  - **FAA**: the `US_Airports` ArcGIS service was retired (new layer has no passenger
    field); pivoted `get_airport_count` to the live `US_Airport` layer. → 13,171 US airports.
  - **BLS OEWS**: the series ID was missing the mandatory areatype digit (24 vs 25 chars),
    which `api.bls.gov` rejected mid-request. → occupation employment now ingests.
  - **FDIC**: `get_financials` wasn't in `capabilities()` so dispatch never registered it;
    exposed it. → largest-bank assets.
  Honest limits recorded: FAA enplanements (Excel-only), Comtrade world-aggregate
  (needs a paid key), OECD/Eurostat values in millions — noted in the manifest, never
  fabricated.

### Fixed — connector ingest correctness (PR A)
- **FRED ingest was broken** — its default converter required a `SeriesInfo`
  object that `get_observations` never returns (and a `series_id` converter param
  would collide with the method arg). Added `observations_only_to_primitive_yaml`
  (`connectors/fred.py`), which derives the source slug + content hash from
  `primitive_slug` + the observation; wired as FRED's dispatch default. `strata
  ingest run --connector fred` now produces a real, hash-pinned primitive.
- **World Bank stamped a bogus `currency: USD`** on non-currency units (a
  population primitive came out with a currency). The converter now only adds a
  currency to a currency-dimension unit (+2 tests; existing 7 still pass).

### Added — data-bank expansion (PR A: themed bulk ingest)
- **First real multi-connector ingest** — expanded `data/ingest-manifest.yaml` to
  46 concept-linked arg-sets across 14 connectors (researched against live APIs +
  each converter's dispatch signature). First live run promoted **11 new
  regulator/aggregator primitives** (bank → 195): FRED US GDP + personal
  consumption, BLS nonfarm employment, World Bank population/GDP/labor-force across
  US·DEU·GBR·FRA·JPN·IND. All hash-pinned to real source snapshots. Remaining
  connectors (OEWS, SUSB, OECD/Eurostat SDMX, EIA, FAA, openFDA, Comtrade, CMS/FDIC)
  are staged in the manifest and being fixed connector-by-connector.
- **Bulk promote** — `strata promote --from-ingest [--validate-only]`
  (`backend/src/strata/cli.py`) walks every staged `~/.strata/auto-primitives/`
  record, stages the whole batch into `data/primitives/`, validates the tree
  **once** (not per-file), and iteratively rolls back only the validator's
  attributed offenders so the committed tree is never left broken. Errors are
  attributed exact-slug-first with an unattributed-only message-scan fallback to
  avoid over-rollback; an unattributable round rolls the remaining batch back.
  `--validate-only` is a dry run that commits nothing (+6 promote-CLI tests).

### Removed
- Deleted the stale repo-root `ingest-manifest.yaml` (legacy `methods:` dict
  shape the loader rejects). `data/ingest-manifest.yaml` is the single canonical
  manifest; README + CLAUDE.md references updated.

### Changed — /simplify pass (behavior-preserving)
- One source of truth for: the e2e local-backend policy (`web/e2e/helpers.ts` —
  `API` + `buildHash`, replacing eight per-file copies so `E2E_API_URL` works
  suite-wide), the method-family labels (`familyLabel` in `lib/format.ts`,
  shared by ConvergenceBanner + MethodDirections), the coded-tag chip label
  (`codedTagLabel`, shared by ScopeStrip + MarketSpecStep), and the
  sign-in/sign-up night-canvas shell (`AuthCanvas`). Full e2e suite 96/0 after.

### Added — methodology honesty: number→source links + named directions (sub-projects 2 & 3, v1)
- **The number itself is now the link.** The evaluator enriches every consumed
  atomic input with its primitive's real `source_url`
  (`InputUsed.source_url`; `backend/src/strata/evaluator/engine.py`); composites
  honestly carry `None` — a union has no single source, and we never link a
  derived number to an invented URL. Display-only: the state-hash payload
  projects name/primitive/hash per input, so no `/tam/<hash>` permalink
  re-mints (+3 backend tests; 785 pass). `Source.url` is now schema-gated
  non-empty so a blank URL fails at ingest, not as a dead link downstream.
- **`SourcedNumber`** (`web/src/components/ui/`): renders a figure as a
  dotted-underline link to its source — wired into the forwardable report's
  per-method equation factors, input lists, and Sources & provenance table
  (`TamReport`) and the workhorse composition product line (`CompositionChart`).
- **`MethodDirections`** (`web/src/components/tam/`): every TAM now NAMES the
  canonical directions backing it — "Top-down ✓ ∧ Bottoms-up ✓" — and when one
  is absent says so plainly ("no bottoms-up method in the data bank yet"),
  distinguishing single-direction estimates from ones cross-checked by
  non-canonical families (comparable revenue / analog penetration / value
  chain). Derived purely from `method_families_used`; a missing direction is
  stated, never fabricated. Rendered on `/build/<hash>` and the report.
- *Deferred (needs real sourcing, no invented figures):* per-source page/section
  locators on the link target, and seeding the missing counterpart method for
  single-direction concepts — both are data work requiring real documents.

### Fixed — authenticated e2e suite fully green (94/94)
- **Refreshed every stale spec to the current UI** (they predated the v0.42
  rebuild and asserted removed surfaces): `build.spec` drives the new market-spec
  gate via a `sizeThroughGate` helper (and asserts reload — not Back — restores a
  minted state, matching the deliberate `router.replace` auto-mint model);
  landing/interpretation/palette use the current nav (Home/Dashboard/Concepts/
  Frameworks), "Featured TAMs", and the `/c` route for deterministic ⌘K; `tam.spec`
  follows the "Triangulated midpoint" rename; resolver/concept/framework specs fix
  drifted copy + strict-mode collisions; `contribute.spec` deleted (surface
  removed until the v0.5 expert layer).
- **De-flaked the harness:** `tam.spec`/`trajectory.spec` derive the artifact hash
  at runtime by building the seeded concept first (hardcoded hashes strand the
  file when seed data re-mints); `tam-share-og`/`wave2-motion` target the LOCAL
  e2e backend via `E2E_API_URL` (never `NEXT_PUBLIC_API_URL`, which `.env.local`
  points at prod); the e2e backend forces a fail-fast LLM (`STRATA_LLM_BACKEND=
  anthropic` + invalid key) so `/resolve` settles to its honest error in ~1s
  everywhere instead of shelling out to a dev machine's real `claude` CLI; local
  workers capped at 3 (the single-process backend's sync evaluator saturates
  beyond that); Featured-TAMs asserts the TamCard buttons that actually exist
  (rows navigate via router.push, not `<a>`).

### Added — market-spec step before sizing (sub-project 1.5, frontend)
- **Pin the market before any number.** `/build?q=` no longer auto-sizes; it
  renders a new **`MarketSpecStep`** (`web/src/components/build/MarketSpecStep.tsx`)
  — editable NAICS/SOC chips, a firm-size segment picker (All firms · SMB · Mid-
  market · Enterprise · custom), geo (default US), and include/exclude rules —
  prefilled from the matched concept's declared scope (`GET /c/<slug>.scope`). The
  **Size** button is the gate: sizing only runs once the market is confirmed.
- **A pinned market is part of the build identity.** `BuildState.scope`
  (`web/src/lib/state-hash.ts`) folds a non-empty scope into the canonical state
  (and thus the hash) — a different market mints a different `/build/<hash>`. An
  empty scope is omitted, so every pre-scope URL still round-trips byte-for-byte.
  On Size, `BuildView` recomputes via `POST /build/recompute { scope }` (priming
  the query cache the workhorse reuses) and redirects to the scope-specific hash.
- **The pinned market drives the scope check, now on `/build` too.** `BuildWorkspace`
  surfaces the declared-market chip strip, the per-input "Scope check" (which
  sources read narrower/broader than the pinned market — why methods disagree),
  and a rail summary — reusing the `/tam` `ScopeCheck` components, gated to a
  non-empty declared scope. Zod `marketScopeSchema` threaded through
  `recomputeRequestSchema` + `conceptDetailSchema`; `needsRecompute()` recomputes
  on a pinned market as well as a what-if. New authenticated e2e
  (`web/e2e/market-spec.spec.ts`) + unit tests for the scope→hash→recompute path.
  (Requires the sub-project-1.5 backend — `size_concept(declared_scope_override=)`,
  commit `64f161d`; deployed backends must redeploy for the pin to take effect.)

### Added — Clerk auth gate + signed-out landing
- **Sign-in now required to use the product.** `web/src/middleware.ts` is
  protected-by-default: every route calls `auth.protect()` except a small public
  allowlist (`/`, `/sign-in`, `/sign-up`, `/embed/*`, `robots.txt`,
  `sitemap.xml`, OpenGraph images). The keyless-CI graceful-degradation guard is
  preserved (no publishable key → pass-through, app renders as before).
- **Public marketing landing** at `/` for signed-out visitors — a split-editorial
  hero on a fixed deep-navy "night canvas" (`.strata-night`): an infinite indigo
  grid + drifting glow (`.grid-canvas`) and glassmorphism panels (`.glass`),
  with the animated Strata pyramid + concept→framework→primitive→TAM pipeline.
  `web/src/components/landing/{NightCanvas,PublicLanding}.tsx`. The app sidebar /
  chrome no longer renders before sign-in.
- **`/sign-in` + `/sign-up`** restyled onto the same night canvas (glass card,
  Strata-indigo Clerk `appearance` via `web/src/lib/clerk-appearance.ts`); the
  shell (`AppShell`) renders bare for the auth routes and the signed-out landing,
  the full sidebar only once signed in.
- **Playwright e2e authenticates under the gate.** `@clerk/testing` +
  `e2e/global.setup.ts` obtain a Clerk Testing Token (bypassing bot detection),
  sign in the standing test user, and save `storageState`; `playwright.config.ts`
  runs feature specs authenticated and a new `e2e/auth-gate.spec.ts` (signed-out)
  asserts the gate redirect + no-chrome landing. The e2e frontend runs on a
  dedicated port against the local backend. (Pre-existing specs that assert on
  removed/renamed UI — `Contribute`, `Recently updated` — remain red and need a
  separate refresh; they are unrelated to auth.)
- **Storybook** (10.x, Vite builder + `@tailwindcss/vite`) with a light/dark
  toolbar toggle and stories for the new UI (`Button`, `NightCanvas` +
  `PublicLanding`, design tokens / `.glass` / `.role-chip`). `bun run storybook`
  / `build-storybook`.

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
