# Strata `goal` CLI + 7 connectors + manifest router — design

**Date:** 2026-05-27
**Author:** Arkash + Claude (Opus 4.7)
**Status:** Approved by Arkash through Q1–Q6 brainstorming on 2026-05-27.
**Target:** v0.3 (bumps from v0.1.0; v0.2 work in `[Unreleased]` lands first.)
**Ship as:** Two PRs (see §11).

---

## 1. Context

The Strata data bank now has 15 connectors, 30 concepts, 350+ primitives, and
a stateless `POST /resolve` HTTP+SSE endpoint that resolves free-form TAM
queries via Claude (parse) → Exa (search) → Claude (extract) → evaluator
(multiply). There is no equivalent on the CLI — `strata size <slug>` requires
a pre-built concept, and `/resolve` is HTTP-only.

The user's stated goal: "we need to fetch data from our databases, update the
CLI so that we can ask it TAM questions and it can give accurate results."
Frontend quality is poor; the CLI needs to become the practical primary
surface.

In parallel, the user wants 7 additional connectors added — Alpha Vantage,
Nasdaq Data Link, yfinance, Reddit, GitHub, Stack Exchange, Twitter/X. Several
of these have known economic or source-tier issues (see §4) that are
acknowledged and proceeding anyway per Q1.

## 2. Goals (non-)

**In scope**

1. Add 7 new connectors following the existing 6-layer pattern.
2. Add a `capabilities()` classmethod to all 22 connectors (15 existing + 7
   new) returning a typed manifest of methods that can be safely invoked from
   a query-time router.
3. New `backend/src/strata/router.py` module: takes a free-form query plus
   the union of all connector manifests, asks Claude which connector +
   method to call, returns a typed routing decision (or "none").
4. Refactor `backend/src/strata/api/routes/resolve.py` to split the Claude
   parse / Exa search / Claude extract helpers into a reusable module under
   `backend/src/strata/resolver/` so both `/resolve` (HTTP) and `strata goal`
   (CLI) share them with zero duplication.
5. New `strata goal "<TAM query>"` CLI subcommand implementing hybrid
   retrieval (Q2 option C):

   ```
   1. concept match  → registry.concept(slug) → evaluator.size_concept → done
   2. primitive match → registry.primitive(slug) → return primitive
   3. connector match → router → connector.method(args) → write primitive
                                                       → registry → evaluate
   4. fallback        → resolver (Claude parse + Exa) → ephemeral result
                                                     → banner
   ```

   Three output modes: compact default, `--stream` chain-of-thought,
   `--json` for piping. Mutually exclusive.
6. Persistence per Q4: step 3 results write atomic-primitive YAML records;
   step 4 results are ephemeral.

**Out of scope (deferred or excluded)**

- Frontend changes (the frontend is acknowledged-poor; CLI is the priority).
- Postgres write-path for connectors (still YAML-first per Q27 of the
  data-layer brainstorm; v0.4+).
- TAM artifact persistence under `data/tam_outputs/` (v0.4 per roadmap).
- Concept seeding to grow registry coverage (separate workstream).
- Embedding-based semantic search of the registry (v1.0).
- New frameworks. The existing 5 with 30 variants are enough for v0.3.
- Updates to the evaluator (works as-is).

## 3. Architecture

```
                    strata goal "<query>"
                              │
                              ▼
              ┌───────────────────────────────┐
              │  cli.goal_command             │
              │  (backend/src/strata/cli.py)  │
              └──────────────┬────────────────┘
                             │ query
                             ▼
              ┌───────────────────────────────┐
              │  resolver.pipeline(query)     │
              │  (NEW module)                 │
              └──────────────┬────────────────┘
                             │
        ┌────────────────────┼────────────────────────┐
        │ step 1: concept    │ step 3: connector live │ step 4: fallback
        ▼                    ▼                        ▼
  registry.concept    router.choose(manifests)   resolver.parse_and_search
        │                    │                        │ (Claude + Exa)
        │                    ▼                        │
        │           connector.method(args)            │
        │                    │                        │
        │                    ▼                        │
        │           writer.upsert_primitive           │
        │                    │                        │
        ▼                    ▼                        ▼
  evaluator.size_concept(registry, slug) → TAMOutput
                             │
                             ▼
              renderer.compact | --stream | --json
```

### File layout (added/changed)

