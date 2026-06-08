# Strata as an MCP-first research engine — handoff spec

> **Author:** drafted 2026-06-07 from a four-stream architecture audit (MCP
> surface, connector/data layer, CLI/report layer, strategy/PR history).
> **Status:** build contract. PRs land stacked, MCP + CLI only, never merged to
> `main` without review.
> **Decision:** the web UI is frozen. Every capability below ships through the
> **MCP server** (`strata.mcp`, the surface agents drive) and the **`strata`
> CLI** (the surface a human analyst drives). The web app is a read-only mirror,
> not a build target.

---

## 0. Why this document exists

Strata already pivoted (see [`docs/STRATEGY-REVIEW-2026-06-06.md`](../STRATEGY-REVIEW-2026-06-06.md))
from "a better IBISWorld" to **the verification layer for AI-generated market
claims, served via MCP**. That pivot is half-built. This spec closes the gap
between the thesis and the surface an analyst (or their agent) actually touches.

The owner's directive, distilled:

1. **MCP + CLI only.** Stop building web. Every feature is an agent tool or a
   CLI command.
2. **Accurate sources.** The engine produces inaccurate results when a market
   is thinly sourced. We need (a) honest handling of first-time/novel queries,
   (b) a way to *grow* the data bank past its 294 static primitives, and (c) a
   feedback loop that turns "this number is wrong" into a durable correction.
3. **Feedback through the MCP with bidirectional sync + admin access.** A user
   gets a TAM, sees a mistake, submits feedback *through the MCP*. It syncs into
   their account. The owner has admin visibility across **all** accounts — all
   via MCP/CLI, no web.
4. **Analyst-grade outputs.** Like Excalidraw-for-market-research: build/edit
   real charts, update metrics, add firm branding, generate PDFs/Excel/DCF/LBO,
   and **drill deeper** ("I got a semiconductor TAM — now go one level down").

This is a compound-engineering plan: each pillar has a **current state**, a
**gap**, **business acceptance criteria** (what an analyst must be able to do),
and a **technical implementation** that names files, models, tools, and
migrations.

---

## 1. Where we actually are (ground truth, 2026-06-07)

Verified live against the hosted MCP (`whoami` → org `clerk_user:…`, scope `*`):

```
bank: { concepts: 100, primitives: 294, frameworks: 25, connectors: 23 }
```

### 1.1 The MCP surface is mature — 19 tools across 6 tiers

| Tier | Tools |
|---|---|
| Read (sourced) | `whoami` · `search_concepts` · `get_primitive` · `list_primitives` · `list_frameworks` · `list_connectors` · `size_tam` · `resolve_market` · `build_tam` · `verify_market_claim` · `get_report` |
| Report (async, DB) | `get_report_for_tam` · `export_report` (branded HTML + WeasyPrint PDF) |
| Live (network-gated) | `get_connector_data` (`STRATA_MCP_LIVE_CONNECTORS=1`) |
| Portfolio write | `import_portfolio` · `size_company` · `list_portfolio` |
| Private bank write | `save_primitive` · `list_my_primitives` |
| **Feedback (closed loop)** | `submit_feedback` · `list_feedback` · `apply_feedback` |

`verify_market_claim` (the thesis tool) and the branded `export_report` already
ship. **The feedback flywheel already closes**: an accepted `primitive_correction`
/ `missing_data` flag becomes an org-private primitive
(`db/feedback.py:apply_feedback_correction`, migrations 014/015), atomically,
behind the same MODELED fence as `save_primitive` (Q20 preserved).

### 1.2 The CLI is the analyst's cockpit

`strata` (Typer, `backend/src/strata/cli.py`) already exposes: `size`, `report
[--premium --pdf --brand-*]`, `verify`, `goal` (the 4-step resolver), `ingest
run|status|refresh`, `promote [--from-ingest]`, `portfolio import|size|list|gaps`,
`feedback submit|list|resolve [--apply]`, `db seed|stats`, `embed`,
`test-connectors`, `verify-integrity`, `resource-status`.

### 1.3 The data bank is broad but **shallow** — this is the core accuracy problem

