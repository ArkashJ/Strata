# Portfolio Sizing + Company Layer — Design

**Date:** 2026-05-31
**Status:** Approved (brainstorm) — pending spec review
**Codename:** Strata · P1 of the "size my portfolio via the MCP" track

---

## 1. Problem

A VC drops a list of portfolio companies into a Claude session that has the
Strata MCP attached and says "size the TAM for these." Today the MCP is
read-only (5 tools) and can only return TAMs for the ~37 curated markets. There
is no way to (a) link a list of companies to an account, (b) size a company that
isn't already a curated market, or (c) grow the primitive bank from that work.

This project delivers the first slice: **link a 4,918-company portfolio to your
org, then size companies on demand**, sourcing real primitives (regulator via
connectors, analyst via Exa) and persisting them — making the primitive bank
more robust with every sizing.

Out of scope for this slice (deferred, see §10): lens-taxonomy expansion, eager
mass-sizing, hosted MCP write-auth, web dashboard.

---

## 2. Decisions locked in brainstorm

| # | Decision | Choice |
|---|----------|--------|
| D1 | Sizing unit | **Hybrid** — shared MARKET concept + org-scoped COMPANY pointer, with optional per-company refinement (overrides) |
| D2 | Sourcing trust (Q20) | **Tiered public with banners** — Exa-located numbers persist as `analyst` tier (url+snapshot); TAMs using them carry a "contains unverified analyst inputs" banner. **No LLM-computed numbers ever persist.** |
| D3 | First slice | **Bulk-import 4,918 company pointers first**, size lazily on demand |
| D4 | Architecture | **A** — DB `companies` table + importable `strata.sizing` service + write-capable MCP tools + CLI |
| D5 | Default org (local) | `"default"` |
| D6 | Surfaces shipped | **CLI + MCP together** (the MCP write tool is the headline deliverable) |

---

## 3. Conceptual model

A company does not have a TAM — the **market it competes in** does. So the
sourced, expensive work lives at the market level; a company is a cheap pointer
plus optional refinement.

```
  4,918 companies ─┐
  (org-scoped      ├─► ~hundreds of MARKETS (shared Concepts, sourced) ─► base TAM
   pointers)       │            ▲ the real work + the primitive bank growth lives here
                   │            │ pointer
  company:cursor ──┴────────────┘  + optional saved EvalOverrides (geo/segment)
                                       └─► refined company-specific scenario
```

Three types:
- **MARKET** = existing `Concept` (shared, public). Unchanged identity.
- **COMPANY** = new org-scoped row pointing at one market (many companies → one market).
- **REFINEMENT** = existing `EvalOverrides` (already powers `/build/recompute`), stored on the company, applied at size time. Never persists as a new primitive (Q20-safe).

---

## 4. Data model

New table `companies` (Alembic migration; mirrors the `PrimitiveRow`/`ConceptRow`
pattern in `db/models.py`):

```
companies
  id                   PK
  org_id               str, indexed            -- from the API-key Principal; "default" locally
  name                 str
  domain               str                     -- normalized (lowercased, scheme/path stripped)
  vertical             str | null              -- the CSV "Industry Vertical" tag
  market_concept_slug  str | null  FK→concepts -- null until sized
  status               enum: unsized | sized | unsizable
  overrides            JSONB | null            -- optional EvalOverrides for per-company refine
  tam_value            float | null            -- cached base/refined TAM
  reason               str | null              -- why unsizable (missing role, etc.)
  sized_at             timestamptz | null
  created_at           timestamptz
  UNIQUE (org_id, domain)                       -- import idempotency
```

RLS: org-scoped reads, consistent with migration 003 `tenant_data` `FORCE RLS`
on `app.org_id`. In-process default-org path for local/CLI.

A lightweight `CompanyRecord` Pydantic model carries this between layers.

---

## 5. The sizing service — `strata.sizing`

