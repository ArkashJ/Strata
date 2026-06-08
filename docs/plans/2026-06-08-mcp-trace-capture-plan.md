# Plan — MCP trace-capture for testing (Direction 1)

**Date:** 2026-06-08
**Status:** ready to build (PR on a feature branch, not `main`).
**Scope:** Direction 1 ONLY — server-side tool-call trace capture + an agent-submitted
reasoning tier + `strata traces` CLI (list/show/export/replay). Direction 2
(demand-ranked connectors) is the sequenced follow-on; out of scope here.
**Source brainstorm:** [`docs/brainstorms/2026-06-08-mcp-cli-robustness-requirements.md`](../brainstorms/2026-06-08-mcp-cli-robustness-requirements.md)
(approach **A — wrap the dispatch — + the agent-submitted reasoning tier from C**).
**Four-pillar spec:** [`docs/plans/2026-06-07-mcp-cli-research-engine-spec.md`](2026-06-07-mcp-cli-research-engine-spec.md).

---

## What we're building (one paragraph)

A tracer around the single MCP `tools/call` chokepoint records every tool call
— name, arguments, structural result summary + hash, ok/error, duration, org,
session, sequence — fire-and-forget into a new RLS-scoped `tool_traces` table,
gated off by default. A new MCP tool lets the agent attach its reasoning to the
session (the *why* the server structurally can't see). A `strata traces` CLI
sub-app lists real sessions, shows a session's ordered calls + reasoning, exports
a session to a versioned golden fixture, and **replays** a captured sequence
against current code to surface silent regressions. This is the instrument that
makes Direction 2's connector picks evidence-driven.

---

## Design decisions (resolving the brainstorm's open questions)

### D1 — How calls are grouped into a "session" (the load-bearing wrinkle)

The hosted HTTP transport is **stateless** (`server.py:182`, `stateless=True`),
so the MCP SDK issues **no** `Mcp-Session-Id` and there is no server-side session
affinity across calls. We therefore stitch a session ourselves, mirroring the
**existing principal `ContextVar` pattern** (`mcp/context.py`):

- Add `current_trace_session: ContextVar[str | None]` to `mcp/context.py`.
- **Hosted:** `McpAuthMiddleware` reads an optional `X-Strata-Trace-Session`
  header and sets the contextvar around the request (same place it already sets
  `current_principal`). When absent, calls are still captured with
  `session_id = NULL` (an ungrouped call is better than a dropped one — AC-1.5
  says capture must never break a call, not that grouping is mandatory).
- **stdio (local-trust):** one process *is* one session. `run_stdio` sets the
  contextvar once at startup to a process-stable id derived from
  `principal-less` boot (no `Math.random`/`Date.now` constraint here — this is
  Python; use `uuid4().hex`). Sequence numbers order calls within it.
- The **agent-submitted reasoning tool** accepts an explicit `session_id` so the
  agent can stitch its reasoning to the exact session it just ran (and, if the
  harness threads the same id into the header, the whole session correlates).

This keeps every tool's `inputSchema` untouched (no `_trace_session` arg
pollution) and reuses the proven contextvar mechanism verbatim.

### D2 — Result fidelity for replay (brainstorm Q3)

Store **a structural summary + a `sha256` hash of the canonicalized result,
always**; do **not** store the full result by default. Rationale:

- The hash is the regression signal — replay re-runs the call and compares
  `result_sha256`; a mismatch *is* the "this changed" flag (AC-1.3).
- The summary (top-level keys, scalar values, array lengths, error code) is
  enough for `traces show` to be diagnosable without dumping megabytes.
- Full result only when `STRATA_TRACE_FULL_RESULTS=1` (heavy; opt-in for when a
  diff needs the actual delta, not just "it changed").
- Canonicalization = `json.dumps(result, sort_keys=True, default=str)` before
  hashing, so equivalent results collide (mirrors the state-hash canonicalization
  already used for `/build/<hash>`).

### D3 — Retention (brainstorm Q2)

Captured args+results can be large and contain org-private portfolio data. Cap
at write time, mirroring the FIFO `reg.remember_tam` cap noted in CLAUDE.md:

