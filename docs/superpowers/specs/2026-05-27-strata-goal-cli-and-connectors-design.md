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
   retrieval (Q2 option C). The pipeline opens with a single **slug
   resolver** call (§3.5) that maps the free-form query to known registry
   slugs OR declares the query novel — then dispatches:

   ```
   pre. slug resolver  → Claude one-shot → {concept_slug?,
                                            primitive_slugs?,
                                            framework_hint?, intent}
         output cached for the rest of the pipeline (parse step of /resolve
         reuses it; never called twice in one invocation)

   1.   concept match  → resolved.concept_slug → registry.concept →
                         evaluator.size_concept → TAMOutput → done

   2.   primitive match → resolved.primitive_slugs → registry.primitive[] →
                          • single primitive  → return value with banner
                                                "single primitive, not a TAM"
                          • multi-primitive   → if framework_hint matches,
                                                run it; else fall to step 3
                          • none              → step 3

   3.   connector live → for each missing input declared by the
                         framework_hint's input list:
                           router.choose(query_about_that_slot, manifests)
                           → connector.method(args) → writer.upsert_primitive
                         capped at `--expansion-budget` (default 6 connector
                         calls per `goal` invocation)
                         → registry → evaluator → TAMOutput

   4.   fallback       → resolver.parse_and_search (Claude+Exa, full
                         /resolve flow) → ephemeral result → banner
                         "synthesized via fallback — not in data bank"
   ```

   Three output modes: compact default, `--stream` chain-of-thought,
   `--json` for piping. Mutually exclusive.
6. Persistence (Q4 + audit fix D): step-3 connector hits write primitive
   YAML to **`~/.strata/auto-primitives/`** (user home, gitignored),
   NOT to the committed `data/primitives/` tree. New `strata promote
   <slug>` subcommand moves a curated auto-primitive into
   `data/primitives/` for human-reviewed inclusion. Step-4 fallbacks
   remain ephemeral.

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
                             ▼
              ┌───────────────────────────────┐
              │  resolver.slug.resolve_slug   │  ← Claude one-shot
              │  → ResolvedQuery              │     (audit fix A+B)
              └──────────────┬────────────────┘  carried through pipeline
                             │
   ┌──────────────┬──────────┴──────────┬─────────────────────┐
   │ step 1       │ step 2              │ step 3              │ step 4
   │ concept      │ primitive(s)        │ connector live      │ fallback
   ▼              ▼                     ▼                     ▼
registry        registry         router.choose      resolver.parse
.concept        .primitive[]     (manifests,         _and_search
   │              │              cached prompt)     (reuses ResolvedQuery)
   │              │                     │                     │
   │              │                     ▼                     │
   │              │            connector.method(args)         │
   │              │                     │                     │
   │              │                     ▼                     │
   │              │            writer.upsert_primitive        │
   │              │            ~/.strata/auto-primitives/     │
   │              │                     │                     │
   ▼              ▼                     ▼                     ▼
evaluator     primitive          evaluator             ephemeral
.size_concept  value             .size_concept          TAMOutput
   │           (banner)               │                  + banner
   │              │                    │                     │
   └──────────────┴────────────┬───────┴─────────────────────┘
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
│   ├── slug.py              — slug-resolution call (§3.5)
│   ├── parse.py             — Claude-driven query parsing (lifted from resolve.py)
│   ├── search.py            — Exa search + Claude extract (lifted from resolve.py)
│   ├── render.py            — compact / stream / json output formatters
│   └── writer.py            — upsert primitive YAML to ~/.strata/auto-primitives/
├── router.py                [NEW] — choose(query, manifests) → RoutingDecision | None
├── cli.py                   [UPDATED] — adds `goal` + `promote` subcommands
└── api/routes/resolve.py    [UPDATED] — re-routes through resolver/ helpers
```

### 3.5 Slug resolution (audit fix A + B)

The pipeline cannot start with `registry.concept(slug)` because the user's
query is free-form, not a slug. Before any retrieval step runs, a single
Claude call maps the query to known registry slugs:

```python
# backend/src/strata/resolver/slug.py

class ResolvedQuery(BaseModel):
    intent: Literal["concept", "primitive", "novel"]
    concept_slug: str | None         # set when intent == "concept"
    primitive_slugs: list[str]       # 0..N matched primitives
    framework_hint: str | None       # e.g. "cost_efficiency"
    confidence: float

