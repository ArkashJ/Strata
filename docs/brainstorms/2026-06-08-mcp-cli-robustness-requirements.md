# Requirements — trace-capture for testing + data-source robustness

**Date:** 2026-06-08
**Scope:** Deep (two linked directions). MCP + CLI only — the web UI is frozen.
**Status:** brainstorm output, ready for `/ce-plan`.
**Related:** [`docs/plans/2026-06-07-mcp-cli-research-engine-spec.md`](../plans/2026-06-07-mcp-cli-research-engine-spec.md) (the four-pillar spec; this doc deepens Pillar B + a new testing capability).

---

## Problem

Two failure modes are holding the MCP+CLI research engine back, and they're linked:

1. **We can't test against reality.** Our tests are hand-written fixtures. But the
   product is driven by *agents* making tool-call sequences we don't anticipate.
   When an analyst's agent gets a wrong or low-quality answer, we have no captured
   record of the **tool calls + arguments + results + the agent's reasoning** that
   produced it — so we can't turn a real failure into a regression test, and we
   can't measure whether a change actually improves real-world answer quality.

2. **First-time queries produce inaccurate answers** because the data bank is
   shallow (87/100 concepts rest on ≤2 sourced primitives) and whole verticals
   have zero coverage (market-research-tools, semiconductor fab capacity). The
   sourcing-gap queue (shipped, PR #135) now *measures* the misses — but nothing
   yet *closes* them: no connectors target the gaps, and there's no loop from
   "ranked gap" → "new sourced primitive."

These are linked because **the trace data from (1) is the highest-signal input to
(2)**: real tool-call traces show exactly which queries miss, what roles go
unsourced, and which gaps recur — a far better connector backlog than guessing.

## Who it's for

- **Primary — you (the owner/operator):** you need to (a) see what real agent
  sessions did and where they produced bad answers, and (b) turn the demand signal
  into the right next connector. Today both are blind spots.
- **Secondary — the analyst's agent (Claude et al.):** benefits indirectly — better
  coverage and a tighter quality loop mean fewer "unsourced — verify" dead-ends.

## Why now

The feedback loop, gap queue, and admin governance just merged. The gap queue
produces a demand signal that is currently *unconsumed*. And as the tool surface
grows (26 tools), hand-written tests can't keep pace with real agent behavior.
Capturing traces now — while usage is small and we control the harness — is far
cheaper than retrofitting it after a customer hits a bad answer we can't reproduce.

---

## Direction 1 — Trace-capture for testing

### What gets captured

The MCP server sees every tool call. The agent's reasoning it does *not* see unless
the agent submits it. So capture has two tiers:

| Tier | What | Mechanism | Cooperation needed |
|---|---|---|---|
| **Automatic** | tool name, arguments, result summary, ok/error, duration, org, session, sequence | server-side wrapper around tool dispatch | none — always on when enabled |
| **Agent-submitted** | the agent's reasoning / chain-of-thought / plan for a session, free-form | an MCP tool the agent calls | the agent opts in (prompted to) |

The automatic tier is the load-bearing one for regression testing (a deterministic
tool-call sequence can be replayed). The agent-submitted tier adds the *why* — the
context the server structurally can't see — which is what makes a captured failure
*diagnosable*, not just reproducible.

### What we do with it

1. **Export a session as a golden fixture** — a captured tool-call sequence + results
   becomes a versioned test fixture (`strata traces export <session>`).
2. **Replay regression** — re-run a captured sequence against current code and diff
   the results (`strata traces replay <session>`). "Does this market still size the
   same way / is this primitive still sourced?" Catches silent regressions a
   hand-written test wouldn't anticipate.
3. **Quality review** — list/show sessions that ended in a miss (`unsourced=true`,
   `unverifiable`, an error, or a feedback flag) so the owner can see real bad
   answers and their full context.

### Acceptance criteria (business)

- **AC-1.1** — As the owner, I can list real MCP sessions (newest-first, filter by
  org / outcome) and see, for any session, the exact ordered tool calls with their
  arguments and result summaries.
- **AC-1.2** — As the owner, I can export any captured session to a golden test
  fixture and check it into the repo.
- **AC-1.3** — `strata traces replay <session>` re-runs the captured tool-call
  sequence against current code and reports which calls produced a *different*
  result than when captured (the regression signal).
- **AC-1.4** — An agent can submit its reasoning for a session via an MCP tool; that
  reasoning is stored alongside the tool-call trace and shown in `traces show`.
- **AC-1.5** — Capture is **off by default**, gated by an env flag, and is
  fire-and-forget — tracing never slows or breaks a real tool call.
- **AC-1.6** — Traces are org-scoped (RLS); the owner sees across orgs via the
  existing admin GUC. Captured arguments/results may contain org-private data, so
  isolation must hold exactly as it does for feedback/gaps.

### Non-goals (Direction 1)

- Not a full observability/APM product (no latency dashboards, no tracing UI — web
  is frozen). Traces are for *testing + quality review*, surfaced through CLI/MCP.
- Not capturing the end user's raw prompts unless the agent chooses to submit them.

---

## Direction 2 — Data-source robustness (closing the gaps)

### The loop we're completing

```
real traces + gap queue ─▶ ranked demand (which sourced numbers are missing, by frequency)
        │
        ▼
   build the connector that fills the top gap ─▶ ingest ─▶ promote ─▶ gap marked sourced
        │
        ▼
   next first-time query for that vertical now resolves SOURCED (not "unsourced — verify")
```

The gap queue (shipped) is the left edge; the connectors are the right edge; this
direction builds the connectors **driven by the ranked queue**, not by guesswork.

### Target verticals (demand-ranked, not breadth-for-its-own-sake)

The spec (§4.3) names candidates; the gap queue will reorder them by real demand.
Initial high-confidence targets where customers hit walls today:

- **Market-research-tools market** — no sourced coverage at all. Candidate sources:
  USPTO PatentsView (free), Census County Business Patterns deepening (software
  vendors by NAICS), G2/Capterra-style category data (vendor counts as adoption
  proxy). Honest limit: vendor *revenue* (Gartner/IDC/Forrester) is paywalled — we
  source the *structural denominators* (firm counts, employment, patents) and let
  frameworks compose them, never fabricating a market-size number.
- **Semiconductor design/fab** — today only Comtrade IC imports + EDGAR company
  financials. Candidate sources: PatentsView (design starts proxy), Census/BLS
  semiconductor NAICS employment + establishments, EIA (fab energy as a capacity
  proxy). Honest limit: true wafer-fab-capacity is proprietary — source what's
  public, gap the rest.

### Novel-query handling (the "first time we see X" answer)

Already half-built: `resolve_market` returns machine-readable `unsourced=true` +
points the agent at `report_sourcing_gap`. This direction adds the *fill* side:

- A connector that produces committed primitives for a gap's `resource_target`
  flips that gap to `sourced` and links the primitive (the `mark_gap_sourced` /
  `strata gaps resolve` loop, shipped).
- **Open question:** should a novel query *auto-attempt* a live connector pull
  (behind a gate) when a matching `resource_target` exists, or stay
  agent-driven (the agent reports the gap, a human/operator sources it)? See
  Outstanding Questions.

### Acceptance criteria (business)

- **AC-2.1** — At least one previously-zero-coverage vertical from the top of the
  gap queue (target: market-research-tools or semiconductor) gains ≥3 sourced
  primitives committed to `data/primitives/`, each hash-pinned and validated.
- **AC-2.2** — Each new connector smoke-passes live (`strata test-connectors --live`)
  and declares its `arg_sets` in the ingest manifest so `ingest run` →
  `promote --from-ingest` produces *committed* primitives (not capability-only).
- **AC-2.3** — Sourcing a gap's `resource_target` flips the matching open gaps to
  `sourced` and links the new primitive — the queue→fill loop is closed end-to-end.
- **AC-2.4** — A first-time query in a newly-covered vertical that previously
  returned `unsourced=true` now returns a sourced scenario tree.

### Non-goals (Direction 2)

- Not fabricating paywalled market-size numbers (Q20). We source structural
  denominators and let frameworks compose; a number we can't source stays a gap.
- Not building every connector — only the demand-ranked ones the queue surfaces.
- Not re-opening the connector-vs-frameworks strategy debate; the strategy review
  said "divest connectors as commodity," and this honors it by building *only*
  what ranked demand justifies.

---

## Recommended sequencing

1. **Direction 1 first (trace-capture).** It's the instrument. Once we capture real
   traces, the gap queue's ranking gets dramatically better signal, so Direction 2's
   connector choices are evidence-driven rather than guessed. Trace-capture is also
   self-contained (no external API dependencies) and de-risks every later change by
   giving us replay regression.
2. **Direction 2 second (connectors), driven by the ranked queue + traces.** Build
   the top-1 vertical end-to-end (queue → connector → promote → gap closed →
   sourced answer) as a vertical slice before fanning out to more connectors.

Rationale: building connectors first is the tempting move, but without the trace +
demand signal we'd be guessing which to build — the exact mistake the strategy
review flagged. The instrument pays for itself immediately.

---

## Approaches considered (Direction 1 capture mechanism)

- **A — Wrap the MCP dispatch (recommended).** A tracer around the single
  `call_tool` dispatch records every call fire-and-forget to a `tool_traces` table.
  *Pro:* one chokepoint, automatic, complete, mirrors the existing audit/feedback
  patterns. *Con:* server-side only sees calls, not reasoning (hence the
  agent-submitted tier). *Best when* we want zero-cooperation, complete tool-call
  capture — which we do.
- **B — Reuse `audit_events`.** Extend the existing audit table instead of a new
  one. *Pro:* no new table. *Con:* audit rows are single-action and lack
  sequence/session/args-result shape; replay needs structured ordered calls. Forcing
  traces into audit muddies both. *Rejected* — different shape, different purpose.
- **C — Client-side only (agent submits everything).** No server wrapper; the agent
  reports its whole session. *Pro:* captures reasoning natively. *Con:* depends
  entirely on agent cooperation; misses calls the agent doesn't report; not
  reproducible. *Rejected as the primary* — but its idea becomes the agent-submitted
  tier on top of A.

**Recommendation: A (server wrapper) + the agent-submitted reasoning tier from C.**
Mirrors the proven feedback/gap RLS + fire-and-forget patterns; replay works off the
deterministic server-captured sequence; reasoning enriches it when the agent opts in.

---

## Scope boundaries

**In:**
- Server-side tool-call trace capture (gated, fire-and-forget, RLS-scoped).
- An MCP tool for the agent to submit session reasoning.
- CLI: `strata traces list|show|export|replay`.
- 1 demand-ranked vertical connector built end-to-end, queue→sourced loop closed.

**Deferred for later:**
- More connectors beyond the first vertical (fan out after the slice proves the loop).
- Auto-live-pull on novel queries (gated) — decide after seeing trace volume.
- Trace-based answer-quality scoring / LLM-judge over captured sessions.

**Outside this product's identity:**
- A web trace viewer / observability dashboard (web frozen).
- Capturing raw end-user prompts without agent opt-in (privacy).
- Fabricating paywalled market figures to "fill" a gap (Q20).

---

## Outstanding questions (resolve in planning)

1. **Auto-live-pull vs agent-driven sourcing** for novel queries with a known
   `resource_target` — gate-and-auto, or keep human/operator in the loop? (Affects
   Direction 2 scope + the live-connector gate.)
2. **Trace retention** — cap rows / TTL per org? Captured args+results can be large
   and contain private data. (Likely a row cap + admin purge, mirroring gaps.)
3. **Result-summary fidelity for replay** — store full results (heavy, exact replay)
   vs a hash/summary (light, detects change but not the diff). Recommend: store a
   structural summary + hash; full result only on demand.
4. **First connector pick** — market-research-tools vs semiconductor. Let the gap
   queue's ranking (once trace-fed) decide, or commit now? (Recommend: let 1–2 weeks
   of real traces rank it.)

---

## Dependencies / assumptions

- **Assumes** the agent harness (Claude in the analyst's tool) will call a
  `record_session_trace`-style tool when prompted — unverified until real usage;
  the automatic tier works regardless, so this is additive, not load-bearing.
- **Assumes** PatentsView / Census CBP / EIA remain free + keyless (they are today).
- **Depends on** the shipped sourcing-gap queue (PR #135) and the connector ingest
  pipeline (`ingest run` / `promote --from-ingest`) — both exist.
- **Assumes** prod gets redeployed (currently stale v0.11.0) so the queue actually
  accumulates real demand — otherwise Direction 2's ranking has no live input.