- Keep the most recent **N=200 sessions per org** (`STRATA_TRACE_MAX_SESSIONS`,
  default 200); on write, prune older sessions for that org in the same
  fire-and-forget task.
- `strata traces purge --org <o> [--before <date>]` for manual/admin cleanup
  (admin scope via the existing `app.is_admin` GUC).
- Args/results are truncated to `STRATA_TRACE_MAX_FIELD_BYTES` (default 64 KB)
  per field before storage; truncation is flagged so `show` is honest about it.

### D4 — Privacy posture (why traces keep what audit hashes)

`_audit_call` deliberately **hashes** arguments (`server.py:151`) — the audit
trail records *what ran* without retaining inputs. Trace-capture deliberately
**keeps** args + result summaries, because replay needs the real inputs. The
heavier privacy load is therefore carried by: (a) **off-by-default gate**
(`STRATA_TRACE_CAPTURE`), (b) the **same closed RLS** as feedback/gaps (own-org
only, fails closed when `app.org_id` unset), and (c) the per-field size cap.
This trade is called out explicitly so it's a decision, not an accident.

### D5 — Out of scope (deferred, per brainstorm)

- Auto-live-pull on novel queries (Q1) — that's Direction 2.
- LLM-judge / answer-quality scoring over captured sessions — later.
- Any web trace viewer — web is frozen.
- Capturing raw end-user prompts unless the agent submits them via the reasoning
  tool.

---

## Architecture (where each piece sits)

```
  MCP tools/call  ──►  _call_tool (server.py:106)
                          │  (unchanged happy path)
                          ├─► _audit_call(...)         ← exists (hashed args)
                          └─► _trace_call(...)  NEW    ← fire-and-forget, gated
                                   │                      records full call row
                                   ▼
                          db/traces.py: record_trace_safe
                                   │  own session, org_session_scope (closed RLS)
                                   ▼
                          tool_traces  (migration 018)   session_id · seq · tool
                                                          args_json · result_summary
                                                          result_sha256 · status · ms

  agent  ──► record_session_reasoning (NEW MCP tool, +1 → 27 tools)
                   │  trace_tools.py  →  db/traces.py: record_reasoning
                   ▼
              trace_sessions  (migration 018)  session_id · org · reasoning · outcome

  strata traces {list|show|export|replay|purge}   ← CLI sub-app (cli.py)
                   list/show  → db/traces readers (org + admin scopes)
                   export     → backend/tests/fixtures/traces/<session>.json
                   replay     → re-run call_tool() per captured call, diff sha256
```

---

## File-by-file work (each mirrors a named existing pattern)

### Backend — models & DB

1. **`backend/src/strata/models/trace.py`** (NEW) — mirror `models/sourcing_gap.py`.
   - `TraceStatus(StrEnum)`: `ok | error`.
   - `ToolCall(BaseModel, from_attributes=True)`: `id, org_id, session_id|None,
     seq, created_at, tool, args (dict), args_truncated: bool, result_summary
     (dict|None), result_sha256: str, result_truncated: bool, status, duration_ms,
     error_code|None`.
   - `TraceSession(BaseModel)`: `session_id, org_id, created_at, last_seen_at,
     call_count, reasoning: str|None, outcome: str|None` (outcome = a coarse
     tag the reasoning tool can set: `ok|unsourced|unverifiable|error|flagged`).

2. **`backend/src/strata/db/models.py`** (EDIT) — add `ToolTraceRow` +
   `TraceSessionRow` SQLAlchemy rows next to `SourcingGapRow`. Columns match
   migration 018 below.

