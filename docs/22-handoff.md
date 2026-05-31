# 22 — Engineering Handoff

> Technical handoff as of 2026-05-31 (`main` @ the #72→#75 merge train). Read with
> [`21-teardown-remediation.md`](21-teardown-remediation.md) (the prioritized plan)
> and [`20-adversarial-teardown.md`](20-adversarial-teardown.md) (the why). This
> doc is for the next engineer: current state, gotchas, and value-ranked specs.

---

## 1. Current state (merged, verified)

| Area | State | Where |
|---|---|---|
| Free-form query → sourced TAM | live | `backend/src/strata/resolver/pipeline.py` |
| Show-the-math equation | live (multiplicative lenses only) | `web/src/components/ResolveResultChart.tsx` |
| Source tier/url/snapshot on inputs | live | `pipeline.py` `_source_fields`, `evaluator/engine.py` `_ResolvedInput.source_tier` |
| Durable `/tam/<hash>` (Postgres) | live | `db/tams.py`, migration `005_tam_outputs`, `api/routes/build.py` |
| Per-input source-tier mix on artifact | live | `web/src/components/tam/TamDetailView.tsx` `SourceTierMix` |
| Modeled-input honesty banner | live | `web/src/components/ResolveView.tsx` `ModeledInputsBanner` |
| Card defensibility (ring + method badge) | live | `web/src/components/TamCard.tsx`, `ui/IndependenceDonut.tsx` |
| `/audit` graceful degrade | live | `api/routes/audit.py` |
| Simple local login | live | `web/src/stores/identity-store.ts`, `components/auth/SimpleSignIn.tsx` |
| Favorites | live | `web/src/stores/favorites-store.ts`, `components/FavoriteStar.tsx` |
| Client `/guides` + handbook | live | `web/src/app/guides/page.tsx`, `docs/guides/CLIENT_PLATFORM_GUIDE.md` |
| Sensitivity tornado | live (on `/tam/<hash>`) | `web/src/components/charts/TornadoChart.tsx` |

**Verification gate (run before any merge):** from `backend/` —
`uv run pytest && uv run pyright src && uv run ruff check src && uv run ruff format --check src`.
Last green: **530 pytest pass, 0 pyright errors (src), ruff clean.** Web: `cd web && bun run typecheck`.

---

## 2. Gotchas the next engineer will hit (learned this session)

- **Dev CORS**: non-prod auto-allows any `localhost:*` origin (`api/app.py`). `next dev`
  grabs whatever port is free (3000/3001/3008…); an exact allowlist silently breaks
  every fetch → empty UI. Prod stays locked to its regex.
- **`uv` editable install**: never run a bare `uv sync` in `backend/` — it can prune the
  editable `strata` install and fall back to miniforge Python (pytest then can't
  `import strata`). Fix: `uv pip install -e .` (or `uv sync --all-extras`).
- **The "300 → 183 primitives" is not data loss**: 202 `prediction_market` primitives are
  quarantined to `data/signals/` (Wave-0, must never feed a framework). **No UI surface
  exists for them yet** — see §4.
- **Vercel git deploys fail** with "Git author ArkashJ must have access" — the GitHub
  login `ArkashJ` is OAuth-bound to the wrong Vercel account (`arkash-8869`), not
  `arkashj`. This is a **dashboard/OAuth fix**, not a code fix. Ship prod via
  `cd web && vercel deploy --prod` (CLI, logged in as `arkashj`).
- **No branch protection** (private repo, Hobby plan) → CI checks are advisory, not
  blocking. The `backend` CI runner is slow/queued (40+ min vs ~2 min locally); rely on
  the **local gate** for merge confidence.
- **Dev overlays in screenshots**: the floating beach emoji, red "1 Issue" pill, and "N"
  circle are Next/Clerk/TanStack **dev-mode** tooling — they do not appear in a prod
  build. Re-capture `/guides` screenshots from a prod build if they bother a client.
- **Cardinal rule**: **never invent a figure.** Every claimed real number needs a real
  source. This is why P1.3 (triangulated hero concepts) is blocked on real sourcing, not
  laziness — faking "sourced" primitives is the exact dishonesty the ASIC-analyst
  teardown caught.

---

## 3. Maximum-value functions (highest ROI, value-ranked)

Each is specced as: **what to build · where · the value it unlocks.**

### MV1 — Triangulated hero concepts (P1.3) · `data/concepts/`, `data/primitives/`
**Build:** seed 5–8 concepts that each carry **≥2 independently-sourced, competing
measurements** of the same quantity (e.g. US software-engineer headcount: BLS OEWS vs
Census CBP vs an analyst figure), wired via `competing_concepts`, each sized by ≥2
method-family frameworks so `independence_score > 0`.
**Value:** lights up the green `△ N methods` badge + the independence ring that already
exist in the UI, and makes the home page show a *visibly defensible* TAM. This is the
single highest-leverage item — it converts "looks like a guess" into "triangulated,
defensible." **Spec constraint:** every primitive needs a real source + `snapshot_sha256`
(use the connectors in `backend/src/strata/connectors/` or Exa). No invented numbers.

### MV2 — Bottoms-up vs tops-down convergence banner · `evaluator/engine.py` + `ResolveResultChart.tsx`
**Build:** when a concept has both a bottoms-up and a tops-down framework, compute both and
surface a headline "bottoms-up $X / tops-down $Y / agree 1.2×" banner.
**Value:** the convergence cross-check is *the* artifact VCs assemble by hand over days and
distrust LLMs for. Directly answers "why trust your number."

### MV3 — Pick one niche vertical, build its value chain · `connectors/` + `data/`
**Build:** ingest a real supply-side vertical (e.g. AI-inference compute: wafer-starts,
CoWoS capacity, HBM bit-supply, hyperscaler capex) + a **supply-constrained framework**
`min(demand, capacity) × ASP × yield` (the six current lenses are all demand-multiplicative
and can't model a capacity ceiling).
**Value:** earns the right to size a niche TAM an analyst would sign — the differentiator
that makes Strata worth paying for over a general LLM.

### MV4 — Metered micropayments · new `api/routes/billing.py` + `web` paywall
**Build:** Stripe metered billing on top of the existing usage meter (`api/metering.py`,
`usage_events` table, `GET /usage`); credit balance; paywall-gate `/build/recompute` and
exports.
**Value:** turns the tool into a product that can charge. Metering already exists — this is
the billing layer + gating, not net-new measurement.

---

## 4. Technical TODOs (concrete, with file pointers)

| # | TODO | File(s) | Notes |
|---|---|---|---|
| ~~T1~~ ✅ | ~~Surface the 202 quarantined signals read-only~~ **Done** | `api/routes/signals.py` + `/signals` web route + sidebar link | Shipped: `GET /signals` + `/signals` page (grouped by concept, value/source/snapshot receipt, loud "never feeds a TAM" banner). 4 backend + 4 e2e tests; `/p`-leak invariant enforced. |
| T2 | Equation footer for additive frameworks | `ResolveResultChart.tsx` | Currently gated to multiplicative lenses. To show `bundle_consolidation` (sum-then-discount), propagate an `equation_kind` from the backend (`ResolverResult`) instead of inferring from `lens`. |
| T3 | Persist favorites/identity server-side | `db/`, `identity-store.ts`, `favorites-store.ts` | Today both are localStorage-only (per-browser). Tie to `Principal.org_id` when real auth lands. |
| T4 | Load DB-stored API keys at boot | `api/auth.py` | `api_keys` table (migration 003) is scaffolding; `_KEY_STORE` is in-process only. |
| T5 | Real RBAC roles | `api/auth.py` `Principal.scopes` | `scopes` field exists but is unused dead-ish code; no role enforcement. |
| T6 | Make `/graph` analytic | `web/src/app/graph/GraphView.tsx` | Resolves a TAM only for a sole Industry concept; Qual/Quant selection returns just a framework count. Resolve (or average) on any pillar selection. |
| T7 | Expand `+N more` in pyramid | `GraphView.tsx` | ~62% of industry concepts hidden behind a non-clickable node. |
| T8 | `tests/` strict-mode debt | `backend/tests/` | ~147 pyright + 37 ruff errors in `tests/` (outside the `src/`-scoped CI gate). Track-and-clean. |

---

## 5. Nice-to-haves

- Compare tray — pit 2–4 concepts/TAMs/scenarios side by side (the "pit ideas against each
  other" ask). Reuse `TamCard` + a compare route.
- Change-over-time window — time-series of a primitive/TAM across `as_of` dates with a
  90d/30d/7d range selector (a recharts area chart; the user supplied the pattern).
- Printable one-pager polish — `tam-print.css` exists + `window.print()`; curate 5–8 TAMs
  that beat a public source side-by-side as the forwardable artifact.
- Strip dev overlays / re-capture `/guides` from a prod build.
- Notifications backend (the bell in `TopBar` is a placeholder).

---

## 6. Value specs — how each function delivers business value

| Function | Business value | Proof to a skeptic |
|---|---|---|
| Sourced primitives + snapshot pin | "Every number traces to a citation" | `/p/<slug>` Source Snapshot; `snapshot_sha256` |
| Durable `/tam/<hash>` | "Paste it in a memo; it stays" | survives an API restart (verified) |
| Show-the-math equation | "See the arithmetic, not a black box" | `Multiplies to A × B = TAM` on `/build` |
| Triangulation (MV1/MV2) | "Two independent methods agree" | independence score + convergence banner |
| Niche value chain (MV3) | "An analyst would sign this" | supply-constrained TAM with real capacity data |
| Modeled-input honesty | "We flag what's modeled vs sourced" | banner on results with `community-modeled` inputs |
| MCP server | "Your agents get cited numbers" | `strata.mcp`, payloads carry source+tier+hash |

The throughline: Strata sells a **defensible, reproducible, customizable artifact**, not an
answer. Every function above exists to make that claim survive a partner's scrutiny.

---

## 7. Deploy & run quick reference

- **Local stack:** `docker compose up -d` (db :5432, api :8000, web :3001). `next dev`
  elsewhere is fine (dev CORS allows any localhost port).
- **Backend prod:** Railway (`strata-api`, tushar's workspace) auto-deploys `main` via CI;
  or `railway up` from repo root. Seed prod DB with `STRATA_SEED_ON_BOOT=1` / `strata db seed`.
- **Frontend prod:** `cd web && vercel deploy --prod` (CLI, account `arkashj`). Git deploys
  are blocked until the GitHub↔Vercel OAuth binding is fixed (see §2).
- **Verification:** §1 gate. Always green before merge; CI is advisory.