- 13 of 23 connectors actually produce committed primitives (294 total). The
  other 10 (Kalshi, GitHub, Reddit, Twitter, Stack Exchange, Alpha Vantage,
  Nasdaq Data Link, yfinance, Dune, Polymarket) are capability-only or
  deliberately quarantined (non-sizing tiers).
- **87 of 100 concepts have ≤2 primitives.** Most AI/SaaS-vertical TAMs rest on
  one analyst-paraphrase or community-modeled number. That is *why results feel
  inaccurate*: the math is sound, the **inputs are thin**.
- **Verticals with no sourced coverage:** market-research tools (Gartner/IDC/
  Forrester revenue), semiconductor fab capacity (only Comtrade IC imports +
  EDGAR company financials), commercial healthcare/PBM spend, enterprise-SaaS
  vertical spend, cloud/IT segment splits.

### 1.4 The novel-query path silently degrades

`resolver/pipeline.py` is a 4-step fallback: concept → primitive → live connector
→ Exa search. A first-time query that misses the registry and the connectors
falls to **Exa fallback** (gated by `STRATA_ALLOW_EXA_FALLBACK`), which
*synthesizes* a number from web snippets behind a "not in data bank" banner.
That number is **unsourced** and ephemeral — and nothing records that the gap
existed. We can't improve what we don't measure.

### 1.5 Analyst outputs stop at branded PDF

`backend/src/strata/report/` renders an Altimeter-grade HTML deck → WeasyPrint
PDF, with inline SVG charts and firm branding. `mcp/charts.py` emits Vega-Lite +
Mermaid **specs**. There is **no XLSX, no DCF/LBO, no editable graph, no
server-rendered raster chart, no recursive deep-dive.** Confirmed: zero hits for
`openpyxl`/`xlsxwriter`/`dcf`/`lbo`/`wacc` in `backend/src`.

---

## 2. The four pillars

```
┌─────────────────────────────────────────────────────────────────────┐
│  PILLAR A — Trust & feedback (admin-grade, bidirectional)             │
│    own-org loop EXISTS → add cross-org admin view + promote-to-shared │
├─────────────────────────────────────────────────────────────────────┤
│  PILLAR B — Data-source robustness (the accuracy fix)                 │
│    sourcing-gap queue · novel-query honesty · new vertical connectors │
├─────────────────────────────────────────────────────────────────────┤
│  PILLAR C — Analyst outputs (Excalidraw-for-research)                 │
│    XLSX workbook · DCF/LBO models · editable graph state · raster PNG │
├─────────────────────────────────────────────────────────────────────┤
│  PILLAR D — Deep-dive research harness                                │
│    recursive "drill one level down" · sub-market expansion · provenance│
└─────────────────────────────────────────────────────────────────────┘
        all four delivered ONLY through  strata.mcp  +  strata CLI
```

---

## 3. PILLAR A — Trust & feedback (admin-grade, bidirectional)

### 3.1 Current state

The org-scoped loop is complete: `submit_feedback` → `feedback_events` (RLS) →
`list_feedback` → `apply_feedback` → org-private primitive. Bidirectional sync
*within an org* already works: an agent flags, the team applies, the next agent
call sees the corrected primitive via `list_my_primitives`.

### 3.2 Gap

1. **No admin cross-org view.** The owner has `scope: ["*"]` but no tool reads
   feedback across *all* tenants. RLS isolates by `app.org_id`; admin needs a
   governed bypass.
2. **No promote-to-shared path.** An accepted correction stays *org-private*.
   The shared bank (`data/primitives/*.yaml`) never benefits. The flywheel ends
   at the tenant boundary.
3. **Thin feedback taxonomy for charts/metrics.** When pillar C lands editable
   graphs, a user editing a metric *is* feedback ("your default WTP is wrong").
   That signal isn't captured.

### 3.3 Business acceptance criteria

- **AC-A1** — As the admin, I run one MCP/CLI call and see every open flag
  across every org, newest-first, with org attribution.
- **AC-A2** — As the admin, I can promote an org-private correction into the
  shared committed bank (validator + MODELED fence gated), creating a normal
  `data/primitives/*.yaml` row, and the originating flag is marked
  `resolved` + linked.