```
backend/src/strata/
├── connectors/
│   ├── alpha_vantage.py     [NEW]
│   ├── nasdaq_data_link.py  [NEW]
│   ├── yfinance.py          [NEW]
│   ├── reddit.py            [NEW]
│   ├── github.py            [NEW]
│   ├── stack_exchange.py    [NEW]
│   ├── twitter.py           [NEW]
│   ├── _capability.py       [NEW] — Pydantic CapabilitySpec model
│   └── CLAUDE.md            [UPDATED]
├── resolver/                [NEW dir]
│   ├── __init__.py          — pipeline(query) → ResolverResult
│   ├── parse.py             — Claude-driven query parsing (lifted from resolve.py)
│   ├── search.py            — Exa search + Claude extract (lifted from resolve.py)
│   ├── render.py            — compact / stream / json output formatters
│   └── writer.py            — upsert primitive YAML on step-3 hits
├── router.py                [NEW] — choose(query, manifests) → RoutingDecision | None
├── cli.py                   [UPDATED] — adds `goal` subcommand
└── api/routes/resolve.py    [UPDATED] — re-routes through resolver/ helpers
```

### Why this shape

- **resolver/ as a module** prevents duplication between `/resolve` (HTTP+SSE)
  and `strata goal` (CLI). Both surface formats consume the same pipeline.
- **router.py at the top of the connectors package** is the single
  authoritative place that knows about all connectors. Adding a new connector
  later means appending one capabilities() classmethod — nothing else.
- **CapabilitySpec as a Pydantic model** means pyright + ruff catch
  manifests with missing fields, and the LLM router sees a structured spec
  rather than freeform prose.
- **writer.py is the ONLY place** that mints primitives from connector
  responses. Centralizing this means the Q20 "no LLM-projected primitives"
  rule is enforced at one chokepoint — and the rule still holds because
  step-3 values come from regulator/aggregator APIs, not LLM extraction.

## 4. New connectors — caveats and tier assignment

All 7 follow the 6-layer pattern (enums → TypedDicts → frozen dataclasses →
unified response → disk cache → client + converters) per
`backend/src/strata/connectors/CLAUDE.md`.

| # | Connector | Source tier | Caveat (carried forward) |
|---|-----------|-------------|--------------------------|
| 1 | Alpha Vantage | `aggregator` | Free tier 25 req/day. Heavy disk cache + ingest-only usage assumed; not for query-time router by default. |
| 2 | Nasdaq Data Link | `aggregator` | Free datasets only; paid datasets gated behind a `tier="premium"` flag on the client. |
| 3 | yfinance | `analyst` | Unofficial Yahoo scraper. Marked `is_fragile=True` on capability spec; router prefers EDGAR/FRED over it. |
| 4 | Reddit | `community` | OAuth via PRAW. Emits count-unit primitives (subscribers, posts/day). Not a $-denominated source. |
| 5 | GitHub | `community` | PAT auth. Count-unit primitives (stars, contributors, language usage). |
| 6 | Stack Exchange | `community` | API key optional. Count-unit primitives (questions per tag per period). |
| 7 | Twitter/X | `analyst` | Free tier is heavily restricted (500 posts/mo write, limited search). Connector ships but `capabilities()` returns mostly empty manifest until paid tier — documented in CLAUDE.md as a known limitation. |

Source tier extension required: `community` already exists per Q26/Q37. No new
tier needed. The unit type system already supports count primitives.

## 5. Capabilities manifest schema

```python
# backend/src/strata/connectors/_capability.py

from typing import Literal
from pydantic import BaseModel, Field

class CapabilityArg(BaseModel):
    name: str
    type: Literal["str", "int", "float", "bool", "date"]
    description: str             # shown to the LLM router
    example: str | None = None

class CapabilitySpec(BaseModel):
    connector: str               # connector slug, e.g. "fdic"
    method: str                  # Python method name on the client
    description: str             # one-line use-when prose for the LLM
    returns: str                 # what the primitive will look like
    args: list[CapabilityArg]
    source_tier: Literal[
        "first_party", "regulator", "aggregator", "analyst",
        "community", "onchain", "prediction_market", "community-modeled"
    ]
    is_fragile: bool = False     # router demotes fragile capabilities
    requires_paid_tier: bool = False
```

Each connector class adds:

