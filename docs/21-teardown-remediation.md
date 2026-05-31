# 21 — Teardown Remediation Plan

> Companion to [`17-yc-remediation-plan.md`](17-yc-remediation-plan.md) and the
> teardown in [`20-adversarial-teardown.md`](20-adversarial-teardown.md).
> Waves ordered so the **thesis becomes true on the surfaces a partner clicks in
> the first 60 seconds**, then defensibility is made visible, then the analytic
> canvas + forwardable artifact land. Favor surfacing existing substrate over
> net-new builds.

## P0 — Demo-blockers (this week, mostly S)

Make the thesis true on the surfaces a partner clicks in 60 seconds.

| # | Item | Pri/Effort | Addresses |
|---|---|---|---|
| 0.1 | **Persist TAMs**: write `remember_tam()` → `tam_outputs` Postgres table; load in `Registry.from_db` (`registry.py:72,127`) so `/tam/<hash>` survives restart | P0/M | Permalink 404 (blocker #1) |
| 0.2 | Flip `page.tsx:191` Featured-TAM hrefs back to `/tam/<state_hash>`; delete the `/build?q=` workaround (`TamCard.tsx:39-40`) | P0/S | Homepage routes around the artifact |
| 0.3 | Wire `Sidebar.tsx:118-123` to Clerk `useUser` (real name or "Sign in"); **remove `j.vega · verified · 27 contribs`** | P0/S | Fabricated identity (blocker #2) |
| 0.4 | Point footer GitHub link (`page.tsx:336`) at the real repo, or remove it | P0/S | Dead diligence link |
| 0.5 | Strip dev overlays (beach emoji, "1 Issue" pill, "N" circle); un-clip the INDEPENDENCE donut + footer on `/build`; re-capture screenshots | P0/S | "Looks unfinished" |
| 0.6 | Suppress/grey the INDEPENDENCE donut for single-method TAMs; lead honestly with the "not yet triangulated" state | P0/S | Unearned-ring blocker #4 |

## P1 — Defensibility made visible

Surface the math and sources the data already carries.

| # | Item | Pri/Effort | Addresses |
|---|---|---|---|
| 1.1 | Port `CompositionChart`'s "Multiplies to $X" equation footer into `ResolveResultChart.tsx`; add `TierBadge` per bar + clickable `source_url` in tooltip | P1/M | Hidden math/sources (blocker #3) |
| 1.2 | Add independence arc + "triangulated · N methods" badge + source-tier color cue to `TamCard.tsx` (reuse BuildWorkspace donut/motion) | P1/M | Cards look like guesses |
| 1.3 | Seed 5-8 hero concepts with ≥2 **competing measurements** + a second method-family framework each; wire `competing_concepts` | P1/L | Triangulation is claimed, not shown |
| 1.4 | Gracefully degrade `/audit` to a read-only `limit-100` public feed for anonymous/non-prod principals instead of hard-401 | P1/S | Broken trust panel |
| 1.5 | **Honesty pass on tiers**: demote `strata.internal`/`community-modeled` primitives out of the "sourced" surface with a loud MODELED banner; stop labeling modeled numbers "sourced" | P1/M | ASIC analyst's strongest hit |

## P2 — Analytic canvas + the forwardable artifact

Turn the taxonomy browser into the triangulation canvas; ship the one-pager.

| # | Item | Pri/Effort | Addresses |
|---|---|---|---|
| 2.1 | Resolve a TAM (or average across compatible frameworks) on Qual/Quant selection in `GraphView.tsx`, not only `soleConcept` | P2/M | Read-only graph |
| 2.2 | Make `+N more` industry node expandable/searchable; raise node-label contrast | P2/M | 62% of markets hidden |
| 2.3 | Add a **sensitivity/tornado** chart on the existing recompute loop in the `/build` right rail ("which assumption moves the answer most?") | P2/M | "Reads as analyst infra, not a chatbot" |
| 2.4 | Curate 5-8 TAMs that **beat a public source side-by-side** as a printable one-page report with snapshot pins | P2/L | The artifact a partner forwards |
| 2.5 | **Pick the niche & build its value chain**: ingest real semiconductor primitives (SEMI/TrendForce/Omdia wafer-starts, CoWoS capacity, HBM bit-supply, hyperscaler capex) + a supply-constrained framework `min(demand, capacity)` × ASP × yield | P2/L | "Zero chip primitives" — earns the right to size an ASIC TAM |

## The differentiation throughline ("how to shut them up")

1. **Show-your-work receipt** incumbents can't match — equation footer + tier badge + clickable source on every result.
2. **Bottoms-up vs tops-down convergence** as the headline banner ("bottoms-up $X / tops-down $Y / agree 1.2×") — the triangulation VCs spend days assembling by hand and distrust LLMs for.
3. **Defensibility encoded on every card** — independence arc + method badge + source-tier color, so a 5-source concept is visibly distinct from a 1-source guess.
4. **MCP as the agent-era wedge** — "Claude's numbers now carry Strata citations, hash-pinned"; surface MCP-sourced payloads on the share artifact.
5. **Pick a niche and out-source the analyst** — curate TAMs that provably beat a public source, fresher series, visible math, snapshot pins; ship as a forwardable printable report.

## Execution status

- ✅ Pre-work already merged this session: CORS dev-port fix (`755672e`); **source tier/url/snapshot now flow through `primitives_used`** (`5c85931`) — partial credit on 1.1 (data reaches the UI; equation footer still to add).
- ⏭ Starting P0.3 / P0.4 / P0.2 / P0.6 (S-effort, highest credibility-per-line), then P0.1 (TAM persistence).