- **AC-A3** — A non-admin org calling an admin tool gets a clean 403-equivalent
  `ToolError`, never another org's data.
- **AC-A4** — Every admin action is written to `audit_events` (who, what flag,
  what primitive, when).
- **AC-A5** — Promotion preserves Q20: a modeled/analyst-tier correction is
  refused with a remediation message, never silently promoted.

### 3.4 Technical implementation

**Admin gate.** Add `STRATA_ADMIN_ORGS` (comma-separated org ids) to settings.
A helper `is_admin(principal) -> bool` in `api/auth.py`. Admin tools assert it
and raise `ToolError(CODE_FORBIDDEN)` otherwise.

**Cross-org read.** A dedicated `admin_session_scope()` in `db/engine.py` that
sets a Postgres role / `app.is_admin = 'on'` GUC. Add a permissive RLS policy
keyed on that GUC to `feedback_events`, `user_primitives` (migration 016):

```sql
CREATE POLICY admin_read ON feedback_events FOR SELECT
  USING (current_setting('app.is_admin', true) = 'on');
```

This is *additive* — the existing closed tenant policy stays. (Fixes the
"fails-open" worry #99 by making the bypass an explicit, audited GUC, not a
column nullability accident.)

**New MCP tools** (`mcp/admin_tools.py`, registered in `tools.py:TOOLS`):

| Tool | Annotation | Returns |
|---|---|---|
| `admin_list_feedback` | read | all-org flags `{org_id, id, kind, target, body, suggested_value, status, created_at}`, filter by `status`/`kind`/`org_id` |
| `admin_promote_correction` | write | takes `feedback_id` + `org_id`; reads the org-private primitive it created, re-validates through the shared-bank writer, writes `data/primitives/<slug>.yaml`, marks flag `resolved` cross-org, audits |

**CLI** (`strata admin` sub-app): `strata admin feedback [--status open] [--org X]`
and `strata admin promote <feedback_id> --org X [--validate-only]`.

**New feedback kind** for pillar C: extend `FeedbackKind` with
`metric_override` (a user changed a chart/metric value) — commentary-only (E1),
surfaces in the admin queue as a sourcing signal.

```
agent flags  ──submit_feedback──▶  feedback_events (org-private, RLS)
                                          │
owner: admin_list_feedback ◀──────────────┤ (cross-org, GUC-gated, audited)
   │
   ▼ picks a high-value correction
admin_promote_correction ──▶ data/primitives/<slug>.yaml (shared, validated)
   │                              │
   └── flag → resolved            └── strata db seed ──▶ every org sees the fix
```

---

## 4. PILLAR B — Data-source robustness (the accuracy fix)

This is the **highest-leverage** pillar: it's *why TAMs are inaccurate*.

### 4.1 Sub-pillar B1 — the sourcing-gap queue (measure the misses)

**Gap:** a novel query that finds no sourced primitive vanishes. We never learn
the market wanted "market research tools TAM" and we had nothing.

**Implementation:**

- New model `SourcingGap` + table (migration 016/017): `{id, org_id, created_at,
  query_text, concept_slug?, role?, lens?, unit_hint?, status (open|sourced|
  wontfix), resolved_primitive_id?, hit_count}`.
- Wire three capture points:
  1. **Resolver step-4 (Exa fallback / no-match):** every `PrimitiveSpec` that
     had to be synthesized records a gap (`record_gap_safe`, fire-and-forget,
     mirrors `record_feedback_safe`).
  2. **Report assembler `gap_text`:** every question that renders its honest
     "unsourced for this market" branch records a gap keyed on
     `resource_target` (e.g. `bls:displacement-by-occupation`).
  3. **`verify_market_claim` → `unverifiable`:** the claim couldn't be checked →
     a gap.
- De-dup by `(normalized query / resource_target)`; bump `hit_count`. The most-
  requested gaps float to the top — that's the connector-build backlog, ranked
  by real demand.

**New MCP tool** `list_sourcing_gaps` (read, admin sees cross-org) +
**CLI** `strata gaps [--top 20] [--status open]`.

