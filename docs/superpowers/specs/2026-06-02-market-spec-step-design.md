# Market-spec step before sizing — design (2026-06-02)

**Goal (user, "strict gate"):** before any TAM, the user pins *which market* they
mean — vertical / persona / segment / geo / include–exclude. No number until the
market is defined. Fixes the recurring complaint: *"until we have a granular
sense of the market, we shouldn't size it."*

This is sub-project 1.5 — it **reuses** the PR #80 `MarketScope` value object and
scope guard; it does not invent a new model.

---

## The change in one diagram

```
                          BEFORE                                  AFTER
  query box ─▶ /build?q= ─▶ size immediately ─▶ /build/<hash>
                                                                  query box ─▶ /build?q=
                                                                       │
                                                                       ▼
                                                          ┌─ PIN THE MARKET (new) ──────────┐
                                                          │ vertical · persona · segment ·  │
                                                          │ geo · include / exclude         │
                                                          │ prefilled from the matched      │
                                                          │ concept's declared scope; edit  │
                                                          │      [ Size this market → ]     │
                                                          └────────────┬────────────────────┘
                                                                       │  user's MarketScope
                                                                       ▼
                                                          size (scope in build state) ─▶ /build/<hash>
                                                                       │
                                                          ScopeReport now reflects the user's
                                                          pinned scope vs each primitive's truth
```

The **Size** button is the gate — sizing only runs after the user confirms the
spec.

---

## Components & data flow

### Frontend
- **`MarketSpecStep`** (`web/src/components/build/MarketSpecStep.tsx`) — the form.
  Editable chips per dimension:
  - **Vertical** — NAICS `CodedTag[]` (chips; add/remove).
  - **Persona** — SOC `CodedTag[]` (chips).
  - **Segment** — a `FirmSizeBand` picker: *All firms · SMB (<100) · Mid-market
    (100–999) · Enterprise (1000+) · custom range*. "All firms" = no band.
  - **Geo** — `geo_supply` / `geo_demand` ISO selectors (default both = US).
  - **Include / Exclude** — free-text rule rows.
  Prefilled from the matched concept's `scope` (from `GET /c/<slug>`); fully
  editable. Copy: *"These narrow the market so we pick the right primitives."*
- **`BuildView`** (`web/src/app/build/BuildView.tsx`) — stop auto-redirecting.
  On a query, render `MarketSpecStep` (prefilled for a matched concept; empty /
  suggested for a no-match). On **Size**, encode the chosen `MarketScope` into
  the build state and proceed (matched → `buildQuery` with scope; no-match →
  `ResolveView` seeded with the scope).
- **`BuildState`** (`web/src/lib/state-hash.ts`) — add `scope: MarketScopeInput`
  (serialized). It is part of the state hash, so a different pinned market mints a
  different `/build/<hash>` (correct — it *is* a different market).
- **Zod** mirror of `MarketScope` in `web/src/lib/schemas.ts` for the request.

### Backend
- **`POST /build/{slug}` + `POST /resolve`** accept an optional `scope:
  MarketScope` in the body. When present it is the **declared** side the scope
  guard checks each consumed primitive against (overriding the concept's default
  declared scope for this build). Empty scope → today's behaviour, unchanged.
- The evaluator already attaches a `ScopeReport`; it now reflects the user's
  pinned scope. No new persistence — scope rides the build state (Q-hash) like
  every other build input. Migration 007 already persists scope on records.

### What stays out of scope (v1)
- No live NAICS/SOC autocomplete service — chips are typed/edited from a small
  curated suggestion list seeded from the concept + a static common-codes table.
  (A real classifier is a later milestone.)
- `product` free-text still display-only (guard emits no PRODUCT warning yet).

---

## Why this is the right shape
- It makes the market a **decision the user makes**, not an assumption buried in a
  primitive — directly answering the wholesale-vs-all-industries and
  mid-market-vs-unspecified mismatches the user flagged.
- It is **additive**: empty scope reproduces today's flow, so nothing breaks; the
  gate only bites once a concept declares (or the user pins) a scope.
- It sets up sub-project 2 (always top-down ∧ bottoms-up): once the market is
  pinned, the evaluator can pick *both* method families that match that scope.

---

## Build sequence
1. Backend: thread optional `scope` into `/build` + `/resolve`; guard uses it as
   declared side; tests for narrower/broader/disjoint against pinned scope.
2. Frontend: `MarketSpecStep` form + scope chips (reuse `/tam` Market chip render).
3. Wire `BuildView` to show the step, encode scope into `BuildState`, gate Size.
4. e2e: a spec that pins a mid-market segment and asserts the ScopeReport warns
   when a primitive is broader.
```
```