```python
@classmethod
def capabilities(cls) -> list[CapabilitySpec]:
    return [
        CapabilitySpec(
            connector="fdic",
            method="bank_count_by_state",
            description="Count of FDIC-insured banks for a US state.",
            returns="atomic primitive, unit=count, geo=US-{state}, "
                    "tier=regulator",
            args=[CapabilityArg(name="state", type="str",
                  description="2-letter US state code", example="CA")],
            source_tier="regulator",
        ),
        # ... ~5-10 per connector
    ]
```

The router calls `_all_capabilities()` which walks every connector module
and concatenates their `capabilities()` returns.

## 6. Router design

```python
# backend/src/strata/router.py

from pydantic import BaseModel

class RoutingDecision(BaseModel):
    connector: str
    method: str
    args: dict[str, str | int | float | bool]
    confidence: float            # Claude-emitted, 0..1
    rationale: str               # one-line "why this"

def choose(query: str, manifests: list[CapabilitySpec]) -> RoutingDecision | None:
    """
    Calls Claude with a prompt that includes:
      - The query
      - All capability specs serialized as JSON
      - Instructions to return strict JSON {connector, method, args, confidence, rationale}
        or {"connector": null} for "none of these fit"

    Demotes capabilities where is_fragile=True or requires_paid_tier=True
    unless the query explicitly asks for them.

    Returns None if confidence < 0.5.
    """
```

The router is the only Claude call in step 3. The actual connector call is
deterministic Python after the router returns.

## 7. `strata goal` CLI

```
$ strata goal "US bank deposit market size 2024"

→ Step 1: no concept match
→ Step 2: no primitive match
→ Step 3: routed to fdic.total_deposits_by_year(year=2024)
          tier=regulator, confidence=0.92
→ wrote data/primitives/fdic-total-deposits-2024.yaml
→ matched concept: us-banking-deposit-base (auto-built from primitive)

  TAM   point: $19.4T
  Source: FDIC BankFind API, sha256:f9c2...
  Run with --verbose for full primitive + source.
```

### Flags

| Flag | Effect | Default |
|---|---|---|
| `--stream` | SSE-style chain-of-thought, one line per pipeline step | off |
| `--json` | Pure JSON to stdout, no pretty-print, no ANSI | off |
| `--verbose` | Compact mode but include scenario tree + all sources | off |
| `--no-live` | Skip step 3 (no connector calls at query time) | off |
| `--no-fallback` | Skip step 4 (no Claude+Exa) | off |
| `--data-dir <p>` | Override data dir (mirrors `strata size`) | `../data` |

`--stream` and `--json` are mutually exclusive. `--no-live` + `--no-fallback`
together makes `goal` equivalent to a registry-only query (useful for CI).

### Exit codes

- 0: TAM produced
- 1: no result (all steps failed)
- 2: invalid query / arg error
- 3: API failure during step 3 (router chose a connector that errored)

## 8. Persistence policy (Q4 decision)

