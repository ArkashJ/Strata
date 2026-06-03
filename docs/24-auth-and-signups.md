# 24 — Auth & sign-ups (Clerk)

How a user gets into Strata, and how the gate is wired. Audience: operators of
the deployment + future-me.

---

## What changed

Strata now **requires sign-in to use any feature**. A signed-out visitor sees a
public marketing **landing** and the **sign-in / sign-up** pages — nothing else.
Everything behind that (the library, build, portfolio, dashboard, TAM artifacts)
is gated.

```
                         ┌─────────────── signed-out ───────────────┐
visitor ─▶ any URL ─▶ middleware (auth.protect)                     │
                         │                                           ▼
                         │  public allowlist?  ──no──▶ redirect ▶ /sign-in ─┐
                         │   /  /sign-in  /sign-up                          │
                         │   /embed/*  robots  sitemap  og-image            │  Clerk
                         └──yes──▶ render (landing / auth page)             │  sign-in /
                                                                            │  sign-up
   signed-in ◀───────────────── session cookie set ◀──────────────────────┘
        │
        ▼
   full app (sidebar + every feature)
```

The only routes left open are ones where a gate has no security value and would
break a real feature: the auth pages themselves, Clerk's callback paths, the
public embeddable TAM iframe (`/embed`), and SEO/OpenGraph files.

Source: `web/src/middleware.ts` (protected-by-default `clerkMiddleware`).

---

## The sign-up flow (what a new user does)

1. Land on `/` → click **Create account** (or **Sign in** → *Sign up*).
2. Enter **email + password**, and (this instance) a **phone number**.
3. Pass the **bot check** (Cloudflare Turnstile) — one click.
4. Verify **email** (code) and **phone** (code).
5. Land back on `/`, now signed in — the sidebar + features unlock.

```
/ ▶ Create account ▶ email+password+phone ▶ Turnstile ▶ verify email ▶ verify phone ▶ / (signed in)
```

The required fields (phone on/off, which social logins) are configured in the
**Clerk dashboard** (dashboard.clerk.com), not in code.

---

## Configuration

Frontend env (Vercel = production, `web/.env.local` = local). Only the
publishable key is read in code to decide whether auth is on; the secret key is
read by Clerk itself.

```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_…      # turns auth ON when present
CLERK_SECRET_KEY=sk_test_…                       # server companion
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in           # where auth.protect() sends you
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL=/
NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL=/
```

**Graceful degradation:** with no publishable key (e.g. CI, a bare local run),
`clerkEnabled` is false — the middleware passes through, no gate, and the app
falls back to the local name/org sign-in. So tests and keyless builds still work.

> **Note — dev keys in prod.** Production currently runs the Clerk **development**
> instance (`pk_test…`, `dynamic-boa-37.clerk.accounts.dev`). It works and is fine
> for the demo, but shows a "development mode" badge and has strict usage limits.
> For a real launch, create a **production** Clerk instance and swap to `pk_live…`
> / `sk_live…` in Vercel.

---

## Testing the gate (Playwright)

Clerk protects sign-up with bot detection, so automated tests use **Clerk testing
tokens** (`@clerk/testing`) to bypass it. Test identities use the reserved
fixtures whose one-time code is always `424242`:

- email with a `+clerk_test` sub-address (e.g. `you+clerk_test@example.com`)
- phone in the `+1 (XXX) 555-01XX` range

A standing test user already exists: `strata+clerk_test@example.com`.

---

## Files

| File | Role |
|---|---|
| `web/src/middleware.ts` | The gate (protected-by-default) |
| `web/src/lib/clerk.ts` | `clerkEnabled` flag (single source of truth) |
| `web/src/app/page.tsx` | `/` → landing (signed-out) vs app home (signed-in) |
| `web/src/components/landing/PublicLanding.tsx` | The marketing landing |
| `web/src/components/landing/NightCanvas.tsx` | Navy grid + glass surface |
| `web/src/app/sign-in/…`, `sign-up/…` | Themed Clerk pages |
| `web/src/lib/clerk-appearance.ts` | Strata-indigo Clerk theme |
| `web/src/components/shell/AppShell.tsx` | No chrome before sign-in |