def resolve_slug(
    query: str,
    *,
    known_concepts: list[ConceptSummary],
    known_primitives: list[PrimitiveSummary],
) -> ResolvedQuery: ...
```

- Prompt includes the **concept index** (30 entries) and **primitive
  index** (350+ entries) as `[{slug, name, one_line_description}]`.
  ~5K input tokens. Sent with `cache_control: ephemeral` on the
  registry-index block so the 5-min Anthropic prompt cache kicks in for
  back-to-back queries.
- If `confidence < 0.5` OR `intent == "novel"`, step 1 and step 2 are
  skipped and the pipeline goes straight to step 3 (with framework_hint
  if any) and then step 4.
- The `ResolvedQuery` is **carried** through the pipeline. When step 4
  fallback fires, its parse step REUSES the existing resolution; we
  never run two Claude parses for one `goal` invocation.

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
| 7 | Twitter/X | `analyst` | Free tier ships with the 2 endpoints that actually work without payment: `user_lookup_by_username` (follower count, public profile) and `user_timeline` (rate-limited but free). Search and tweet-volume endpoints are NOT included; capability spec for those declares `requires_paid_tier=True` so the router never picks them on a free-tier key. (Audit fix F — no dead-code stub.) |

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

### 6.1 Prompt caching (audit fix E)

The router prompt is dominated by the static manifest payload. 22 connectors
× ~8 methods each × ~120 tokens per CapabilitySpec ≈ **21 K input tokens**
per router call. To avoid paying that on every `goal` invocation:

- Serialize all manifests into a single immutable system block.
- Send with Anthropic `cache_control: {"type": "ephemeral"}` so the 5-min
  prompt cache kicks in.
- Cache key is the manifest block content; rotates automatically when any
  connector's `capabilities()` changes.
- Expected outcome: first router call in a session pays full price
  (~$0.06 input on Sonnet 4); subsequent calls in the same 5-min window
  pay ~10% of that. Documented in §12 risks.

## 7. `strata goal` CLI

```
$ strata goal "US bank deposit market size 2024"

→ Slug resolver: intent=novel, framework_hint=platform_throughput
→ Step 1: skipped (no concept)
→ Step 2: skipped (no primitive)
→ Step 3: framework platform_throughput needs {bank_count, avg_deposits}
          [1/2] router → fdic.bank_count_total(year=2024) tier=regulator
                conf=0.94 → wrote ~/.strata/auto-primitives/fdic-bank-
                count-us-2024.yaml
          [2/2] router → fdic.total_deposits_by_year(year=2024)
                tier=regulator conf=0.92 → wrote ~/.strata/auto-
                primitives/fdic-total-deposits-us-2024.yaml
→ evaluator: 2 inputs · 1 scenario path

  TAM   point: $19.4T
  Inputs:
    • fdic-bank-count-us-2024         4,577     FDIC BankFind 2024-12
    • fdic-total-deposits-us-2024     $19.4T    FDIC BankFind 2024-12

  Two auto-primitives written to ~/.strata/auto-primitives/.
  Run `strata promote fdic-bank-count-us-2024` to move into data/primitives/.
