# Temporal TAM — today market + future market sizing

> **Status:** in flight (`feat/temporal-tam`). **Author:** review-driven (VC reader).
> **Scope:** lights up the schema's dormant temporal machinery to give every TAM a
> *today* market and a *future* market, on the MCP + CLI product surface.

---

## 1. The gap

A `size_tam` result today is a single steady-state point estimate per scenario
(`flow · per-year · nominal`). There is no *today / realized* market figure
distinct from a *future / saturated* one. Sizing `ai-coding-assistants-us` returns
four scenarios between \$132M and \$900M — every one an end-state. A VC reads a
market as **current realized spend** vs **the prize at maturity**; a single
saturated number conflates the two, and the adoption-curve frameworks
(`cost-efficiency-adoption-gated`, the latent-demand logistics) make it worse —
they collapse the *whole* adoption curve into one asymptotic value via
`adoption_midpoint` / `adoption_steepness` rather than emitting a current-year and
a horizon-year point.

The symptom is visible in the output: the `penetration` chart
(`mcp/charts.py::_penetration`) is hardcoded to an **empty** spec with the note
*"No dated adoption/CAGR primitives are sourced for this concept yet."* The
plumbing for a temporal view was scaffolded and never fed.

## 2. What already exists (don't rebuild it)

This is **not** a greenfield feature. The schema authors reserved the temporal
machinery; it is dormant, not absent. The defensible move is to *light it up*,
not bolt on a parallel system.

| Asset | Where | State |
|---|---|---|
| `InputRole.GROWTH_INDEX` — the Q6 "time-travel role" | `models/framework.py:60` | declared, **unused** by all 25 frameworks |
| `HorizonClass` (`snapshot` / `short_extrapolation` / `long_extrapolation`) | `models/framework.py:72` | every framework declares `snapshot`; the other two **never used** |
| `Framework.expansion_stage_parameter` | `models/framework.py:129` | declared, unused |
| `trajectory()` + `TAMTrajectory` / `TrajectoryPoint` | `evaluator/engine.py:591`, `models/tam_output.py:166` | **backward-looking** historical reconstruction from primitive `as_of` dates; exposed **only** on the HTTP API (`/build/<slug>/trajectory`), **absent from MCP + CLI** |
| `penetration` chart scaffold | `mcp/charts.py:108` | honest-empty placeholder |
| `Convergence` (method-agreement ratio) | `models/tam_output.py:116` | per-TAM; we mirror its "never fabricate the second thing" discipline |

So two things are true at once: there is a *backward* time series nobody on the
product surface (MCP/CLI) can reach, and there is **no** *forward* projection at
all. This plan delivers the forward half and surfaces both.

## 3. The defensibility contract (non-negotiable)

Every rule below maps to a locked decision in `docs/07-data-layer-brainstorm.md`
or `CLAUDE.md`'s "What NOT to do". The feature is worthless to a VC if the future
number is a guess wearing a suit.

1. **No LLM-projected primitives, ever (Q20).** The future market is driven by a
   **growth primitive** — a sourced, hash-pinned CAGR / adoption rate that lives
   in the data bank like any other number. A projection is *arithmetic over a
   sourced input*, exactly the unit-crossing math frameworks already own (Q3). We
   do not invent a growth rate inside the engine.
2. **Refuse rather than fabricate.** If a concept has **no** sourced growth
   primitive, `project_tam` returns `None` and the penetration chart stays the
   honest-empty placeholder. A missing future market is reported as a gap
   (`report_sourcing_gap`), never manufactured. This mirrors `Convergence`
   returning `None` for single-method concepts.
3. **Provenance rides the projection (Q5, Q37).** The projection carries the
   growth primitive's `snapshot_sha256`, `source_tier`, and — when the growth rate
   is `community-modeled` / `analyst` — the same `MODELED` banner the evaluator
   already raises (`_banners_for`). A modeled CAGR produces a banner-flagged future
   number, never a silent one.
4. **The today anchor is honest about its base year.** "Today" is the TAM midpoint
   anchored to the **latest `as_of`** among the primitives the TAM actually
   consumed — not the wall clock. The horizon year is `base_year + horizon_years`.
   Both points are labelled (`realized` vs `projected`).
5. **Derived, not hashed.** Like `Convergence` and `ScopeReport`, the projection is
   pure synthesis over already-pinned inputs and is **not** part of the TAM state
   hash — the permalink identity is unchanged.

