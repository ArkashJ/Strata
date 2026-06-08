# Strata v2 — Handoff: the MCP/CLI TAM-intelligence engine (accuracy-first)

> **Status:** strategy + acceptance criteria + technical plan. This is a *plan to generate plans*:
> each workstream below has a "How to generate the detailed plan" line naming the exact skill to run.
> **Scope lock:** the **MCP connector + CLI + data layers** are the entire product. **No web frontend.**
> Everything an analyst does happens inside their AI tool of choice (Claude Code / claude.ai / Cursor)
> via the connector, or in the terminal via the CLI.

---

## 0. How to use this document (which skill drives which workstream)

| Workstream | Skill to run | Command |
|---|---|---|
| Sharpen any section into a spec | compound-engineering brainstorm | `/ce-brainstorm <section>` |
| Turn a spec into a build plan | compound-engineering plan | `/ce-plan <spec>` (then "deepen the plan") |
| Architecture review of a plan | ce-architecture-strategist / ce-doc-review | `/ce-doc-review <plan>` |
| New/expanded MCP tools | mcp-builder | invoke `mcp-builder` skill |
| New data connectors / source research | ce-best-practices-researcher + ce-web-researcher | dispatch those agents |
| Accuracy/verification eval | ce-optimize | `/ce-optimize` (metric = sourcing accuracy) |
| Financial models (DCF/LBO) | ce-plan + ce-best-practices-researcher | — |
| Excel/xlsx export | `xlsx` skill | invoke `xlsx` |
| Build execution (hands-off) | `lfg` / `ce-work` | `/lfg <workstream>` |
| Capture learnings after each PR | ce-compound | `/ce-compound` |

**impeccable** is intentionally *not* in the critical path — it governs UI, and there is no UI. Keep it
only for the one place visuals leave the system: the **rendered report deck** (HTML/PDF), where the
report's typographic/chart contract still matters even though it's generated, not a web app.

**The meta-loop:** for each Phase below, run `/ce-brainstorm` → `/ce-plan` → `/lfg`, then `/ce-compound`.

---

## 1. Vision & strategic frame

**One line:** *Plaid for market data + an analyst copilot* — strong API connectors feed a verified
data bank; strong MCP tools let any AI agent assemble a defensible, fully-cited TAM analysis, financial
model, and report **without leaving the chat or terminal**.

Three pillars, in priority order:

1. **Accuracy is the moat.** Today the engine produces inaccurate results (thin/missing sources, no
   confidence, no cross-check). v2's job is to make *every number* sourced, triangulated, confidence-
   scored, freshness-stamped, and reproducible — or honestly absent. A wrong number dressed as sourced
   is the worst outcome; the system must prefer "I don't have this, here's the gap" over a guess.
2. **Connector + data breadth.** We can't size markets we have no data for (e.g. *market research
   tools* — see §6). Robust API connectors + a principled "how to source any market" recipe close this.
3. **The feedback flywheel (via MCP).** An analyst flags a bad/missing number → the flag is published
   back to *their* portal (org-scoped) → **you (admin) see every org's feedback through the MCP** →
   you curate/correct the shared bank → the tool gets more accurate for everyone. All through the
   connector. This is the compounding loop that turns usage into data quality.

**Anti-goals:** no web app build-out; no fabricated figures; no "analyst said so" without a citation;
no number without a confidence + a source-of-record.

---

## 2. Personas

- **Maya — investment analyst (primary).** At a top fund (Altimeter/Sequoia). Lives in Claude Code +
  terminal. Wants a defensible TAM with named, dated sources she can drop in an IC memo, plus a DCF/LBO
  and an Excel export — in minutes, without a $30k report. She must be able to *verify* and *correct*
  every number.
- **You — the Admin / data curator (founder).** Have MCP-level admin access to **all orgs' feedback**.
  Triage flags, accept corrections into the shared bank, watch which markets analysts keep hitting gaps
  on, and direct connector/primitive expansion from real demand.