**Business AC:**
- **AC-B1.1** — Every first-time query that can't be sourced is recorded, not
  silently synthesized. The synthesized answer still returns (with its
  "unsourced — verify" banner), *and* the gap is logged.
- **AC-B1.2** — `strata gaps --top 20` shows the 20 most-requested unsourced
  numbers across the platform, ranked by demand, each pointing at the connector/
  method that *would* fill it.
- **AC-B1.3** — Closing a gap (sourcing the primitive) flips its status and
  links the new primitive.

```
novel query ─▶ resolver miss / report gap_text / unverifiable claim
                         │ record_gap_safe (de-dup, hit_count++)
                         ▼
                 sourcing_gaps  ──list_sourcing_gaps / strata gaps──▶ ranked backlog
                         │
        owner builds connector or hand-sources ──▶ promote ──▶ gap.status=sourced
```

### 4.2 Sub-pillar B2 — novel-query honesty contract

**Gap:** Exa fallback synthesizes a number that *looks* like a sourced TAM.

**Implementation:** harden the resolver output contract. A `via="fallback"`
result must carry `estimate_kind="synthesized"`, `independence_score=0.0`, an
explicit `unsourced=true` flag, and a `sourcing_gap_id`. The MCP `resolve_market`
and CLI `goal` already banner this — make the flag machine-readable so an agent
*cannot* mistake it for sourced. No synthesized number is ever persisted to any
bank (already true; assert it in a test).

**Business AC:**
- **AC-B2.1** — An agent receiving a synthesized TAM can programmatically detect
  `unsourced=true` and tell the user "this is an estimate, not sourced."
- **AC-B2.2** — A synthesized number can never be promoted (regression test
  asserts `strata promote` + `save_primitive` refuse `estimate_kind=synthesized`).

### 4.3 Sub-pillar B3 — new vertical connectors (fill the demand-ranked gaps)

**Strategy note:** the 2026-06-06 review says "divest from connectors (commodity)."
That's right for *macro* connectors (another govt API). It's *wrong* for the
verticals customers actually size. The gap queue (B1) tells us which to build.
Build connectors that fill **ranked demand**, not breadth for its own sake.

Priority targets (each is a typed client following the 6-layer connector pattern
in `connectors/CLAUDE.md`):

| Target | Source | Tier | Fills |
|---|---|---|---|
| **Crunchbase / PitchBook-lite** (or open alt: OpenVC, Dealroom public) | aggregator | analyst | startup funding, category sizing for AI/SaaS verticals |
| **G2 / Capterra category data** | aggregator | community→analyst | software-category vendor counts, review volume (proxy for adoption) |
| **USPTO PatentsView** (free API) | regulator | regulator | innovation intensity, semiconductor/biotech design starts |
| **Census ACS + County Business Patterns deepening** | regulator | regulator | vertical firm-size bands (already have CBP — extend method coverage) |
| **World Bank WDI + IMF deepening** | aggregator | aggregator | per-country adoption denominators for latent_demand lens |
| **OpenCorporates** (free tier) | aggregator | aggregator | global company counts by jurisdiction/industry |

**Critical design rule:** every new connector must declare its `arg_sets` in
`data/ingest-manifest.yaml` linked to concepts, so `strata ingest run` →
`promote --from-ingest` produces *committed* primitives, not just capability.
A connector that produces zero committed primitives is honest-zero (the GitHub
rule), not a win.

**Business AC:**
- **AC-B3.1** — At least one previously-unsourced vertical from the gap queue
  (target: "market research tools" or "semiconductor design") gains ≥3 sourced
  primitives committed to `data/primitives/`, each hash-pinned and validated.
- **AC-B3.2** — `strata test-connectors --live` smoke-passes every new connector
  against its real (keyless or keyed) API.

### 4.4 Sub-pillar B4 — freshness as a first-class loop

**Gap:** primitives are static YAML, refreshed only by a manual cron. A 2024
number presented in 2026 is "inaccurate" even if it was once sourced.

