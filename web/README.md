# Strata web — landing + auth + OAuth consent only

The full web app has been **retired**: Strata ships through the **CLI and the
MCP server** (the direction lock in the root `CLAUDE.md`). This Next.js app now
serves only three surfaces:

- `/` — the public marketing landing
- `/sign-in`, `/sign-up` — Clerk auth pages
- `/oauth/authorize` — the hosted-MCP OAuth consent page (pointed at by
  `backend/src/strata/config.py`; do not break it)

Everything else (build studio, TAM pages, browse, connectors, dashboards, …)
was removed. The complete app is preserved on the **`frontend-archive`** branch
and the **`frontend-archive-2026-06-10`** tag.

## Develop

```bash
bun install
bun run dev        # http://localhost:3000
bun run build      # production build (must stay green for Vercel)
bun run check      # tsc + biome + eslint
```

Deployed at [stratabank.vercel.app](https://stratabank.vercel.app).