```

### Flags

| Flag | Effect | Default |
|---|---|---|
| `--stream` | SSE-style chain-of-thought, one line per pipeline step | off |
| `--json` | Pure JSON to stdout, no pretty-print, no ANSI | off |
| `--verbose` | Include scenario tree + all sources in compact output | off |
| `--no-live` | Skip step 3 (no connector calls at query time) | off |
| `--no-fallback` | Skip step 4 (no Claude+Exa) | off |
| `--primitive-only` | Step 2 returns a single primitive without trying to compose a TAM (audit fix C) | off |
| `--expansion-budget <N>` | Max connector calls in step 3 per `goal` invocation (audit fix C) | 6 |
| `--data-dir <p>` | Override data dir (mirrors `strata size`) | `../data` |

`--stream` and `--json` are mutually exclusive. `--no-live` + `--no-fallback`
together makes `goal` equivalent to a registry-only query (useful for CI).

### Environment (audit fix K)

`STRATA_OFFLINE=1` sets `--no-live` AND `--no-fallback` by default. CI sets
this; humans don't. Explicit CLI flags override.

### Exit codes

- 0: TAM produced
- 1: no result (all steps failed or both `--no-live` + `--no-fallback`
  set with no registry match)
- 2: invalid query / arg error
- 3: API failure during step 3 (router chose a connector that errored)
- 4: expansion budget exceeded before all inputs found

### `strata promote <slug>` (companion subcommand)

Moves a YAML file from `~/.strata/auto-primitives/{slug}.yaml` to
`data/primitives/{slug}.yaml` after running the full validator pipeline
on it. Refuses promotion if the validator rejects (mirrors the v0.5
contribution-flow validator chain). Idempotent: re-running on an
already-promoted slug is a no-op.

## 8. Persistence policy (Q4 + audit fix D)

- **Step 3 hits write to `~/.strata/auto-primitives/{slug}.yaml`.**
  User home, gitignored — never the committed `data/primitives/` tree.
  Each file is a full atomic-primitive YAML record with source snapshot
  sha256-pinned (the connector's existing converter pattern). Slug is
  human-meaningful (audit fix I) — `{connector}-{semantic-stub}-{geo}-{period}`
  e.g. `fdic-bank-count-us-2024`. Dedup hash lives in metadata, not the slug.
- **`strata promote <slug>`** is the only way auto-primitives reach the
  committed tree, and it runs the full v0.5 validator chain before
  moving the file.
- **Step 4 fallbacks are ephemeral.** Result printed to terminal, never
  written. Banner: "synthesized via fallback — not in data bank, do not
  cite without manual verification."
- **No TAM artifact persistence.** Deferred to v0.4 per roadmap.
- **Registry loader change:** the in-memory Registry loads from
  `data/` only (unchanged). `goal` augments the in-memory Registry with
  auto-primitives loaded from `~/.strata/auto-primitives/` at startup,
  flagged `is_auto=True` so callers can filter them out if they only
  trust the committed tree.

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

### 9.1 SSE event-name contract (audit fix H)

`/resolve` emits these SSE events today. The refactor MUST preserve the
exact event names and payload shapes; the resolver/ module is the new
implementation, but the wire format is frozen:

| Event | Payload shape | When emitted |
|---|---|---|
| `parsing` | `{query, model}` | Before Claude parse |
| `searching` | `{primitive_name, role}` | Per primitive search start |
| `framework_selected` | `{framework, lens}` | After parse, before evaluator |
| `evaluating` | `{inputs: [{slug, value, unit}]}` | Before multiplying |
| `result` | `{tam_usd, scenarios, sources}` | Terminal success |
| `error` | `{message, step}` | Terminal failure |

A regression test asserts the event-name set is exactly this list,
plus payload-shape pydantic validation. The refactor is rejected if
any event name changes.

## 10. Testing

### New tests

| File | Coverage |
|---|---|
| `tests/test_capability_manifest.py` | Every connector's `capabilities()` returns a non-empty list of valid CapabilitySpec. Catches missing methods, type mismatches. Asserts each declared `method` actually exists on the connector client class. |
| `tests/test_router.py` | Mocked Anthropic client. 12 golden queries → expected RoutingDecision. Tests demotion of fragile/paid capabilities. Asserts prompt-cache header is set. |
| `tests/resolver/test_slug.py` | (audit fix J) Mocked Claude. 8 queries with known concept/primitive indices. Asserts `intent`, `concept_slug`, `primitive_slugs`, `framework_hint`. Includes "novel" case. |
| `tests/resolver/test_parse.py` | (audit fix J) Pure unit test of the extracted Claude parse helper. |
| `tests/resolver/test_search.py` | (audit fix J) Mocked Exa + Claude. Tests Exa snippet → extracted-value flow. |
| `tests/resolver/test_writer.py` | (audit fix J) Tests writing to `~/.strata/auto-primitives/`, slug collision (idempotent upsert), and validator pass. |
| `tests/test_sse_event_contract.py` | (audit fix H) Asserts /resolve still emits exactly the 6 events from §9.1 with matching payload shapes. |
| `tests/test_goal_cli.py` | Typer CliRunner. Tests all 4 retrieval steps with mocked router + mocked Claude. Tests `--stream`, `--json`, `--no-live`, `--no-fallback`, `--primitive-only`, `--expansion-budget`, `STRATA_OFFLINE`. Tests exit codes. |
| `tests/test_promote_cli.py` | Typer CliRunner. Tests `strata promote` happy path, validator-rejected path, idempotency, missing-file. |
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

### PR-B: router + resolver refactor + `strata goal` + `strata promote` (~2,200 LOC)

**Branch:** `ArkashJ/goal-cli` (off the same base as PR-A; merges after)
**Includes:**
- `resolver/` module — `slug.py` (audit fix A/B), `parse.py`, `search.py`,
  `writer.py`, `pipeline.py`, `render.py`
- `router.py` with prompt-cache wiring (audit fix E)
- `cli.py`: new `goal` and `promote` subcommands
- `~/.strata/auto-primitives/` reader injected into Registry startup
  (audit fix D)
- Router + CLI tests + resolver/ unit tests (audit fix J)
- SSE event-contract regression test (audit fix H)
- `STRATA_OFFLINE` env handling (audit fix K)
- `CHANGELOG.md` update under `[Unreleased]`
- `docs/13-strata-goal-cli.md` user-facing howto (new file)
- `CLAUDE.md` update: add `strata goal` + `strata promote` to the CLI section

**Acceptance:** as above plus three manual `strata goal` queries land
correct TAMs end-to-end:

1. Registry hit: `strata goal "P&C insurance doc-gen TAM"` → us-pc-doc-gen
2. Live connector: `strata goal "FDIC bank count California 2024"` → step 3
3. Fallback: `strata goal "global hyperscale GPU capex 2027"` → step 4 with
   ephemeral banner

## 12. Risks

| Risk | Mitigation |
|---|---|
| Claude router picks wrong connector → bad TAM | Confidence threshold 0.5; `--verbose` prints rationale; `--no-live` opt-out for CI; expansion budget caps blast radius |
| Step-3 primitives pollute `data/primitives/` | (audit fix D) Writes to `~/.strata/auto-primitives/` (gitignored); `strata promote` is the only path into the committed tree, runs validator first |
| Per-query cost on `goal` (audit fix G) | Slug resolver ~5K tok cached. Router ~21K tok cached (5-min Anthropic prompt cache). Step 4 fallback hits Exa N times + Claude (parse+extract×N) ≈ $0.10–0.20 per fallback query. Documented in CLAUDE.md; `--no-fallback` flag exists |
| Prompt cache misses inflate cost when traffic is bursty | Manifest block is content-hashed cache key; warm-up cost ~$0.06 per cold start; users running `goal` >1×/5min stay hot |
| Twitter/X / Alpha Vantage rate limits brick the test suite | Tests are fully mocked; `test-connectors` skips when keys unset; live smoke is opt-in |
| /resolve refactor breaks SSE clients | (audit fix H) §9.1 freezes the event-name contract; new regression test gates the refactor |
| yfinance breaks because Yahoo changed something | `is_fragile=True`; router demotes; documented in CLAUDE.md; tests run against a recorded fixture |
| Large diff in PR-A | Each connector reviewable in isolation; manifests are uniform; tests are uniform |

## 13. Open questions (none blocking)

- Should `strata goal` also expose the scenario tree in JSON mode? **Decided
  yes** — `--json --verbose` returns the full TAMOutput.
- Where do `.env.example` entries live? **Existing file at repo root** —
  append the 7 new vars; document in CLAUDE.md.
- Naming of step-3 auto-primitives (audit fix I): **human-meaningful
  semantic slug** — `{connector}-{semantic-stub}-{geo}-{period}` e.g.
  `fdic-bank-count-us-2024`. Args hash lives in the primitive's metadata
  for dedup, NOT in the slug. If the same connector+method+args combo
  is requested twice, the upsert is idempotent (no second YAML written).

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

---

## Appendix A — Stage A primitive-seeding prompt

Self-contained brief for a fresh Claude Code session to seed the ~50 curated
primitives across the 9 already-integrated-but-unseeded connectors. Paired
with this spec so the work executes against the design.

```
# Stage A — seed primitives for 9 already-integrated connectors

