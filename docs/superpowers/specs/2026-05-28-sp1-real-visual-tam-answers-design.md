# SP-1 — Real, Visual TAM Answers

**Status:** design (awaiting user review)
**Date:** 2026-05-28
**Branch:** `ArkashJ/sp1-real-visual-tam` (off `main`)
**Author:** Arkash + Claude

This is the first of three sub-projects decomposed from the 2026-05-28 goal.
SP-2 (Stripe micro-payments + agentic 402 rail) and SP-3 (launch the `strata`
CLI + flagship connector) are **out of scope** here and get their own specs.

---

## 1. Problem

The product "feels mock" not because the data is fake — it isn't (358 primitives,
5 frameworks, 30 concepts, all connector-sourced and validated) — but because the
**headline feature, the dynamic resolver, returns nothing real**. Diagnosed
concretely this session:

```
ANTHROPIC_API_KEY is present in the shell env (sk-ant-api03-…, out of credits).

  claude -p  WITH inherited env   → is_error:true, 400 "Credit balance is too low"   ✗
  claude -p  WITH key unset       → is_error:false, result:"PONG"  (subscription auth) ✓
```

Two defects make every LLM call die — locally *and* in prod:

1. **`resolver/llm.py::_complete_cli`** spawns `claude -p …` inheriting the
   ambient `ANTHROPIC_API_KEY`, so the CLI is API-billed against a dead key
   instead of using the Claude Code subscription that authenticates the
   interactive session.
2. **`resolver/slug.py:110`** calls `anthropic.Anthropic().messages.create()`
   **directly**, bypassing `llm.complete()` entirely — so it ignores the
   backend switch and the env scrub, and always hits the out-of-credits API.

Net effect: `strata goal` and `POST /resolve` always fall through to the honest
"AI backend unavailable" path. The chain-of-thought, the attached primitives,
the charts — all the things that would make it feel real — never render for a
live query.

Secondary gaps surfaced while scoping:

- **0 composite primitives** exist (358 atomic). The same-unit set-op layer
  (Q3) is unexercised, so no query demonstrates union/filter/restrict.
- Charts are **hand-rolled recharts/reactflow** components, not the shadcn
  chart system the user wants; visual quality is inconsistent.
- Only 6 originals + worked examples are deeply wired; the registry needs more
  VC-relevant worked TAM questions so concept-hit queries (which need **no LLM**)
  return rich, real answers even where the `claude` CLI is absent (e.g. Railway).

## 2. Goals / Non-goals

**Goals**

- G1. A live TAM query (`strata goal "<q>"` and `POST /resolve`) streams a
  **real** chain-of-thought with attached primitives, wherever the `claude` CLI
  is available, authenticating via subscription (no funded API key required).
- G2. Four new VC-relevant worked TAM questions resolve via **concept-hit**
  (no LLM needed), each backed by a new **composite** primitive (same-unit set
  op) plus new connector-sourced atomic primitives — so the demo is robust in
  prod too.
- G3. The web result surfaces (`/build`, `/resolve`, `/tam/<hash>`) render
  **shadcn interactive charts** on every query, replacing the four hand-rolled
  recharts components.
- G4. A Playwright-CLI e2e proves the full path: type a question → see the
  chain-of-thought → see attached primitives → see charts.
- G5. ast-grep rules guard the two resolver invariants so the defects can't
  regress; existing gates (`pytest`, `pyright`, `ruff`, `bun run check`) stay
  green.

**Non-goals (explicit)**

- N1. Stripe / payments / agentic 402 — that is **SP-2**. SP-1 adds **no**
  payment surfaces, not even stubs.
- N2. Packaging/publishing the CLI or a new connector — that is **SP-3**.
- N3. Full UI migration to shadcn. SP-1 is **charts + targeted polish only**;
  the bespoke app shell, theme, sidebar, and command palette stay.
- N4. New connectors. We author primitives from the connectors that already
  exist (BLS, Census, FRED, FDIC, EDGAR, EIA).
- N5. Funding the production Anthropic key. Prod novel-query LLM remains an ops
  decision (documented in §8 Risks); SP-1 makes seeded questions work without it.

## 3. Architecture & data flow

No new services. The change is two surgical resolver fixes, a data-authoring
pass, a frontend chart layer swap, and tests.

