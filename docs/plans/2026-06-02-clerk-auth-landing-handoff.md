# Handoff — Clerk auth gate, landing redesign, e2e, Storybook, market-spec (2026-06-02)

Pick-up notes for a fresh session. Everything below is **committed + pushed** on
branch `feat/clerk-auth-and-landing` (9 commits ahead of `main`, no PR yet).

---

## 0. Resume in 30 seconds

```bash
cd /Users/arkashjain/Desktop/work/VC_stuff
git checkout feat/clerk-auth-and-landing
git pull
# web/.env.local already holds the Clerk keys (gitignored). Dev server:
cd web && bun dev            # http://localhost:3000 (or pick a free port: bun dev --port 3100)
```

- **Clerk instance:** dev — `dynamic-boa-37.clerk.accounts.dev` (keys in `web/.env.local`, also on Vercel prod).
- **Test user:** `strata+clerk_test@example.com` (exists in the instance). Any
  `+clerk_test` email / `+1 XXX 555-01XX` phone verifies with code **`424242`**.
- **Live prod:** `https://strata-pied-three.vercel.app` (gated). Backend:
  `https://strata-api-production-9740.up.railway.app` (healthy).

---

## 1. What shipped this session (done + verified)

| Area | What | Where |
|---|---|---|
| **Auth gate** | Sign-in required for every route except a public allowlist (`/`, `/sign-in`, `/sign-up`, `/embed`, robots/sitemap/og). Keyless graceful-degradation preserved. | `web/src/middleware.ts` |
| **Landing** | Signed-out `/` = split-editorial marketing page on a deep-navy infinite grid + glassmorphism; **no app sidebar before login**. | `web/src/components/landing/{NightCanvas,PublicLanding}.tsx`, `globals.css` (`.strata-night`/`.grid-canvas`/`.glass`) |
| **Auth pages** | `/sign-in` + `/sign-up` themed on the night canvas (glass card, indigo Clerk `appearance`). | `web/src/app/sign-in/...`, `sign-up/...`, `web/src/lib/clerk-appearance.ts` |
| **Shell** | `AppShell` renders bare for auth routes + signed-out landing; full sidebar only signed-in. `/` branches via `useAuth()` (one branch mounts). | `web/src/components/shell/AppShell.tsx`, `web/src/app/page.tsx` |
| **Deploy** | Clerk env on Vercel prod (6 vars); prod is live + gated. Railway backend healthy. | Vercel project `strata` |
| **Theme** | Light/dark toggle confirmed intact in the signed-in shell (night canvas is intentionally always-dark). | `web/src/components/shell/ThemeToggle.tsx` |
| **e2e auth** | Suite runs authenticated: Clerk Testing Token → `storageState`; signed-out gate spec. | `web/e2e/global.setup.ts`, `web/e2e/auth-gate.spec.ts`, `web/playwright.config.ts` |
| **Storybook** | Storybook 10 (Vite) + light/dark toolbar + stories (Button, NightCanvas+PublicLanding, design tokens). | `web/.storybook/`, `*.stories.tsx` |
| **Market-spec (backend)** | `size_concept(declared_scope_override=...)` + `POST /build/recompute { scope }`. Pinned market drives the scope-guard's declared side and the state hash. **+3 tests, 15 pass.** | `backend/src/strata/evaluator/engine.py`, `backend/src/strata/api/routes/build.py`, `backend/tests/test_scope_report.py` |

---

## 2. Remaining work (the real to-do)

### #4 — Market-spec step: FRONTEND (in progress, backend done)

Decision locked: **strict gate, prefilled, one-click accept**. Spec is the
contract: `docs/superpowers/specs/2026-06-02-market-spec-step-design.md`.

```
query ─▶ /build?q= ─▶ ┌ PIN THE MARKET (new) ───────────────────┐ ─▶ Size ─▶ /build/<hash>
                      │ vertical · persona · segment · geo ·     │
                      │ include/exclude — prefilled from the     │
                      │ concept's declared scope, editable       │
                      │            [ Size this market → ]        │
                      └──────────────────────────────────────────┘
```

Build order (each step verifiable):
1. `web/src/lib/schemas.ts` — Zod `MarketScope` mirroring the backend model
   (`CodedTag{system,code,label}`, `FirmSizeBand{min_emp,max_emp,label}`,
   `vertical/persona/segment/geo_supply/geo_demand/product/include/exclude`).
2. `web/src/lib/state-hash.ts` — add optional `scope` to `BuildState` (rides the
   encoded `?s=`).
