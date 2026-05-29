# SP-1 — Real, Visual TAM Answers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a live TAM query stream a real, sourced chain-of-thought with attached primitives and render it in modern shadcn charts — fixing the "feels mock" root cause and deepening the registry so it works with or without a live LLM.

**Architecture:** Two surgical resolver fixes (subscription-auth env scrub + route slug through the LLM abstraction), a data-authoring pass adding 4 connector-sourced worked TAM questions each with a same-unit composite, a shadcn chart layer swap for the 4 hand-rolled recharts components, and Playwright + ast-grep verification. No new services.

**Tech Stack:** Python 3.12 / Pydantic v2 / FastAPI / Typer (backend); Next 16 / React 19 / TanStack Query / Zod / Tailwind 4 / shadcn / recharts (web); Playwright + ast-grep (verify).

**Spec:** [`../specs/2026-05-28-sp1-real-visual-tam-answers-design.md`](../specs/2026-05-28-sp1-real-visual-tam-answers-design.md)

---

## File map

| File | Action | Responsibility |
|---|---|---|
| `backend/src/strata/resolver/llm.py` | modify | scrub `ANTHROPIC_API_KEY` from `claude -p` subprocess env |
| `backend/src/strata/resolver/slug.py` | modify | route `resolve_slug` through `llm.complete()` |
| `backend/tests/resolver/test_llm_env.py` | create | env-scrub + slug-routing unit tests |
| `backend/src/strata/api/routes/healthz.py` | modify | add `GET /healthz/llm` backend probe |
| `data/composites/*.yaml` | create (4) | same-unit set-op primitives (1 per question) |
| `data/primitives/*.yaml` | create (~10) | connector-sourced atomics the composites union |
| `data/concepts/*.yaml` | create (4) | the 4 worked TAM questions |
| `data/frameworks/*.yaml` | modify | attach new concept slugs to existing L1/L2/L4/L6 variants |
| `web/components.json` + `web/src/components/ui/chart.tsx` etc. | create | shadcn init + chart/card/tabs/tooltip/badge primitives |
| `web/src/components/{WaterfallChart,ScenarioBarChart,ScenarioGraph}.tsx`, `web/src/components/tam/TamTrajectoryChart.tsx` | modify | refactor onto shadcn `ChartContainer` |
| `web/e2e/sp1-real-tam.spec.ts` | create | full-path e2e (query → CoT → primitives → chart) |
| `sgconfig.yml` + `rules/*.yml` | create | ast-grep guards for the two resolver invariants |

---

## Workstream W1 — Resolver hardening

### Task 1: Scrub `ANTHROPIC_API_KEY` from the `claude -p` subprocess

**Files:**
- Modify: `backend/src/strata/resolver/llm.py` (`_complete_cli`)
- Test: `backend/tests/resolver/test_llm_env.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/resolver/test_llm_env.py
from unittest.mock import patch, MagicMock
import json
from strata.resolver import llm


def test_complete_cli_scrubs_anthropic_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-dead")
    captured = {}

    def fake_run(args, **kwargs):
        captured["env"] = kwargs.get("env")
        return MagicMock(returncode=0, stdout=json.dumps({"result": "ok"}), stderr="")

    with patch.object(llm.subprocess, "run", side_effect=fake_run):
        out = llm._complete_cli("hi", system=None, model="claude-sonnet-4-6")

    assert out == "ok"
    assert captured["env"] is not None, "must pass an explicit env"
    assert "ANTHROPIC_API_KEY" not in captured["env"], "dead key must be scrubbed"
```

- [ ] **Step 2: Run test, verify it fails**

Run: `cd backend && uv run pytest tests/resolver/test_llm_env.py::test_complete_cli_scrubs_anthropic_api_key -v`
Expected: FAIL (env is `None` / key present).

- [ ] **Step 3: Implement the scrub**

In `_complete_cli`, before `subprocess.run`, build a clean env and pass it:

```python
    # The claude CLI authenticates via the Claude Code subscription ONLY when
    # the API-key env vars are absent; an inherited (and here, dead) key forces
    # API billing. Scrub them so headless completion uses the subscription.
    child_env = {k: v for k, v in os.environ.items()
                 if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}
    proc = subprocess.run(
        args, capture_output=True, text=True, timeout=120,
        stdin=subprocess.DEVNULL, env=child_env,
    )
```

- [ ] **Step 4: Run test, verify it passes**