3. **`backend/alembic/versions/018_tool_traces.py`** (NEW) — **copy 017 verbatim**,
   two tables:
   - `tool_traces`: `id, org_id, session_id(null), seq, created_at, tool,
     args (JSONB), args_truncated, result_summary (JSONB null), result_sha256,
     result_truncated, status, duration_ms, error_code(null)`. Indexes:
     `(org_id, session_id, seq)`, `(org_id, created_at)`, `(org_id, status)`.
   - `trace_sessions`: `session_id (pk-ish, unique per org), org_id, created_at,
     last_seen_at, call_count, reasoning (Text null), outcome (null)`. Unique
     `(org_id, session_id)`.
   - **RLS on both, identical to 017**: `ENABLE` + `FORCE`, closed
     `*_tenant_isolation` policy (`org_id = current_setting('app.org_id', true)`,
     `USING` + `WITH CHECK`), additive `*_admin_read` `FOR SELECT` policy
     (`current_setting('app.is_admin', true) = 'on'`). The entrypoint already
     auto-runs migrations on boot, so 018 lands on redeploy.

4. **`backend/src/strata/db/traces.py`** (NEW) — mirror `db/sourcing_gaps.py`
   (org-scoped session passed in; tool owns `org_session_scope`):
   - `record_trace_safe(*, org_id, session_id, seq, tool, args, result, status,
     duration_ms)` — fire-and-forget on its own `org_session_scope` (mirror
     `record_audit_safe`, `db/audit.py:64`): canonicalize+hash result, build
     summary, truncate oversized fields, `INSERT`; then upsert the
     `trace_sessions` row (`call_count += 1`, `last_seen_at = now()`); then prune
     sessions beyond `STRATA_TRACE_MAX_SESSIONS` for that org. Bare `except` —
     **never raises into the call path**.
   - `record_reasoning(session, *, org_id, session_id, reasoning, outcome)` —
     upsert the session row's reasoning (`INSERT … ON CONFLICT (org_id,
     session_id) DO UPDATE`, mirror `record_gap`).
   - `list_sessions / get_session_calls / admin_list_sessions /
     admin_get_session_calls` — mirror `list_gaps` / `admin_list_gaps` exactly,
     newest-first, status/outcome filters, RLS doing isolation.
   - `next_seq(session, org_id, session_id)` — `SELECT coalesce(max(seq),0)+1`.
     (Concurrency: two calls racing for the same seq is benign — seq is for
     ordering display/replay, ties broken by `created_at`; we do not need a hard
     unique on seq.)
   - `purge_sessions(session, *, before|session_id)`.

### Backend — MCP server wiring

5. **`backend/src/strata/mcp/context.py`** (EDIT) — add
   `current_trace_session: ContextVar[str | None]` + a `current_trace_session_id()`
   accessor, exactly alongside `current_principal`.

6. **`backend/src/strata/mcp/server.py`** (EDIT) — in `_call_tool` (line 106):
   - capture `t0 = time.monotonic()` before dispatch (the module already imports
     `time`), compute `duration_ms` after.
   - after the existing `await _audit_call(...)` (line 134), add
     `await _trace_call(name, arguments, status, result_or_summary, duration_ms)`.
   - `_trace_call` (NEW, mirror `_audit_call` at 142): early-return unless
     `settings.trace_capture_enabled`; resolve `org = current_org_id()`,
     `session_id = current_trace_session_id()`; compute `seq` and call
     `record_trace_safe`. Wrapped in bare `except` — capture never breaks a call.
   - `run_stdio` (line 163): set `current_trace_session` to `uuid4().hex` once so
     a local stdio session groups.

7. **`backend/src/strata/api/mcp_auth.py`** (EDIT — the middleware that sets
   `current_principal`) — also read `X-Strata-Trace-Session` and set
   `current_trace_session` around the request. (Confirm exact filename during
   build; it is the `McpAuthMiddleware` referenced in `server.py`'s docstring.)

8. **`backend/src/strata/mcp/trace_tools.py`** (NEW) — mirror
   `sourcing_gap_tools.py`:
   - `async def record_session_reasoning(reg, *, payload)` — `[WRITE]`. Refuses
     over stdio with `no_tenant` when `current_principal is None` (same guard as
     `report_sourcing_gap`). `payload: {session_id?, reasoning, outcome?}`. If
     `session_id` omitted, use `current_trace_session_id()`. Opens
     `org_session_scope(org)`, calls `record_reasoning`. Returns
     `{recorded, session_id, outcome}`.

9. **`backend/src/strata/mcp/tools.py`** (EDIT) — register one tool (26 → 27):
   - `_h_record_session_reasoning` handler (mirror `_h_report_sourcing_gap`,
     line 924).
   - `TOOLS["record_session_reasoning"]` entry with `_WRITE` annotation
     (mirror the `report_sourcing_gap` entry, line 1169).
   - In `resolve_market` / `verify_market_claim` miss payloads (the `next_action`
     hints already present near line 313), optionally add a nudge to call
     `record_session_reasoning` so the agent opts in. *(Light touch; the auto tier
     is load-bearing, this is additive — brainstorm "Dependencies/assumptions".)*

10. **`backend/src/strata/mcp/schemas.py`** (EDIT) — add `RECORD_SESSION_REASONING`
    inputSchema + an output schema entry, mirroring the gap schemas.

### Backend — config

11. **`backend/src/strata/config.py`** (EDIT, near `portfolio_enabled` line 117) —
    add: `trace_capture_enabled: bool = False`,
    `trace_max_sessions: int = Field(default=200, ge=1)`,
    `trace_max_field_bytes: int = Field(default=65536, ge=1024)`,
    `trace_full_results: bool = False`. Env: `STRATA_TRACE_CAPTURE`,
    `STRATA_TRACE_MAX_SESSIONS`, `STRATA_TRACE_MAX_FIELD_BYTES`,
    `STRATA_TRACE_FULL_RESULTS` (the settings prefix is already `STRATA_`).

### Backend — CLI

12. **`backend/src/strata/cli.py`** (EDIT) — add a `traces_app = typer.Typer(...)`
    sub-app + `app.add_typer(traces_app)`, mirroring `gaps_app` (line 1375):
    - `traces list [--org|--all] [--outcome] [--top N]` — mirror `gaps_list`;
      `--all` uses `admin_session_scope`, prints `session_id · calls · outcome ·
      last_seen`.
    - `traces show <session_id> [--org]` — ordered calls (`seq tool status ms`) +
      the reasoning block.
    - `traces export <session_id> --org <o> [--out <path>]` — writes the ordered
      calls + reasoning to `backend/tests/fixtures/traces/<session>.json` (AC-1.2).
    - `traces replay <session_id|--fixture <path>>` — **the new logic** (see below).
    - `traces purge --org <o> [--before <date>]` — admin/manual retention.

### Backend — replay harness (the one genuinely new algorithm)

13. **`backend/src/strata/traces/replay.py`** (NEW) — pure, offline:
    - Load a captured session (from DB or a fixture JSON).
    - Build a **registry-first, offline** registry (`STRATA_OFFLINE=1` semantics;
      force live connectors OFF so replay is deterministic — reuse the
      `STRATA_MCP_LIVE_CONNECTORS` gate, default off during replay).
    - For each captured call in `seq` order: invoke `call_tool(reg, tool, args)`
      (await if awaitable, exactly as `server.py:113-117` does), canonicalize +
      `sha256` the fresh result, compare to the captured `result_sha256`.
    - Emit a `ReplayReport`: per-call `{tool, match: bool, captured_hash,
      fresh_hash, captured_summary, fresh_summary}` and an overall pass/fail.
      `traces replay` prints it and exits non-zero if any call diverged (the
      regression signal, AC-1.3) — so it's CI-usable.
    - **Skip/flag** write tools (`_WRITE`-annotated) on replay by default
      (`--include-writes` to override) so a replay doesn't mutate org data; their
      divergence is reported as `skipped`, not a false regression.

### Tests (mirror `tests/test_mcp_*` + `tests/test_*gap*`)

14. **`backend/tests/test_trace_capture.py`** (NEW):
    - capture writes a row per dispatched call; off-by-default (no rows when
      `trace_capture_enabled=False`); a raising `record_trace_safe` never breaks
      the tool call (AC-1.5).
    - RLS isolation: org A cannot read org B's traces; admin GUC sees both
      (AC-1.6) — mirror the gap/feedback RLS tests.
    - `record_session_reasoning` stitches reasoning to a session; refuses over
      stdio `no_tenant` (AC-1.4).
    - retention prune keeps ≤ N sessions/org; field truncation flagged.
15. **`backend/tests/test_trace_replay.py`** (NEW):
    - export → replay round-trips green on unchanged code (AC-1.2/1.3);
    - a deliberately mutated result (monkeypatch a handler) makes replay report
      the divergence and exit non-zero;
    - write tools are skipped, not mutated, on default replay.
16. **`backend/tests/fixtures/traces/`** (NEW dir) — one checked-in golden fixture
    produced by `traces export` as the canonical example.

### Docs

17. **`docs/architecture/MCP-DIAGRAMS.md`** (EDIT) — add the trace-capture loop
    diagram (dispatch → tracer → table → replay/export) to the existing diagram set.
18. **`CLAUDE.md`** (EDIT, Repo-state block) — note the new tool (27), migration
    018, the `STRATA_TRACE_CAPTURE` gate, and the `strata traces` CLI.
19. **`CHANGELOG.md`** (EDIT) — `[Unreleased]` entry.

---

## Acceptance-criteria → work mapping

| AC | Where it's satisfied |
|---|---|
| 1.1 list sessions + ordered calls | `traces list` / `traces show` (#12) over `db/traces` readers (#4) |
| 1.2 export golden fixture | `traces export` (#12) → `tests/fixtures/traces/` (#16) |
| 1.3 replay reports divergence | `traces/replay.py` (#13), `traces replay` exits non-zero on diff |
| 1.4 agent submits reasoning | `record_session_reasoning` MCP tool (#8/#9), stitched in `trace_sessions` (#3) |
| 1.5 off-by-default, fire-and-forget, never breaks a call | `trace_capture_enabled` gate (#11) + bare-except `_trace_call`/`record_trace_safe` (#4/#6) |
| 1.6 org-scoped RLS + admin GUC | migration 018 RLS = 017 (#3); admin readers (#4); tests (#14) |

---

## Build order (vertical slice first, then breadth)

1. **Migration 018 + models + `db/traces.py` + config flag** — the substrate.
2. **`_trace_call` wrapper + contextvar + middleware header** — capture works
   (verify a row lands with the gate on; nothing when off).
3. **`record_session_reasoning` tool** (26 → 27) + schemas + handler.
4. **`traces list/show`** — prove we can read real captured sessions.
5. **`traces export` + a checked-in fixture.**
6. **`traces/replay.py` + `traces replay`** — close the loop; non-zero on diff.
7. **`traces purge` + retention prune.**
8. **Tests green, pyright/ruff clean, docs + CHANGELOG.**

Each step is independently testable; steps 1–4 alone already deliver AC-1.1/1.4/1.5/1.6.

## Verification

`cd backend && uv run pytest && uv run pyright && uv run ruff check . && uv run ruff format --check .`
plus a manual `STRATA_TRACE_CAPTURE=1` round-trip: drive 3–4 MCP calls →
`strata traces list` shows the session → `strata traces show` shows the ordered
calls → `strata traces export` writes the fixture → `strata traces replay` is
green → monkeypatch a handler → `replay` goes red + non-zero.

## Risks / watch-items

- **Stateless transport + session grouping (D1)** — the one real unknown; the
  contextvar+header approach is sound but the exact middleware file (#7) must be
  confirmed to be the same one setting `current_principal`. If the harness never
  sends the header, sessions group only over stdio and via the reasoning tool's
  explicit `session_id` — still enough for AC-1.1–1.4, just less automatic
  grouping on hosted.
- **Result size / private data (D4)** — mitigated by gate-off-default + size cap
  + RLS; flagged as a conscious trade, not silent.
- **Replay determinism** — replay must force connectors off and run registry-first,
  else network variance reads as a false regression (handled in #13).

## Follow-on (NOT this PR)

**Direction 2 — demand-ranked connectors.** Once real traces accumulate (needs the
prod redeploy off stale v0.11.0 so the gap queue gets live demand), the
trace+gap ranking picks the top-1 zero-coverage vertical
(market-research-tools or semiconductor) and we build that connector end-to-end:
queue → connector → `promote --from-ingest` → gap flips `sourced` → first-time
query resolves sourced (AC-2.1–2.4 in the brainstorm). Planned separately.