- **The AI agent (Claude) — the operator.** Drives the loop: resolve → size → verify → model → report,
  calling MCP tools and surfacing the analyst's verify/modify/export actions.

---

## 3. Business outcomes

1. **Defensible in an IC.** Every figure: source name + URL + as-of date + tier + snapshot hash +
   confidence; triangulated across ≥2 independent methods; reproducible at a permalink.
2. **Coverage.** Any market an analyst asks for is either sizeable from the bank, or returns a precise
   gap report naming the exact missing primitives + which connectors could fill them.
3. **Full analyst toolkit in-chat.** Verify, modify, graph, report, table, Excel, DCF, LBO, metrics,
   citations — all via MCP/CLI.
4. **Compounding accuracy.** Feedback volume → curated corrections → measurable accuracy gains (tracked
   by the eval harness). Admin sees demand → expands the right connectors.
5. **Zero-UI distribution.** Works inside whatever AI tool the analyst already uses.

---

## 4. Business acceptance criteria (Given / When / Then)

> These are the contract. Each maps to MCP tools + CLI commands (§9) and tests (§10). "An analyst can…"

**AC-1 — Verify a source.**
*Given* a TAM with sourced inputs, *when* the analyst calls `verify_source(primitive_slug)` (MCP) or
`strata source verify <slug>`, *then* they get: the source name, URL, as-of date, tier, the **stored
snapshot** (the actual cited document bytes/excerpt), a serve-time integrity status
(`verified|stale|unpinned`), and — if a connector backs it — a **live re-fetch** that re-derives the
number and reports drift. No number is "trust me": it can always be opened to its evidence.

**AC-2 — Modify / correct a source.**
*Given* a wrong or missing number, *when* the analyst calls `submit_feedback` (correction with a
`suggested_value` + citation) or `propose_primitive`, *then* the correction is stored org-private,
validator + fence gated (no modeled/fabricated tier), linked to the flag, and **published to their
portal**; on admin acceptance it promotes to the shared bank. The analyst's own builds can use the
corrected number immediately (org-private overlay).

**AC-3 — Generate graphs.**
*Given* a sized TAM, *when* `export_report`/`get_charts` is called, *then* the analyst receives chart
specs (Vega-Lite + Mermaid) **and** static inline-SVG/PNG, each with title, axis units, source
footnote, and the tier-vs-method colour contract — renderable in their AI tool or embeddable in the
report. (Charts only ever plot sourced numbers.)

**AC-4 — Generate reports.**
*Given* a TAM hash, *when* `export_report(format=html|pdf, branding?)` or `strata report <hash>
--pdf --brand…`, *then* a self-contained, Altimeter-grade deck is produced (exec summary, market def +
scope, TAM/SAM/SOM, top-down∧bottoms-up triangulation, segmentation, competitive landscape, growth
drivers, sensitivity, **sources appendix with every figure named+dated+hashed**, limitations).

**AC-5 — Generate tables + Excel.**
*Given* a TAM (and optional model), *when* `export_table`/`export_xlsx` (MCP) or `strata export xlsx`,
*then* a workbook lands with: a TAM tab (inputs · values · units · tier · source · snapshot · confidence),
a scenarios tab, a sensitivity tab, a sources/citations tab — formulas live where derived, every cell
traceable.

**AC-6 — Generate a DCF.**
*Given* a company/market + drivers, *when* `build_dcf(...)` (MCP) or `strata model dcf`, *then* a
full DCF (revenue build off the sized TAM × share, EBIT margin path, taxes, D&A, capex, NWC, FCF, WACC,
terminal value, EV→equity bridge, sensitivity grid on WACC×g), each assumption tagged sourced vs
analyst-set, exportable to xlsx with live formulas.

**AC-7 — Generate an LBO.**
*Given* an entry case, *when* `build_lbo(...)` or `strata model lbo`, *then* sources&uses, debt
schedule (tranches, cash sweep), operating model, exit at multiple, returns (IRR/MOIC), and a
returns-sensitivity grid — assumptions tagged, xlsx-exportable.