**Implementation:** surface staleness through MCP/CLI. `Source.freshness_sla_days`
already exists. Add `strata refresh-stale [--older-than 180d]` that runs
`ingest refresh` only on past-SLA primitives, and a `staleness` field on every
primitive citation in MCP output (`fresh|stale|expired`). An agent can then say
"this input is 2 years old — treat with caution."

**Business AC:**
- **AC-B4.1** — Every primitive citation in MCP output carries a freshness
  status derived from `as_of` + SLA.
- **AC-B4.2** — `strata refresh-stale` re-pulls only stale primitives and rewrites
  only those whose snapshot hash changed.

---

## 5. PILLAR C — Analyst outputs (Excalidraw-for-market-research)

The output today is a beautiful but **read-only** PDF. Analysts need to *work*
the numbers: edit a graph, swap an assumption, build a financial model, and
export to the format their IC actually reads (Excel, branded PDF).

### 5.1 Sub-pillar C1 — XLSX workbook export

**Implementation:** add `openpyxl` dependency. New `report/render_xlsx.py` that
turns a `TAMOutput` + resolved report into a multi-sheet workbook:

```
Workbook
├─ "Summary"        — headline TAM, method families, convergence, independence
├─ "Scenarios"      — one row per scenario: lens, framework, value, unit, banners
├─ "Inputs"         — every InputUsed: slug, value, unit, source_url, tier, as_of, snapshot
├─ "Sensitivity"    — tornado data: each input ±X% → TAM swing (sorted by |impact|)
├─ "Sources"        — deduped bibliography with hash pins + freshness
└─ "Assumptions"    — any user override, clearly flagged "USER ASSUMPTION — not sourced"
```

Live formulas where honest: the "Scenarios" headline cell is an actual Excel
`=PRODUCT(...)` over the input cells, so an analyst editing an input recomputes
in Excel. **Every sourced cell carries its citation in a comment.** No fabricated
cell — a missing input is a labelled blank, not a guess.

**New MCP tool** `export_workbook(state_hash, branding?)` → `{xlsx_base64,
sheet_summary, citations}`. **CLI** `strata report <concept|hash> --xlsx`.

### 5.2 Sub-pillar C2 — DCF / LBO financial models

**Implementation:** new `strata.finance` package — pure, deterministic, sourced:

- `finance/dcf.py` — `build_dcf(revenue_base, growth_schedule, margin_schedule,
  wacc, terminal_growth, years) -> DCFOutput` (FCF projection, PV, terminal
  value, enterprise value, sensitivity grid on WACC × terminal growth).
- `finance/lbo.py` — `build_lbo(entry_ev, entry_multiple, debt_pct, rate,
  hold_years, exit_multiple, ebitda_schedule) -> LBOOutput` (sources & uses,
  debt paydown, equity IRR, MOIC, returns attribution).

