# Strata — Full-App QA Pass (2026-05-30)

End-to-end audit driven by Playwright CLI against the **local** stack, plus a
data-integrity investigation and a prod-readiness gap catalog.

## Environment

| Layer | URL | Notes |
|---|---|---|
| Frontend | http://localhost:3008 | `next dev` (port drifted from 3001 → 3008) |
| Backend API | http://localhost:8000 | docker-compose `api` (migrations + seed on boot) |
| Postgres | localhost:5432 | docker-compose `db` |
| LLM backend | anthropic SDK | `STRATA_LLM_BACKEND=anthropic`, key from root `.env` |

Frontend defaults `NEXT_PUBLIC_API_URL` → `http://localhost:8000` when unset,
so the two match.

## Headline finding — CORS was masking everything

Every API fetch (`/c`, `/p`, `/f`) was **blocked by CORS** because the backend
allowlist was `["http://localhost:3000","http://localhost:3001"]` and the
frontend had drifted to `:3008`. Result: the UI rendered empty — no concepts,
no primitives, **no sources**, no live TAM. Every downstream complaint ("looks
bad", "sources don't show", "can't build a TAM") traced to this single bug.

**Fix (committed `755672e`):** non-prod auto-allows any `localhost:*` origin via
regex; prod stays locked to its explicit regex. After the fix: 0 console
errors on home, library counts live (Concepts 37, Primitives 184, Frameworks 5),
build-your-own-TAM works.

## Data integrity — "300 primitives disappeared to 183"

Not lost — **quarantined**:

```
data/primitives/  = 183 files   ← shown in app (184 via API)
data/signals/     = 202 files   ← prediction_market (Kalshi), Wave-0 quarantine
                    ─────
                    385 total   ← the "over 300"
```

The 202 `prediction_market` primitives were intentionally moved to
`data/signals/` (Wave 0: prediction-market probabilities must never silently
feed a TAM framework). They are intact on disk but have **no UI surface** and
`GET /signals` returns 0 — so they appear deleted. **Gap:** build a read-only
Signals surface (also a differentiator — live signals beat a static Claude answer).

## Page-by-page sweep (Playwright)

| Route | Console errors | State | Verdict |
|---|---|---|---|
| `/` home | 0 (after fix) | live counts, hero, search | ✅ good |
| `/build?q=…` | 0 | resolved $900M live, primitives + provenance banner | ✅ works; **no math shown, no source links** |
| `/dashboard` | 2 | `GET /audit` → 401 | ⚠️ panel broken without auth |
| `/graph` pyramid | 0 | 3-pillar graph, geo/time/stage filters, frameworks rail | ✅ polished |
| `/integrations` | 0 | OAuth/CRM gallery | ✅ |
| `/c` `/p` `/f` | 0 | live lists | ✅ |
| `/c/<slug>` | 0 | concept "disagreement view" | ✅ |
| `/p/<slug>` | 0 | value, unit, methodology, **SOURCE SNAPSHOT (url+tier+accessed)** | ✅ sources DO show here |
| `/f/<slug>` | 0 | framework detail | ✅ |
| `/browse` | 0 | promoted TAMs | ✅ |
| `/search` (direct URL) | 1 | 404 | ℹ️ no route, but **no UI links here** (sidebar Search opens ⌘K palette) — non-bug |

## Gap catalog (prod-readiness)

| # | Gap | Evidence | Severity |
|---|---|---|---|
| G1 | CORS broke all data in dev | preflight failures on :3008 | **fixed** `755672e` |
| G2 | 202 signals invisible | `GET /signals` → 0; no route | high |
| G3 | Build result hides the math | primitives listed without the `×` derivation | high (core differentiator) |
| G4 | Build result hides sources | `primitives_used` payload drops `source_tier`/`source_url` (present on `/p` detail) | high (core differentiator) |
| G5 | Dashboard `/audit` 401 | `require_authenticated`, no graceful degrade | medium |
| G6 | Hard-coded user in sidebar | `j.vega / 27 contribs` — `TODO(auth)` | medium (RBAC) |
| G7 | No favorites/watchlist | — | feature |
| G8 | No compare ("pit ideas") | — | feature |
| G9 | No change-over-time window | — | feature |
| G10 | No micropayments/billing | metering exists, no paywall/Stripe | feature (monetization) |
| G11 | Agent/MCP surface not promoted | `strata.mcp` exists, not discoverable | feature |

Build roadmap → see `docs/plans/` (generated from the moat-blueprint workflow).