**AC-8 — Metrics, sources, citations.**
*Given* any output, *when* requested, *then* a metrics block (CAGR, independence score, spread,
convergence, confidence) and a citations block (every source: name, publisher, date, URL, tier,
snapshot) are available as structured data and as a formatted bibliography.

**AC-9 — Admin sees all feedback (via MCP).**
*Given* admin credentials, *when* `admin_list_feedback(filters)` (admin-scoped MCP tool) or
`strata admin feedback`, *then* feedback **across all orgs** is returned (org, market, kind, severity,
suggested correction, status), with triage + promote (`apply_feedback`) actions — all through the
connector, no web portal needed.

**AC-10 — Honest gap report.**
*Given* an unsizeable market, *when* `resolve_market`/`size_tam` is called, *then* the result names the
exact missing primitives/roles, the methods that *would* work, and the connectors/sources that could
fill the gap (a "data shopping list"), instead of returning a fabricated number.

---

## 5. The accuracy engine (the core moat)

> How to generate the detailed plan: `/ce-brainstorm accuracy engine` → `/ce-plan` → `/ce-optimize`
> (metric = % of golden TAMs whose sourced inputs match ground truth within tolerance).

Make accuracy a *measured, first-class* property, not a hope.

- **Per-number provenance record (extend the model):** add `confidence: float`, `freshness_sla_days`,
  `source_of_record` (the canonical source), `method` (how derived), `corroborations` (other sources
  agreeing), `verification_status` (`verified|stale|modeled|estimated|disputed`). Pydantic v2 +
  pyright-strict; an unsourced number stays structurally impossible (keep the Q20 fence).
- **Triangulation + cross-check engine:** for each concept, compute estimates from *independent*
  method families and *independent* source families; emit convergence (spread, N×), an outlier flag
  (z-score / MAD over corroborating sources), and a confidence derived from (source tier × corroboration
  count × freshness × method independence). Surface "why methods disagree" via the scope guard.
- **Verification on serve:** `verify_source` re-hashes the snapshot and (if a connector backs it)
  re-fetches live to detect drift; reports `verified|stale`.
- **Citation integrity:** host allowlist (gov/edu/registry/known-publisher); tier derived from host
  class, never the LLM's word; reject fabricated hosts.
- **Grading, shown loudly:** every figure carries a badge — `REGULATOR` (Census/BLS) > `AGGREGATOR`
  (World Bank/OECD) > `ANALYST` (Gartner/IBISWorld, paraphrased+cited) > `MODELED` (community, banner)
  > `ESTIMATED` (triangulated synthesis). The headline TAM states its weakest-link grade.
- **Eval harness (gate):** extend the golden-set eval — accuracy score = fraction of sourced inputs
  within tolerance of a curated ground truth; CI gate ≥ target; track over time. This is how "we
  produce inaccurate results" becomes a number that goes up.

---

## 6. Data-source & primitive expansion (the breadth ask)

> How to generate the detailed plan: dispatch **ce-web-researcher** + **ce-best-practices-researcher**
> per target market to enumerate sources; then `/ce-plan` a connector batch.

### 6.1 The reusable recipe — "how to source ANY market" (4 independent paths)

```
                       ┌─ TOP-DOWN ── analyst/industry total (Gartner/IBISWorld/Statista, cited)
market concept ──▶ size├─ BOTTOMS-UP ─ population (Census/BLS firm or worker counts by NAICS/SOC)
                       │              × unit economics (spend/firm, ARPU, price) from surveys/filings
                       ├─ COMPARABLE ─ Σ public-comp revenue (EDGAR/XBRL) + private estimates (PitchBook)
                       └─ VALUE-THEORY  value created × capture rate (economic-value model)
                          convergence across paths → confidence; divergence → scope explanation
```
Each path names the connector(s) that feed it. A market is "well-sourced" when ≥2 *independent* paths
agree. This recipe is itself a primitive of the system — encode it so the agent always tries all four.