Productize the proven engine in `scripts/tam_77_pipeline.py` into an importable,
pure, testable module. Single entry point:

```python
def size_company(reg: Registry, company: CompanyRecord, *, opts: SizeOptions) -> SizeResult
```

Pipeline (each step isolated + independently testable):

```
1. MARKET MATCH  (registry-first, free, no LLM)
   match_concept(name / vertical / description) clears threshold?
     hit  → link company.market_concept_slug, return shared TAM (+ overrides)   [cheapest]
     miss → step 2

2. CLASSIFY  (Claude, one tool call: classify_company)
   → primary lens + framework_slug (one of the 5) + geo + concept definition
   + the 2–3 input primitive ROLES the framework requires (REQUIRED_PRIMITIVE_ROLES)

3. SOURCE each required input, in strict priority order:
   a. connector hint present → call live API (BLS/Census/FRED/WorldBank/openFDA)
      → regulator tier + real value + sha256(response)        [via connectors/_dispatch]
   b. else Exa search → fetch the top real result page → VERBATIM GUARD (§6)
      → analyst tier + url + sha256(page text)                [persisted, banner downstream]
   c. NEVER an LLM-computed number. An input that can't be sourced stays unfilled.

4. PERSIST  (only if ≥ all required roles sourced)
   - upsert market concept + sourced primitives + a framework variant binding them
   - writer.upsert_primitive for the new primitives (this GROWS the bank)
   - if any input is analyst tier → set a measurement flag so the TAM/report carry
     the "contains unverified analyst inputs" banner

5. EVALUATE  size_concept(slug) → TAMOutput
   - apply company.overrides via EvalOverrides if present → refined scenario
   - link company.market_concept_slug, cache tam_value, status = sized

6. UNSIZABLE  if < required roles sourced → status = unsizable,
   record {proposed_lens, missing_role, reason} to the lens-gap log (§9)
```

`SizeOptions`: `allow_live` (connectors), `allow_exa` (analyst fallback),
`budget` (max LLM/Exa spend per batch), `persist` (dry-run when false).
`STRATA_OFFLINE=1` forces registry-first only (CI-safe).

### Isolation boundaries
- `strata.sizing.classify` — company → classification (Claude). Pure given a completion fn.
- `strata.sizing.source` — role → sourced primitive (connector | Exa+guard). Pure given client fns.
- `strata.sizing.persist` — classification + sourced primitives → written market concept.
- `strata.sizing.service.size_company` — orchestrates the four above. No I/O of its own beyond what it's handed.

This mirrors the existing resolver split (parse/search/match/writer) so it reads like the codebase.

---

## 6. The verbatim guard — the Q20 wall

The single most important new component. It is the wall between "extracted a real
sourced number" (allowed to persist) and "an LLM produced a number" (forbidden).

```
value V extracted by the LLM from Exa result page P:
   normalize(P.text) CONTAINS normalize(V)?
     yes → persist analyst primitive (value=V, url=P.url, snapshot=sha256(P.text))
     no  → REJECT — do not persist; the input stays unsourced
```

`normalize` must treat these as equal so the guard isn't trivially defeated and
isn't falsely tripped:

```
$4.2B  ≡  4.2 billion  ≡  4,200,000,000  ≡  USD 4.2bn
```

Implementation: parse V into a magnitude; scan the page text for any surface form
that resolves to the same magnitude within a tight tolerance (exact for integers,
±0.5% of the rounded form for "4.2B"-style). The guard returns the matched
substring + offset so provenance is auditable.

This component gets dedicated adversarial tests (§8) and is the first thing a
reviewer should scrutinize.

---

## 7. Surfaces