## Context (Strata / VC_stuff repo)

This is Strata, an open-source market-sizing engine for VCs and operators.
Atomic primitives = single sourced numbers in YAML; frameworks combine them
into TAM. Repo root: /Users/arkashjain/Desktop/work/VC_stuff. Backend lives
in backend/ (uv + Python 3.12, pyright strict, ruff). Data lives in data/
at repo root.

Load-bearing reading before you touch anything:
  - CLAUDE.md (project conventions, schema rules, what NOT to do)
  - docs/07-data-layer-brainstorm.md (Q1–Q40 schema lock)
  - backend/src/strata/connectors/CLAUDE.md (6-layer connector pattern)
  - data/primitives/bls-software-developers-us-2024.yaml and
    data/primitives/fred-*.yaml (canonical primitive YAML shape — copy this)

## Current state

15 typed connectors exist in backend/src/strata/connectors/. Six of them
(BLS, FRED, Census, EDGAR, World Bank, Kalshi) have populated primitives in
data/primitives/. Nine others are fully wired with ~170 query methods and
167 passing tests but have ZERO primitives emitted. This task fills that gap.

API keys are already in /Users/arkashjain/Desktop/work/VC_stuff/.env. EXCEPT
STRATA_COMTRADE_API_KEY which is empty — Comtrade requires registering at
comtradeplus.un.org. If empty when Comtrade step runs, skip Comtrade and
report it at the end; don't block on it.