### 6.2 Worked example — **TAM for "market research tools"** (the user's gap)

The miss today is no data. Here is exactly where the numbers come from:

- **Direct (best):** the industry has a **NAICS code — 541910 "Marketing Research and Public Opinion
  Polling."** The **Census County Business Patterns / SUSB / Economic Census** report *receipts and
  payroll* for 541910 directly → a sourced top-down US revenue figure (REGULATOR tier). This single
  connector call gives a defensible anchor we currently lack.
- **Comparable (corroboration):** sum public pure-plays' revenue from **EDGAR/XBRL** — Gartner (IT),
  Forrester, Nielsen, Ipsos, Kantar (private), Morningstar, FactSet, S&P Global (data), Comscore — plus
  private-co estimates (PitchBook/Crunchbase connector) → bottoms-up of the supply side.
- **Bottoms-up demand:** Census firm counts (CBP/SUSB) for the buyer universe (e.g. NAICS 5418
  advertising/marketing, mid+ firms) × research spend per firm (CMO Survey / Gartner marketing-budget
  benchmarks, analyst tier, cited) → demand-side TAM.
- **Top-down (cite, don't trust blindly):** IBISWorld/Statista/Grand-View market-size figures ingested
  as **ANALYST-PARAPHRASE** (named + dated + flagged), used only to bracket the triangulation.
- **The new primitives this creates:** `naics-541910-receipts-us` (regulator), `market-research-comps-
  revenue-sum` (composite of EDGAR), `marketing-research-spend-per-firm` (analyst), plus a `market-
  research-tools` concept binding them to the comparable + bottoms-up frameworks.

The takeaway: **most "we can't size X" gaps are solved by mapping X to a NAICS/SOC code + a public-comp
set.** Encode a `naics_lookup` + `comp_set` resolver so the agent does this automatically.

### 6.3 Connector wishlist (typed, 6-layer pattern, rate-limited, cached)

| Tier | Connectors to add / harden |
|---|---|
| Regulator (have many) | Census **Economic Census + 541910-style receipts by NAICS**, BEA (GDP-by-industry, input-output), BLS (already), SEC **EDGAR full-text + XBRL frames** (comp revenue/segment) |
| Aggregator | World Bank/OECD/Eurostat (have), IMF, UN |
| Private markets | **PitchBook / Crunchbase / Dealroom** (private-co revenue, funding, headcount) — the biggest coverage unlock for VC TAMs |
| Financial markets | Alpha Vantage / Nasdaq Data Link / yfinance (prices, multiples for comps & DCF WACC) |
| Industry / trade | trade-association stats (e.g. Insights Association for market research), IAB, IDC/Gartner where licensable |
| Analyst (paraphrase) | IBISWorld / Statista / Grand View / Forrester — ingested as cited ANALYST-PARAPHRASE, never as fact |
| Web fallback (fenced) | Exa / SERP — only behind the double-fence, synthesized + "verify before citing" |

Each connector: enums → TypedDicts → frozen dataclasses → unified response → disk cache (sha256, TTL)
→ typed client + YAML→primitive converter, with retry/backoff + a capability manifest the MCP exposes.

---

## 7. The feedback → portal → admin loop (all via MCP)

> How to generate the detailed plan: `/ce-brainstorm feedback flywheel` → `/ce-plan`.

```
analyst (in Claude/CLI) ──submit_feedback / propose_primitive──▶ org-private feedback_events (RLS)
        │                                                              │
        │  list_feedback / strata feedback list  ◀── "published to    │
        │      their portal" (their org's queue, read via MCP)        │
        ▼                                                              ▼
   ADMIN (you), MCP admin scope ──admin_list_feedback(all orgs)──▶ triage across every tenant
        │                                                              │
        └── apply_feedback / promote ──▶ validator + fence ──▶ SHARED bank (public primitive)
                                              │
                                              └──▶ accuracy eval re-runs ──▶ tool improves for everyone
```

- **"Published to their portal"** = the org's own feedback is readable back through the MCP
  (`list_feedback`) + REST `/me/feedback` — no web UI needed; their AI tool *is* the portal.
- **Admin access to everybody's feedback** = a new **admin-scoped** principal + MCP tool
  `admin_list_feedback` / `admin_resolve_feedback` (gated by an `is_admin` claim / an admin API key;
  RLS bypass only for that role, audited). This is how you (founder) see demand + corrections across all
  orgs entirely through the connector.
- **The compounding step:** `apply_feedback` already writes an org-private correction; add an admin
  **promote** path (org-private → shared/public, validator-gated) so accepted corrections raise quality
  for all tenants. Track "corrections applied" + "markets unblocked" as the flywheel metric.

---

## 8. Financial-modeling layer (DCF / LBO / Excel / metrics)

> How to generate the detailed plan: `/ce-plan finance package` after a ce-best-practices-researcher
> pass on DCF/LBO conventions.

New `strata.finance` package (pure, typed, numpy-backed; assumptions tagged sourced-vs-set):

- `dcf.py` — revenue build (sized TAM × share path), margin/tax/D&A/capex/NWC → FCF, WACC (CAPM off the
  markets connector), terminal value (Gordon/exit-multiple), EV→equity bridge, WACC×g sensitivity grid.
- `lbo.py` — sources&uses, multi-tranche debt + cash sweep, operating model, exit, IRR/MOIC, returns grid.
- `comps.py` — pull comp multiples (EDGAR/markets), apply to the metric → implied value.
- `metrics.py` — CAGR, Rule-of-40, independence/convergence/confidence, etc.
- **Excel:** `export_xlsx` via the **`xlsx` skill / openpyxl** — multi-tab workbook with *live formulas*
  (not just values) so an analyst can flex it; every input cell carries a source comment.

MCP: `build_dcf`, `build_lbo`, `comps_value`, `export_xlsx`, `export_table`. CLI: `strata model
dcf|lbo|comps`, `strata export xlsx|csv|md`.

---

## 9. The MCP + CLI surface (target)

**MCP tools (existing + new):** existing 22 (search/size/build/resolve/verify_market_claim/
get_report_for_tam/export_report/connectors/feedback/portfolio/…) **plus**: `verify_source`,
`propose_primitive`, `get_charts`, `export_table`, `export_xlsx`, `build_dcf`, `build_lbo`,
`comps_value`, `naics_lookup`, `comp_set`, `gap_report`, `admin_list_feedback`, `admin_resolve_feedback`.
Every result keeps max-utility shape: `structuredContent` + `resource_links` + `next_actions` + charts
+ citations + confidence.

**CLI (`strata`) command tree:**
```
strata size <market>                       # sized TAM (+ --json --premium)
strata resolve "<query>" [--gap-report]    # resolve or honest data-shopping-list
strata source verify|modify|list <slug>    # AC-1 / AC-2
strata report <concept|hash> --pdf --brand # AC-4
strata export xlsx|csv|table <hash>        # AC-5 / AC-8
strata model dcf|lbo|comps <args>          # AC-6 / AC-7
strata feedback submit|list|resolve [--apply]
strata admin feedback [--all-orgs]         # AC-9 (admin)
strata connectors list|test|ingest         # connector ops
strata eval accuracy                       # the moat metric
```

---

## 10. Super-technical implementation notes

- **Data model:** extend `AtomicPrimitive`/`Source` with `confidence`, `freshness_sla_days`,
  `source_of_record`, `verification_status`, `corroborations`; new `FinancialModel`, `WorkbookSpec`
  Pydantic models. Migrations additive + reversible. pyright-strict, ruff clean, 100-char.
- **Typing bar (explicit ask):** Enums for every closed set; frozen dataclasses for connector layers;
  TypedDicts for raw API shapes; Pydantic v2 for domain models; `functools.partial` for connector
  method binding; discriminated unions for source tiers / answer strategies.
- **Rust / fast libs (use them all):** `rapidfuzz` (already in — fuzzy concept/NAICS match), **`polars`**
  for connector data wrangling + comp aggregation (fast, typed), `numpy` for DCF/LBO math,
  `orjson` for payloads, `xxhash`/`blake3` for snapshot hashing, `pydantic-core` (already). For
  structural code ops use the **ast-grep** skill.
- **Connectors:** keep the 6-layer pattern; add a shared `HttpConnector` base (retry/backoff,
  per-host rate-limit token bucket, ETag/conditional-GET caching, circuit breaker), and a capability
  manifest surfaced by `list_connectors` (args/returns/example/tier/freshness/cost).
- **Accuracy engine:** `strata/accuracy/` — `triangulate.py`, `corroborate.py` (outlier/MAD),
  `confidence.py`, `verify.py`; wired into `size_concept` so every `TAMOutput` carries confidence +
  verification. Golden eval in `strata/evals/`.
- **Admin/RLS:** an `is_admin` principal (admin API key or Clerk claim); `admin_*` tools open a
  cross-org read scope, every call audited; never expose admin scope to a normal key.
- **MCP ergonomics:** structured outputs + `outputSchema` on all new tools; resource templates for
  workbooks/models/snapshots (`strata://workbook/{hash}`, `strata://model/{hash}`); prompts
  `strata.size|verify|report|model|gap`; progress notifications on long connector/model ops; elicitation
  when a market is ambiguous or a model needs a missing driver.
- **Testing:** golden accuracy eval (gate), connector contract tests (recorded fixtures), finance
  model unit tests (known DCF/LBO answers), MCP contract tests (stdio↔HTTP parity, outputSchema
  validation), feedback RLS + admin-scope tests.

---

## 11. Phased roadmap (each = its own PR(s); generate the detailed plan per phase)

| Phase | Theme | Generate plan with | Headline deliverable |
|---|---|---|---|
| **A** | Accuracy engine + provenance model | `/ce-brainstorm`→`/ce-plan`→`/ce-optimize` | confidence + triangulation + verify_source + eval gate |
| **B** | Connector breadth (NAICS/EDGAR/private + recipe) | ce-web-researcher → `/ce-plan` | sizes "market research tools" end-to-end; gap_report |
| **C** | Feedback flywheel + admin-via-MCP | `/ce-plan` | admin_list_feedback + promote-to-shared loop |
| **D** | Finance layer (DCF/LBO/comps/metrics) | `/ce-plan` + researcher | build_dcf/build_lbo |
| **E** | Exports (xlsx/table/csv) + report polish | `xlsx` skill + impeccable (report only) | export_xlsx with live formulas; pro report |
| **F** | CLI completeness + MCP ergonomics | mcp-builder | full command tree, prompts, elicitation, progress |

Run each phase with `/lfg`; capture learnings with `/ce-compound`; keep PRs stacked, reviewed
(`/ce-code-review` + `/simplify`), never merged to main without review.

---

## 12. Open questions for you (decide before Phase B/C)

1. **Private-market data:** PitchBook/Crunchbase are paid + licensed — which can we license now? (Biggest
   coverage lever for VC TAMs.)
2. **Analyst-report ingestion:** legal posture on paraphrasing IBISWorld/Gartner figures (cited, not
   reproduced)? Defines how much top-down we can show.
3. **Admin identity:** admin via a dedicated API key, a Clerk org role, or a separate principal? (Sets
   the `admin_*` gate.)
4. **Accuracy ground truth:** what's the curated golden set we grade against, and who owns it?
5. **Excel fidelity:** values-only first, or live formulas from day one? (Formulas = much higher value,
   more work.)
```
flag (analyst) ─▶ MCP publishes to their portal ─▶ admin sees all orgs (MCP) ─▶ curate shared bank
   accuracy engine grades every number ─▶ eval score rises ─▶ the connector gets more trusted
```