```
strata goal "<q>"  /  POST /resolve
        │
        ▼
 resolver/pipeline.run
   pre. slug.resolve_slug ──[FIX 2]──▶ llm.complete()  (was: direct SDK call)
        │                                   │
        │                                   ▼
        │                       llm._complete_cli ──[FIX 1]──▶ subprocess.run(
        │                                   env = {**os.environ, ANTHROPIC_API_KEY removed})
        │                                   └─▶ claude -p … (subscription auth) ✓
        ▼
   1. concept match → evaluator.size_concept ──▶ scenario tree  ◄── NEW composites+primitives (W2)
   2. primitive match → single / compose
   3. connector live (router → connector → upsert)
   4. fallback (Claude+Exa, ephemeral)
        │
        ▼  SSE: parsing→searching→framework_selected→evaluating→result
 Frontend (Next 16 / React 19 / TanStack Query)
   ResolveView (CoT stream) · BuildWorkspace · TamDetailView
        └─▶ shadcn ChartContainer (W3): Area / Bar / Radial  ◄── replaces hand-rolled recharts
```

## 4. Workstream W1 — Resolver hardening

**Files:** `backend/src/strata/resolver/llm.py`, `backend/src/strata/resolver/slug.py`
(+ tests under `backend/tests/`).

- **W1.1** In `_complete_cli`, build an explicit subprocess env that **removes
  `ANTHROPIC_API_KEY`** (and `ANTHROPIC_AUTH_TOKEN` if present) before
  `subprocess.run(...)`, so the CLI uses subscription auth. Pass `env=` rather
  than mutating `os.environ`. WHY-comment the inheritance trap.
- **W1.2** In `slug.py::resolve_slug`, replace the direct `anthropic.Anthropic()`
  call with `llm.complete(prompt, system=…, model=…)` + the existing
  `_strip_code_fence` / JSON parse. This unifies the backend switch and inherits
  the W1.1 scrub. The `STRATA_LLM_BACKEND=anthropic` opt-in path still works for
  funded-key deployments.
- **W1.3** Add a lightweight resolver self-check: `GET /healthz/llm` (or extend
  existing healthz) that reports whether a backend is reachable, so the UI/ops
  can distinguish "no backend" from "transient error". Read-only, no secrets.
- **W1.4** Tests: unit test that `_complete_cli` constructs an env without
  `ANTHROPIC_API_KEY`; unit test that `resolve_slug` calls `llm.complete` (mock).
  Keep the existing SSE contract tests green.

**Acceptance:** with `ANTHROPIC_API_KEY` set to a dead key, `strata goal
"<seeded q>" --stream` still streams a real result (subscription path), and a
novel query parses instead of erroring at `pre`.

## 5. Workstream W2 — Data depth (4 worked TAM questions)

Author **4 new concepts**, each with one **composite** (same-unit set op) and
the **atomic primitives** it unions, all connector-sourced and sha256-pinned.
No invented figures — every number traces to a connector pull or a labelled
community-modeled multiplier with a range. Composites are **same-unit only**;
all unit-crossing math stays in frameworks (Q3, hard line).

| # | Concept (TAM question) | Lens | Composite (same-unit set op) | Atomic primitives (source) |
|---|---|---|---|---|
| 1 | AI legal assistants (US) | L1 cost×persona | `us-legal-professionals` = lawyers ∪ paralegals — **persons** | BLS OES 23-1011 lawyers; 23-2011 paralegals; seat $/yr (community-modeled, ranged) |
| 2 | AI coding assistants (US devs) | L6 productivity | `us-software-engineers` = developers ∪ QA/test ∪ ops — **persons** | BLS OES 15-1252 devs; 15-1253 QA; 15-1244 netops; value-split (modeled, ranged) |
| 3 | Embedded payments / vertical SaaS (US) | L2 revenue | `us-smb-card-volume` — **USD/yr** | Census CBP SMB counts; FRED card-volume series; take-rate (modeled, ranged) |
| 4 | US instant-payments / RTP rails | L4 throughput | `us-realtime-payment-volume` = RTP ∪ FedNow — **USD/yr** | FRED/clearing-house RTP value; FedNow value; FDIC institution counts; take-rate (modeled) |

Each concept reuses an **existing framework variant** (L1/L2/L4/L6 already
shipped) so we wire pointers, not new framework math. Where a multiplier is
community-modeled it carries a `range` and a provenance banner per Q20/Q37.

**Schema work:** composites are the first of their kind in `data/`. The plan
phase will read the canonical composite shape from `docs/07-data-layer-brainstorm.md`
§Final design + the Pydantic model, and place files under `data/composites/`
(the loader already has the directory convention). Validator L1+L2 must accept
them (unit signatures, set-op kind). If the composite path has bit-rot from
never having a real record, fixing the loader/validator is in scope.

**Acceptance:** `strata stats -d ../data` shows ≥4 composites; each question
resolves via concept-hit with `--no-fallback --no-live` (pure registry, no LLM),
returning a scenario tree with attached primitives; all records `strata validate`
clean.