**Sourcing discipline (the Strata differentiator):** the *revenue base* and
*growth* can be **bound to sourced primitives / a Strata TAM** (e.g. revenue_base
= a company's sized market × share). WACC, multiples, leverage are **analyst
assumptions** — every one is flagged `assumption: true` with no source, so the
output honestly separates "sourced foundation" from "your judgment." This is
exactly the Q20 line applied to finance: we never *invent* a market number, but
we *do* let the analyst layer their own assumptions on top, clearly marked.

**New MCP tools** `build_dcf` / `build_lbo` (take a `state_hash` to anchor the
revenue base in a sourced TAM, plus assumption params) → structured model +
sensitivity. **CLI** `strata dcf <concept|hash> [--wacc 0.11 --terminal 0.025 …]`
and `strata lbo …`. Output flows into the XLSX (C1) as dedicated sheets.

### 5.3 Sub-pillar C3 — editable graph state (the Excalidraw analogy)

**Implementation:** the `build_tam` what-if engine + `EvalOverrides` already
support node-level overrides; what's missing is a *durable, shareable, iterable*
graph document. Reuse the `boards`/`board_items` tables (migration 009) as the
persistence layer for an analyst's working graph:

- `save_graph(state_hash, edits[]) -> board_id` — persist a set of overrides +
  layout + branding as an org-private board.
- `get_graph(board_id)` / `list_graphs()` — reload and iterate.
- `fork_graph(board_id)` — branch a scenario.

Each save mints a new `state_hash` (canonical, sorted-key sha256) so every graph
version is a permanent, citeable artifact. An override is a `metric_override`
feedback signal (pillar A) — the analyst editing a number tells us our default
was off.

**Business AC for pillar C:**
- **AC-C1** — `strata report <hash> --xlsx` produces a 6-sheet workbook; opening
  it and changing an input cell recomputes the headline (live formula); every
  sourced cell has a citation comment.
- **AC-C2** — `strata dcf <hash> --wacc 0.11` produces a DCF whose revenue base
  is the sourced TAM and whose WACC/terminal are clearly flagged assumptions;
  output includes a WACC × terminal-growth sensitivity grid.
- **AC-C3** — `build_lbo` returns equity IRR + MOIC + sources&uses + debt
  schedule, with every market input sourced and every financial assumption
  flagged.
- **AC-C4** — An analyst can save a working graph (overrides + branding),
  reload it, fork it, and export any version to PDF/XLSX. Each version has a
  permanent `state_hash`.
- **AC-C5** — Firm branding (name, logo, color, prepared-by, disclaimer) flows
  through *every* export format (PDF already; add XLSX + DCF/LBO sheets).

### 5.4 Sub-pillar C4 — server-rendered raster charts (optional, for non-Vega hosts)

Today charts are Vega-Lite/Mermaid *specs* (great for Claude, useless for a host
that can't render them). Add an optional `matplotlib`-based PNG renderer behind
the same chart spec, so `export_report`/`export_workbook` can embed real raster
charts. Keep specs as the default (portable); PNG is opt-in for embedding.

---

## 6. PILLAR D — Deep-dive research harness

"I researched semiconductors and got a TAM from Strata — now let me go deeper."

### 6.1 Gap

`size_tam` / `resolve_market` are one-shot. There's no way to take a result and
**recursively decompose** it: segment the market, size each sub-segment, drill
into a specific input's provenance, or expand a node into its own TAM.

### 6.2 Implementation

A new MCP tool `deepen_market(state_hash | concept_slug, axis, target?)`:

- `axis = "segment"` — break the market into sourced sub-segments (by NAICS
  child codes, geo, persona band) and size each, returning a tree of child TAMs.
- `axis = "input"` — take one input of the TAM and resolve *its* provenance and
  drivers (e.g. "where does this adoption rate come from, and what drives it?").
- `axis = "competitor"` — size the addressable slice per named competitor.
- `axis = "time"` — project the historical trajectory from sourced time series.

Each deepen call returns child `state_hash`es, so the analyst walks a *tree* of
permanent artifacts, every node sourced or honestly gapped (and every gap feeds
pillar B's queue). This is the recursive research loop — the agent can keep
calling `deepen_market` on any node until it bottoms out at raw primitives.

**CLI** `strata deepen <hash> --axis segment` prints the child tree;
`--axis input --target <slug>` drills one input.

### 6.3 Business AC

- **AC-D1** — From any TAM, `deepen_market(axis="segment")` returns ≥2 sourced
  child segments (or honest gaps), each a permanent `state_hash`.
- **AC-D2** — `deepen_market(axis="input", target=<slug>)` returns the input's
  full provenance chain + any driver primitives.
- **AC-D3** — Every deepen result is itself deepenable (the tree recurses) and
  every unsourced branch records a sourcing gap (pillar B integration).

```
size_tam("semiconductors") ─▶ /tam/<h0>
       │ deepen axis=segment
       ├─▶ "logic / foundry"      /tam/<h1>  ─▶ deepen axis=competitor ─▶ TSMC slice …
       ├─▶ "memory (DRAM/NAND)"   /tam/<h2>
       └─▶ "analog / power"       /tam/<h3>  ─▶ deepen axis=input target=fab-capacity
                                                  └─▶ provenance + driver primitives
```

---

## 7. PR sequence (stacked, MCP+CLI only, never auto-merged)

| PR | Branch | Scope | Depends on |
|---|---|---|---|
| **PR-1** | `feat/mcp-cli-spec` | **this document** | — |
| **PR-2** | `feat/admin-feedback` | Pillar A: `STRATA_ADMIN_ORGS`, admin GUC + migration 016, `admin_list_feedback` / `admin_promote_correction` MCP tools, `strata admin` CLI, audit | PR-1 |
| **PR-3** | `feat/sourcing-gap-queue` | Pillar B1/B2: `SourcingGap` model + migration 017, capture hooks, `list_sourcing_gaps` MCP, `strata gaps` CLI, novel-query honesty flag + regression tests | PR-1 |
| **PR-4** | `feat/analyst-xlsx-finance` | Pillar C1/C2: `openpyxl` XLSX export, `strata.finance` DCF/LBO, `export_workbook`/`build_dcf`/`build_lbo` MCP tools, CLI, branding through all formats | PR-1 |
| **PR-5** | `feat/deepen-research` | Pillar D: `deepen_market` MCP tool + `strata deepen` CLI, segment/input/competitor/time axes, gap-queue integration | PR-3 |
| **PR-6** | `feat/vertical-connectors` | Pillar B3/B4: 2–3 demand-ranked connectors (PatentsView, G2/Capterra-alt, OpenCorporates), manifest entries, freshness loop (`strata refresh-stale`), staleness on citations | PR-3 |
| **PR-7** | `feat/editable-graph` | Pillar C3: board-backed graph save/fork/list, `metric_override` feedback, raster charts (C4) | PR-4 |

Each PR ships green: `uv run pytest && uv run pyright && uv run ruff check . &&
uv run ruff format --check .`, and every new MCP tool has a tool-level test +
an honest-failure test (no-tenant, fence-refusal, gap-on-miss).

---

## 8. Cross-cutting invariants (do not violate)

1. **Q20 — no invented numbers.** Synthesized/fallback numbers are flagged and
   never persisted. DCF/LBO market inputs are sourced; financial assumptions are
   flagged. A missing input is a labelled blank, never a guess.
2. **E1 — feedback is commentary.** A flag/override never mutates a sourced
   number; it proposes a new (org-private, then optionally promoted) one.
3. **RLS isolation holds.** Admin cross-org read is an *additive, audited GUC*
   bypass, not a relaxation of the closed tenant policy.
4. **Every number carries provenance.** `source_url`, `source_tier`,
   `snapshot_sha256`, freshness — in every MCP payload and every export cell.
5. **MCP + CLI parity.** Anything an analyst can do in the CLI, an agent can do
   through MCP, and vice-versa (the agent-native rule).
6. **Web is frozen.** No `web/` changes. Existing routes keep rendering; they
   read the same backend.

---

## 9. Compound-engineering workflow for the build

Use the installed skills, in order, per PR:

1. `ce-plan` (or this doc) → a right-sized task list for the PR.
2. Implement in a worktree; keep diffs small.
3. `ce-code-review` (tiered persona agents) before commit.
4. `lfg` / `ce-commit-push-pr` to ship the PR (open, **never merge**).
5. `ce-compound` to write a `docs/solutions/` learning for any non-obvious
   gotcha (auth GUC, openpyxl formula quirks, connector API edge cases).

The MCP-building skill (`mcp-builder`) governs new tool design: clear input
schemas, structured output, `readOnlyHint`/`destructiveHint` annotations, honest
error taxonomy with remediation.

---

## 10. Definition of done (the demo)

An analyst, entirely through Claude + the Strata MCP (no web):

1. Asks for a semiconductor TAM → gets a sourced scenario tree, or an honest
   "thinly sourced, here's what we have + what's missing."
2. **Deepens** into the foundry segment, then into TSMC's addressable slice.
3. Spots a wrong adoption assumption, **submits feedback** through the MCP.
4. (Owner, via admin tools) sees that flag across all orgs, **promotes** the
   correction into the shared bank.
5. Builds a **DCF** anchored on the sourced TAM with their own WACC.
6. Exports a **branded XLSX + PDF** deck with live formulas and full citations.
7. The unsourced numbers they hit are now in the **sourcing-gap queue**, ranked,
   driving the next connector build.

That loop — size → deepen → correct → promote → model → export → improve — all
through MCP and CLI, is v1.0 of Strata-as-a-research-engine.
