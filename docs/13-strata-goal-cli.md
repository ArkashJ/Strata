# `strata goal` — ask free-form TAM questions from the terminal

`strata goal "<query>"` is the v0.3 CLI surface for the dynamic resolver
pipeline. It takes a free-form market-sizing question and walks it through a
4-step hybrid retrieval that maps the query to whatever the data bank already
knows about — falling back to live connector calls, then to a Claude+Exa
synthesis, only when the data bank misses.

If you already have a concept slug, `strata size <slug>` is still the cheapest
and most defensible path (no Claude calls, no network). `strata goal` is for
the case where you don't yet know which slug applies — or whether one exists.

## TL;DR

```bash
$ uv run strata goal "US bank deposit market size 2024"

→ Slug resolver: intent=novel, framework_hint=platform_throughput
→ Step 3: framework platform_throughput needs {bank_count, avg_deposits}
          [1/2] router → fdic.bank_count_total(year=2024) tier=regulator
                conf=0.94 → wrote ~/.strata/auto-primitives/fdic-bank-
                count-us-2024.yaml
          [2/2] router → fdic.total_deposits_by_year(year=2024)
                tier=regulator conf=0.92
→ evaluator: 2 inputs · 1 scenario path

  TAM   point: $19.4T
  Inputs:
    • fdic-bank-count-us-2024         4,577     FDIC BankFind 2024-12
    • fdic-total-deposits-us-2024     $19.4T    FDIC BankFind 2024-12

  ⚑ Two auto-primitives written to ~/.strata/auto-primitives/.
  Run `strata promote fdic-bank-count-us-2024` to move into data/primitives/.
```

## How it works

```
                strata goal "<query>"
                          │
                          ▼
            ┌─────────────────────────────┐
            │ pre. slug resolver          │ ← single Claude call, registry
            │     intent: concept |       │   index sent as cached system
            │     primitive | novel       │   block (5-min Anthropic prompt
            │                             │   cache)
            └──────────────┬──────────────┘
                           │
   ┌───────────┬───────────┴───────────┬─────────────────────┐
   │ step 1    │ step 2                │ step 3              │ step 4
   │ concept   │ primitive(s)          │ connector live      │ fallback
   ▼           ▼                       ▼                     ▼
registry    registry              router.choose         resolver.parse
.concept    .primitive[]          (manifest, cached      _and_search
   │           │                    prompt — §6.1)       (Claude + Exa)
   │           │                       │                     │
   ▼           ▼                       ▼                     ▼
evaluator   value with banner    connector.method      ephemeral TAM
.size_concept                    → writer.upsert       + warning banner
                                 → ~/.strata/
                                   auto-primitives/
                                 → evaluator
```

Each step is opt-out (see flags below). The pipeline always carries the
slug-resolver output through so we never make two Claude parse calls in
one invocation.

## Flags

| Flag | Effect | Default |
|---|---|---|
| `--stream` | One-line-per-step chain-of-thought to stdout | off |
| `--json` | Pure JSON ResolverResult (pipe-friendly) | off |
| `--verbose` | Include the scenario tree + sources in compact mode | off |
| `--no-live` | Skip step 3 (no connector calls at query time) | off |
| `--no-fallback` | Skip step 4 (no Claude+Exa) | off |
| `--primitive-only` | Step 2 returns a single primitive without composing | off |
| `--expansion-budget N` | Cap connector calls in step 3 | 6 |
| `--data-dir PATH` | Override `data/` location | `data` |

`--stream` and `--json` are mutually exclusive. Setting both is an arg error
(exit 2). `--no-live --no-fallback` reduces `goal` to a pure-registry query
that returns exit 1 when the registry misses — useful in CI.

## Environment

`STRATA_OFFLINE=1` is shorthand for `--no-live --no-fallback`. CI sets it;
humans don't. Explicit CLI flags override.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | TAM produced |
| 1 | No result (registry miss with `--no-live --no-fallback`) |
| 2 | Invalid query / arg error |
| 3 | Pipeline failed during step 3 or 4 (API error, parse failure) |
| 4 | Expansion budget exceeded before all inputs found |

## `strata promote <slug>`

`goal`'s step-3 writes land in `~/.strata/auto-primitives/{slug}.yaml`, NOT in
the committed `data/primitives/` tree. To curate one into the committed bank:

```bash
$ strata promote fdic-bank-count-us-2024
✓ Promoted fdic-bank-count-us-2024 → data/primitives/fdic-bank-count-us-2024.yaml
```

The full validator pipeline runs against the staged copy; promotion rolls
back if validation fails. Re-running on an already-promoted slug is a no-op.

## Cost notes

Per-query cost depends on which steps fire:

- **Slug resolver** — one Claude call, ~5K input tokens (registry index),
  cached for ~5 min so back-to-back queries pay ~10% of the cold price.
- **Step 3 router** — one Claude call, ~21K input tokens (manifest of all 22
  connectors), also cached. Each connector hit afterwards is deterministic
  Python.
- **Step 4 fallback** — one Claude parse + N (≤2) Exa searches + N Claude
  extracts. Typically $0.10–$0.20 per query when this path fires.

The first `goal` in a session pays the full cache-cold price; subsequent
queries within 5 min stay warm.

## When NOT to use it

- You already have the concept slug → use `strata size <slug>` (free, no LLM).
- You want a reproducible TAM with no LLM in the loop → use `strata size` +
  the registry.
- You need promote-able primitives for the committed data bank → use `goal`
  with `--no-fallback` so only regulator/aggregator-tier connector hits land
  in `~/.strata/auto-primitives/`. The step-4 fallback path is ephemeral and
  never written to disk; banners on the output remind you not to cite it
  without manual verification.
