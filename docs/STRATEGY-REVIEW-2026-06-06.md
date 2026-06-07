# Strata — Strategic Adversarial Review (2026-06-06)

A four-lens adversarial review (value-prop, long-term architecture, data-moat/GTM,
systemic integrity), commissioned because the owner saw "tons of short-term
vulnerabilities but no long-term thinking, misses on value props." All four lenses
ran independently against the 41 mermaid flows in
[`architecture/DIAGRAMS.md`](architecture/DIAGRAMS.md), the data bank, and the code.
**They converge on one reframe.** Every finding is a GitHub issue on the
[Strata project](https://github.com/users/ArkashJ/projects/5) (#93–#108).

---

## The one reframe (all four lenses agree)

> **Strata is competing on the losing axis — data depth / "every number is sourced" —
> while sitting on the winning one: the honest, recipe-driven _verification layer for
> AI-generated market claims_, distributed via MCP.**

Three moves follow:

1. **Own the defensible-assumption layer, not the sourced-primitive layer** (#94, #95).
   A VC doesn't pay for the BLS headcount (free, anyone pulls it). They pay for the
   defensible **join coefficient** — capture rate, ACV, adoption, replacement. In
   Strata those are exactly the `community-modeled` primitives that self-cite their
   own YAML. So "every number is sourced" is technically true and strategically
   hollow: the cheap numbers are sourced to BLS, the expensive ones to themselves.
   And the honesty fence makes the **most valuable numbers the least trustworthy** —
   an existential contradiction. **Fix:** turn the binary MODELED fence into a
   **graded confidence model** (corroboration count, mandatory range, an
   "as-reasoned-by" defense, sensitivity weight) — "disagreement gets a page" →
   "assumption gets a defense." **Do this before PR4 hardens the binary fence.**

2. **Re-thesis to the verification layer** (#96). Every LLM hallucinates TAMs;
   someone must be the sourced oracle an agent calls to check "is this $50B
   defensible?" Strata already has the rare asset: sourced primitives + the Q20
   no-LLM-number fence + content-hash pinning + an MCP transport + a
   convergence/disagreement engine. Ship `verify_market_claim(claim, market) →
   {supported | unsupported | spread, sources}` as the flagship MCP tool. This turns
   the "0 proprietary data / can't out-depth Statista" weaknesses into non-issues
   (verification needs coverage of the _claim's_ primitives, not 1M datasets), and
   **agents become the contributor flywheel humans won't be** (a VC won't publish
   their alpha; an agent has no such incentive).

3. **Invest in frameworks + the trust fence; divest from connectors** (#104, #107).
   Measured today: **280 primitives (52% raw gov-API passthrough), 0 first-party.**
   Frameworks: **6 canonical lens shapes + 19 subframeworks** (the old "5 → 25
   distinct frameworks" goal was reframed 2026-06-07 — see
   [`docs/plans/2026-06-07-frameworks-taxonomy-reframe.md`](plans/2026-06-07-frameworks-taxonomy-reframe.md);
   there are only 6 distinct shapes, the rest are realism-modifier specializations,
   now enforced by the validator). The fork-proof assets are the parameterized+sourced **recipes** and the
   verification fence — not the data. One org-private first-party feed beats all 23
   public connectors. Pick the **single-TAM-for-an-IC-memo beachhead** (#105); ship a
   real **private-first contributor incentive** or drop "community" from the pitch
   (#106). Measure success in "TAMs pasted into an IC memo," not primitive count.

---

## Company-enders (systemic integrity — fix before real customer data)

The product's thesis is "provenance is the product," so a correctness bug and a
trust bug are the same bug, and the failure mode is a silent, plausible-looking lie.

- **#99 — dual-purpose `tam_outputs` RLS fails OPEN to public.** On an unset
  `app.org_id`, `current_setting(...)` is NULL so only the `org_id IS NULL` disjunct
  survives — a path hitting the table via the wrong (non-scoped) session silently
  serves/accepts global rows; a tenant save that lands `org_id=NULL` becomes
  world-readable. `audit_events` fails _closed_ under the identical bug — opposite
  behavior, same root cause. **One fund seeing another's portfolio is terminal for
  this audience.** Needs a cross-tenant **property test in a blocking gate**, a schema
  invariant (`FORCE RLS` + `WITH CHECK == USING` on every `org_id` table), and making
  the wrong session factory _impossible_, not just discouraged.
- **#100 — the snapshot pin is decorative.** `demo-bls-software-developers-us-2024`
  is a _genuinely regulator-sourced_ BLS number carrying the same fake `d3d3…d3` hash
  as the modeled rows. "Their SHA-256-pinned badge is fake" is currently true and
  demonstrable. **Fix:** snapshot is a FK to stored bytes — NULL or a hash that
  recomputes equal, no third state; tier derived from evidence; CI invariant.
- **#101 — Clerk inert-default silently = no auth in prod**; no iss/aud pinning by
  default; the org claim is the unpinned tenant key. Needs a fail-closed boot
  invariant.
- **#102 — quarantine enforced on the YAML path only, not the DB path** (prod) —
  social/community data can feed a TAM in prod (Q20 violation). Make quarantine a
  property of the record via one shared constant, tested on both load paths.
- **#103 — modeled→sourced laundering** via hand-edited `tier`; the citation
  allowlist drifts permissive (`.gov`/`.edu` blanket). Couple tier to evidence
  structurally.
- **#108 — billing-blocked CI removes the net under all of the above.** Local-green
  is not a control; the enforced invariant set silently shrinks to "whatever the last
  committer ran." Minimum guardrail: the cross-tenant + snapshot tests in a blocking,
  off-laptop gate **before PR1 ships to real data.**

---

## Long-term architecture (substrate rot — #97, #98)

Five risks share one root cause: **an in-memory, single-process, read-mostly,
single-author substrate, with every roadmap PR piling multi-tenant / multi-writer /
agent-concurrent / contributor-write features on top without changing the substrate.**

- The Registry is loaded **once** per process from YAML at boot and never refreshed —
  a contributor/promote/ingest/`/me/primitives` write lands in Postgres but is
  invisible to the running worker (and across workers). No reload path exists.
- **#98 (affects the PR1 in flight): `user_primitives` is Postgres-only and invisible
  to the evaluator** — `/build` reads the public-only in-memory registry, so a user's
  private primitive can **never feed a TAM.** "My Bank" can't participate in a bank's
  whole point. Fix: the build's session must be RLS-scoped so `org_id IS NULL OR
  org_id = caller` returns public + private in one query.
- Permalinks are stored process-local (FIFO cap 512); only _promoted_ TAMs reach
  Postgres — so a shared `/build/<hash>` link is a coin-flip under multiple workers.
- **Highest-leverage move:** do the substrate work _first_ — Postgres as the single
  runtime source of truth, YAML → seed/fixtures asserted equal by CI, the registry as
  a query-backed repository — **before** PR1–5 pour more features onto sand.

---

## Demo-vs-reality (for tomorrow) — #107

- The convergence/triangulation banner (what PRODUCT.md leads with) is **dark for 92%
  of the library** — only ~8 concepts have ≥2 competing measurements. Demo a curated
  concept; the 2nd off-script query collapses to a single method or a connector gap.
- The flagship report is **42% coverage** (27 answers / 37 gaps), gaps clustering on
  the decision-driving questions → reads "incomplete" to an LP.
- PR2's "watch it build" reveal animates a result computed in one synchronous call —
  the program's own honesty principle calls faked streaming "theater."
- **For the demo:** pre-pick the query, ensure a real degrade-to-sourced-skeleton
  fallback for off-script queries, and lead with a concept that actually triangulates.

---

## "Strings" / UI copy & API recommendations (from the review)

- **Copy:** the load-bearing string is the MODELED banner. "MODELED — do not cite as
  fact" is a trust-destroyer; replace with "MODELED — triangulates N analyst notes;
  range $X–$Y; moves the answer Z%" (ties to #95). Never render a citation affordance
  on a modeled number; never render "SHA-256 pinned" except per-row when a blob backs
  it (#100).
- **API:** the long-term flagship is an MCP `verify_market_claim` tool with a
  **versioned provenance contract** (`/mcp/v1`) as the core domain output, with the
  human UI + existing tools as thin consumers (#96). Land `/mcp` auth + per-agent
  `org_id` before any agent write tool (#96, #99).

---

## Program status (2026-06-06)

| PR | Scope | Status |
|----|-------|--------|
| PR 0 | trust quick-wins + doc/architecture recovery | ✅ merged (#91) |
| PR 4 | 109-question sourced-only report engine | ✅ merged (#92) |
| — | 41-diagram mermaid architecture set | ✅ on `main` |
| PR 1 | multi-tenant workspace + dual-purpose RLS | 🔭 in flight (see #98, #99) |
| PR 2 | Build Studio live tree | ⬜ (see #107 — descope the reveal) |
| PR 3 | dashboards + Gartner charts + real PDF | ⬜ |
| PR 5 | breadth to v1.0 (frameworks, connectors, embeddings) | ⬜ (re-weight per #104) |

CI is **billing-blocked**; PRs 0 + 4 merged on local-green only (#108).

---

## The honest bottom line

The engineering instincts are genuinely good — the soft-data fence, scope guard,
unit signatures, Q20 quarantine are real and differentiated. But PR0–5 is a
**quality-and-completeness program disguised as a strategy program**: it makes a
mediocre value prop more polished without making it defensible. The data bank is not
the moat. **The honest, recipe-driven verification of market claims — served to
agents — is**, and Strata is one reframe away from owning it.