Run: `cd backend && uv run pytest tests/resolver/test_llm_env.py -v` → PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/strata/resolver/llm.py backend/tests/resolver/test_llm_env.py
git commit -m "fix(resolver): scrub ANTHROPIC_API_KEY so claude CLI uses subscription auth"
```

### Task 2: Route `resolve_slug` through `llm.complete()`

**Files:**
- Modify: `backend/src/strata/resolver/slug.py`
- Test: `backend/tests/resolver/test_llm_env.py` (add a case)

- [ ] **Step 1: Write the failing test** — assert `resolve_slug` calls `llm.complete`, not the SDK.

```python
def test_resolve_slug_uses_llm_complete():
    from strata.resolver import slug
    from strata.resolver.slug import ConceptSummary
    payload = '{"intent":"novel","concept_slug":null,"primitive_slugs":[],"framework_hint":null,"confidence":0.0}'
    with patch.object(slug._llm, "complete", return_value=payload) as m:
        out = slug.resolve_slug("q", known_concepts=[], known_primitives=[])
    m.assert_called_once()
    assert out.intent.value == "novel"
```

- [ ] **Step 2: Run, verify it fails** (slug has no `_llm`; calls SDK).

- [ ] **Step 3: Implement** — replace the `client.messages.create(...)` block in `resolve_slug` with:

```python
from . import llm as _llm  # top of file; drop the get_anthropic_client + TextBlock imports

    # registry index goes in the system prompt so it benefits from prompt caching
    raw_text = _llm.complete(instruction, system=registry_block, model=model, max_tokens=512)
    raw: dict[str, Any] = json.loads(_strip_code_fence(raw_text))
    return ResolvedQuery.model_validate(raw)
```

Note: `llm.complete`'s CLI path passes `system` via `--append-system-prompt`; the SDK path passes it as `system=`. Prompt-cache `cache_control` only applied on the SDK path — acceptable (correctness over cache hit).

- [ ] **Step 4: Run** `cd backend && uv run pytest tests/resolver/ -v` → PASS
- [ ] **Step 5: Commit** `fix(resolver): slug resolver goes through llm.complete (respects backend switch + env scrub)`

### Task 3: `GET /healthz/llm` backend probe

**Files:** Modify `backend/src/strata/api/routes/healthz.py`; test `backend/tests/api/test_healthz_llm.py`.

- [ ] **Step 1:** Test that `GET /healthz/llm` returns `{"backend": "...", "ok": <bool>}` and never leaks secrets or raises.
- [ ] **Step 2:** Run → fail (404).
- [ ] **Step 3:** Add a route that reports the selected backend (`anthropic` if `STRATA_LLM_BACKEND=anthropic` else `claude-cli`) and a cheap reachability check (CLI: `shutil.which("claude") is not None`; SDK: key present). No live completion call.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(api): /healthz/llm reports resolver backend availability`.

### Task 4: Manual end-to-end smoke (subscription path)

- [ ] With a dead `ANTHROPIC_API_KEY` exported, run `cd backend && uv run strata goal "AI coding assistants in the US" --data-dir ../data --stream`. Expected: streams `slug_resolved`/`parsing`/.../`result` — NOT "credit balance too low". Capture output to the spec's acceptance log.

---

## Workstream W2 — Data depth (4 worked TAM questions)

> Before authoring: read `backend/src/strata/models/primitive.py` end-to-end to confirm the full `CompositePrimitive` field set (`inputs`, `set_operation`, `tag_filter`, `unit`, `geo`, `geo_perspective`, plus any `source`/value fields below `geo_perspective`) and `backend/src/strata/validator/` rules. Composites are **same-unit set ops only** — every `inputs` member must share the composite's `unit` (Q3). All atomics need a `source` with `snapshot_sha256`; compute it from the pulled connector payload (`strata` ingest writes pins) — never invent.

### Task 5: Confirm composite path loads (regression guard before authoring 4)

**Files:** create one throwaway `data/composites/_smoke-union.yaml` + atomics; test via `strata stats`/`strata validate`.

- [ ] **Step 1:** Author a minimal composite (`set_operation: union`) over 2 existing same-unit `persons` atomics (e.g. two BLS headcount primitives already in `data/primitives/`), `concept_slug` pointing at an existing concept.
- [ ] **Step 2:** Run `cd backend && uv run strata validate -d ../data` and `uv run strata stats -d ../data`. Expected: composite count = 1, validates clean. If the loader/validator chokes (never had a real composite), fix it here (in scope).
- [ ] **Step 3:** Delete the smoke file once green. Commit any loader/validator fix separately: `fix(loader): composite_primitive path handles real records`.

### Tasks 6–9: Author the four questions (one task each)

