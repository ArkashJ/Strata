# Strata Live — Interactive Compute, Charts, Thin Auth & Polish

**Date:** 2026-05-30
**Status:** Approved (brainstorm forks resolved with user)
**Branch:** `feat/strata-live-interactive-compute`

## Context

Strata v0.4.0 is deployed (Railway backend on the funded Anthropic SDK path;
Vercel frontend with the corrected `NEXT_PUBLIC_API_URL`). The backend evaluator,
ReactFlow graph, `/resolve` SSE, and shadcn charts (SP-1) all exist. The product's
core differentiator — *ask a nuanced TAM question, see it computed, edit a graph
node, watch it recompute* — is **not yet interactive**: the evaluator has no
override path and graph nodes are read-only.

This spec adds that loop plus three supporting tracks. It deliberately stays
inside the load-bearing schema rules (Q1 scenario trees, Q3 composite/framework
line, Q15 no scalar defaults, Q20 no invented citable primitives).

## Approved decisions

1. **Priority:** crown-jewel (interactive compute) gets the deep work; auth is a thin shell.
2. **Node edits:** BOTH primitive-swap **and** transient what-if scalar overrides.
   What-if values are URL-only, never persisted as a primitive, and every affected
   scenario carries a `user_override` banner with `uses_synthetic_primitives=true`.
3. **Clerk:** scaffold fully now; user supplies publishable/secret keys.

---

## Track A — Edit → Recompute loop (crown jewel)

### Data flow
```
/build/<hash>
  ├ free-text query ─► POST /resolve (SSE) ─► TAMOutput                [exists]
  ├ click input node ─► OverridePanel
  │     ├ (A) swap primitive  → BuildState.framework_assumptions[fw][input]=slug
  │     └ (B) what-if scalar  → BuildState.primitive_overrides[slug]={value,unit}
  ├ confirm ─► POST /build/recompute {concept_slug, framework_assumptions?, primitive_overrides?}
  │              evaluator(override-aware) → scenarios + fresh mint_state_hash
  │              overridden scenarios get user_override banner; uses_synthetic=true
  └ URL → /build/<new_hash>?s=… ; headline + graph + charts recompute
```

### Backend (`backend/src/strata/`)
- **`evaluator/engine.py`** — introduce an `EvalOverrides` dataclass:
  `{primitive_overrides: dict[Slug, OverrideValue], framework_assumptions: dict[Slug, dict[str, Slug]]}`
  where `OverrideValue = {value: float, unit: Unit}`. Thread an optional
  `overrides: EvalOverrides | None = None` through `size_concept` →
  `_iter_scenario_builds` → `_build_to_scenario`. Default `None` preserves all
  current call sites and the 310 existing tests.
- When a primitive slug is in `primitive_overrides`, substitute its value at
  evaluation time, append `ScenarioBanner(kind="user_override", text=…)`, and set
  the scenario/output `uses_synthetic_primitives=True`. **Never** write to the
  registry. `framework_assumptions` re-points an input to a different existing
  primitive (schema-pure; no banner needed).
- **`api/routes/build.py`** — new `POST /build/recompute`. Body:
  `RecomputeRequest{concept_slug: Slug, framework_assumptions: dict | None,
  primitive_overrides: dict | None}`. Validate each override's `unit` against the
  consuming `framework.inputs[*].unit_signature`; 422 on mismatch. Return
  `TAMOutput` with a freshly minted `state_hash`.
- **Tests (TDD, `backend/tests/`)** — write first: (1) a scalar override changes
  the scenario value, (2) the affected scenario has a `user_override` banner and
  `uses_synthetic_primitives=True`, (3) the new `state_hash` differs from the
  baseline, (4) a unit-mismatched override returns 422, (5) a primitive-swap to a
  valid existing primitive recomputes with no banner.

### Frontend (`web/src/`)
- **`lib/state-hash.ts`** — add `primitive_overrides: Record<string, {value:number; unit:string}>`
  to `BuildState`; include it in `canonicalizeState`.
- **`lib/schemas.ts` / `lib/queries.ts`** — `recomputeRequestSchema`,
  `recompute(state)` mutation → `POST /build/recompute`; debounced 300ms.
- **`components/ScenarioGraph.tsx`** — make input nodes clickable (`onNodeEdit`);
  overridden nodes render with a distinct accent + a "what-if" chip.
- **`components/build/OverridePanel.tsx`** (new) — tabbed: *Swap primitive*
  (select from compatible sourced primitives) and *What-if* (number input + slider,
  shows sourced baseline vs override delta and the unit). Confirm → recompute →
  push new `/build/<hash>?s=…`.
- **`components/build/BuildWorkspace.tsx`** — hold `primitive_overrides` state,
  show a recompute spinner on the headline + graph, count-up the new TAM value.

---

## Track B — Charts (shadcn / recharts)

Extend the existing `components/ui/chart.tsx` primitives (already initialized,
SP-1 `0e7ae60`). New `web/src/components/charts/`:
- `ScenarioComparisonChart` — bar/area across scenarios of the current TAM.
- `TrajectoryChart` — area chart from `GET /build/{slug}/trajectory` (the
  `ChartAreaLegend` pattern the user supplied).
- `CompositionChart` — breakdown of inputs contributing to the headline value.
Rendered in the `/build` results region and reused on `/tam/<hash>`.

---

## Track C — Thin Clerk auth + dashboard + audit

- **Clerk** (`@clerk/nextjs`): `<ClerkProvider>` in `app/layout.tsx`, sign-in/up
  routes, `middleware.ts` protecting `/dashboard`. Env: `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`,
  `CLERK_SECRET_KEY` (placeholders committed to `.env.example`; real keys go to
  `.env`/Vercel by the user).
- **`/dashboard`** (`app/dashboard/`): the user's saved `/build` artifacts (from
  the existing local state-hash history), live library counts (reuse sidebar
  counts), recent resolves, and the audit feed.
- **Audit** (backend): `audit_events(id, actor, action, target, ts, meta jsonb)`
  table + Alembic migration; append on resolve / recompute / promote. `GET /audit`
  (paginated) feeds the dashboard. Actor = Clerk user id, or `"anon"` when absent.

---

## Track D — Landing + animations

- Proposed dependency: `motion` (framer-motion). Animated landing hero with the
  pyramid + a live example-query → resolve demo; page transitions; graph node
  enter animations; TAM headline count-up. Scope: **landing + dashboard only** —
  no invented extra pages.

---

## Parallelization & batches

Backend (Track A-be, Track C-audit) is fully isolated from `web/` and runs as a
parallel subagent. Frontend shared foundation (deps, layout/provider, shadcn
chart CLI, BuildState/schema additions) is done by the lead first; then bounded
new-file features (charts, landing, override panel, dashboard) parallelize.

Commit + push in batches on `feat/strata-live-interactive-compute`:
1. spec doc
2. shared FE foundation + deps
3. Track A backend (evaluator overrides + /build/recompute + tests)
4. Track A frontend (override panel + graph editing + recompute wiring)
5. Track B charts
6. Track C Clerk + dashboard + audit
7. Track D landing + animations

## Verification
- Backend: `cd backend && uv run pytest && uv run pyright && uv run ruff check .`
  — the 5 new recompute tests pass; existing 310 unaffected.
- Frontend: `cd web && bun run build` clean; Playwright e2e smoke on the
  edit→recompute loop (override a node, assert headline + URL hash change).
- End-to-end: local docker stack, override WTP on a seeded concept, confirm the
  graph recomputes and the `user_override` banner appears in the export footnote.