- **Step 3 hits write primitives.** New atomic primitive YAML file under
  `data/primitives/`. Slug derived from `{connector}-{method}-{args-hash}`.
  Source snapshot sha256-pinned (the connector's existing converter pattern).
- **Step 4 fallbacks are ephemeral.** Result printed to terminal, never
  written. Banner: "synthesized via /resolve fallback — not in data bank,
  do not cite without manual verification."
- **No TAM artifact persistence.** Deferred to v0.4 per roadmap.

## 9. /resolve refactor

The current `backend/src/strata/api/routes/resolve.py` (314 lines) holds the
Claude parse + Exa search + Claude extract logic inline. Extract into:

- `resolver/parse.py` — `parse_query(query: str) -> ParsedQuery`
- `resolver/search.py` — `search_primitive(spec: PrimitiveSpec) -> PrimitiveHit | None`
- `resolver/pipeline.py` — `run(query, *, allow_live, allow_fallback) -> ResolverResult`

`resolve.py` becomes ~80 lines of SSE plumbing that calls into `resolver/`.

This refactor is mechanical and behavior-preserving. The 7 existing
`/resolve` tests in `test_resolve_sse.py` continue to pass with no test
changes — they validate behavior, not internal structure.

## 10. Testing

### New tests

| File | Coverage |
|---|---|
| `tests/test_capability_manifest.py` | Every connector's `capabilities()` returns a non-empty list of valid CapabilitySpec. Catches missing methods, type mismatches. |
| `tests/test_router.py` | Mocked Anthropic client. 12 golden queries → expected RoutingDecision. Tests demotion of fragile/paid capabilities. |
| `tests/test_goal_cli.py` | Typer CliRunner. Tests all 4 retrieval steps with mocked router + mocked Claude. Tests `--stream`, `--json`, `--no-live`, `--no-fallback`. Tests exit codes. |
| `tests/connectors/test_<new>.py` × 7 | Smoke + cache + converter tests for each new connector. Mirrors existing connector test files. |

### Live smoke

`strata test-connectors` extended to cover the 7 new connectors. Skipped if
API key env var unset.

### Verification (pre-PR)

```
cd backend
uv run pytest -q
uv run pyright
uv run ruff check .
uv run ruff format --check .
uv run strata test-connectors   # if API keys are set
```

All four must pass before either PR merges. Pyright strict mode is mandatory.

## 11. PR sequencing

### PR-A: connectors + capabilities manifests (~7,500 LOC)

**Branch:** `ArkashJ/connectors-batch-3`
**Includes:**
- 7 new connector files
- `_capability.py` schema
- `capabilities()` classmethod on all 22 connectors (15 existing + 7 new)
- Tests for new connectors + manifest validity
- `connectors/CLAUDE.md` update
- 7 env-var entries in `.env.example` for new API keys

**No behavior change to `/resolve` or any existing CLI command.** Pure
additions.

**Acceptance:** all tests + pyright + ruff clean; `strata test-connectors`
passes on a workstation with all keys set; `strata stats` counts include
the new connectors but no new primitives yet (connector code shipped, no
ingest run yet).

### PR-B: router + resolver refactor + `strata goal` (~1,900 LOC)

**Branch:** `ArkashJ/goal-cli` (off the same base as PR-A; merges after)
**Includes:**
- `resolver/` module (extract from `resolve.py`)
- `router.py`
- `cli.py`: new `goal` subcommand
- Router + CLI tests
- `CHANGELOG.md` update under `[Unreleased]`
- `docs/13-strata-goal-cli.md` user-facing howto (new file)
- `CLAUDE.md` update: add `strata goal` to the CLI section

**Acceptance:** as above plus three manual `strata goal` queries land
correct TAMs end-to-end:

1. Registry hit: `strata goal "P&C insurance doc-gen TAM"` → us-pc-doc-gen
2. Live connector: `strata goal "FDIC bank count California 2024"` → step 3
3. Fallback: `strata goal "global hyperscale GPU capex 2027"` → step 4 with
   ephemeral banner

## 12. Risks

| Risk | Mitigation |
|---|---|
| Claude router picks wrong connector → bad TAM | Confidence threshold 0.5; `--verbose` prints rationale; `--no-live` opt-out for CI |
| Step-3 primitive proliferation pollutes data bank | Slug includes args hash; idempotent upsert; primitives tagged with `source_tier` matching the connector tier; routine cleanup queryable |
| Twitter/X / Alpha Vantage rate limits brick the test suite | Tests are fully mocked; `test-connectors` skips when keys unset; live smoke is opt-in |
| /resolve refactor breaks SSE clients | Mechanical extract, no behavior change; existing 7 SSE tests gate the refactor |
| yfinance breaks because Yahoo changed something | `is_fragile=True`; router demotes; documented in CLAUDE.md |
| Large diff in PR-A | Each connector reviewable in isolation; manifests are uniform; tests are uniform |

## 13. Open questions (none blocking)

- Should `strata goal` also expose the scenario tree in JSON mode? **Decided
  yes** — `--json --verbose` returns the full TAMOutput.
- Where do `.env.example` entries live? **Existing file at repo root** —
  append the 7 new vars; document in CLAUDE.md.
- Naming of step-3 auto-primitives: **`{connector}-{method-slug}-{args-hash}`**
  e.g. `fdic-bank-count-by-state-ca-2024-abc123`.

## 14. Out-of-band decisions captured during Q1–Q6

- Q1 (connector scope): user picked **all 7** despite my pushback on
  duplicates/fragile/economically-broken cases. Caveats recorded in §4.
- Q2 (retrieval strategy): **Hybrid C** — concept → primitive → connector → resolver.
- Q3 (routing): **Manifest + LLM router (D)** — single Claude call with all
  manifests as context.
- Q4 (persistence): **Step-3 primitives persist; step-4 fallbacks ephemeral.**
- Q5 (output): **Compact default + `--stream` + `--json`**.
- Q6 (PR sequencing): **Two PRs** as defined in §11.
- Mid-flight: command name is **`strata goal`** (user request, not `ask`).