## 6. Workstream W3 — shadcn interactive charts

**Scope:** charts + targeted polish (per user decision). Keep the bespoke shell.

- **W3.1** Initialise shadcn in `web/` for Tailwind 4 / React 19 / Next 16
  (canary-compatible CLI). Generate `components.json`; add only the primitives
  we use: `chart`, `card`, `tabs`, `tooltip`, `badge`. shadcn charts are thin
  recharts wrappers, so they compose with the existing recharts dep — low risk.
  Confirm tooling fits the bun/biome toolchain before generating (CLAUDE.md
  tooling caution).
- **W3.2** Refactor the four hand-rolled chart components into shadcn
  `ChartContainer` + `ChartConfig`, preserving props/tests:
  - `TamTrajectoryChart.tsx` → **Area/Line** (scenario tree over time)
  - `ScenarioBarChart.tsx` → **Bar** (low/base/high scenarios)
  - `WaterfallChart.tsx` → **Bar** (primitive contributions)
  - `ScenarioGraph.tsx` → **Bar/Line** (consolidate or keep ReactFlow if it is
    truly a graph, not a chart — decide in plan)
  - `PyramidGraph.tsx` / `LineageGraph.tsx` → **unchanged** (ReactFlow; not charts)
- **W3.3** Wire charts into the result surfaces so they render on **every** query:
  `ResolveView` (after `result` SSE), `BuildWorkspace`, `TamDetailView`. Charts
  read the live `scenarios[]` / `primitives_used[]` payload — no mock arrays.
- **W3.4** Theme: charts consume the existing CSS-variable tokens (`--accent`,
  `--fg-*`) and respond to the light/dark `ThemeToggle`.

**Acceptance:** every query result renders a live shadcn chart bound to real
payload data; light/dark both legible; `bun run check` (typecheck + biome +
knip) green.

## 7. Workstream W4 — Verification (cross-cutting)

- **W4.1** Playwright-CLI e2e (`web/e2e/`): start backend + web, drive the home
  query box with a seeded question, assert the chain-of-thought steps appear,
  assert ≥1 attached primitive is shown, assert a chart canvas/SVG renders, and
  assert the `/tam/<hash>` artifact loads. Run via the `playwright-cli` skill.
- **W4.2** ast-grep rules (new `sgconfig.yml` + `rules/`): (a) forbid
  `anthropic.Anthropic(` outside `llm.py` (guards the slug.py regression);
  (b) forbid `subprocess.run` of `claude` without an explicit `env=` kwarg.
- **W4.3** Full gate: `cd backend && uv run pytest && uv run pyright && uv run
  ruff check . && uv run ruff format --check .` + `cd web && bun run check &&
  bun run test`. All green before done.

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Prod (Railway) has no `claude` CLI → novel queries still fall back | W2 makes the 4 seeded questions resolve with **no LLM**; novel-query prod LLM = ops decision (fund key + `STRATA_LLM_BACKEND=anthropic`), documented, not blocking SP-1 |
| Nested `claude -p` from inside a Claude Code session is slow / rate-limited | Subprocess `timeout=120` already set; e2e uses seeded (LLM-free) questions for determinism; live-LLM test marked non-blocking |
| shadcn CLI incompatible with Tailwind 4 / React 19 canary | Verify before generating; fall back to hand-adding the shadcn chart component source (it is copy-in, not a runtime dep) |
| Composite loader/validator bit-rot (no record ever existed) | In scope to fix; covered by validate + stats acceptance |
| `ANTHROPIC_API_KEY` scrub breaks the `anthropic` SDK opt-in path | Scrub applies **only** in `_complete_cli`; the SDK path (`STRATA_LLM_BACKEND=anthropic`) is untouched |

## 9. Acceptance criteria (definition of done)

1. With a dead `ANTHROPIC_API_KEY` in env, `strata goal "AI coding assistants
   in the US" --stream` streams a real chain-of-thought (subscription path).
2. Each of the 4 seeded questions resolves via concept-hit with
   `--no-fallback --no-live` and returns a scenario tree + attached primitives.
3. `strata stats` shows ≥4 composites; all records validate clean.
4. Web: typing each seeded question renders CoT + primitives + a live shadcn
   chart, in both light and dark.
5. Playwright-CLI e2e (W4.1) passes.
6. ast-grep rules (W4.2) present and passing; full gate (W4.3) green.

## 10. Out of scope (tracked for later specs)

- **SP-2:** Stripe micro-payments (human Link checkout) + agentic HTTP-402
  metered `/resolve` endpoint. Planned rail: **both**.
- **SP-3:** package + publish the `strata` CLI and a flagship connector.
- Full shadcn UI migration; new connectors; semantic search.