```
CLI (local, default org)
  strata portfolio import "Cos list.csv"            → N rows under org "default", status=unsized
  strata portfolio size --vertical Dev --limit 20 --budget 5.00
  strata portfolio size --domain cursor.com
  strata portfolio list --status sized|unsized|unsizable

MCP (Claude session, write-capable for the first time)
  import_portfolio(rows: [{name, domain, vertical}])   [WRITE]  → counts
  size_company(domain | name)                          [WRITE]  → sourced TAM + provenance
  list_portfolio(status?, vertical?, limit?)           [READ]   → company rows + TAM

HTTP (thin, optional in this slice; mirrors CLI)
  POST /portfolio/import   POST /portfolio/{id}/size   GET /portfolio
```

### MCP write-capability (new)
- `tools.py` gains three handlers; `TOOLS`/`schemas.py` advertise them.
- Write tools require an authenticated principal (`org_id` from the API-key
  Principal — substrate already exists). Read tools stay open.
- Local stdio MCP + CLI use `org_id = "default"`.
- The existing read-only tools are unchanged; this is additive.

### Account linkage = the literal "link my 4.9k" ask
`import_portfolio` inserts the rows under your `org_id`, all `unsized`,
idempotent on `(org_id, domain)`. Sizing stays lazy/on-demand for cost control.
`list_portfolio` shows progress (sized / unsized / unsizable counts).

---

## 8. Testing

- `strata.sizing` unit tests with a fake `Registry`, mocked connector dispatch,
  and a stub Exa/LLM — no network. Cover: registry-first hit, connector source,
  Exa-analyst source, unsizable path.
- **Verbatim-guard adversarial suite** (its own test file):
  - `"$4.2B"` vs page `"4.2 billion"` → pass
  - `"$4.2B"` vs page `"$4,200,000,000"` → pass
  - `"$4.2B"` vs page `"$3.9B"` → reject
  - LLM value absent from page → reject
  - unit/format noise (`"USD 4.2bn"`, whitespace, footnote marks) → pass
- Import idempotency: re-import the same CSV → no duplicate rows.
- Banner propagation: a market with an analyst input → TAM + report carry the
  "unverified analyst inputs" banner.
- One gated live smoke (`STRATA_OFFLINE` skips) sizing a single real company end-to-end.
- Regression: existing 542 backend tests stay green; the 5 read-only MCP tools unchanged.

---

## 9. Lens-gap log — makes the deferred P3 honest

Every `unsizable` company appends a structured row:

```
{ company, domain, proposed_lens, missing_role, reason, ts }
```

After a few hundred sizings, this log is the evidence base for which new lenses /
frameworks are actually needed. **P3 (lens expansion) becomes "add the top-N
proven-missing lenses," not a speculative taxonomy rewrite.** Stored as a JSONL
artifact (and/or a `lens_gaps` table) queryable by `strata portfolio gaps`.

---

## 10. Deliberately deferred (YAGNI)

```
✗ Lens taxonomy expansion (P3)  — data-driven via §9, after this slice runs.
✗ Eager-size all 4,918           — on-demand only; batch = size loop + budget cap.
✗ Hosted /mcp write-auth         — local/default-org first; HTTP write-auth later (Wave-3 keys exist).
✗ Per-company web dashboard      — CLI/MCP first; web view later.
✗ SAM/SOM                        — TAM only this slice.
```

---

## 11. Build sequence (for the implementation plan)

```
1. companies table + migration + CompanyRecord model + RLS
2. strata.sizing: classify → source → persist → service (with the verbatim guard first, TDD)
3. CLI: strata portfolio import|size|list|gaps
4. MCP write tools: import_portfolio / size_company / list_portfolio (+ schemas, auth gate)
5. (thin) HTTP: /portfolio import|size|list
6. Tests throughout (guard suite first); gated live smoke
7. Import the real Cos list.csv under org "default"; size a handful; verify provenance + banners
8. Docs: docs/NN-portfolio-sizing.md + CLAUDE.md repo-state + CHANGELOG
```

The verbatim guard (§6) and the sizing service (§5) are the load-bearing units;
everything else is plumbing around them.
