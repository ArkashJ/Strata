# Agents Components

Personal-tier components for the `/agents` page — the MCP/CLI harness surface + activity/sync log.

## Components

- **`ActivityLog.tsx`** — Surfaces the audit_events table as a clean, tabular activity log showing every agent call (resolve, recompute, portfolio mutations). Wired to `auditQuery` from `lib/queries-personal.ts`.
  - States: loading (skeleton), error, empty (honest message), and data (sorted descending by timestamp).
  - Design: tabular, editorial register. Mono timestamps, semantic badges for action types (warn=write, neutral=read), truncated hashes, tertiary actor.
  - No shared state; purely presentational over React Query.

## Design Contract

Governed by `/impeccable` (PRODUCT.md + DESIGN.md):

- WCAG 2.2 AA contrast (tertiary text `#6b6b73` on `#fafafa` = 5.06:1)
- Mono timestamps (tabular figures via `tabular-nums`)
- Semantic badges: write actions (`--warn-soft` + `--warning-ink`), read actions (`--accent-soft` + `--accent-active`)
- Editorial voice, no AI-slop tells, restrained hierarchy
- No resting drop shadows; flat card edges on borders
- Reduced-motion safe (no animations in current version)

## Integrations

- **`lib/queries-personal.ts`**: `auditQuery(limit, offset)` — safe-parse wrapper that returns `[]` on error (personal tier surfaces must degrade gracefully).
- **`lib/schemas.ts`**: `AuditEvent` type — id, actor, action, target, ts (ISO-8601), meta (freeform).
- **`/agents` page**: imports and renders `ActivityLog` below the tool catalog.

## Future (Phase 5+)

- Pagination (currently hardcoded 50 most recent).
- Inline detail expansion (meta field, timing, error details).
- Filtering by action type (resolve, recompute, portfolio, etc.).
- Macro-recording UI (parameterized reusable recipes the user saves).