For **each** question below: (a) pull the atomic values via the named connector method (`uv run strata` connector call or the connector client), (b) write atomics to `data/primitives/<slug>.yaml` using the atomic template, (c) write the composite to `data/composites/<slug>.yaml` (same `unit` as members), (d) write the concept to `data/concepts/<slug>.yaml` listing the composite + multipliers in `measurements`, (e) add a `variant` to the existing framework attaching the new concept slug, (f) `uv run strata validate -d ../data` clean, (g) `uv run strata goal "<question>" --no-fallback --no-live -d ../data` resolves via concept-hit with a scenario tree + attached primitives, (h) commit.

| Task | Concept slug | Lens / framework | Composite (set_operation) — unit | Atomics (connector) |
|---|---|---|---|---|
| 6 | `ai-legal-assistants-us` | L1 cost_efficiency / `bottoms-up-cost-efficiency` | `us-legal-professionals` (union) — persons | BLS OES 23-1011 lawyers; 23-2011 paralegals; seat $/yr (community-modeled, ranged) |
| 7 | `ai-coding-assistants-us` | L6 productivity_uplift | `us-software-engineers` (union) — persons | BLS OES 15-1252 devs; 15-1253 QA testers; 15-1244 sysadmins; value-split % (modeled, ranged) |
| 8 | `embedded-payments-vertical-saas-us` | L2 revenue_generation | `us-smb-card-volume` (union or restrict) — USD/yr | Census CBP SMB counts; FRED card-volume series; take-rate % (modeled, ranged) |
| 9 | `us-instant-payments-rails` | L4 platform_throughput | `us-realtime-payment-volume` (union of RTP ∪ FedNow) — USD/yr | FRED/clearing-house RTP value; FedNow value; FDIC institution count; take-rate % (modeled) |

**Atomic YAML template** (fill per pull; no invented numbers):

```yaml
kind: atomic_primitive
slug: bls-lawyers-headcount-2024
schema_version: 1
concept_slug: ai-legal-assistants-us
name: US employed lawyers (BLS OES 23-1011)
description: Total US employment for SOC 23-1011 (Lawyers), BLS OES May 2024.
value: <PULLED>            # from connector — do not invent
unit: { kind: stock, dimension: people }
as_of: '2024-05-01'
geo: { level: country, codes: [USA] }
geo_perspective: supply
distribution_shape: normal
source:
  slug: bls-oes-23-1011-2024
  tier: regulator
  url: https://www.bls.gov/oes/current/oes231011.htm
  accessed: '2026-05-28'
  snapshot_sha256: <COMPUTED FROM PULL>
```

**Composite YAML template** (members must share `unit`):

```yaml
kind: composite_primitive
slug: us-legal-professionals
schema_version: 1
concept_slug: ai-legal-assistants-us
name: US legal professionals (lawyers ∪ paralegals)
description: Union of US employed lawyers and paralegals — the addressable persona pool for AI legal assistants.
inputs: [bls-lawyers-headcount-2024, bls-paralegals-headcount-2024]
set_operation: union
as_of: '2024-05-01'
unit: { kind: stock, dimension: people }
geo: { level: country, codes: [USA] }
geo_perspective: supply
```

- [ ] Task 6 · Task 7 · Task 8 · Task 9 — each its own commit: `feat(data): <concept-slug> TAM (composite + connector-sourced primitives)`.

### Task 10: Registry-deep acceptance

- [ ] Run `uv run strata stats -d ../data` → composites ≥ 4. Run each of the 4 questions with `--no-fallback --no-live`; confirm concept-hit + scenario tree + primitives, no LLM used. Commit acceptance log to spec.

---

## Workstream W3 — shadcn interactive charts

> Before init: read the 4 chart components in full to preserve their props/tests. shadcn charts are recharts wrappers, so the existing `recharts` dep is reused. Verify shadcn CLI supports Tailwind 4 / React 19 (canary) before generating; if not, copy the chart component source by hand (it is copy-in, not a runtime dep) — confirm tooling with the user only if a new runtime dep would be added (CLAUDE.md tooling caution).

### Task 11: Initialise shadcn + add primitives

**Files:** create `web/components.json`, `web/src/components/ui/{chart,card,tabs,tooltip,badge}.tsx`, `web/src/lib/utils.ts` (cn helper).

- [ ] **Step 1:** `cd web && bunx shadcn@latest init` (style: new-york; base color: per existing tokens; CSS vars: yes). Then `bunx shadcn@latest add chart card tabs tooltip badge`.
- [ ] **Step 2:** Map shadcn token vars to the existing `--accent`/`--fg-*`/`--bg-*` tokens in `globals.css` so charts theme correctly in light/dark.
- [ ] **Step 3:** `bun run typecheck` clean; `bun run lint:biome` clean (add generated `ui/*` to biome ignore only if it fights generated style).
- [ ] **Step 4:** Commit `chore(web): init shadcn + chart/card/tabs/tooltip/badge primitives`.

