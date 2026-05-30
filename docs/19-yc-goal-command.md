# Strata — YC `/goal` Command (run all waves)

Paste one of the two blocks below into Claude Code. Both drive off the
executable spec in [`docs/18-yc-execution-spec.md`](18-yc-execution-spec.md)
(acceptance criteria + signatures + schemas), the 116-rec backlog in
[`docs/16`](16-adversarial-yc-readiness-review.md), and the wave plan in
[`docs/17`](17-yc-remediation-plan.md).

**Pre-resolved decisions** (baked into the command so it runs without stalling):
- `simple-icons` is **approved** for the BrandIcon set (Wave 5C).
- Recommended run order: **0 → 5A → 2 → 1 → 3 → 5B → 4** (demo + MCP land first;
  customer-data connectors come *after* the auth/RLS substrate).

---

## A) Full single command — runs ALL waves (≈4.7k chars)

Use this if your input box has no ~4000-char limit. It is the most complete.

```text
/goal Execute the FULL Strata YC remediation to the letter of docs/18-yc-execution-spec.md — ALL waves, end to end, in this order: Wave 0 → Wave 5A → Wave 2 → Wave 1 → Wave 3 → Wave 5B → Wave 4. Drive each wave off its End Goal, Acceptance Criteria (ACxx), Technical Design, and TODO in docs/18. Treat docs/16 (116-rec backlog) and docs/17 (wave sequencing) as supporting context. A wave is DONE only when every one of its ACxx criteria passes a real, written test/assertion under the Global Definition of Done. Pre-approved: add the simple-icons dependency for the Wave 5C BrandIcon set. Wave 5B (private OAuth data connectors) MUST run after Wave 3 (auth + Postgres RLS) — never before.

GLOBAL GATE (must stay green after EVERY wave): uv run pytest && uv run pyright && uv run ruff check . && uv run ruff format --check . ; cd web && (bun run build || npm run build) && (bun run typecheck || npx tsc --noEmit). Open ONE PR per wave; bump VERSION; add a CHANGELOG [Unreleased] block. Honor all CLAUDE.md hard rules: no invented figures, no LLM-projected primitives (Q20), composites=same-unit set-ops only (Q3), frameworks have no scalar defaults (Q15), annotations never affect math (E1), citations sha256-pinned (Q5), don't rename the project.

EXECUTION MODEL per wave: run a workflow — (1) implement each TODO with TDD (write the ACxx test first, watch it fail, implement, watch it pass); (2) fan out adversarial verifier subagents using the matching lens(es) from docs/16 and confirm the targeted findings flip FAIL→PASS; (3) fix what they surface; (4) only then open the PR. After each wave, STOP and report an ACxx pass/fail table before starting the next wave (I stay in the loop but you do not wait for my input to continue).

WAVES (full detail/signatures/schemas in docs/18):
- WAVE 0 demo-blockers: persist TAMs so /tam/<hash> resolves (reg.tam_outputs, FIFO-cap); resolver registry-first → concept hit returns a multi-scenario tree (resolver/match.py); novel path emits estimate_kind=single_method + honesty banner, never a bare point; quarantine 202 prediction_market primitives to data/signals/ + dual stats count; seed 5-8 TRIANGULATED demo concepts (competing_concepts wired, ≥2 independent sources, independence_score>0); /tam/[hash] SSR + OpenGraph + opengraph-image.tsx.
- WAVE 5A Strata MCP server (mcp/server.py over the existing engine): stdio + /mcp ASGI transport; tools search_concepts/get_primitive/list_frameworks/size_tam/resolve_market return SOURCED, sha256-pinned payloads; read-only; hosted endpoint behind the (later) Wave-3 key but ship stdio now; README `claude mcp add` snippet.
- WAVE 2 motion/craft: recompute count-up + node pulse; pyramid right-click context menu + 250ms hover ghost card (useHoverIntent); sensitivity TornadoChart + GET /build/{slug}/sensitivity; prefers-reduced-motion gates all motion; CLS<0.1.
- WAVE 1 AI defensibility: citation-host allowlist (resolver/citations.py) — zero fabricated/strata.internal hosts; tier derived from the Source record, never the LLM; sha256 snapshot integrity enforced on load (IntegrityError + strata verify-integrity); verifier/critic pass → dark_estimate banner on outliers; resolver eval harness (backend/src/strata/evals + golden.yaml ≥20, CI baseline ≥0.8); end-to-end unit guard; freshness_sla_days + StaleChip.
- WAVE 3 substrate: API-key auth (api/auth.py + api_keys table); token-bucket rate-limit on /resolve → 429 + Retry-After; usage_events metering + GET /usage; non-wildcard CORS in prod; request-id + structured logging + /metrics or OTel; org_id + Postgres RLS cross-tenant isolation.
- WAVE 5B inbound OAuth connectors (connectors/saas/, REQUIRES Wave 3): HubSpot or Stripe end-to-end first; OAuth tokens encrypted + org-scoped; tenant data → tier:first_party PRIVATE primitives in an org namespace, excluded from /browse + other tenants, feeding the same evaluator (private banner); disconnect purges tokens + tombstones data; a 2nd stub provider proves the framework is generic. Then build Wave 5C: simple-icons BrandIcon registry (all SaaS + 15 gov vendors + Anthropic), /integrations gallery grouped Inbound/Outbound/Public-data-bank with status, "old way vs new way" comparison card, and an animated sources→Strata-engine→verifier→outputs PipelineFlow (ReactFlow + existing motion, reduced-motion safe).
- WAVE 4 GTM/moat: sitemap.xml + SSR promoted /tam pages (crawlable); /embed/tam/[hash] iframe widget; POST /contribute validator-gated (no low-tier auto-publish); doc-count consistency CI (VERSION==pyproject==tag, README counts match strata stats).

END STATE / FINAL GATE: complete the Cross-wave checklist in docs/18; re-run the 11-lens adversarial audit as a workflow; do NOT stop until all waves ship green AND the re-audit overall score is ≥80 AND all five existential risks (single-point resolver, empty moat, dead share links, Kalshi padding, no company substrate) are flipped. Finish with a final ACxx scorecard across every wave.
```

