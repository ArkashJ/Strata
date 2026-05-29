# Strata — TAM Visualization & Graph Layer (design)

**Date:** 2026-05-28 · **Status:** approved (brainstorm) · builds on the v0.42
frontend rebuild (`~/.claude/plans/run-the-frontend-and-floofy-pearl.md`).

## Goal

Make TAM *legible and alive*: a brainstormed graph framework, modern animations,
a consistent brand kit, an easy related-entities network modal, polished TAM
charts, and a **current-vs-previous TAM trajectory** graph.

## Decisions (brainstorm)

| Decision | Choice | Why |
|---|---|---|
| Node-link graphs | **React Flow** (pyramid, scenario tree) **+ vis-network** (related-entities modal, lineage) | React Flow already powers the fixed pyramid; vis-network gives the force-directed physics the `/network-graph-modal` skill is built around. |
| TAM history source | **Primitive `as_of` time series** | Most sourced/honest: re-evaluate the framework with inputs known as of each date. Needs a backend endpoint. |
| Charts + motion | **Recharts + `motion`** (Framer Motion successor) | Recharts already in stack; `motion` orchestrates entrance/layout/graph transitions, driven by brand-kit motion tokens. |

## Components

### PR12 — Backend trajectory endpoint
`GET /build/{concept_slug}/trajectory` → `TAMTrajectory`:
```
{ concept_slug, concept_name, unit,
  points: [ { as_of: date, value: float, low: float, high: float,
              method_families: [...], scenarios_n: int } ] }
```
Algorithm: collect the concept's measurement primitives, take the sorted set of
distinct `as_of` dates; at each date evaluate the applicable frameworks using
the value of each primitive **as known up to that date** (latest `as_of` ≤ point,
skip the point if a required input is not yet available). Reuses the existing
`evaluator` + `registry`; add an `as_of`-filtered evaluation path. Returns an
empty `points: []` when fewer than one fully-satisfiable date exists (frontend
shows an empty state — never fabricate a trajectory). 167+ backend test suite
stays green; add `tests/test_trajectory.py`.

### PR14 — Related-entities network modal (vis-network)
Follow the `network-graph-modal` skill scaffold. A `<NetworkGraphModal>` opened
from a button on `/c/<slug>` and `/tam/<hash>`. Root = the concept; neighbours =
other concepts/primitives/frameworks connected by **shared signals**: same
`primary_lens`, shared `source.slug`, shared measurement primitives, same
`method_family`. Hover-highlight 1-hop, click-to-pin sidebar, multi-hop expand,
branch collapse, pattern detection on shared signal values. Data from the
existing `/c`, `/p`, `/f` list endpoints (client-side graph assembly) — no new
backend. New files only + thin trigger buttons in the two detail views.

### PR13 — TAM trajectory + comparison chart (Recharts + motion)
`<TamTrajectoryChart>`: area band (low–high) + mid line over `as_of` points from
`/trajectory`; the latest point is "current TAM", earlier points are "previous";
delta callout (▲/▼ % vs prior point). `<TamComparison>` small-multiple for
fork/compare. Surfaced on `/build`, `/tam`, `/c`. Animated reveal via `motion`.

### PR11 — Animation + brand-kit + polish (lead-driven, last)
Add `motion`; animate route transitions, card/grid entrances, graph node
enter/layout, ⌘K palette. Fix the **double-⌘K** (home defers to shell palette).
Slim redundant `/contribute` + ResolveView headers. Brand-kit token audit (no
hardcoded hex). Responsive (sidebar collapse/drawer). Verify **prod build in the
main tree** (`bun run build` — the Turbopack symlink failure is worktree-only).
Run the **full Playwright e2e matrix twice**.

## Parallelization (current tasks persist!)

Wave 3 (PR5 pyramid · PR6 build · PR9 data) keeps running. Wave 4 = PR12 +
PR14, dispatched now in their own worktrees over disjoint files (backend / new
network-modal files + detail-view triggers). PR13 + PR11 follow after the merge.

## Verification

Each PR: `typecheck + biome + vitest` (frontend) / `pytest + pyright + ruff`
(backend). At integration: full `test:e2e` **twice**, prod build, and a Playwright
walkthrough batch. Commit + push in batches; document via the PR description +
inline PR comments on notable decisions/trade-offs.