### Tasks 12–15: Refactor each chart onto `ChartContainer` (one task each)

For each: keep the exported component name + props identical (so callers + vitest pass), swap the internal recharts JSX for shadcn `ChartContainer` + `ChartConfig` + `ChartTooltip`, bind to live props (no mock arrays), verify `bun run test` for that component's test stays green, commit.

- [ ] **Task 12:** `tam/TamTrajectoryChart.tsx` → Area/Line (trajectory points).
- [ ] **Task 13:** `ScenarioBarChart.tsx` → Bar (low/base/high scenarios).
- [ ] **Task 14:** `WaterfallChart.tsx` → Bar (primitive contributions; stacked offset for waterfall).
- [ ] **Task 15:** `ScenarioGraph.tsx` → Bar/Line (decide vs keep ReactFlow after reading; if it is a true node graph, leave it and note so).

### Task 16: Render charts on every query result

**Files:** modify `web/src/components/ResolveView.tsx`, `web/src/components/build/BuildWorkspace.tsx`, `web/src/components/tam/TamDetailView.tsx`.

- [ ] **Step 1:** After the `result` SSE envelope, feed `scenarios[]` / `primitives_used[]` into `ScenarioBarChart` + `WaterfallChart` in `ResolveView`. Confirm `BuildWorkspace`/`TamDetailView` already pass live data (they consume `TAMOutput`).
- [ ] **Step 2:** `bun run check` + `bun run test` green.
- [ ] **Step 3:** Commit `feat(web): render shadcn charts on live resolve/build/tam results`.

---

## Workstream W4 — Verification (cross-cutting)

### Task 17: ast-grep guard rules

**Files:** create `sgconfig.yml`, `rules/no-direct-anthropic-outside-llm.yml`, `rules/claude-subprocess-needs-env.yml`.

- [ ] **Step 1:** Rule A — pattern `anthropic.Anthropic($$$)` flagged everywhere except `resolver/llm.py` (guards Task 2 regression). Rule B — flag `subprocess.run` invoking `claude` without an `env=` kwarg (guards Task 1).
- [ ] **Step 2:** Run `ast-grep scan` → both rules pass on the fixed tree.
- [ ] **Step 3:** Commit `chore(lint): ast-grep rules guarding resolver LLM invariants`.

### Task 18: Playwright e2e — full path

**Files:** create `web/e2e/sp1-real-tam.spec.ts`. Use the `playwright-cli` skill to author/run.

- [ ] **Step 1:** Spec: navigate `/`, type a **seeded** question (e.g. "AI coding assistants in the US"), submit. Assert the chain-of-thought steps render (parsing → searching → evaluating → result), assert ≥1 attached primitive name is visible, assert a chart `<svg>`/canvas is present, navigate to the minted `/tam/<hash>` and assert it loads. (Seeded question = deterministic, no live LLM needed.)
- [ ] **Step 2:** Run `cd web && bun run test:e2e sp1-real-tam.spec.ts` (webServer auto-boots backend+web per `playwright.config.ts`). Expected: PASS.
- [ ] **Step 3:** Commit `test(e2e): SP-1 full-path real-TAM render`.

### Task 19: Full gate + done

- [ ] `cd backend && uv run pytest && uv run pyright && uv run ruff check . && uv run ruff format --check .` → all green.
- [ ] `cd web && bun run check && bun run test` → green.
- [ ] `ast-grep scan` → green.
- [ ] Update `CHANGELOG.md` `[Unreleased]`. Open PR (do not merge without user sign-off).

---

## Self-review

- **Spec coverage:** G1→Tasks 1–4; G2→Tasks 5–10; G3→Tasks 11–16; G4→Task 18; G5→Tasks 17,19. All goals covered.
- **Placeholders:** `<PULLED>` / `<COMPUTED FROM PULL>` are data-acquisition steps (values come from connector pulls at execution, never invented) — intentional, not placeholders.
- **Type consistency:** `_complete_cli(prompt, system, model)` signature unchanged; `llm.complete(instruction, system=, model=, max_tokens=)` matches its definition; `CompositePrimitive` fields match the model (`inputs`, `set_operation`, `unit`, `geo`, `geo_perspective`).
- **Open confirmations (resolved at execution):** full `CompositePrimitive` tail fields; whether `ScenarioGraph` is a chart or a graph; shadcn CLI vs hand-copy for Tailwind 4.