---

## B) Trimmed single command — same all-waves run, **under 4000 chars** (≈3.1k)

Use this if your input box caps near 4000 chars. The detail still lives in docs/18.

```text
/goal Execute the FULL Strata YC remediation to the letter of docs/18-yc-execution-spec.md — ALL waves in order 0 → 5A → 2 → 1 → 3 → 5B → 4. Drive each wave off its End Goal, Acceptance Criteria (ACxx), Technical Design, and TODO in docs/18; docs/16 (backlog) and docs/17 (plan) are supporting context. A wave is DONE only when every ACxx passes a real written test under the Global Gate. Pre-approved: add simple-icons for the Wave 5C BrandIcon set. Wave 5B (private OAuth data) MUST run after Wave 3 (auth + RLS).

GLOBAL GATE after EVERY wave: uv run pytest && uv run pyright && uv run ruff check . && uv run ruff format --check . ; cd web && (bun run build || npm run build) && (bun run typecheck || npx tsc --noEmit). One PR per wave; bump VERSION; add CHANGELOG [Unreleased]. Honor CLAUDE.md hard rules (no invented figures, no LLM-projected primitives Q20, composites=same-unit only Q3, frameworks no scalar defaults Q15, annotations never affect math E1, citations sha256-pinned Q5, don't rename project).

EXECUTION per wave: run a workflow — (1) implement each TODO with TDD (ACxx test first, fail, implement, pass); (2) fan out adversarial verifier subagents using the matching docs/16 lens(es) to flip findings FAIL→PASS; (3) fix; (4) open the PR. After each wave STOP and report an ACxx pass/fail table, then continue without waiting for me.

WAVES (detail/signatures/schemas in docs/18):
- W0 demo-blockers: persist TAMs so /tam/<hash> resolves; resolver registry-first → concept hit returns a multi-scenario tree; novel path emits estimate_kind=single_method + honesty banner; quarantine 202 prediction_market primitives to data/signals/; seed 5-8 TRIANGULATED demo concepts (independence_score>0); /tam SSR + OpenGraph.
- W5A Strata MCP server: stdio + /mcp transport; tools search_concepts/get_primitive/list_frameworks/size_tam/resolve_market return sourced + sha256-pinned payloads; read-only; README `claude mcp add` snippet.
- W2 motion: recompute count-up + node pulse; pyramid right-click menu + 250ms hover ghost card; sensitivity TornadoChart; reduced-motion gates; CLS<0.1.
- W1 AI defensibility: citation-host allowlist (zero fabricated hosts); tier from Source not LLM; sha256 integrity enforced; verifier → dark_estimate banner; resolver eval harness (golden ≥20, CI baseline ≥0.8); unit guard; staleness chips.
- W3 substrate: API-key auth; token-bucket rate-limit on /resolve; usage metering + GET /usage; non-wildcard CORS; request-id + /metrics; org_id + Postgres RLS isolation.
- W5B OAuth connectors (needs W3): HubSpot/Stripe first; encrypted org-scoped tokens; tenant data → tier:first_party PRIVATE org-namespaced primitives feeding the same evaluator, isolated, disconnect purges; then W5C: simple-icons BrandIcon registry + /integrations gallery (Inbound/Outbound/Public) + old-vs-new card + animated sources→engine→verifier→outputs PipelineFlow.
- W4 GTM: sitemap + SSR promoted /tam pages; /embed widget; POST /contribute validator-gated; doc-count consistency CI.

END STATE: complete the docs/18 cross-wave checklist; re-run the 11-lens audit workflow; do NOT stop until all waves are green AND re-audit score ≥80 AND all five existential risks are flipped. End with a final ACxx scorecard.
```

---

## How it behaves when you run it

```
/goal (all waves)
   │
   ├─ Wave 0 ──> workflow: TDD + adversarial verify ──> PR ──> ACxx table ──┐
   ├─ Wave 5A ─> ...                                                         │ keeps going
   ├─ Wave 2 ──> ...                                                         │ wave→wave
   ├─ Wave 1 ──> ...                                                         │ without
   ├─ Wave 3 ──> ...                                                         │ waiting for
   ├─ Wave 5B ─> (gated on Wave 3) ...                                       │ you, but
   └─ Wave 4 ──> ...                                                         │ reports
                                                                            ─┘ each wave
   FINAL ─> re-run 11-lens audit ─> stop only when score ≥80 & 5 risks flipped
```

- It opens **one PR per wave** so you can review/merge at your own pace.
- It **stops and reports an ACxx pass/fail table** after each wave, then continues
  on its own (the Stop hook keeps it from ending until the final gate is met).
- Interrupt anytime; the per-wave PRs mean no work is lost.
