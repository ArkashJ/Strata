# Rigorous Market Definition — design

**Date:** 2026-05-31
**Status:** approved, implementing
**Codename:** Strata · sub-project 1 of 3 (market-definition rigor)

---

## Why

A product review of the live TAM surfaces found that every disputed number
traced back to the same root cause: **markets are sized before they are
defined.** Concrete failures observed in the seed data:

| Symptom (what a reviewer saw) | Ground truth in the data | Root cause |
|---|---|---|
| AI sales-ops range $2B–$30.2B | seat method 1.46M × $1,400 ≈ $2.0B vs firm method 120k × $260k ≈ $31.2B (15× apart) | two methods size two *different* markets; no shared scope |
| "1.5M sales reps" but scope says "all reps" | `demo-bls-sales-reps-us-2024` = SOC **41-4012 wholesale & mfg only** | the primitive's true scope ≠ the concept's declared scope; nothing checks it |
| "Why mid-market?" — never declared | `demo-census-midmarket-firms-us-2022` silently narrows one method to 100–999-employee firms | scope assumptions live inside a primitive, invisible to the reader |
| AI legal ≈ $950M off a 2022 base | `census-cbp-5411-employees-2022` (all NAICS-5411 employees, 2022) under a "lawyers" reading | declared persona ≠ primitive's real population |

The fix is to make the **market scope a first-class, structured, checkable
object** that sits above every number — and to make every number's displayed
scope tell the truth about the primitive actually behind it.

This sub-project does **not** address stale base years or unsourced
community-modeled values (→ sub-project 3, provenance/freshness) or showing
top-down *and* bottoms-up together (→ sub-project 2). It builds the shared
`MarketScope` contract those two depend on.

---

## Decisions (locked with the user)

1. **Gate strength → live editable tags.** Scope renders as editable chips
   above the result; editing a tag mints a new `/build/<hash>` and recomputes
   via the existing `/build/recompute` path. No blocking wall.
2. **Scope is enforced, not decorative → a scope-consistency guard.** Tags are
   code-anchored; primitives declare their own true scope; a guard compares
   them.
3. **Mismatch behaviour → snap-to-truth + warn.** The *displayed* tag always
   equals the primitive's actual scope, so a number can never misrepresent its
   market. When that truth is narrower / broader / different than what the user
   typed, a mismatch chip explains the gap; a "widen →" action re-selects from
   the registry (honest gap if nothing matches).

---

## Data model

One `MarketScope` value object, used in three places.

```
MarketScope
  vertical    (CodedTag…)   industry / firm universe   → NAICS
  persona     (CodedTag…)   headcount / seat pool      → SOC occupation
  segment     FirmSizeBand? firm-size band             → employee band
  geo_supply  (str…)        ISO 3166 supply geography  (reconciles Q8)
  geo_demand  (str…)        ISO 3166 demand geography
  product     (str…)        what software counts       (free taxonomy)
  include     (str…)        explicit inclusion rules   (free text)
  exclude     (str…)        explicit exclusion rules   (free text)
```

| Lives on | Field | Role |
|---|---|---|
| `Concept` | `scope: MarketScope` (default empty) | the market's **canonical** identity |
| `AtomicPrimitive` | `scope: MarketScope` (default empty) | the primitive's **true** scope — what makes the guard possible |
| Build state | live tags | the user's **current** refinement |

`CodedTag = {system: NAICS|SOC|custom, code: str, label: str}`. Multiple codes
per dimension are allowed (e.g. B2B sales = SOC `41-3000` + `41-4000`).
`FirmSizeBand = {min_emp?: int, max_emp?: int, label: str}`. Both new fields
default to an empty `MarketScope()`, so existing YAML loads unchanged
(`extra="forbid"` records gain an optional field, not a required one).

Q8 note: scope carries `geo_supply` / `geo_demand` as parallel fields — the
shape Q8 mandates — even though the legacy `primitive.geo` remains a single
`Geo` + `GeoPerspective` until the v0.3 geo restoration. Scope geo and legacy
geo coexist; scope geo is the one the guard reads.