## 4. Design

### 4.1 Data model (additive, backward-compatible)

- `Concept.growth_index: Slug | None = None` (`models/concept.py`). Optional;
  existing YAML loads unchanged. Points at the atomic growth primitive that sizes
  this market's expansion. Explicit beats unit-sniffing — a VC can see *which*
  sourced rate drives the projection.
- `ProjectionPoint(year: int, value: float, kind: "realized" | "projected")` and
  `TAMProjection(concept_slug, concept_name, unit, base_year, horizon_year, cagr,
  cagr_primitive, cagr_source_tier, cagr_snapshot_sha256, today, horizon, banners)`
  in `models/tam_output.py`. Mirrors the `TAMTrajectory` shape and banner
  discipline.

A **growth primitive** is an ordinary `AtomicPrimitive` whose unit is a per-year
rate (`kind=intensive, dimension=percent, denominator="per-year"`). It obeys every
existing fence: tier, snapshot, uncertainty range, `_derive_provenance`. A
`community-modeled` growth rate is allowed *with* its `MODELED` banner — the same
bar the existing `ai-coding-assistant-acv-per-engineer-2024` ACV clears.

### 4.2 Engine

`project_tam(registry, concept_slug, *, horizon_years=5, overrides=None) ->
TAMProjection | None` in `evaluator/engine.py`:

1. `size_concept(...)` → today TAM. `today_value` = midpoint of scenario values
   (same triangulation the trajectory uses).
2. Resolve `concept.growth_index`; if absent / not an atomic / wrong unit → return
   `None` (honest gap).
3. `base_year` = max `as_of` year across consumed primitives.
4. `cagr` = growth primitive value (fraction). `horizon_value = today_value *
   (1 + cagr) ** horizon_years`. Finite-checked like `_eval_formula`.
5. Attach the growth primitive's banner(s); pin its snapshot. Return
   `TAMProjection` with `today` (`realized`) and `horizon` (`projected`) points.

Pure, offline, registry-only — no live calls on a render path (F3).

### 4.3 Surface (MCP + CLI are the product)

- `_serialize_tam_output` (`mcp/tools.py`) gains a `projection` block and a
  `trajectory` block (backward points), so `size_tam` / `resolve_market` /
  `build_tam` carry today + future. When `project_tam` is `None`, the field is
  `null` with a one-line honest reason — the agent can chain
  `report_sourcing_gap`.
- `charts.py` gains a **pure** `penetration_spec(points, projection)` builder
  (no registry dependency — fed by the MCP layer that has `reg`). Historical
  trajectory points + today + projected horizon, the projected leg dashed and
  annotated. The honest-empty `_penetration` stays as the fallback when there is
  no projection.

### 4.4 Out of scope for this PR (tracked follow-ups)

- DB round-trip / migration for `Concept.growth_index` (local YAML + stdio is the
  driving surface; the field defaults `None` so seed/DB load is unaffected).
- A first-class `GROWTH_INDEX`-role framework variant that projects *inside* the
  scenario tree (this PR projects the TAM midpoint; a per-scenario growth input is
  the natural next step now that the role is lit).
- Sourcing real analyst/aggregator CAGRs to replace community-modeled seeds.

## 5. Verification

- Unit: projection math (`today * (1+cagr)^n`); `None` when no growth primitive;
  modeled-tier growth raises a `MODELED` banner; horizon/base years correct;
  non-finite refused.
- Chart: `penetration_spec` returns a populated, well-formed Vega-Lite spec with a
  `realized` and a `projected` series; honest-empty when projection is `None`.
- Surface: `size_tam` payload carries `projection` + `trajectory`; `null`
  projection on a concept with no growth primitive.
- Regression: full suite stays green (`pytest && pyright && ruff check && ruff
  format --check`).

## 6. Worked example

`ai-coding-assistants-us` gets a `community-modeled` growth primitive
(`ai-coding-assistant-spend-cagr-2024`, banner-flagged, ranged) and
`growth_index:` set. Sizing then returns: today ≈ the current midpoint anchored to
2024, and a 2029 horizon at the modeled CAGR — with a loud "this CAGR is modeled,
not sourced" banner. The methodology is the product; the seed is honest-but-modeled
until a real CAGR is sourced.
