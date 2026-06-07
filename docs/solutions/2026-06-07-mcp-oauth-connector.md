---
title: "MCP OAuth 2.1 connector — async-FastAPI traps when standing up an OAuth AS"
date: 2026-06-07
type: [architecture, bug, conventions]
tags: [oauth, mcp, authlib, pkce, cors, rfc9728, clerk, revocation, audience]
pr: worktree-mcp-oauth-connector (#125)
status: active
---

# MCP OAuth 2.1 connector — load-bearing learnings

Standing up an OAuth 2.1 Authorization Server co-hosted with the `/mcp/` Resource
Server so claude.ai / ChatGPT web UIs (OAuth-only — no static-header field) can
connect in one click. The reusable traps below cost the most thought; most were
surfaced (or confirmed) by a 9-persona adversarial code review.

---

## 1. authlib's `AuthorizationServer` is sync + Flask/Django-coupled — don't wire it into async FastAPI

`authlib.oauth2`'s `AuthorizationServer` / `grants.AuthorizationCodeGrant` /
`RefreshTokenGrant` are **synchronous** and built around the Flask/Django request
objects and sync `save_*`/`query_*` callbacks. There is **no async OAuth-provider
integration** (the Starlette integration is OAuth *client* login only). Forcing
the sync server into an async FastAPI app means a sync↔async bridge fighting the
whole stack.

**What works:** use authlib for the one part you must not hand-roll —
`authlib.oauth2.rfc7636.create_s256_code_challenge` (PKCE S256) — wrapped in a
constant-time compare, and write the grant orchestration (validate → consume code
→ issue/rotate token) yourself in async route handlers backed by an async
persistence layer. authlib also does **not** implement RFC 9728 (protected-resource
metadata) or RFC 8707 (`resource` audience binding) — both are small hand-written
additions. Verify the library contract with `ctx7` before assuming the framework
integration exists.

## 2. An opaque-token cache must be a short-lived *lookaside*, not a lifetime store — or revocation never lands

Mirroring the API-key dict cache (`_KEY_STORE`) for OAuth access tokens is the
right hot-path shape, but API keys only *revoke*, while OAuth access tokens **also
rotate** (refresh issues a new pair and revokes the old). If the cache entry is
trusted for the token's whole `expires_at`, a refresh-rotated/revoked access token
keeps authenticating from the stale entry until its full TTL — and across multiple
workers, the revoke (done on one worker's DB row) **never propagates** to the others.

**Fix:** give each cache entry a short `cache_until` (e.g. 30s) separate from the
token's hard `expires_at`. The auth path re-warms from the DB whenever the entry is
past `cache_until`; a re-warm miss (revoked/expired in DB) **evicts** the entry. So
revocation propagates fleet-wide within the cache TTL while the steady state stays a
dict lookup. Sweep expired entries on insert to bound growth (tokens rotate, so dead
entries would otherwise accumulate — unlike a key cache bounded by key count).

## 3. A manual `Access-Control-Allow-Origin: *` collides with the app CORS middleware → duplicate header → browser rejects

The RFC 9728/8414 `.well-known` docs are fetched cross-origin from the browser by
claude.ai/ChatGPT, so the instinct is to set `Access-Control-Allow-Origin: *` on
them. But if the app already runs `CORSMiddleware` with the connector origins
allow-listed (as Strata does in prod), the middleware **also** adds an ACAO header
(echoing the request Origin). The browser then sees **two** ACAO values and rejects
the response — a silent connect failure. **Let one layer own CORS.** Drop the manual
header and ensure the connector origins are in the middleware allowlist.

## 4. RFC 9728 path-insertion: register BOTH `/.well-known/oauth-protected-resource/mcp` and `…/mcp/`

RFC 9728 forms the discovery URL by inserting `/.well-known/oauth-protected-resource`
*before* the resource's path component. A resource of `…/mcp` probes `…/mcp` (no
slash); `…/mcp/` probes `…/mcp/`. Trailing-slash sensitivity is the same class of
bug as the `/mcp/` 307-redirect that strips the `Authorization` header. Register both
suffixed variants so either probe resolves.

## 5. ChatGPT's callback is dynamic per-connector — allowlist by host, match by DCR registration

Confirmed 2026-06-07 (OpenAI Apps SDK): Claude's callback is static
(`https://claude.ai/api/mcp/auth_callback`), but ChatGPT's is
`https://chatgpt.com/connector/oauth/{callback_id}` — **dynamic per connector**
(plus legacy `…/connector_platform_oauth_redirect`). A hardcoded full-URL allowlist
cannot work. Instead: DCR (RFC 7591, accept-any) persists the client's declared
`redirect_uris`; `/authorize` requires the incoming `redirect_uri` to **exact-match**
a registered one AND its scheme+host to pass a **trusted-host allowlist**
(claude.ai / chatgpt.com / chat.openai.com over https + RFC 8252 loopback for Claude
Code). Reject userinfo in the URL outright (`https://evil@claude.ai/` parses to host
`claude.ai`); a bad `redirect_uri` is a 400, never a redirect (open-redirect defense).

## 6. Map the OAuth token to the SAME `org_id` the rest of the system uses

The issued token derives its org from the verified Clerk session exactly as the
existing Clerk-JWT bearer path does (`clerk_org:…` / `clerk_user:…`), so `/bank`,
saved primitives, and RLS all line up. OAuth tables (`oauth_clients` / `_auth_codes`
/ `_tokens`) are **NOT under RLS** — like `api_keys`, they're looked up by hash
*before* an org is known; isolation rides on the carried `org_id` → `org_session_scope`
+ RLS on the data tables, plus the RFC 8707 audience check (reject a token whose bound
`resource` != our MCP URL, enforced at both warm-time and the sync resolve).

## 7. Single-use codes + refresh rotation: verify-before-consume, atomic-update-as-lock

- Auth code single-use: the lock is `UPDATE … SET consumed_at=now() WHERE
  consumed_at IS NULL … RETURNING` — two concurrent `/token` calls race on the row;
  exactly one wins. **Verify PKCE + redirect/client match on a `peek` BEFORE the
  consume**, so a bad `code_verifier` (client bug) doesn't burn a legitimate,
  retryable code. Bind the issued token from the *consumed* row, not the peek.
- Refresh rotation: `UPDATE … SET revoked_at=now() WHERE revoked_at IS NULL …
  RETURNING` revokes the old refresh and issues a new pair; a reused old refresh
  finds no live row → `invalid_grant` (reuse detection). Use Postgres `func.now()`
  in the WHERE clauses, not the app clock, to avoid cross-service skew.

## 8. Test the security primitives DB-free

The redirect_uri allowlist and PKCE check are the load-bearing defenses, but if
they're only exercised through Postgres-gated endpoint tests, a DB-less CI lane (or
a green dev run) proves nothing. Add **pure unit tests** for `is_trusted_redirect_uri`
(every spoof/scheme/loopback branch, incl. `https://evil@claude.ai`) and
`verify_pkce_s256` (match / mismatch / empty) so the open-redirect and PKCE-downgrade
defenses are always covered.

---

**Deferred (P3, follow-ups):** per-IP rate limit on `/oauth/register` + `/oauth/token`
(the existing limiter is per-org; these are pre-auth); a GC reaper for expired codes /
revoked tokens; an independent Clerk org-membership re-check at consent (currently
parity with the existing JWT-claim org derivation); a scope whitelist.
