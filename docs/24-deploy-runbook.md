# Deploy runbook — Railway (backend) + Vercel (frontend)

Neither prod deploys from `git push`. Both are CLI-driven from this machine.
This doc captures the exact steps **and the root cause of each trap** so the
failure modes below aren't re-discovered. A `scripts/deploy-smoke.sh` smoke test
(see bottom) verifies a deploy actually took.

```
  main (merged) ──▶ railway up ──▶ strata-api (Railway)      ──┐
                 └─▶ vercel build+deploy ──▶ stratabank (Vercel) ─┴─▶ scripts/deploy-smoke.sh
```

## Backend — Railway

Service lives in **`tushar1gupta's Projects → strata-backend → service
strata-api`** (`https://strata-api-production-9740.up.railway.app`). Logged in as
`arkjain@bu.edu`.

```bash
# from repo root
railway service strata-api
railway up --service strata-api --detach          # uploads context, builds remotely
```

Build config: `railway.json` (`dockerfilePath backend/Dockerfile`, context = repo
root). After deploy, if the DB schema changed: `alembic upgrade head` + re-seed
(`strata db seed` or `STRATA_SEED_ON_BOOT=1`).

### TRAP — Railway serves a STALE image / "the deploy didn't take"

**Root cause:** GitHub→Railway auto-deploys were failing silently, so prod kept
serving an old build (a 5-day-stale image was observed; `/report` 404'd in prod
because the image predated the report engine). **Railway does not redeploy on
push.** Always deploy `main` manually with the commands above, then **verify a
route only the new code has** (e.g. `/report` → 200), not just `/healthz` — a
stale image answers `/healthz` fine.

## Frontend — Vercel

Project `arkashjs-projects/stratabank`, canonical domain `stratabank.vercel.app`.
**Not git-connected.** Deploy from `web/`:

```bash
cd web
vercel build --prod --yes
vercel deploy --prebuilt --prod --yes            # --prod auto-aliases the canonical domain
```

### TRAP — "commit email could not be matched" blocks the prebuilt deploy

**Root cause:** Vercel ties a prebuilt deploy to the local HEAD commit's **author
email**. After a GitHub squash-merge, HEAD's author is
`<id>+<user>@users.noreply.github.com`, which is **not** a verified email on the
Vercel account, so the deploy is blocked. `arkjain@bu.edu` **is** verified.

```bash
# the dance — only needed when HEAD's author is the GitHub noreply (squash-merge checkout)
git commit --amend --reset-author --no-edit       # rewrites author to local arkjain@bu.edu
#   ... vercel build + deploy from web/ ...
git reset --hard origin/main                       # undo the amend
```

If your local git author is already `arkjain@bu.edu` (fresh local commits, not a
squash-merge checkout), skip the amend.

### TRAP — Vercel uploads the repo root and `bun install` fails

**Root cause:** `vercel link` writes a repo-root `.vercel/repo.json` with
`directory: "."`, so it builds the repo root (no `package.json` there).
**Fix:** delete any root + `web` `.vercel`, write a DIRECT link
`web/.vercel/project.json` = `{projectId, orgId}`, and deploy from `web/`.

## LOCAL trap — a stale Docker container shadows the fresh backend on :8000

**Root cause:** a leftover **Docker** container binds `*:8000` on **IPv6**
(`[::1]:8000`); a fresh `uvicorn` binds `127.0.0.1:8000` (IPv4). `localhost`
resolves to `::1` first, so `curl localhost:8000/...` hits the stale Docker image
— e.g. `/report` 404s even though your fresh server has it.

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN     # look for "com.docker … *:8000"
curl 127.0.0.1:8000/...              # force IPv4 to hit the fresh server, or:
docker stop <container>              # so localhost hits the fresh server
```

## Auth note (not a deploy failure)

Signed-out requests to gated routes (`/build`, `/c/<slug>/questions`, …) bounce
to `/sign-in` by design (Clerk). The saved e2e Clerk session
(`web/e2e/.clerk/user.json`) is **localhost-scoped** and will NOT carry to the
prod domain — prod uses Clerk DEV keys. To screenshot an authed prod page you
need a real prod session; locally, `web/scripts/shot.ts` loads the saved session.

## CI note

The GitHub `backend` check is **billing-blocked** ("job was not started because
recent account payments have failed") — it is **not an enforced gate**. The real
gate is the local suite (`cd backend && uv run pytest && uv run pyright && uv run
ruff check .`). PRs merge via `gh pr merge --squash --admin` once local is green.

## Verifying a deploy

```bash
scripts/deploy-smoke.sh        # backend /healthz + /report, CORS allow-origin, frontend 200
```

Non-zero exit = something didn't take. See the script for the exact checks.
