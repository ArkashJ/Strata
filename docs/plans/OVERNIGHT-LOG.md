# Overnight build log

Self-paced `/loop` driving **both** initiatives to green, pushed PRs awaiting
human merge. **No merges. No pushes to main.** One unit per iteration.

A/B reconciliation (decided up front, per the overnight contract):
- The 6 Plaid specs (`docs/plans/00`–`05`) are **canonical / KEEP**. They resolve
  Track-A item #3 (aggregate learning) on the backend/data-model side.
- Tie-break when surfaces collide: **Track B wins on backend/data-model**, **Track A
  wins on frontend nav/IA**. Conflicts noted per-PR and here.
- PR #84 (lens palette) and PR #85 (nav/IA restructure) are DONE — left for human merge.

Work queue, dependency-ordered:
- Track B: **P1 → P2 → (P3 ∥ P4) → P5**
- Track A: phases **7, 8, 9** (these are the deeper-direction tracks; their
  backend/data-model contract is Track B's P3/P4/P1 respectively).

---

## Iteration log

### 2026-06-06 · iteration 1 — P1 (deepen the data bank), kickoff

- Resumed from clean `feat/frontend-restructure`; PRs #84/#85 open (untouched).
- Probed env: network up (FRED reachable), 27 API keys in `backend/.env`,
  215 primitive files, 64 manifest arg_sets, ingest CLI functional.
- **Decision:** execute P1 via the spec's §7 fan-out, but subagents AUTHOR +
  live-verify manifest fragments (read-only API probing to confirm codes) and
  return them as text; the reconciler (me) does the single live `ingest run` +
  `promote --from-ingest` so the committed tree is written exactly once
  (spec §7 "Recommended"). Quality over quantity — only live-read, validator-
  passing primitives are promoted; never fabricate a figure (Q20).
- Groups (disjoint connector keys): regulators-A (oecd, eurostat, comtrade),
  regulators-B (eia, faa, openfda, fdic, cms, usda_nass), markets (alpha_vantage,
  nasdaq_data_link, yfinance), signals (github, stack_exchange, reddit, twitter, dune).
- Branch: `feat/p1-deepen-data-bank` (off `main`).

**Blocked (logged, app-code follow-ups outside P1's "data + manifest only" contract):**
- **markets group (alpha_vantage, nasdaq_data_link, yfinance) — ALL BLOCKED.**
  Root cause is a *dispatch-glue defect*, not missing data: `_dispatch.call_and_convert`
  decomposes a response dataclass into its fields to match converter positionals.
  That works for wrapper responses (FRED `.observations`) but fails for connectors
  whose method returns the convertible dataclass *directly* — alpha_vantage
  (`CompanyOverview`) and yfinance (`YahooQuote`) → converter positional unsatisfiable.
  nasdaq requires a non-YAML-expressible keyword-only `meta: NasdaqDatasetMeta`.
  yfinance is *also* independently dead (Yahoo `/v7/finance/quote` → 401, no crumb/cookie).
  Live data itself verified (IBM cap $283.6B, MSFT $3.18T). Fix = dispatch-safe
  converter variants (app code) + add hosts `www.alphavantage.co` (aggregator),
  `data.nasdaq.com` (aggregator), `finance.yahoo.com` (analyst). **→ follow-up, not P1.**
- **signals group (github, stack_exchange, reddit, twitter, dune) — ALL BLOCKED.**
  github/stack_exchange: converter-positional/method-arg *name collision* (`repo`, `tag`)
  — the documented dispatch trap; the splitter strips the colliding arg so the method
  call fails. API/data verified live (unauth GitHub; SO `pytorch`=24341 Qs). reddit/twitter:
  empty credentials in `.env` (OAuth 401 / ctor raises). dune: no stable self-owned
  single-valued public query — pinning a mutable third-party Dune query would break
  snapshot reproducibility (Q5). Fix = rename converter positionals / dispatch alias
  (app code) + real reddit/twitter keys; hosts `github.com`,`stackoverflow.com`,
  `www.reddit.com`,`x.com`,`dune.com`. **Design flag:** raw social counts are
  community-tier latent-demand proxies — decide signals/ vs primitives/ deliberately
  before wiring (community tier is NOT auto-quarantined like kalshi). **→ follow-up, not P1.**
- **Net for tonight's P1:** deliverable = the two regulator groups' depth (oecd, eurostat,
  comtrade, eia, faa, openfda, fdic, cms, usda_nass), which have working converters +
  allowlisted hosts. markets/signals activation is a separate app-code PR.

**P1 RESULT — shipped (branch `feat/p1-deepen-data-bank`):**
- Reconciled both fragments into `data/ingest-manifest.yaml` (+67 arg_sets): oecd 2→12,
  eurostat 2→15, eia 2→10, fdic 1→5, cms 1→6, faa 2→8, openfda 2→7, comtrade 2→10,
  usda_nass 0→8 (activated). 9 connectors **2-deep → producing**; producing connectors 13→~17.
- Single live `ingest run` (9 connectors, 0 failures) → `promote --from-ingest`
  (validator-gated, **0 rejected**): **+65 sourced primitives** (214→279 sizing-grade).
  Every value live-read + sha256-pinned (US GDP $26.05T, corn $5.95/bu, etc.) — nothing invented.
- Authored **57 concept YAMLs** (incl. backfilling pre-existing dangling refs), each with
  ≥1 `measurements` link. NASS commodity concepts named `us-{c}-price` (honest: they're
  prices received, not market sizes).
- **Reconciliations / fixes (recorded for the reviewer):**
  - NASS `*-market`→`*-price` rename also removed a resolver fuzzy-match collision: the
    char-level matcher scored "test market" → `us-egg-market` at 0.72 (shared word "market"),
    hijacking `/resolve`'s synthesis path. Renamed to `*-price` (data-only, no matcher change).
  - Dropped the `latent_demand` lens on 3 new concepts (petroleum/household consumption) →
    `platform_throughput`/`revenue_generation`. P2's `latent_demand` framework doesn't exist
    yet; `test_no_pipeline_concept_uses_latent_demand_yet` enforces this. (Track B P2 will
    revisit when the framework lands.)
- **Gate:** `STRATA_OFFLINE=1 pytest` **798 passed, 1 skipped (no DB)**. `ruff check src/`
  clean, `pyright src` **0 errors**. (The broad `ruff check .`/`pyright` show ~30/152
  PRE-EXISTING errors in `alembic/scripts/tests` from newer tool versions `uv sync` pulled —
  0 `.py` files changed here; the real CI gate is src-scoped per CLAUDE.md.)
- Env note for future iterations: `uv sync --extra dev` is required (pytest/ruff live in the
  `dev` optional-extra; a bare `uv run pytest` otherwise resolves the global miniforge pytest
  and fails import). Use `uv run python -m pytest`.
- **NOT merged.** Left as a green PR for human review. Next unit: Track B **P2** (formula engine).

---

## v1.0 program (docs/TODO_june6.md · 6 stacked PRs) — `/loop /goal-v1`

### 2026-06-06 · PR 0 — trust quick-wins + doc/architecture recovery — DONE (open, locally green)

- Branch `feat/pr0-trust-and-docs` → **PR #91** (open, against `main`, NOT merged).
- Scope: killed 12 `strata.internal` URLs (→ repo-file model links, tier-keyed
  fence intact); demo `d3d3` snapshots render "not pinned (demo)" (display-only,
  data unchanged); curated sourced-forward homepage allowlist; `usda_nass`
  host-mapped (=8), `github` honest-zero (+regression test); dead charts deleted;
  18 deleted docs restored byte-faithfully from `0e2787b^`; architecture/questions
  added to index.
- Gates (local, all green): 867 pytest · pyright src 0 · ruff src clean · strata
  validate 0 err · verify-integrity · resolver-eval · doc-count · web tsc · 174
  web tests · live authed browser smoke (not-pinned-demo + usda_nass=8).
- Learnings: `docs/solutions/2026-06-06-pr0-trust-honesty-fences.md`.
- **⚠️ BLOCKER (external, affects ALL 6 PRs): GitHub Actions CI cannot run** —
  "job not started: recent account payments have failed / spending limit." No
  code fix; user must resolve Actions billing (Settings → Billing & plans), then
  re-run. CI-green is unreachable until then; per-PR bar is "open + locally green."

### 2026-06-06 · PR 1 — multi-tenant workspace — DONE (merged #109)
- Clerk→backend JWKS bridge (inert/keyless-safe), migrations 008 (dual-purpose tam_outputs RLS) + 009 (user_primitives/boards), /me CRUD + saved TAMs + audit + lineage, frontend bearer wiring. 922 tests incl. cross-tenant RLS isolation. BLOCKED: live-prod Clerk JWKS. Known limits: #98, #99.
- Strategic adversarial review → docs/STRATEGY-REVIEW-2026-06-06.md + GH #93–#108.
- Merged: PR0 #91, PR4 #92, PR1 #109. Remaining: PR2 (this branch), PR3, PR5.