---

## The scope guard (`scope/guard.py`)

Pure, deterministic, no network / no LLM — mirrors `sizing/guard.py`.

Per dimension, classify the **declared** scope against the **actual** (primitive)
scope into a `Relationship`:

```
EXACT      actual == declared                       clean
NARROWER   actual ⊂ declared (covers less)          ⚠ undercounts
BROADER    actual ⊃ declared (covers more)          ⚠ may overcount
PARTIAL    overlap + a gap on each side             ⚠ mixed
DISJOINT   no overlap                               ✗ wrong market
UNKNOWN    a side declares nothing / free-text only  unverified
```

**Code hierarchy.** NAICS and SOC are hierarchical; comparison strips
separators and trailing hierarchy-padding zeros to a *significant prefix*, then
`A` is an ancestor of (broader than) `B` iff `sig(A)` is a prefix of `sig(B)`.

- NAICS `5411` ⊃ `541110`; `5411` vs `5415` → disjoint.
- SOC `41-4000` ⊃ `41-4012`; `41-4012` vs `41-3091` → disjoint.

**Set-of-codes per dimension.** Declared and actual are *sets* of codes. The
relationship aggregates: every actual code covered by some declared code and the
declared set covering strictly more → `NARROWER` (and the guard names the
declared codes with **no** actual coverage — e.g. "missing SOC 41-3000 services
sales reps entirely", which is exactly the wholesale-vs-all complaint).

`geo` compares ISO-code sets (with `global` as wildcard); `segment` compares
employee ranges by containment; `product`/`include`/`exclude` are free text →
`EXACT` on set equality else `UNKNOWN` (advisory only, never block).

**Output** — `ScopeMatch`:

```
ScopeMatch
  displayed: MarketScope        the primitive's actual scope (snap-to-truth)
  warnings:  (ScopeWarning…)    {dimension, relationship, message}
  ok:        bool               True iff every checked dimension is EXACT
```

The displayed scope is always `actual` — the UI binds tags to truth.

---

## Flow

```
query / concept ─► canonical scope tags render above result
                          │
        ┌─────────────────┼──────────────────┐
   edit a tag        widen a tag          (no edit)
        │                 │                    │
   re-select        registry search       compute under
   primitives       → match? swap         shown scope
   recompute        → none? honest gap
        ▼                 ▼                    ▼
   new /build/<hash>; every number's tag = the primitive actually used
```

---

## Build sequence (commits)

1. **Foundation** — `models/scope.py`, `scope:` on `Concept` + `AtomicPrimitive`,
   `scope/guard.py` classifier, adversarial tests (`tests/test_scope_guard.py`),
   this spec. *No behaviour change to existing sizing yet.*
2. **Backfill demo data** — add `scope:` to the ~10 primitives + 4 concepts in
   the reviewed examples (codes already sit in their `description`). Validate clean.
3. **API + evaluator wiring** — attach per-input `ScopeMatch` to the sizing /
   build response; expose declared scope on the concept payload.
4. **Frontend** — editable scope tags above the result, snap-to-truth display,
   mismatch chips, "widen →" action.

Each commit keeps the full verification suite green
(`uv run pytest && uv run pyright && uv run ruff check . && uv run ruff format --check .`).

---

## Reuse vs. new

| Reuse | New |
|---|---|
| `/build/recompute` + `EvalOverrides` | `MarketScope`, `CodedTag`, `FirmSizeBand` |
| `sizing/guard.py` pattern + adversarial-test style | `scope/guard.py` classifier |
| source-tier / banner-chip components | `ScopeMatch`, snap-to-truth tags, "widen →" |

## Out of scope (follow-on specs)

- **Sub-project 2 — always multiple methods:** attempt top-down *and* bottoms-up
  for every concept; explain divergence. Builds on `MarketScope` as the shared
  contract that makes the convergence cross-check apples-to-apples.
- **Sub-project 3 — number-level provenance:** the number *is* the hyperlink;
  deep-link + page/section anchor; show each number's derivation; reconcile
  stale base years; plain-language "community-modeled".
