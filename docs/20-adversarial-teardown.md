# 20 — Adversarial Teardown (Tournament Review)

> Companion to [`16-adversarial-yc-readiness-review.md`](16-adversarial-yc-readiness-review.md).
> Generated 2026-05-30 by a bracket tournament: **16 critics (prelims) →
> adversarial refutation (knockouts) → theme clustering (quarterfinals) →
> malicious designer + Sequoia/Benchmark VC + ASIC analyst (semifinals) →
> synthesis (finals)**. 108 agents. **107 findings → 87 serious → 65 survived
> refutation.** Remediation in [`21-teardown-remediation.md`](21-teardown-remediation.md).

## Verdict — 46 / 100

> A genuinely strong evaluator core wrapped in a demo that **breaks its own
> thesis on the first three surfaces a partner clicks**: the shareable artifact
> is RAM-only and the homepage routes around it, the chrome ships a fabricated
> "verified" contributor and a dead GitHub link, and the resolve hero hides both
> the math and the sources the data already carries.

The substrate (evaluator, MCP server, source-pinning, RLS/auth scaffolding) is
real and ahead of the surface. The product loses the room not on what it lacks
but on **self-inflicted credibility wounds in the first 60 seconds**.

## Scorecard

| Lens | Score | One-line |
|---|---|---|
| Distribution / shareable permalink | **28** | Broken end-to-end: `remember_tam` writes an in-process FIFO dict; `from_db` loads `tam_outputs={}`; homepage links `/build?q=` not `/tam/<hash>` |
| Trust / first-glance credibility | **35** | `Sidebar.tsx:122` hard-codes `j.vega · verified · 27 contribs` with a `TODO(auth)` admitting it's fake |
| Defensibility (sourced/triangulated) | **40** | Data carries `source_tier`+`sha256`+uncertainty, but surfaces strip it |
| Analytic canvas (graph) | **40** | `GraphView` is read-only nav; resolves a TAM only for a sole Industry concept |
| Differentiation vs LLM | **42** | The wedge is "see the equation + sourced primitives"; the chart shows two anonymous bars |
| Trust / RBAC | **45** | Auth+metering+RLS scaffolded, but `/audit` hard-401s anonymously in every demo |
| Data depth & honesty | **55** | Kalshi quarantine landed (184 sizing-grade); **zero semiconductor primitives**; "sourced" hero is `community-modeled` |
| UI / craft | **58** | Strong tokens + serif hero, but the result screen ships clipped donut + dev overlays |
| Agent-usability (MCP) | **62** | 5 sourced MCP tools — the strongest forward asset |

## Top blockers (survived refutation)

1. **Shareable `/tam/<hash>` is RAM-only and routed-around.** `registry.py:127`
   writes to an in-process FIFO dict; `from_db` (`registry.py:72`) loads
   `tam_outputs={}`; `page.tsx:191` + `TamCard.tsx:36-43` link `/build?q=` with a
   doc comment admitting `/tam/<hash>` 404s. The reproducible-artifact thesis is
   defeated at every layer.
2. **Fabricated `j.vega · verified · 27 contribs`** (`Sidebar.tsx:122-123`) with a
   self-incriminating `TODO(auth)` at `:113`. Inventing a verified contributor on
   a *trust* product is the single most damaging line in the codebase.
3. **Resolve hero hides math AND sources.** `ResolveResultChart.tsx` has no
   "Multiplies to $X" equation footer (`CompositionChart` already ships one
   ~`132-146`), no `TierBadge` per bar, no clickable `source_url`.
4. **The hero leads with an unearned INDEPENDENCE donut** over a "single method
   family — not yet triangulated" banner (`03-build-resolve.png`).
5. **Graph is a taxonomy browser, not a triangulation canvas.** Qual/Quant
   selection returns only "compatible frameworks N/5", never a TAM.
6. **Dead trust signals:** footer GitHub → bare `https://github.com`
   (`page.tsx:336`); `/audit` 401s anonymously; sidebar `TAMs: 0`.

## The interrogation

### Malicious designer
> "Defensible TAM, fast" in a beautiful serif — surrounded by a dead Search link,
> a 404 artifact page, an invented "verified" user, a TAM count of literally
> zero, and a cartoon beach emoji floating over every screen.

- Why is `Search` a top-level nav item on every screen when it 404s? (delete it or build it — the sidebar button opens ⌘K, but the route is reachable and broken)
- The sidebar reads `TAMs: 0`. A market-sizing product whose TAM count is zero — why would I believe anyone has ever sized a market here?
- What is the giant teal beach-island emoji + red "1 Issue" pill + "N" circle on every screenshot? (dev overlays leaking into the captured product)

### The VC (took a Cerebras-class company public)
> A "hash-pinned, reproducible TAM" product whose flagship permalink 404s after a
> restart, whose homepage routes around its own artifact, whose "show your work"
> chart hides the equation and the sources.

- **"WHY would I trust YOUR ASIC TAM over my own? I size with wafer starts × die-per-wafer × yield × ASP. Your resolver multiplies 'inputs' into a number and the chart won't even show me which inputs."**
- "I built a TAM and curl'd `/tam/<hash>` — it 404'd. Your own homepage doesn't trust your own artifact."
- Concept/primitive counts drift across docs (`~100`, `350+`, `30`, `184`) — which is real?

### ASIC domain analyst (ex-IBISWorld/Gartner)
> Strata cannot produce an "AI inference ASIC TAM 2027" I would sign — there is
> **not a single semiconductor, wafer, accelerator, or hyperscaler-capex
> primitive** in the entire 184-record bank; it's a US-SaaS-seat × labor-headcount
> library.

- Searched every slug/name for asic/chip/wafer/fab/hbm/foundry/accelerator/datacenter — **zero hits.**
- The headline "sourced" primitive `ai-coding-assistant-acv-per-engineer-2024` is `tier=community-modeled`, `url=https://strata.internal/models/…` — **that's a model, not a source.** Stop labeling modeled numbers "sourced."
- An inference-ASIC TAM is a **value-chain / supply-constrained** problem (`min(demand, CoWoS capacity)` × ASP × yield). The six demand-multiplicative lenses can't model it.
- 37 primitives are `as_of 2022`, 4 are 2018, one 2010 — silicon ASPs move quarter-to-quarter.

## How we shut them up (the build)

See [`21-teardown-remediation.md`](21-teardown-remediation.md). The throughline:
**make the thesis true on the first surfaces clicked, surface the math+sources
the data already carries, and pick a niche where we can provably out-source a
human analyst** — then ship that as a printable one-page report.