3. `web/src/components/build/MarketSpecStep.tsx` — the form. Segment presets:
   **All firms / SMB (<100) / Mid-market (100–999) / Enterprise (1000+) / custom**.
   Geo defaults US. Prefill from `GET /c/<slug>` (`concept.scope`).
4. `web/src/app/build/BuildView.tsx` — **the critical path; verify headed.**
   Stop auto-redirecting; render `MarketSpecStep` (prefilled, 1-click accept) →
   on Size, `POST /build/recompute { concept_slug, scope }` → redirect to
   `/build/<hash>?s=...`. No-match query path (`ResolveView`) stays as-is.
5. e2e: pin a mid-market segment, assert the `ScopeReport` warns on a broader
   primitive (`web/e2e/`, authenticated `chromium` project).

Gotcha: a different pinned scope **mints a different `/build/<hash>`** — that's
correct (it is a different market). Empty scope = today's behaviour.

### #5 — Methodology (needs REAL sourcing — no invented figures)
From the user's break-notes: always show **both top-down ∧ bottoms-up** (+ extra
approaches); **hyperlink the number itself** to its source with exact page/section;
make each figure back-solvable. Maps to PR #80 sub-projects 2 & 3. Backend
evaluator + data work; **do not fabricate** — source every figure.

### #6 — Refresh stale e2e specs (mechanical, NOT auth-related)
28 specs were already red before this work. They assert on removed/renamed UI:
`"Contribute"` nav, `"Data"` nav, `"Recently updated"` section, lowercase
`"defensible"`, and resolver/LLM content. Update them to the current UI so the
authenticated suite goes fully green. Start with `web/e2e/landing.spec.ts`.

---

## 3. How to run / verify

```bash
# Backend (from backend/)
uv run pytest && uv run pyright && uv run ruff check . && uv run ruff format --check .

# Web typecheck + lint (from web/)
bun run typecheck && bunx biome check .

# e2e — Clerk-authenticated. Next 16 locks ONE `next dev` per dir, so kill any
# hand-run dev server first. Dedicated e2e port avoids collisions.
cd web && lsof -ti:3100 | xargs kill -9 2>/dev/null
E2E_PORT=3200 bunx playwright test --project=setup --project=public   # auth + gate (fast)
E2E_PORT=3200 bunx playwright test --project=chromium                  # full authed suite

# Storybook (from web/)
bun run storybook            # dev
bun run build-storybook      # proof it builds

# Live headed walkthrough
playwright-cli open --headed --browser=chrome http://localhost:3000/
```

---

## 4. Gotchas / landmines

- **Clerk `appearance`:** use the `variables` block only. A full `elements`
  className map made Clerk **SSR-404** the sign-in page. (`clerk-appearance.ts`.)
- **`middleware.ts`, not `proxy.ts`:** Clerk 7.4.2's `clerkMiddleware` expects the
  old filename; Next 16 prints a deprecation warning — ignore it. Switching breaks
  Clerk's matcher.
- **Prod uses Clerk DEV keys** (`pk_test…`). Fine for demo (shows "development
  mode"), but make a **production** Clerk instance + swap to `pk_live…` before launch.
- **Next 16 single-instance dev lock:** only one `next dev` per directory. Kill the
  old one before e2e or a second server.
- **CORS:** the e2e frontend points at the LOCAL backend (`:8000`, dev CORS allows
  localhost). Pointing local at the Railway prod backend gives CORS errors on
  `localhost:*` — expected, not a regression.
- **Vercel deploy:** `cd web && vercel deploy --prod` (CLI, as `arkashj`). Git push
  is blocked on this account; the production alias is `strata-pied-three.vercel.app`
  (the raw per-deployment URL 401s — Vercel deployment protection).
- **Railway:** `status` showed "Deploy failed 1d" but the running deploy is healthy
  (`/healthz` 200) — the status line was stale.

---

## 5. Docs / specs to read first
- `docs/superpowers/specs/2026-06-02-market-spec-step-design.md` — #4 build contract.
- `docs/24-auth-and-signups.md` — the auth/sign-up flow + config.
- `CHANGELOG.md` `[Unreleased]` — the running list.
- This repo's `CLAUDE.md` — project orientation; memory file `clerk_auth_landing.md`.

## 6. Open decision for the user
Open a PR for `feat/clerk-auth-and-landing` → `main`? (9 commits; auth + landing
are live in prod already via direct Vercel deploy. A PR would let CI run + give a
review surface.)