## Goal

Seed ~50 atomic primitive YAML files across the 9 connectors below, each
chosen to plug into at least one of Strata's 6 analysis lenses
(L1 cost_efficiency, L2 revenue_generation, L3 latent_demand,
L4 platform_throughput, L5 bundle_consolidation, L6 productivity_uplift).

Curated target distribution (do NOT exceed without justification — tighter
is better than broader):

| Connector | Count | Lens slot                                           |
|-----------|-------|-----------------------------------------------------|
| OECD      | 11    | L3 population/GDP-per-cap (38 countries); R&D, health |
| Eurostat  | 6     | L2 EU sector value-add by NACE                       |
| Comtrade  | 5     | L4 top HS-code bilateral flows (semis, EV batt, pharma) |
| FDIC      | 7     | L2 deposits/non-interest income; L5 concentration    |
| CMS       | 5     | L2 Medicare spend by category                        |
| EIA       | 4     | L2 retail electricity $/MWh × MWh consumed           |
| USDA NASS | 3     | denominators: major crop output $                    |
| FAA       | 4     | L4 airport passenger ops + cargo tonnes              |
| openFDA   | 5     | L3 drug approvals / device clearances by year        |

## Mechanics

For each connector create:

  backend/scripts/seed_<connector>_primitives.py

Each script must:
  1. Instantiate the existing client from
     backend/src/strata/connectors/<connector>.py (do NOT modify the client).
  2. Call ~5–10 typed query methods that hit the lens slots above.
  3. Use the connector's existing YAML converter functions (every connector
     already has them — search the file for `to_primitive` or
     `as_primitive_yaml`).
  4. Write files to data/primitives/<connector>-<series>-<year>.yaml using
     kebab-case slugs.
  5. Each primitive must carry: structured unit (kind/dimension/denominator/
     currency/basis as applicable), geo (ISO 3166), source with
     snapshot_sha256, source tier (regulator | aggregator), value + as-of
     date.

Run scripts from backend/ with `uv run python scripts/seed_<connector>_primitives.py`.
Data dir argument: `--data-dir ../data`.

## Schema rules (do NOT drift — these are load-bearing)

  - TAMs are scenario trees, never scalars + error bars. Primitives are single
    numbers though — that's correct.
  - Units are structured (kind, dimension, denominator, currency, basis).
  - Currency stored nominal, normalized at query time.
  - NO LLM-projected primitives. Every value comes from an actual API call.
  - NO synthetic / community-modeled primitives in this task — only
    regulator/aggregator tier.
  - Source citations must be content-hash pinned (snapshot_sha256 of the
    raw API response payload).
  - Geo uses two parallel fields at v0.3 but v0.2 still uses single `geo` +
    `geo_perspective` — match what existing bls-*/fred-* primitives do.
  - Slug naming: kebab-case, connector-prefixed, year-suffixed.

## Execution order (cheapest auth first)

  1. OECD       — no auth (SDMX)
  2. Eurostat   — no auth (SDMX)
  3. FDIC       — no auth
  4. CMS        — no auth
  5. FAA        — no auth (public endpoints only)
  6. EIA        — key in .env
  7. USDA NASS  — key in .env
  8. openFDA    — key in .env
  9. Comtrade   — REQUIRES STRATA_COMTRADE_API_KEY; skip + report if empty

You can dispatch these in parallel with the Agent tool (each is independent —
different connector, different data dir subset, different output filenames).

## Verification (must pass before declaring done)

From backend/:
  uv run strata validate -d ../data
  uv run pytest
  uv run pyright
  uv run ruff check .
  uv run ruff format --check .
  uv run strata stats -d ../data   # should show +~50 primitives

## Out of scope

  - Do NOT modify existing connectors or schemas.
  - Do NOT add new frameworks or concepts in this task.
  - Do NOT introduce new dependencies.
  - Do NOT touch the frontend.
  - Do NOT exceed the curated counts above without a written justification.

## Report back

When done, output:
  - count of primitives written per connector
  - any connector that was skipped + why (e.g. Comtrade key missing)
  - the verification command outputs (one line each, pass/fail)
  - links to 2–3 example primitive YAMLs to spot-check
```
