# Strata — Adversarial YC-Readiness Review & Remediation Spec

> Generated 2026-05-30 from an 11-lens adversarial audit of the *actual* codebase (not the docs' claims). Lenses: docs-vs-reality recon + 10 hostile critics (YC partner, product/differentiation, frontend UX, motion, backend architecture, AI resolver, data/TAM rigor, GTM/moat, ops/trust, demo narrative). 986k subagent tokens, 253 tool calls, ~16min wall-clock.


**Overall YC-readiness score: `42/100`** — 116 prioritized recommendations across 8 themes.


---

## Executive verdict

Strata is a genuinely impressive engineering artifact wrapped in a pitch its own data and dynamic path cannot back up. The bones are real and better than most pre-seed: a unit-checked override-aware evaluator that builds real scenario trees on the curated path, 15 typed connectors, content-hash state minting, a clean token-driven design system with working light/dark and reduced-motion, and one legitimately differentiated interaction (click a graph node, set a what-if, watch the TAM recompute). But verification against the code confirms the lenses' harshest findings: the headline 'type any market, get a defensible sourced TAM' surface (/resolve) collapses to a single point estimate built from Exa snippets the LLM self-grades as 'regulator' tier, with fake strata.internal citation URLs — the precise hallucination-becomes-citable failure the project says is its worst case. The defensibility centerpiece (disagreement / triangulation) is empty: every one of 32 concepts has competing_concepts:[], 31/32 score 0.0 independence, and 56% of primitives are Kalshi betting odds. The 'community' moat has zero contributors and a deleted contribute UI. And the distribution primitive — the shareable /tam/<hash> permalink the whole pitch leans on — 404s because TAMs are never persisted, with no OG tags and no SSR so nothing is even indexable.

The single biggest thing blocking YC-readiness is that the product contradicts its own thesis on the surfaces partners will actually click: the demo number is undefensible, the share link is dead, and the moat is hollow on inspection. None of these are deep — they are concrete, mostly S/M fixes. The path forward is not more breadth (more connectors, more concepts) but ruthless depth on ONE wedge: persist TAMs so links work, hand-pick 5-8 genuinely triangulated demo concepts with competing measurements and real low/base/high ranges, route /resolve through the registry first, quarantine the Kalshi noise, and either ship a thin contribution loop or honestly reframe as a curated (not yet community) engine. Do that and the genuinely strong evaluator/override architecture finally gets a narrative that survives diligence. Today it does not.


## The five existential risks

1. The 'defensible numbers' thesis is contradicted by the code on every surface a YC partner would touch: the dynamic /resolve path returns a single LLM-multiplied point estimate with no unit-checking, self-assigned source tiers, and fake strata.internal citation URLs — i.e. it produces exactly the 'LLM-projected primitives' CLAUDE.md Q20 forbids.
2. The moat (community-curated + triangulated disagreement) is structurally empty: 0 annotations, 0 contributors, contribute UI deleted, all 32 concepts have competing_concepts:[], and 31 of 32 concepts wire one framework so independence_score is hard-zero.
3. Distribution is broken at the root: TAMs are never persisted (no tam_outputs dir, no upsert_tam, no OG tags, fully client-rendered) so every shareable /tam/<hash> link 404s and nothing is SEO-indexable — there is no growth loop.
4. Data integrity is theater: 56% of primitives (202/360) are Kalshi prediction-market noise padding the headline count, sha256 'pins' are never verified against stored snapshots, and as_of stores ingest date not data period.
5. No company substrate: no auth, no metering, no rate-limiting on a paid LLM endpoint (cost-DoS), no observability/alerting, no paying customer or instrumented funnel, wildcard CORS — it reads as a sophisticated single-player demo, not a fundable product.


## Per-lens scorecard

| Lens | Score | One-line verdict |
|---|---|---|
| Docs-promised vs actually-shipped gap map (vaporware audit) | 52 | Strata's backend skeleton is real and more complete than most pre-seed demos, but the gap between what the docs/pitch promise and what ships is wide on exactly … |
| Hostile YC partner — 10-minute interview | 28 | This is an impressive engineering artifact and a thin company. The core "wow" demo — type a market, get a defensible sourced TAM — actually returns a single LLM… |
| Product strategist hunting for the missing innovative edge | 38 | Strata has one genuinely defensible primitive — content-hash-pinned, unit-checked sourced numbers wired through transparent multiplicative frameworks — but it s… |
| Senior product designer — UX & visual craft | 62 | This is far above the typical YC-stage frontend: a real CSS-variable token system, a working light/dark theme with no-flash bootstrap, honest loading/error/empt… |
| Motion/interaction designer (Linear/Vercel/Stripe polish) | 58 | The motion foundation is more careful than most YC-stage apps: there's a shared, token-driven motion primitive set (FadeIn/Stagger/HoverLift), a genuinely nice … |
| Staff backend engineer — architectural impressiveness & scalability | 52 | The backend is clean, well-typed, and honest — but it is architecturally a sophisticated single-process read-mostly CRUD app, not the "engine" the docs imply. T… |
| AI/ML engineer — LLM resolver quality & defensibility | 38 | The resolver is a thin, plausible-looking wrapper around single-shot Claude calls plus a 5-result Exa search — it works as a demo but is NOT defensible as the "… |
| Skeptical VC analyst / data scientist — are the TAMs defensible? | 28 | The headline "361 sourced primitives / 30 concepts / 5 frameworks" does not survive contact with the data. 56% of primitives (202/360) are Kalshi prediction-mar… |
| Growth/GTM strategist + moat analyst | 28 | Strata has a genuinely defensible long-term moat thesis (provenance-pinned community data network effects), but as shipped it has zero working growth loops and … |
| Production/SRE + trust auditor | 38 | For a product whose entire pitch is "defensible numbers," the trust machinery is mostly theater right now. SHA256 pinning is a regex shape-check, not integrity … |
| Pitch/demo coach — first-time-VC walkthrough and 60-second demo readiness | 52 | The core magic moment is real and undersold: clicking a graph node to set a what-if and watching the TAM recompute live with charts (BuildWorkspace.tsx + /build… |

## Recommendation distribution

- **By severity:** 🔴 critical 19 · 🟠 high 36 · 🟡 medium 44 · ⚪ low 17
- **By effort:** S 33 · M 59 · L 24 · XL 0
- **By category:** frontend 30 · product 18 · ai 16 · data 16 · backend 15 · gtm 11 · ops 6 · design 4
- **By theme:** The Wow Demo 12 · AI Defensibility 13 · Data Depth & Rigor 18 · Motion & Visual Craft 19 · Architecture Impressiveness 10 · GTM & Moat 13 · Trust & Reliability 17 · Fundability Narrative 13 · Product 1

## Themes

### The Wow Demo
The 60-second partner walkthrough must be deterministic and end in a shareable artifact. Today the share link 404s, the landing features un-triangulated single-method estimates, concepts are named after portfolio codenames a VC won't type, and the one real wow (live recompute) is buried, undiscoverable, and visually flat.

### AI Defensibility
The LLM resolver is a single-shot wrapper that multiplies unit-unchecked numbers, lets the model self-assign source tier, captures no snapshot, has no eval harness, and emits a single scalar — violating the project's own 'scenario trees, never scalars' and 'no LLM-projected primitives' rules. This is the most fundable thing to fix and the most damaging to demo as-is.

### Data Depth & Rigor
The headline data metrics don't survive inspection: 56% Kalshi padding, 82% of primitives wired to nothing, all concepts disagree with nobody, sha256 pins unverified, fake citation URLs, as_of=ingest-date, and only 5 of a promised 25+ frameworks (L3 latent_demand unbuildable). Depth on one vertical beats this breadth.

### Motion & Visual Craft
A careful motion foundation exists (FadeIn/Stagger, reduced-motion, hero glyph) but stops at entrance animations. The centerpiece graph is static, the recompute payoff is a dim+pill instead of a number tween, modals hard-cut (AnimatePresence used nowhere despite Motion 12), and hierarchy is a flat gray field. It reads 'clean indie SaaS,' not 'expensive.'

### Architecture Impressiveness
The evaluator/override/connector-dispatch core is real and survives CTO scrutiny, but the system around it is a single-process read-mostly app: dead pool config, boot-frozen registry that drops composites/annotations/TAMs in prod, no caching on the flagship recompute, multiply-only frameworks, and full-registry LLM prompts instead of vector retrieval.

### GTM & Moat
No working growth loop and no realized moat: broken permalinks, no OG/SSR/sitemap (zero SEO), no embeddable widget, dead GitHub link, no contribution path, no instrumented funnel, no design partner. The provenance moat is invisible (stubbed TODOs) and the wedge (portfolio-TAM pipeline) isn't surfaced.

### Trust & Reliability
For a 'defensible numbers' product the trust machinery is theater: integrity not enforced, no staleness signaling on 2010-era data, lossy unattributed audit log, prompt-injection surface via web snippets, no monitoring/alerting, unauthenticated unmetered paid endpoint, and wildcard CORS.

### Fundability Narrative
Self-contradicting docs (open vs proprietary, version drift, ghost routes, inflated test/connector counts), broad 'VCs and operators' positioning, no crisp answer to 'why not just ask ChatGPT,' and a flagship worked example (TAM-77) that misses its own targets 6x. The story needs one narrow vertical where the number provably beats an incumbent.


---

## Full recommendation backlog

Sorted within each theme by severity then effort. IDs are stable (`R0xx`).


### The Wow Demo

#### R019 · Feature triangulating concepts on the landing page, not slice(0,3)  🔴
`critical` · effort `S` · _frontend_ · via _Pitch coach_

- **Problem:** page.tsx features concepts.slice(0,3) — the first 3 alphabetically — which are single-method 'degenerate' TAMs with a greyed-out donut, the exact opposite of the 'triangulated, defensible' hero promise.
- **Fix:** Hand-pick 3 featured slugs that triangulate (e.g. doc-gen-pc-insurance) showing a real low–high band and a lit donut, with 'triangulated from N independent methods' as the card headline.
- **YC impact:** Leading with un-triangulated point estimates makes Strata look like every other guess-a-number tool.

#### R036 · Wire Fork to a working pre-populated /build state  🟠
`high` · effort `S` · _product_ · via _Pitch coach; Product strategist_

- **Problem:** TamDetailView Fork links to bare '/build' (with a '404s for now' comment); the 'every edit forks to a new state' narrative has no working entry point from a shared artifact.
- **Fix:** Wire Fork to /build/<hash>?s=<encoded BuildState> using the existing encodeState/BuildState machinery so it lands in the editable workspace pre-populated.
- **YC impact:** 'Fork and remix someone's TAM' is the community/network-effect story YC will probe; a 404 guts it.

#### R020 · Rename portfolio-codename concepts to the markets a VC actually types  🟠
`high` · effort `M` · _product_ · via _Skeptical VC; Pitch coach_

- **Problem:** ~24 of 32 concepts are company codenames ('Echelon — ServiceNow agents', 'Kyber PC doc-gen'). A VC typing 'cybersecurity TAM' or 'tax software' matches nothing and falls to the flaky LLM resolver.
- **Fix:** Set the public name to a clean market term ('AI cybersecurity tooling, US') with the codename as internal metadata, and add query aliases so common markets route deterministically to curated concepts.
- **YC impact:** The demo must be deterministic; mis-routing the obvious query to a backend that may fail kills a rehearsed run.

#### R064 · Add the right-click context menu and 250ms hover ghost cards to the pyramid  🟠
`high` · effort `M` · _frontend_ · via _Vaporware audit_

- **Problem:** PyramidGraph wires only click+shift-click; no onContextMenu anywhere (grep:0) and no 250ms hover ghost card — both explicitly promised in docs/08 Surface 3.
- **Fix:** Add a right-click menu (Expand children / Suggest framework) and a 250ms-delayed hover ghost card showing value+source+snapshot. Cheap, demo-able, promised.
- **YC impact:** The centerpiece feels like a static diagram, not the interactive exploration tool the deck claims.

#### R075 · Add clickable example-query chips and a /demo autoplay route  🟠
`high` · effort `M` · _gtm_ · via _Pitch coach_

- **Problem:** There's no guided 'try this' affordance; the hero placeholder is grey text, so a VC must guess a query and discover the recompute by accident.
- **Fix:** Add 3-4 clickable example chips under the hero routing to triangulating concepts, and a /demo route that autoplays query→range→node edit→recompute→share. Rehearse it as THE pitch.
- **YC impact:** YC partners spend ~60s; the product must walk itself to the wow without narration.

#### R108 · Guarantee the resolver path on the public demo (funded key + pre-warmed cache)  🟠
`high` · effort `M` · _ops_ · via _GTM strategist; Pitch coach_

- **Problem:** The headline 'type any market' /resolve depends on a funded Anthropic backend that's fragile in prod and degrades to 'pick a curated concept'; if live-synthesis fails on the partner's own query, the wow evaporates.
- **Fix:** Ensure a funded key in prod, pre-compute and cache resolved TAMs for the top 100 likely VC queries, and make the fallback graceful-but-impressive so cold demos always hit a sourced range.
- **YC impact:** The first query a partner types must produce a sourced range, not a fallback; reliability here is growth-critical.

#### R111 · Make the recompute loop the landing hero, not a buried /build feature  🟠
`high` · effort `M` · _frontend_ · via _Hostile partner; Pitch coach_

- **Problem:** The landing is a competent-but-generic SVG pyramid + concept grid; the genuinely novel UI (edit an assumption, watch the TAM and citations recompute) lives buried on /build.
- **Fix:** Lead the landing with an autoplaying real interactive 'change this developer-count assumption, watch the $129B TAM move and citations update' as the first thing seen.
- **YC impact:** Interview demos win on one unforgettable interaction; yours is hidden behind a search box.

#### R034 · Make graph-node editability discoverable with a coachmark and affordance  🟡
`medium` · effort `M` · _frontend_ · via _Product designer; Motion designer; Pitch coach_

- **Problem:** The entire interactive thesis hinges on discovering nodes are editable, but the only cue is a 10px 'edit' label and a 1px hover ring — a VC in a self-guided demo may never realize the graph is clickable.
- **Fix:** On hover reveal a pencil/slider icon with a spring, add a one-time ambient pulse on editable nodes on first /build visit, strengthen the hover ring to 2px accent, and show a 'Click any input to run a what-if' coachmark.
- **YC impact:** If reviewers don't discover the core interaction, the differentiator is invisible in a shared link.

#### R074 · Replace the abstract hero glyph with a looping real-product capture  🟡
`medium` · effort `M` · _frontend_ · via _Product designer; Pitch coach_

- **Problem:** The hero visual is a decorative abstract pyramid with no numbers; the most compelling asset (live triangulated recompute) is below the fold and only after a query.
- **Fix:** Replace/supplement the glyph with a muted looping screen-capture of a real triangulated TAM recomputing on a node edit.
- **YC impact:** Show, don't tell — a 5-second recompute loop communicates the value prop faster than any copy.

#### R100 · Add an inline 'show your work' receipt after every recompute  🟡
`medium` · effort `M` · _product_ · via _Product strategist_

- **Problem:** After recompute the user sees only a new headline number, not 'because you changed persona_pool 1.2M→1.5M, TAM moved +$Y, here's the full multiply chain'; LineageGraph exists but the override-to-delta causal story isn't surfaced at the moment of change.
- **Fix:** Render an inline receipt: the full input×input×input=TAM chain with the changed factor highlighted and its contribution to the delta, reusing the InputUsed chain the evaluator already returns.
- **YC impact:** Auditable 'show your work' is the antidote to 'it's just an LLM guessing'; you have the data structure, just surface it.

#### R106 · Add a one-time first-run onboarding/legend on the build canvas  🟡
`medium` · effort `M` · _product_ · via _Product designer_

- **Problem:** A first-time user on /build sees nodes with no explanation that they're clickable, no legend for node types or the independence donut; the most novel interaction is undiscoverable without reading code.
- **Fix:** Add a one-time hint ('Click any sourced input to swap it or run a what-if'), a node-type + donut legend, and a subtle pulse on the first editable node.
- **YC impact:** The differentiating interaction is invisible in a self-guided demo or shared link.

#### R033 · Add a live optimistic preview while dragging the what-if slider  🟡
`medium` · effort `L` · _frontend_ · via _Motion designer; Product strategist_

- **Problem:** OverridePanel updates only a local number until the user clicks 'Recompute' (a network round-trip), so the most satisfying interaction — drag slider, watch TAM move — is gated behind a button and spinner.
- **Fix:** Scale the affected single-input framework value and headline midpoint client-side during drag as a ghosted preview that the real recompute then confirms; debounce the /recompute call on slider release.
- **YC impact:** Live-drag-to-resize-TAM is a jaw-drop moment the architecture already supports; gating it squanders it.


### AI Defensibility

#### R002 · Make the dynamic resolver emit a real scenario tree, not a single point  🔴
`critical` · effort `M` · _ai_ · via _Vaporware audit; AI/ML; Skeptical VC; SRE/trust_

- **Problem:** resolve.py:171 returns scenarios:[{"label":"point","value":tam_value}] — one number — directly contradicting the 'TAMs are scenario trees, never scalars' thesis on the most-clicked surface.
- **Fix:** Run the resolved inputs through the same scenario-tree builder as the curated path (size_concept), propagating per-primitive uncertainty.range into low/base/high branches; compute a real independence score from source-domain diversity. If a tree can't be built, label the output 'single-method estimate, verify before citing.'
- **YC impact:** Stops the headline AI feature from refuting your own pitch the moment a partner types a query.

#### R003 · Unit-check resolver-multiplied primitives before composing a TAM  🔴
`critical` · effort `M` · _ai_ · via _AI/ML; Skeptical VC_

- **Problem:** pipeline.py _step4_fallback does tam_value *= float(h['value']) with no unit/dimension/currency inspection, so people×people or USD×USD silently produces a nonsense dollar TAM rendered as credible.
- **Fix:** Before multiplying, assert a valid unit signature (one currency/people base × dimensionless multipliers), normalize percentages to decimals, reject same-dimension×same-dimension, and reuse the framework unit checker. Emit the resulting unit so the UI shows $/yr vs $.
- **YC impact:** Prevents the live demo from confidently outputting a unit-incoherent number — an instant credibility kill.

#### R004 · Route /resolve through the curated registry before the LLM fallback  🔴
`critical` · effort `M` · _ai_ · via _AI/ML; Pitch coach; Skeptical VC_

- **Problem:** _http_slug hardcodes ResolverIntent.NOVEL and allow_live=False, so the web product NEVER uses curated concepts, the connector router, or the real evaluator — even for queries that exactly match a concept. The strongest, most-defensible path is unreachable from the site.
- **Fix:** Run real slug resolution (resolver/slug.py) on /resolve: a registry hit returns the fully-composed unit-checked scenario tree; only genuinely novel queries fall to the streaming Exa path. Cache the slug call to avoid the extra round trip.
- **YC impact:** Makes the demo bulletproof and shows the curated data bank you actually built instead of routing around it.

#### R012 · Ship bottoms-up vs tops-down convergence as the hero output  🔴
`critical` · effort `L` · _product_ · via _Product strategist; Skeptical VC_

- **Problem:** The evaluator multiplies per framework and averages a naive midpoint; method_family exists in data but no convergence/divergence between bottoms-up and tops-down is ever computed — the most credible thing a TAM tool can show is computed nowhere.
- **Fix:** Add a triangulation layer that groups scenarios by method_family, computes the bottoms-up/tops-down ratio and a convergence score, and surfaces 'bottoms-up $X / tops-down $Y / agree N.Nx' as the hero banner on /build and /tam.
- **YC impact:** Transforms the demo from 'a sourced number' to 'a number two independent methods agree on' — the exact thing VCs distrust LLMs for.

#### R026 · Build an eval/golden-set harness for the resolver  🔴
`critical` · effort `L` · _ai_ · via _AI/ML_

- **Problem:** No eval/golden/accuracy/ground-truth harness exists (grep confirmed); resolver tests only assert SSE plumbing with mocked LLMs. The core 'trustworthy numbers' claim has zero quality signal.
- **Fix:** Build a 20-40 query golden set with verified expected lens, primitive roles, source URLs, and a TAM order-of-magnitude band; run nightly with the real LLM scoring extraction accuracy, unit coherence, and lens-classification; gate releases on it.
- **YC impact:** 'Here's our accuracy benchmark and the number' is the single most fundable AI artifact and the difference between a wrapper and a product.

#### R028 · Derive source_tier from the resolved domain, never from the LLM  🟠
`high` · effort `S` · _ai_ · via _AI/ML; SRE/trust_

- **Problem:** search.py lets the LLM output its own source_tier (default 'community'); the model can launder a blog into 'regulator', and tier drives downstream trust.
- **Fix:** Map source_tier deterministically from the domain (allowlist of .gov/regulator, known aggregators); default unknown to 'community'; never let the model upgrade a tier.
- **YC impact:** Self-graded tiers are trivially gameable and embarrassing when shown.

#### R030 · Let parsed lens determine primitive arity instead of hardcoding 'exactly 2'  🟠
`high` · effort `M` · _ai_ · via _AI/ML_

- **Problem:** parse.py forces 'exactly 2' primitives and the fallback requires 2 hits to multiply, so the dynamic engine structurally can't represent the six-lens taxonomy (latent_demand is 3-factor).
- **Fix:** Derive arity from the lens, bind primitives to named framework roles from the registry's framework definitions, and reject when required roles are unfilled — instantiate a real framework, not an ad-hoc product.
- **YC impact:** If the live engine can only do A×B, the six-lens slide is marketing the backend doesn't deliver.

#### R039 · Use semantic concept matching on the registry-hit hot path  🟠
`high` · effort `M` · _ai_ · via _Product strategist; AI/ML_

- **Problem:** BuildView matches a query to a concept by lowercased substring includes(); 'AI tools for lawyers' misses 'ai-legal-assistants-us'. The 'LLM parses your query' promise is fake on the hot path.
- **Fix:** Route the query through resolver/slug.py (already used by the CLI) or add embedding-based concept matching on the registry-hit path too.
- **YC impact:** A partner typing a natural query and getting no match is a fatal demo moment; the intelligence exists but the front door bypasses it.

#### R027 · Ground-check extracted numbers against captured source snapshots  🟠
`high` · effort `L` · _ai_ · via _AI/ML; SRE/trust_

- **Problem:** search.py trusts float(raw['value']) from one LLM pass over Exa highlights with no check the number appears in the source, no snapshot, no triangulation — the Q20 hallucination-becomes-citable path.
- **Fix:** Capture+hash the snippet/URL content at extract time, reject hits whose digit-string isn't substring-present in the snapshot, extract from top-3 results independently and require agreement within tolerance, and add a verifier re-read of number+unit+year.
- **YC impact:** Pinned, grounded, triangulated extraction is the moat vs ChatGPT-with-search; the current one-shot extract is a liability.

#### R080 · Replace the fake fuzzy interpretation cards with real LLM constraint parsing + ranges  🟠
`high` · effort `L` · _ai_ · via _Vaporware audit; Pitch coach_

- **Problem:** The /?q= multi-interpretation cards are client-side fuzzy string matching with index-based broad/narrow labels and previewRange:null — docs promise an LLM constraint-set parse with NARROW/BROAD preview ranges.
- **Fix:** Either show real per-concept $ range previews under each interpretation (cheap, you have buildQuery) or wire the actual LLM parse for ambiguous queries; drop the arbitrary scope theater.
- **YC impact:** 'Definitional ambiguity is a first-class step' is a real differentiator vs Statista; a Levenshtein match is vaporware on a strategic claim.

#### R029 · Set temperature=0 and enforce schema-valid JSON via tool-use  🟡
`medium` · effort `M` · _ai_ · via _AI/ML_

- **Problem:** _complete_sdk calls with no temperature (~1.0) and parses free-text JSON via fence-stripping, so the same query yields different lenses/numbers and a malformed response fails the whole resolution — non-reproducible by construction for a 'permanent hash' product.
- **Fix:** Set temperature=0 on all parse/route/extract/slug calls, use forced tool-use or prefilling to guarantee schema-valid JSON, and cache resolved results by (query, registry-version) hash.
- **YC impact:** Same query → different number undermines the hash-pinned-artifact promise.

#### R110 · Add probability/confidence calibration into the emitted TAM, not a lone point  🟡
`medium` · effort `M` · _ai_ · via _AI/ML_

- **Problem:** The fallback emits a single 'point' value with independence_score hardcoded 0.0 and no per-input confidence or range, discarding extraction confidence and source-disagreement spread.
- **Fix:** Propagate per-primitive extraction confidence and source-disagreement spread into a triangulated low/base/high tree and compute a real independence score from source-domain diversity.
- **YC impact:** A point estimate from the least-trustworthy path contradicts your own 'scenario trees not scalars' thesis.

#### R093 · Add a bounded query-reformulation/retry loop and per-primitive connector fallback  🟡
`medium` · effort `L` · _ai_ · via _AI/ML_

- **Problem:** The fallback is strictly linear — one search per primitive, silently drop empties, fail the whole query if <2 survive; a single weak search kills the resolution.
- **Fix:** Add a bounded ReAct loop reformulating the search query 2-3 times on empty/low-confidence results, let an individual missing primitive fall back to a connector, and track per-primitive confidence.
- **YC impact:** YC expects 'agent' to mean iterative reasoning; one-shot search-and-multiply is a 2023-era wrapper.


### Data Depth & Rigor

#### R005 · Quarantine the 202 Kalshi prediction-market primitives out of the headline count  🔴
`critical` · effort `S` · _data_ · via _Vaporware audit; Hostile partner; Product strategist; Skeptical VC_

- **Problem:** 202 of 360 primitives (56%) are tier:prediction_market Kalshi contracts ('2028 Democratic VP nominee', 'Eurovision Winner 2026') wired into zero frameworks — pure inventory padding. Confirmed via grep.
- **Fix:** Move prediction-market data into a clearly separated 'signals' namespace (or drop it), report the honest sizing-grade count (~88 regulator / ~158 non-prediction), and add a CI check that fails if a non-prediction primitive is referenced by no concept/framework.
- **YC impact:** A partner who clicks one 'Eurovision Winner' primitive concludes the whole data bank is padded; honest small numbers beat fake big ones.

#### R006 · Seed 5-8 hero concepts with genuinely competing measurements  🔴
`critical` · effort `M` · _data_ · via _Vaporware audit; Product strategist; Skeptical VC_

- **Problem:** All 32 concepts have competing_concepts:[] (confirmed) and DisagreementBar renders a concept's own inputs as 'rows', not independent methodologies. The signature 'disagreement gets a page' feature is structurally empty.
- **Fix:** For top demo concepts seed 4-6 genuinely competing sourced measurements each (e.g. US dev headcount: BLS OEWS vs LinkedIn vs Stack Overflow) and wire competing_concepts links so the bar shows real spread. Curation work, not engineering.
- **YC impact:** This is THE differentiator vs IBISWorld; demoing it on data where every concept disagrees with nobody guts the pitch.

#### R008 · Replace fake strata.internal/strata.ai citation URLs with real methodology pages  🔴
`critical` · effort `M` · _data_ · via _Hostile partner; Skeptical VC; SRE/trust_

- **Problem:** 13 community-modeled primitives (the most TAM-sensitive capture/consolidation rates) cite non-existent URLs like https://strata.internal/models/... — LLM-derived numbers dressed as sourced primitives, the exact Q20 failure mode.
- **Fix:** Either publish a real methodology page per modeled multiplier with reasoning + comparable anchors, or downgrade them to explicit user-adjustable assumption sliders clearly labeled 'modeled, not sourced.' Never let a 404 sit behind a 'source' link.
- **YC impact:** A VC who clicks one capture-rate node and gets a dead strata.internal link concludes the entire sourcing layer is theater.

#### R007 · Give 5-8 demo concepts a second independent framework so triangulation is non-zero  🔴
`critical` · effort `L` · _data_ · via _Skeptical VC; Vaporware audit; Product strategist_

- **Problem:** 31 of 32 concepts wire exactly one framework, so _independence() returns 0.0; the hero TAM advertises 'Independence 0.0', actively telling the VC the number is un-triangulated.
- **Fix:** Author a second method-family-distinct framework (bottoms-up AND top-down) for each flagship concept so the UI shows two methods converging within Nx. Fewer concepts each triangulated beats 30 single-method estimates.
- **YC impact:** Triangulation is the entire defensibility story; a lit-up convergence donut is the demo's strongest trust signal.

#### R010 · Propagate primitive uncertainty.range into low/base/high branches  🔴
`critical` · effort `L` · _backend_ · via _Skeptical VC; AI/ML; Hostile partner; Product strategist_

- **Problem:** engine.py multiplies point values and derives range as min/max across framework variants; 147 primitives carry uncertainty.range that the evaluator never reads. The 'scenario tree' is cosmetic — there is no propagated uncertainty.
- **Fix:** Sample/propagate each input's uncertainty.range through the multiplicative evaluator to emit true conservative/base/aggressive branches per scenario. Make uncertainty.range mandatory for the load-bearing primitives that feed frameworks.
- **YC impact:** A sourced range with visible drivers is the antidote to the false precision a skeptical VC distrusts.

#### R011 · Build a sensitivity / tornado chart on the existing recompute loop  🟠
`high` · effort `M` · _product_ · via _Product strategist; Skeptical VC_

- **Problem:** Zero uncertainty surfacing exists (grep: no tornado/Monte Carlo/sensitivity). The product cannot answer 'which assumption moves the answer most?' — the #1 operator question.
- **Fix:** Perturb one input at a time across its low/mid/high and render a tornado chart in the /build right rail ranking inputs by their swing on the final TAM, reusing the recompute plumbing.
- **YC impact:** The visual that makes the demo read as serious analyst infrastructure rather than a chatbot.

#### R091 · Drop raw XBRL frame sums as primitives and fix broken metadata  🟠
`high` · effort `M` · _data_ · via _Skeptical VC_

- **Problem:** edgar-frames-assets-2023q4 has value $76.6T (sum of ALL filers), source slug 'edgar-frame-unknown-sum', a dead sec.gov URL, contradictory units, and as_of=ingest date.
- **Fix:** Remove XBRL frame sums as primitives (not addressable markets), fix 'unknown-sum' sources, and set as_of to the data period.
- **YC impact:** A $76T 'primitive' is an immediate sign nobody validated the ingest pipeline's outputs for sizing relevance.

#### R009 · Ship the L3 latent_demand framework (population × adoption × WTP)  🟠
`high` · effort `L` · _data_ · via _Vaporware audit; Product strategist; Skeptical VC_

- **Problem:** No latent_demand/adoption_curve framework exists in data/frameworks/ (confirmed), so 1 of the 6 advertised lenses is unbuildable and consumer/marketplace TAMs — the most common shape YC sees — cannot be sized.
- **Fix:** Build the 3-input L3 framework with sourced/ranged population, adoption, and WTP inputs. Add 2-3 more frameworks per vertical to credibly claim a 'library' rather than 5 two-factor multiplies.
- **YC impact:** Not being able to size the most common consumer/marketplace TAM with your own advertised lens is a glaring, partner-probed hole.

#### R085 · Wire orphan primitives into frameworks or remove them  🟠
`high` · effort `L` · _data_ · via _Skeptical VC_

- **Problem:** The 5 frameworks reference ~66 distinct primitive slugs; ~295 of 360 primitive files are never consumed by any sizing path — mostly unused inventory.
- **Fix:** Wire orphans into frameworks (real depth) or remove them, and add a CI check that fails on unreferenced non-prediction primitives so the corpus stays load-bearing.
- **YC impact:** 66 real primitives is a weekend of data entry, not the defensible community data bank you claim over IBISWorld.

#### R084 · Seed 3-5 composites demonstrating union/filter/restrict  🟡
`medium` · effort `S` · _data_ · via _Vaporware audit_

- **Problem:** data/composites has exactly 1 real file (confirmed), so the load-bearing same-unit-set-ops layer that justifies the composite/framework hard line is barely demonstrated.
- **Fix:** Seed 3-5 composites showing union/filter/restrict (e.g. addressable = total minus excluded segment) so the layer is visible.
- **YC impact:** Reviewers notice when an architecture-diagram 'layer' is one row.

#### R044 · Split as_of into data_period and ingested_at; key trajectory on data_period  🟡
`medium` · effort `M` · _data_ · via _Skeptical VC; SRE/trust_

- **Problem:** 212 primitives have as_of=ingest date (e.g. EDGAR CY2023-Q4 carries as_of 2026-05-28), and trajectory() keys time-series on as_of — so a 2023 figure plots at 2026.
- **Fix:** Add data_period (what the number measures) vs ingested_at (when fetched); key trajectory on data_period; audit the corpus for drift.
- **YC impact:** A trajectory chart plotting 2023 data at 2026 is an obvious bug a partner catches by eye.

#### R087 · Add double-counting / overlap detection across frameworks  🟡
`medium` · effort `M` · _backend_ · via _Skeptical VC_

- **Problem:** When >1 framework applies the evaluator averages their values with no check they measure the same scope without overlap (supply-side cost vs demand-side spend shouldn't be blended).
- **Fix:** Tag each framework with what it counts; refuse to average incommensurable bases (present as alternative views) and warn when two frameworks share an input primitive.
- **YC impact:** Double-counting is the #1 way TAMs get laughed out of a partner meeting; detecting it is a feature.

#### R088 · Use source tier to weight scenario branches and a sourcing-quality score  🟡
`medium` · effort `M` · _backend_ · via _Skeptical VC_

- **Problem:** The 8 source tiers exist to weight confidence but the evaluator multiplies every value identically; tier only triggers a banner — a Kalshi vol number and a BLS figure are treated the same in the math.
- **Fix:** Use tier to drive branches (regulator anchors base, community-modeled widens high/low) and compute a per-TAM sourcing-quality score surfaced in the UI and exports.
- **YC impact:** Tier-weighted confidence is designed-for in the schema but unbuilt — a concrete differentiator vs a flat spreadsheet.

#### R089 · Down-weight or segregate analyst-paraphrase inputs and track their value share  🟡
`medium` · effort `M` · _data_ · via _Skeptical VC_

- **Problem:** 20 analyst-paraphrase primitives flow into TAMs multiplied identically to regulator figures; a paraphrase of a Gartner estimate re-multiplied is the IBISWorld-lite black box the product claims to replace.
- **Fix:** Visually segregate paraphrase inputs (anchor a high branch, not the base), require a primary-source replacement task per paraphrase, and track what % of each TAM's value derives from paraphrase vs regulator.
- **YC impact:** If a fifth of your sourced layer is paraphrased analyst opinion, you ARE the black box.

#### R082 · Add an L3 market-implied TAM framework consuming Kalshi probabilities  🟡
`medium` · effort `L` · _data_ · via _Product strategist_

- **Problem:** 202 prediction_market primitives feed zero frameworks; market-implied probability-weighted TAM is a genuinely novel feature the data already supports but nothing exposes.
- **Fix:** Build a framework that consumes Kalshi/Polymarket probabilities to produce probability-weighted market-implied TAM scenarios (or, per R005, quarantine the data if not used).
- **YC impact:** Market-implied TAM is a tweetable feature no incumbent can do; the insight is currently left on the floor.

#### R086 · Implement multi-stage (3-4 input) frameworks, not 2-factor multiplies  🟡
`medium` · effort `L` · _data_ · via _Skeptical VC; Staff backend_

- **Problem:** Every framework is a 2-input A×B product with a 'v0.2 simplification' disclaimer; bottoms_up_cost_efficiency admits it's a 2-input cut of the real 4-input lens.
- **Fix:** Complete cost-efficiency to its full 4-input form and add addressable_share/capture_rate as first-class sourced/ranged inputs; richer multi-stage frameworks demonstrate the recipe engine.
- **YC impact:** A multiply anyone can do in Excel is not a defensible 'framework'; the wedge is reusable recipes.

#### R083 · Seed real onchain primitives via the available Dune connector  ⚪
`low` · effort `M` · _data_ · via _Product strategist_

- **Problem:** 'onchain' is an advertised source tier (Q26/Q37) with zero data; claiming it empty is a credibility gap, and a Dune MCP is available in this environment.
- **Fix:** Seed a few real onchain primitives (stablecoin transfer volume, DEX TVL) and wire one onchain-sourced crypto-market TAM, or drop onchain from the advertised list until Phase 4.
- **YC impact:** Crypto/fintech is a big YC TAM category; a real onchain-sourced TAM is differentiated and one MCP away.

#### R090 · Add corroborating second sources for single-source base counts  ⚪
`low` · effort `M` · _data_ · via _Skeptical VC_

- **Problem:** Framework-wired bases lean heavily on Census CBP 2022 and EDGAR frames with no second source corroborating any base count; a single connector error propagates undetected.
- **Fix:** Add a corroborating source per base count (e.g. BLS OES vs Census CBP), flag divergence >X% as a data-quality warning, and mark single-source values in the UI.
- **YC impact:** Showing you detect and surface single-source risk is a trust win with a data-savvy investor.


### Motion & Visual Craft

#### R013 · Add the recompute number-tween payoff moment  🔴
`critical` · effort `M` · _frontend_ · via _Motion designer; Pitch coach_

- **Problem:** The what-if recompute — the product's hero interaction — only dims the headline to opacity 0.5 with a tiny 'recomputing…' pill, then hard-cuts to the new value. The dopamine that sells the live thesis is absent.
- **Fix:** Animate the headline value with a Motion spring from old→new over ~500ms, crossfade the independence donut arc, add an accent border pulse on the fresh value, a ±% delta badge ('$4.2B → $5.1B, +21%'), and a node pulse on the edited input. Replace the dim with a shimmer sweep.
- **YC impact:** 'I dragged this assumption and the market resized 21% in real time' is the screenshot that wins the partner meeting.

#### R032 · Adopt AnimatePresence for all modals and the override panel  🟠
`high` · effort `M` · _frontend_ · via _Motion designer_

- **Problem:** AnimatePresence is used nowhere (grep: 0, confirmed) despite Motion 12 installed; OverridePanel, CommandPalette, and every modal hard-cut in and out with no transition — the most common 'cheap app' tell.
- **Fix:** Build a shared Motion <Modal> with backdrop fade+blur and a panel spring from scale 0.96/y:8, with proper exit animation. Migrate the native <dialog> palette to it or use @starting-style.
- **YC impact:** Spring+backdrop-blur modals are table stakes for the 'expensive' feel of Linear/Stripe.

#### R060 · Add detail/density hierarchy to the build view layout  🟠
`high` · effort `M` · _design_ · via _Product designer_

- **Problem:** Build view stacks Headline, graph, Method comparison, Composition, Trajectory as identical canvas-card p-6 blocks with the same 20px header + 13px gray subhead — a single column of equal-weight panels reading as a report dump.
- **Fix:** Make the headline+graph a visually dominant 'result' zone, group the two charts side-by-side on wide screens, demote trajectory to a lighter treatment, and vary padding/background for rhythm.
- **YC impact:** Even great content looks junior when every block has equal weight.

#### R061 · Establish a real 4-5 step type scale with weight/color contrast  🟠
`high` · effort `M` · _design_ · via _Product designer_

- **Problem:** Body sits at 12-13px in fg-2/fg-3 with 11px uppercase labels; the only large type is the serif headline and mono number, with no mid-tier — a uniform gray field with no scan-path.
- **Fix:** Define a 4-5 step scale and use weight/color (not just size) to separate primary content from metadata; promote at least one number/label per card to high-contrast fg-1.
- **YC impact:** Flat hierarchy is the difference between 'real product' and 'dev dashboard.'

#### R062 · Make the scenario graph responsive and add fullscreen/mobile fallback  🟠
`high` · effort `M` · _frontend_ · via _Product designer_

- **Problem:** ScenarioGraph is fixed h-520px with 320px nodes inside a 1280px column minus a 320px rail; fitView zooms the DAG until text is illegible, and mobile is a tiny pan-only box.
- **Fix:** Make height responsive (min 60vh desktop), add fit/expand-to-fullscreen, auto-scale node size to viewport, and give mobile a stacked list fallback of the same scenario tree.
- **YC impact:** The graph is the demo; illegible on the partner's laptop, it looks unfinished.

#### R067 · Morph skeletons into content with a directional shimmer  🟠
`high` · effort `M` · _frontend_ · via _Motion designer_

- **Problem:** Skeleton is a single animate-pulse block that hard-cuts to the real layout, with geometry that doesn't match the final view, so it jumps on resolve.
- **Fix:** Crossfade skeleton→content via AnimatePresence (~200ms), upgrade pulse to a translateX gradient shimmer, and match skeleton shapes to the final layout.
- **YC impact:** A polished skeleton morph makes a slow LLM/recompute backend feel fast and intentional.

#### R031 · Animate the scenario graph: entrance stagger, hover lift, data-flow edges  🟠
`high` · effort `L` · _frontend_ · via _Motion designer_

- **Problem:** The always-on centerpiece graph is fully static — nodes appear instantly, edges are animated:false, hover is a 1px ring. It reads as a wireframe, not a live instrument.
- **Fix:** Wrap nodes in motion.div with a tier-depth-staggered fade+scale entrance, spring scale-1.03 on hover, and a stroke-dash flow animation on edges feeding a just-overridden node (target←framework←primitive).
- **YC impact:** A motion-alive graph is the most GIF-able asset for the YC application video.

#### R065 · Add a global prefers-reduced-motion CSS block and gate recharts  🟡
`medium` · effort `S` · _frontend_ · via _Motion designer_

- **Problem:** globals.css has no reduced-motion rule (grep:0); CSS transitions, animate-pulse skeletons, and recharts default animations keep running for users who asked for reduced motion.
- **Fix:** Add a global @media (prefers-reduced-motion: reduce) block neutralizing durations/pulse and pass isAnimationActive={!reduce} to every recharts chart.
- **YC impact:** A half-implemented reduced-motion story is an easy, visible a11y miss.

#### R068 · Animate the ResolveView streaming chain-of-thought rows  🟡
`medium` · effort `S` · _frontend_ · via _Motion designer_

- **Problem:** The /resolve streaming feed appends ThoughtRow and primitive-hit items to plain lists with no entrance animation; rows hard-appear as SSE events land.
- **Fix:** Wrap each row in the existing FadeIn/StaggerItem so reasoning steps slide+fade as they stream, with a blur-in on the phase label; keep auto-scroll.
- **YC impact:** The streaming resolver is the most AI-native surface; animating it makes the intelligence legible and impressive.

#### R069 · Morph chart bars between values instead of regrowing from zero  🟡
`medium` · effort `S` · _frontend_ · via _Motion designer_

- **Problem:** recharts re-runs its mount animation on every recompute, so method-comparison bars regrow from zero on each what-if tweak, looking like a reload.
- **Fix:** Use stable bar keys and a short animationDuration (~300ms) with ease-out so existing bars glide to new lengths.
- **YC impact:** Bars that glide sell a live instrument; bars that reload sell a static report.

#### R076 · Give empty/error states real visual weight  🟡
`medium` · effort `S` · _design_ · via _Product designer_

- **Problem:** EmptyState/ErrorState are centered title + gray paragraph with no icon, container, or rhythm — the most generic surface in the app, judged harshly when data is sparse.
- **Fix:** Give them a bordered card/subtle background, an icon (reuse the pyramid glyph), generous vertical rhythm, and a clear primary action.
- **YC impact:** Empty states are scrutinized in live demos where data is thin.

#### R077 · Style the override modal: icon close, branded slider, unit suffix, validation  🟡
`medium` · effort `M` · _frontend_ · via _Product designer_

- **Problem:** OverridePanel — the marquee what-if interaction — uses a bare '×', default native range/number inputs, no unit suffix, and no min/validation so a negative typo flows to recompute.
- **Fix:** Use an icon close button, brand-styled slider track/thumb, inline unit in the number field, and guard nonsensical values. This is the screen you'll screenshot for the YC application.
- **YC impact:** Your differentiator currently looks the least designed.

#### R063 · Add zoom-to-pillar / search-within-pillar to the PyramidGraph  🟡
`medium` · effort `L` · _frontend_ · via _Product designer_

- **Problem:** PyramidGraph caps the industry column at 14 of ~30 concepts with a dead-end '+N more' node; the 'always-on centerpiece' can't render the current catalog and won't scale to the roadmap's 250+.
- **Fix:** Add level-of-detail layout that expands a column on focus plus search-within-pillar so the full set is reachable.
- **YC impact:** The signature visual doesn't scale to your own stated data growth.

#### R070 · Add tactile press feedback to the Button primitive  ⚪
`low` · effort `S` · _frontend_ · via _Motion designer_

- **Problem:** Button only has transition-colors; HoverLift (whileTap scale) exists in motion.tsx but is unused, so primary CTAs feel rigid.
- **Fix:** Back Button with motion.button (whileTap scale 0.97, whileHover y:-1, spring), gated on reduced-motion, applied to 'Size it' and 'Recompute' CTAs.
- **YC impact:** Tactile press feedback is a pervasive micro-signal of craft.

#### R104 · Replace the opacity-based framework toggle with a real switch control  ⚪
`low` · effort `S` · _frontend_ · via _Product designer_

- **Problem:** Framework rows signal off-state only via opacity 0.45 + tiny 'on/off' text, which reads as disabled/loading; the meaningful toggle→recompute action has a weak affordance.
- **Fix:** Add a real toggle/checkbox with a clear checked accent fill, keep the row full-opacity, and reserve dimming for genuinely disabled rows.
- **YC impact:** A core interactive control currently reads as a styling shortcut.

#### R066 · Run a WCAG contrast audit in both themes  ⚪
`low` · effort `M` · _design_ · via _Product designer_

- **Problem:** fg-3 (#7e7e86/#71717a) is used heavily for content text on bg-0/bg-1, and graph edge/canvas tones are borderline; no evidence a contrast audit was run.
- **Fix:** Run axe/Lighthouse in both themes, reserve fg-3/fg-4 for true decoration, and bump content text contrast plus graph edge/node contrast.
- **YC impact:** Accessibility gaps are easy partner ammunition.

#### R072 · Add page-level route transitions  ⚪
`low` · effort `M` · _frontend_ · via _Motion designer_

- **Problem:** Navigation between routes produces instant content swaps with no shared layout transition; combined with hard-swap skeletons, navigation feels abrupt.
- **Fix:** Add a ~150ms crossfade via the CSS View Transitions API or a Motion AnimatePresence wrapper keyed on pathname.
- **YC impact:** Cohesive transitions are a baseline 'designed product' signal.

#### R073 · Animate the command palette open and slide the selection highlight  ⚪
`low` · effort `M` · _frontend_ · via _Motion designer_

- **Problem:** CommandPalette uses dialog.showModal() (hard-cut) and rows have only a bg-color jump on selection.
- **Fix:** Animate open via @starting-style or Motion, add a backdrop blur, and use a layoutId shared highlight that glides between rows as arrows move.
- **YC impact:** A buttery ⌘K tells technical partners the team sweats details.

#### R071 · Add a signature landing→build shared-element transition  ⚪
`low` · effort `L` · _frontend_ · via _Motion designer_

- **Problem:** The hero PyramidGlyph and the real ScenarioGraph are visually unrelated and submit hard-cuts to the route; the landing's best animation is a dead end.
- **Fix:** On submit, animate the glyph collapsing toward the page transition, longer-term a Motion layoutId shared-element from glyph apex → target node; at minimum a route fade.
- **YC impact:** A signature transition makes a 90-second YC video feel designed by a real team.


### Architecture Impressiveness

#### R021 · Wire the configured DB pool into create_async_engine  🟠
`high` · effort `S` · _backend_ · via _Staff backend_

- **Problem:** config.py defines engine_pool_kwargs() and claims it's 'wired into create_async_engine', but db/engine.py ignores it (confirmed) — prod runs on SQLAlchemy defaults (pool_size=5) regardless of config. Dead documented config.
- **Fix:** Pass **settings.engine_pool_kwargs() into create_async_engine. One-line fix.
- **YC impact:** Due-diligence engineers grep for dead config; documented-but-unused tuning signals the prod-hardening is cosmetic.

#### R022 · Load composites/annotations/tam_outputs from DB in Registry.from_db and add reload  🟠
`high` · effort `M` · _backend_ · via _Staff backend_

- **Problem:** Prod registry is loaded once at boot and from_db hardcodes empty composite/annotation/tam_outputs dicts, so any concept whose input resolves to a composite 422s in prod but works locally, and a data update requires a full restart.
- **Fix:** Load composites/annotations/tam_outputs from DB in from_db(); add an auth-gated POST /admin/reload-registry or a short-TTL cache so 'strata db seed' takes effect without downtime.
- **YC impact:** 'How do you ship a data update without downtime?' currently answers 'restart the server,' and prod evaluates differently than dev — corrosive for a numbers product.

#### R046 · Invert the LLM backend default so prod uses the SDK, not the claude CLI  🟡
`medium` · effort `S` · _ai_ · via _Staff backend_

- **Problem:** llm.complete defaults to _complete_cli (subprocess 'claude'), a binary absent from the Railway container; the SDK is opt-in via STRATA_LLM_BACKEND=anthropic — the 'default' path can't run in prod.
- **Fix:** Select the SDK when ANTHROPIC_API_KEY is present or env==prod, fall back to CLI only in dev; this also unblocks /resolve concurrency (the blocking subprocess caps throughput at the thread-pool size).
- **YC impact:** A prod resolver whose default code path can't run in prod is exactly the brittleness that breaks live demos.

#### R025 · Cache size_concept by state_hash on the recompute hot path  🟡
`medium` · effort `M` · _backend_ · via _Staff backend_

- **Problem:** /build/recompute runs the full concept synchronously on every interactive override with no memoization, despite a deterministic state_hash that's a perfect cache key. Fine at 32 concepts, falls over when the data bank is real.
- **Fix:** Add an LRU/Redis cache on size_concept keyed by state_hash, and persist minted TAMOutputs so the content-hash design becomes load-bearing rather than decorative.
- **YC impact:** Makes the 'permanent shareable /tam/<hash>' claim actually work and reads as real engineering.

#### R081 · Verify content-addressed /build/<hash> minting actually collides equivalent states  🟡
`medium` · effort `M` · _frontend_ · via _Vaporware audit_

- **Problem:** BuildWorkspace stashes overrides client-side and ad-hoc 'replace the URL'; it's unverified that the canonical state_hash from /build/recompute drives /build/<hash> and that equivalent states collide per U6.
- **Fix:** Confirm the backend state_hash drives the URL and that sorted-key canonicalization makes equivalent states collide so 'Copy URL' produces a reproducible permalink.
- **YC impact:** If URLs aren't truly content-addressed, shared links drift, breaking the reproducibility promise the memo workflow depends on.

#### R095 · Implement (or delete the claim about) prompt-cache control on the system prompt  🟡
`medium` · effort `M` · _ai_ · via _AI/ML_

- **Problem:** slug.py/router.py docstrings claim the ~21K-token index/manifest is sent with cache_control:ephemeral to hit the prompt cache, but _complete_sdk passes system as a plain string with no cache_control (grep confirms none) — every call re-bills the full manifest.
- **Fix:** Split static index/manifest into a cache_control:ephemeral system block in _complete_sdk and measure the savings, or delete the false docstring claims.
- **YC impact:** Docstrings describing optimizations that don't exist tell a diligence reviewer the codebase over-claims, and per-query cost matters for unit economics.

#### R040 · Add pgvector retrieval so slug resolution scales past the whole-catalog prompt  🟡
`medium` · effort `L` · _ai_ · via _Staff backend; Vaporware audit_

- **Problem:** resolve_slug stuffs EVERY concept and primitive summary into one Claude prompt (O(registry) tokens/query); it doesn't scale past a few hundred records and the roadmap's own v1.0 target is 250+.
- **Fix:** Add a pgvector index over concept/primitive descriptions (you already run Postgres), retrieve top-k, and let the LLM disambiguate among k — not the whole bank.
- **YC impact:** 'How does this scale to 10,000 primitives?' — pgvector retrieval is the expected answer you don't yet have.

#### R048 · Parallelize ingest with retry/backoff, or move to a task queue  🟡
`medium` · effort `L` · _backend_ · via _Staff backend_

- **Problem:** ingest/orchestrator runs targets in a serial for-loop swallowing failures with a counter — no concurrency, retry, or backpressure; a real data bank would refresh one-at-a-time with invisible failures.
- **Fix:** Parallelize with a bounded pool first; for scale move to arq/RQ/Celery with per-target retry + dead-letter so freshness is event-driven (cron enqueues, workers drain).
- **YC impact:** 'Continuously-fresh sourced data bank' is the story; a serial retry-less cron loop isn't that.

#### R047 · Centralize the model id and tier models by step cost  ⚪
`low` · effort `S` · _ops_ · via _AI/ML_

- **Problem:** 'claude-sonnet-4-6' is hardcoded in 7 files with no config or env override and no startup validation; the same top model does cheap classification and expensive extraction.
- **Fix:** Centralize model ids in config.py with env override and startup validation; use a Haiku-class model for slug/route classification and a stronger model for extraction/verification.
- **YC impact:** A retired hardcoded model id is a latent prod outage; uniform top-model use inflates cost-per-query.

#### R101 · Add a per-concept assumption time-travel scrubber  ⚪
`low` · effort `M` · _product_ · via _Product strategist_

- **Problem:** trajectory() re-evaluates only at whatever as_of dates happen to exist; there's no user-controllable 'replay how this TAM changed as sources updated, with why,' despite hash-pinned state + audit_events making it trivial.
- **Fix:** Use the state-hash history + audit_events for a timeline scrubber: drag a slider and watch the headline and the specific changed primitive re-render, annotated with the source-update reason.
- **YC impact:** Time-travel makes the hash-pinning architecture visible and impressive rather than an unseen backend detail.


### GTM & Moat

#### R001 · Persist computed TAMs so /tam/<hash> permalinks resolve  🔴
`critical` · effort `M` · _backend_ · via _GTM strategist; Pitch coach; SRE/trust; Vaporware audit_

- **Problem:** No data/tam_outputs dir exists, no upsert_tam in db/, and /build/recompute never persists the TAMOutput; GET /tam/{hash} only reads the in-memory seed registry, so every user-built share link 404s after a restart or on another instance.
- **Fix:** On /build/recompute and /resolve, upsert the full TAMOutput (inputs, overrides, framework variant, scenarios) into a Postgres tam_outputs table keyed by state_hash; have GET /tam/{hash} read from it. Reuse the existing audit_events persistence pattern. Add an in-memory LRU as a minimum-viable session cache.
- **YC impact:** Turns every 'Copy URL / Cite / Fork' click into a working viral artifact instead of a dead link in front of a partner — the #1 broken demo beat.

#### R016 · Add OpenGraph + Twitter cards and dynamic OG images to TAM/concept pages  🔴
`critical` · effort `M` · _gtm_ · via _GTM strategist; Pitch coach_

- **Problem:** layout.tsx sets only title+description (no openGraph/generateMetadata anywhere, confirmed). Pasted links render as bare grey snippets — for a product whose GTM is 'paste a defensible number into a memo,' the viral surface has no payload.
- **Fix:** Add generateMetadata to /tam/[hash], /c/[slug], /f/[slug] with openGraph + twitter:summary_large_image, and a Next ImageResponse OG route rendering the triangulated range + concept name + independence donut + brand.
- **YC impact:** Every shared link becomes a mini-ad; the cheapest growth engine available.

#### R018 · Ship a thin contribution loop or honestly reframe the 'community' pitch  🔴
`critical` · effort `M` · _product_ · via _GTM strategist; Hostile partner; Vaporware audit; Product strategist_

- **Problem:** data/annotations is empty (0), there is no /contribute route or CONTRIBUTING.md, LICENSE is proprietary, and the contribute UI was deleted — yet 'community-curated' is the network-effect moat. The thesis is cold-start-dead and self-contradictory.
- **Fix:** Either ship a GitHub-PR/issue-based primitive+annotation submission flow with attribution and seed 3 design-partner contributors, OR drop 'community-curated' and sell as 'fastest defensible bottoms-up TAM for [vertical].' The current both-and is incoherent.
- **YC impact:** 'Who contributes and why' is the first question on a community-data company; today there is no answer.

#### R017 · Server-render public pages so they are SEO-indexable  🔴
`critical` · effort `L` · _gtm_ · via _GTM strategist_

- **Problem:** Every public surface is 'use client' with client-side fetch, no sitemap.ts, no robots — Googlebot sees an empty shell, so the 'programmatic SEO goldmine' of ~400 indexable TAM/primitive pages produces zero traffic.
- **Fix:** Convert /c, /f, /p, /tam, /browse to server components rendering real numbers in initial HTML (keep interactive bits as client islands); add app/sitemap.ts enumerating every slug and app/robots.ts.
- **YC impact:** Programmatic SEO is the most credible zero-CAC growth story for a data product — but only if pages render server-side.

#### R037 · Ship an embeddable /embed/<hash> TAM widget + oEmbed  🟠
`high` · effort `M` · _gtm_ · via _Product strategist; GTM strategist_

- **Problem:** No embed/iframe/oEmbed exists (grep confirmed); VCs and operators live in Notion/memos/decks but there's no way to drop a live auto-updating Strata range into an external doc.
- **Fix:** Add /embed/<hash> (minimal chrome: midpoint + band + provenance footer + 'sized by Strata' backlink) and an oEmbed endpoint so Notion/Substack auto-unfurl. Document GET /build/{slug} and /tam/{hash} as a public TAM API.
- **YC impact:** Every embed is a branded backlink + live provenance demo — the Stripe-button-style distribution loop YC loves.

#### R056 · Surface the provenance moat instead of leaving it a TODO  🟠
`high` · effort `M` · _product_ · via _GTM strategist; Pitch coach_

- **Problem:** The per-input source-tier mix on the TAM artifact is a visible 'TODO(api): per-input tier count' / 'not yet exposed by the API'; the thing that makes Strata un-copyable by a GPT wrapper is hidden.
- **Fix:** Expose per-input source_tier on inputs_used and render the stacked tier bar + 'N regulator / M analyst / K community, every number reproducible from these sources' + one-click 'verify' showing the raw snapshot.
- **YC impact:** Provenance is the entire defensibility argument vs 'just ask ChatGPT'; a TODO makes the moat invisible.

#### R079 · Wire /browse to a real is_promoted curation endpoint  🟠
`high` · effort `M` · _gtm_ · via _GTM strategist_

- **Problem:** /browse admits via TODO it has no is_promoted flag and dumps all 30 seed concepts labeled 'TAMs' with no curation, trending, or most-shared ordering.
- **Fix:** Add an is_promoted flag and GET /tams?promoted=true with trending/most-forked ordering so /browse is a crawlable hub and a reason to return.
- **YC impact:** An obvious 'this is just the seed data' page signals pre-traction; a lively curated registry signals usage.

#### R055 · Fix the placeholder GitHub link and add an open-source star CTA  🟡
`medium` · effort `S` · _gtm_ · via _GTM strategist; Pitch coach_

- **Problem:** The landing footer links to the literal 'https://github.com' placeholder; for an OSS-positioned product, stars are top-of-funnel and the link is dead.
- **Fix:** Point at the real repo, add a star CTA and count, and lean into 'open-source market sizing' in the hero (after resolving R018's open/proprietary tension).
- **YC impact:** OSS traction is the cheapest credible growth metric; a dead GitHub link signals the open-source story is theater.

#### R038 · Build a real PDF export instead of window.print()  🟡
`medium` · effort `M` · _frontend_ · via _Product designer; Vaporware audit_

- **Problem:** 'Download PDF' is window.print() in 3 places (confirmed), producing whatever the browser renders; for a tool whose value is 'a range you paste in a memo,' the take-home artifact is the least controlled surface.
- **Fix:** Server-render a branded one-pager PDF with citations as footnotes per the U10 export spec, or relabel to 'Print' and ship a validated branded print stylesheet. Lean on the real Markdown export meanwhile.
- **YC impact:** The memo artifact is the virality loop; a raw print dialog wastes it.

#### R096 · Persist a queryable primitive→TAM provenance/dependency graph  🟡
`medium` · effort `M` · _data_ · via _Staff backend_

- **Problem:** Pins live only inside emitted TAMOutputs; there's no stored edge graph, so you can't answer 'which TAMs depend on FRED series X / what breaks if it updates,' and the Q5 change-notification feature is unimplemented.
- **Fix:** Persist primitive→TAM dependency edges on recompute (cheap given InputUsed) to enable impact analysis and 'this source updated, here are the N affected TAMs.'
- **YC impact:** Turns the provenance moat from inline hashes into a demoable feature.

#### R102 · Ship the thinnest read+write annotation loop (red-dot-in-context)  🟡
`medium` · effort `M` · _product_ · via _Product strategist; Vaporware audit_

- **Problem:** data/annotations is empty (0, confirmed), the U8 red-dot annotation UI is unwired, and the annotation panel hardcodes 'No expert annotations'; the community/expert flywheel has zero on-screen presence.
- **Fix:** Let a Clerk-signed-in user attach a text annotation/challenge to any measurement rendered as the red-dot-in-context, and seed 2-3 expert annotations on the disagreement view.
- **YC impact:** The expert flywheel is the long-term moat; with zero annotation surface YC sees a static database, not a network.

#### R097 · Add usage-based 'data network effect' signals (most-used/forked primitives)  🟡
`medium` · effort `L` · _product_ · via _GTM strategist_

- **Problem:** Nothing gets better with usage: recomputes are audited but not mined, no saved/forked TAMs accrue, no most-trusted-primitive signal — the data network-effect thesis runs on a static seed bank.
- **Fix:** Surface 'this primitive is used in N TAMs,' which overrides users converge on (a crowd prior), and rank saved forks; mine the audit stream.
- **YC impact:** A visible mechanic where usage improves the data is the difference between a wrapper and a moat.

#### R098 · Add saved builds + 'your sources changed, re-size' retention email  🟡
`medium` · effort `L` · _product_ · via _GTM strategist_

- **Problem:** No notifications, no saved persistent builds, no change alerts; the schema promises Q5 sensitivity-aware change notifications but nothing emits them — a one-shot calculator with no reason to return.
- **Fix:** Once TAMs persist, add per-user saved builds and a 'sources for your TAM updated — re-size?' email using dated snapshots and the trajectory endpoint.
- **YC impact:** 'Your sourced numbers auto-update and we ping you' is a retention story competitors without provenance can't tell.


### Trust & Reliability

#### R014 · Remove the hardcoded fake 'j.vega · verified · 27 contribs' contributor  🔴
`critical` · effort `S` · _frontend_ · via _Product designer_

- **Problem:** Sidebar.tsx (lines 120-121, confirmed) renders a fabricated 'verified' user with a fake contribution count in always-visible chrome — the single most damaging credibility leak on a product whose pitch is sourced, no-invented-numbers data.
- **Fix:** Wire to the real Clerk user when signed in; show a 'Sign in' affordance or nothing when signed out. Never ship a fabricated verified contributor.
- **YC impact:** Partners pattern-match fake social proof as an instant red flag on a trust product.

#### R041 · Enforce SHA256 snapshot integrity against stored source content  🔴
`critical` · effort `L` · _backend_ · via _SRE/trust; Skeptical VC_

- **Problem:** The 'all SHA256-pinned' claim is a 64-char-hex regex check; no snapshot content is ever stored or re-hashed, ~90 SHAs are reused across multiple files, and modeled primitives carry SHAs for URLs that 404. The pins are decorative.
- **Fix:** Store fetched source snapshots content-addressed (data/snapshots/<hash>), add a validator that recomputes sha256 over stored bytes and fails CI on mismatch/missing, and surface 'snapshot verified' vs 'unverified' in the UI.
- **YC impact:** The first diligence question is 'prove this number is real and unaltered'; today the answer is 'we check it's 64 characters.'

#### R015 · Stop fabricating source-tier sparklines on concept cards  🟠
`high` · effort `S` · _frontend_ · via _Product designer_

- **Problem:** ConceptCard.tsx invents a 55/25/20 tier distribution from measurement_count and renders it as a TierSparkline that looks like real per-concept provenance — exactly the 'invented figure' CLAUDE.md forbids, on every landing card.
- **Fix:** Expose a real per-concept tier breakdown from the backend, or drop the sparkline until you have it. A product about provenance must not fake provenance visuals.
- **YC impact:** A data-integrity moat can't ship fabricated data-integrity visuals.

#### R042 · Enforce unit-checking on the interactive primitive swap path  🟠
`high` · effort `S` · _backend_ · via _Skeptical VC; SRE/trust_

- **Problem:** framework_assumptions lets a user re-point an input to any existing primitive during /build/recompute; _build_scenario validates only that the slug exists, never that its unit matches the input signature — a 'people' primitive can be bound into a 'percent' slot.
- **Fix:** After resolving a re-pointed/overridden input, assert resolved.unit.kind/dimension == input_def.unit_signature and raise EvaluatorError on mismatch.
- **YC impact:** Your 'unit-checked recompute' differentiator has a demoable counterexample that produces nonsense.

#### R043 · Add freshness/staleness signaling on primitives and TAMs  🟠
`high` · effort `S` · _frontend_ · via _SRE/trust_

- **Problem:** Primitives range from as_of 2010 to 2024 but the UI only prints raw dates; a 16-year-old number can size a 2026 TAM with no 'stale' badge.
- **Fix:** Compute data age at render, show a 'stale / N years old' badge above a threshold and on expired primitives, and propagate a worst-case freshness indicator to the TAM result and into export footnotes.
- **YC impact:** An operator who cites a stale number and gets burned in a board meeting churns and tells everyone.

#### R024 · Add request-ID tracing, error reporting, and latency/cost metrics  🟠
`high` · effort `M` · _ops_ · via _Staff backend; SRE/trust_

- **Problem:** No Sentry/OTel/Prometheus anywhere (confirmed); no request correlation IDs, no p95, no failure-rate alerting on a product with multi-second LLM calls in the hot path.
- **Fix:** Add a request-ID middleware into structlog contextvars, wire Sentry on FastAPI + Next.js with release tagging, emit timing around each resolver pipeline step, and alert on /resolve failure rate and /healthz/llm available=false.
- **YC impact:** A CTO asks 'show me p95 on /resolve' — you can't. For LLM-in-the-loop, latency/cost observability is how you prove unit economics.

#### R023 · Add auth + per-key metering on the API, starting with /resolve  🟠
`high` · effort `L` · _backend_ · via _Staff backend; SRE/trust_

- **Problem:** The only middleware is CORS; /resolve is unauthenticated, unmetered, and burns paid Anthropic+Exa tokens on every anonymous request — a literal cost-DoS and no substrate for the documented Phase-2 paid product.
- **Fix:** Add an APIKeyHeader dependency + usage_events table (copy the audit pattern) keyed by key/tenant, and a token-bucket limiter + query length cap on /resolve. Gate it behind Clerk in prod.
- **YC impact:** YC asks 'how do you charge?' and 'who can drain your credits?' — both currently have no code behind them.

#### R051 · Default CORS to an explicit allowlist and fail-closed in prod  🟡
`medium` · effort `S` · _ops_ · via _Staff backend; SRE/trust_

- **Problem:** config defaults cors_origins=['*'] with methods/headers '*'; lockdown depends entirely on an env var, with no code assertion that prod implies a non-wildcard list (unlike the Clerk prod-safety pattern).
- **Fix:** In create_app(), if env==prod and origins==['*'] with no regex, raise on startup; default methods/headers to an explicit allowlist.
- **YC impact:** Wildcard CORS on an unauthenticated paid endpoint is a 30-second ding for a security-conscious partner.

#### R078 · Show consistent value semantics on graph nodes (mark unsourced inputs)  🟡
`medium` · effort `S` · _frontend_ · via _Product designer_

- **Problem:** PrimitiveCard falls back to the role_name when value/unit is missing, so a node reads '$4,200' in one framework and 'population' (a label) in another — users can't tell sourced numbers from un-enriched placeholders.
- **Fix:** Always render a consistent value slot; show an explicit muted 'unsourced / no value' marker instead of substituting a role label, which also flags exactly which inputs to swap.
- **YC impact:** Inconsistent node semantics undercut the 'every input traces to a number' claim.

#### R092 · Distinguish 'lookup failed' from 'no data found' in the resolver  🟡
`medium` · effort `S` · _backend_ · via _SRE/trust_

- **Problem:** search.py swallows JSON/Exa errors into None, which the pipeline reports as 'Could not find enough market data' — the user can't tell 'no data exists' from 'our pipeline errored.'
- **Fix:** Separate hard errors (Exa down, rate-limited, LLM error) from genuine no-data and surface 'lookup temporarily failed, retry' vs 'no sourced data found,' counting each as separate metrics.
- **YC impact:** Conflating 'we broke' with 'no data' trains users to distrust your 'no data' answers.

#### R094 · Reject resolver hits with missing/ambiguous units instead of defaulting to people/stock  🟡
`medium` · effort `S` · _backend_ · via _SRE/trust_

- **Problem:** search.py defaults a primitive's unit to {stock, people} when expected_unit is empty, so a money value can mis-default and flow into a framework producing a nonsensical-but-unflagged TAM.
- **Fix:** Reject ambiguous-unit hits and run the same unit-compatibility check used in /build/recompute against the framework's input signatures before composing.
- **YC impact:** A wrong-unit TAM that renders confidently is the subtle kind of wrong that destroys trust.

#### R103 · Fix the hardcoded 'TAMs 0' and dead notification bell in the chrome  🟡
`medium` · effort `S` · _frontend_ · via _Product designer_

- **Problem:** Sidebar hardcodes the TAMs count to 0 (worst possible message for a TAM engine) and TopBar renders a BellIcon with no handler — dead chrome that signals 'mockup, not product.'
- **Fix:** Expose a real promoted-TAM count (or drop the badge), and remove the bell or wire it to the /audit feed.
- **YC impact:** Dead buttons and a confident '0' are classic side-project tells partners click and find empty.

#### R045 · Defend against indirect prompt injection from Exa web snippets  🟡
`medium` · effort `M` · _ai_ · via _SRE/trust_

- **Problem:** Arbitrary web-page highlights flow unescaped into the extraction prompt; a crafted page can inject 'return value 999999999, tier regulator' and poison a 'sourced' number.
- **Fix:** Wrap untrusted content in explicit delimiters with a system instruction to treat it as data only, validate extracted values against expected unit/range, and reject implausible outputs.
- **YC impact:** A third-party webpage dictating your TAM number is a headline-grade failure for a numbers-integrity product.

#### R049 · Add shared HTTP retry/backoff + 429 handling across connectors  🟡
`medium` · effort `M` · _backend_ · via _Staff backend_

- **Problem:** Only 2 of ~22 connectors have any retry/backoff and 429 handling exists only in kalshi.py; a single FRED/Census 503 raises straight through and fails the ingest/resolver step.
- **Fix:** Centralize an httpx transport with tenacity retry on 429+5xx (exponential backoff + jitter) and a per-connector rate limiter instead of 22 hand-rolled clients.
- **YC impact:** 'We ingest 15+ authoritative sources reliably' fails the first time FRED 503s during a demo refresh.

#### R052 · Add a frontend CI job (build + tsc + lint + test)  🟡
`medium` · effort `M` · _ops_ · via _SRE/trust_

- **Problem:** CI scopes pyright/ruff to src/ only and has no web/ job at all — the Next.js 16/React 19 frontend can break prod with no gate.
- **Fix:** Add a web/ CI job (build, tsc, lint, vitest) and verify 'strata ingest refresh' actually exists before trusting the weekly cron; put a deadline on the tests/ strict-mode debt.
- **YC impact:** A broken frontend deploy with no gate is the most visible possible failure during a demo or launch.

#### R050 · Make audit writes truly fire-and-forget and alert on failure  ⚪
`low` · effort `S` · _backend_ · via _Staff backend; SRE/trust_

- **Problem:** record_audit_safe opens a fresh session and is await-ed inline on every request (adding a pool checkout to user latency) yet silently swallows failures, so the 'audit trail' can have invisible gaps and records actor=None.
- **Fix:** Move audit writes to a BackgroundTask/queue, emit a metric/alert on write failure, and record the real actor once /resolve is authed.
- **YC impact:** A lossy unattributed log that drops rows won't survive an enterprise security review — the natural buyer for defensible TAM.

#### R109 · Reconcile the test/connector count drift and add a nightly live-smoke suite  ⚪
`low` · effort `S` · _ops_ · via _Staff backend; SRE/trust_

- **Problem:** Docs claim 453 tests (actual ~421) and 15 connectors (22 in dispatch); connector tests are all mocked with no network markers, so upstream schema drift isn't caught.
- **Fix:** Reconcile the doc numbers and add a small gated nightly live-smoke suite so upstream API contract breaks surface before a demo.
- **YC impact:** Founders citing inflated/inconsistent metrics in their own docs is a DD red flag; a real live-smoke tier beats a big mocked count.


### Fundability Narrative

#### R115 · Get 3-5 design partners using it on live deals and capture WTP  🔴
`critical` · effort `M` · _gtm_ · via _Hostile partner_

- **Problem:** Zero evidence of a user: no billing, no analytics, no waitlist, no logos, no usage; the repo is a beautiful demo with no demand signal against incumbents (PitchBook, CB Insights, internal data teams).
- **Fix:** Before the interview, get 3-5 VCs/operators to use it on a live deal, capture quotes + a willingness-to-pay number, and instrument sessions so you can show real usage ('we sized 40 deals for 3 funds last month').
- **YC impact:** YC funds traction or a sharp wedge; with neither this reads as a side project.

#### R057 · Narrow to the portfolio-TAM wedge and instrument the funnel  🟠
`high` · effort `M` · _gtm_ · via _GTM strategist; Hostile partner_

- **Problem:** Positioning is broad ('VCs and operators'); the genuinely novel asset (the TAM-77 portfolio pipeline) isn't surfaced as the product, and there's no analytics beyond an internal audit table.
- **Fix:** Lead with 'paste your portfolio, get a defensible TAM-per-company deck in 10 minutes,' instrument the landing→query→/tam→share funnel with PostHog, and capture a willingness-to-pay number from 3-5 design partners.
- **YC impact:** YC funds a sharp wedge with a measured funnel, not a horizontal 'market sizing engine.'

#### R059 · Curate a small set of TAMs that provably beat a public alternative  🟠
`high` · effort `M` · _data_ · via _Hostile partner_

- **Problem:** The flagship TAM-77 worked example computes Skyramp at $792M vs a $4-6B target (~6x miss); shipping the misses as a showcase tells an analyst not to trust it.
- **Fix:** Curate 5-8 TAMs where the bottoms-up number is tight and beats a public source, show the side-by-side, and explain why yours is better (fresher source, visible math). Don't demo the misses.
- **YC impact:** A partner asks 'is this number actually right?' — your own doc currently answers 'often no.'

#### R116 · Reframe the market from 'cheaper reports' to an expanding workflow wedge  🟠
`high` · effort `M` · _gtm_ · via _Hostile partner_

- **Problem:** Positioning as 'eat the bottom 80% of IBISWorld' is a low-ACV, commoditizing category general LLMs already nibble; there's no articulated 'why a $1B company' or 'why now beyond LLMs exist.'
- **Fix:** Reframe to a pull wedge: embedded TAM inside the VC workflow (Affinity/Harmonic) or auto-refreshed sizing for every company in a fund's pipeline (the TAM-77 pipeline is the most novel asset). Lead with that.
- **YC impact:** Partners reject 'cheaper version of a shrinking category'; you need a wedge that expands.

#### R058 · Prepare a crisp 'why not just ask ChatGPT' answer with a live side-by-side  🟠
`high` · effort `L` · _gtm_ · via _Hostile partner; AI/ML_

- **Problem:** The dynamic path IS Claude+Exa producing a number a VC can get free in the chat window; the only differentiation is a tiny curated registry that isn't yet demonstrably better.
- **Fix:** Make the curated layer win on verifiability + freshness: continuously-refreshed regulator series with snapshot pins and a 'show me the exact BLS series and date' trail, demoed side-by-side against raw ChatGPT.
- **YC impact:** This is THE question; without a crisp win over the free model there is no company.

#### R053 · Reconcile self-contradicting docs (open vs proprietary, versions, counts, ghost routes)  🟡
`medium` · effort `S` · _product_ · via _Hostile partner; Pitch coach_

- **Problem:** README implies open-source while LICENSE is proprietary and vision.md says 'not closed-source'; status shows both v0.4.0 and v0.3.0; connector counts drift (15 vs 22); test count claimed 453 vs actual ~421; /contribute route referenced but absent.
- **Fix:** One honest pass: single version, real connector/test counts, remove ghost routes, reconcile open vs proprietary.
- **YC impact:** Self-contradicting docs are the documents a partner skims first and signal 'demo, not company.'

#### R099 · Resolve the analyst-paraphrase takedown/IP exposure before scaling SEO  🟡
`medium` · effort `S` · _product_ · via _GTM strategist_

- **Problem:** Roadmap v0.2's takedown endpoint for the analyst-paraphrase tier (Q40) is unshipped; paraphrasing paywalled analyst figures onto indexable pages is exactly the legal surface that kills a data startup as SEO traction arrives.
- **Fix:** Drop analyst-paraphrase from public/indexed pages until a takedown endpoint + 'paraphrase, not reproduction' provenance label exists; clean the IP posture before programmatic SEO amplifies exposure.
- **YC impact:** YC diligence asks about data rights; an unaddressed paraphrase-of-paywalled risk is fundability-existential.

#### R105 · Bring the promised 3-panel build layout or update the spec to match  🟡
`medium` · effort `L` · _product_ · via _Product designer_

- **Problem:** The MVP spec describes a 3-panel build 'wiring' workhorse but BuildWorkspace ships a 2-column layout with no persistent left context (pillars/constraints live on a separate /graph page).
- **Fix:** Either add a left rail bringing pillar/constraint context into /build, or update the spec/docs so the demo doesn't contradict the deck.
- **YC impact:** A visible gap between docs and shipped invites the 'did you actually build it' question.

#### R054 · Replace invented SITE_STATS with a live /stats endpoint  ⚪
`low` · effort `S` · _frontend_ · via _Product designer; GTM strategist_

- **Problem:** page.tsx hardcodes SITE_STATS (30/350/87) but real counts are 32/360/88, and Sources is permanently 87 (no endpoint) — invented, slightly-wrong stats on a 'don't invent numbers' homepage.
- **Fix:** Add GET /stats returning live counts (incl. sources) and bind all four StatBlocks to it.
- **YC impact:** A sharp investor who notices the homepage stats are hardcoded-and-wrong questions every other number you show.

#### R107 · Editorial sweep for copy voice and casing consistency  ⚪
`low` · effort `S` · _product_ · via _Product designer_

- **Problem:** Microcopy mixes registers and casing ('recomputing…', 'Thinking…', lowercased mid-sentence banners, inconsistent curly quotes/ellipses) — small, but reads as unedited in aggregate.
- **Fix:** Adopt sentence-case for status/microcopy, standardize quote/ellipsis usage, and pass an editorial sweep for tone.
- **YC impact:** Polished copy is cheap signal that the team sweats details.

#### R112 · Make the headline version/status a live /healthz pill, not a hardcoded string  ⚪
`low` · effort `S` · _frontend_ · via _Pitch coach_

- **Problem:** page.tsx footer hardcodes 'v0.4.0 — backend live' while pitching the PR #55 'Strata Live' story, and the GitHub link is the bare placeholder.
- **Fix:** Replace the hardcoded version with a live status pill driven by /healthz and point GitHub at the real repo.
- **YC impact:** Self-labeling as an older version while demoing 'Live' features reads as unfinished.

#### R113 · Don't demo premature SaaS scaffolding (auth/dashboard) over the wedge  ⚪
`low` · effort `S` · _product_ · via _Hostile partner_

- **Problem:** PR #55 added Clerk auth, /dashboard, and an audit feed before a single user exists — effort spent on 'looks like a SaaS' over validating demand.
- **Fix:** Keep the auth scaffolding but don't lead the interview with it; redirect demo energy to one killer vertical demo and a design partner.
- **YC impact:** Building login before users is a classic 'feature, not company' tell.

#### R114 · Don't lead with 22 connectors; show the 4-5 that produce trusted primitives  ⚪
`low` · effort `S` · _gtm_ · via _Hostile partner_

- **Problem:** 22 connector files exist but only ~5 (BLS/FRED/Census/EDGAR/WorldBank) feed real primitives; the rest are built-but-unused surface area that reads as 'wide and shallow.'
- **Fix:** In the pitch show the 4-5 connectors that produce trusted primitives and the depth in one vertical, not the breadth.
- **YC impact:** Partners read breadth-without-data-depth as a founder who builds infra to avoid talking to customers.


### Product

#### R035 · Add a /compare?a=&b= TAM-diff view  🟠
`high` · effort `M` · _product_ · via _Product strategist_

- **Problem:** Fork just changes a URL; there's no way to diff a fork against its parent, even though hash-addressed state makes the substrate nearly free.
- **Fix:** Add a /compare view that diffs two BuildStates (which assumptions differ) and their resulting scenario values as a side-by-side waterfall of what changed.
- **YC impact:** Comparative diffing turns a single-player calculator into a multi-player audit trail — the thing that makes a fund standardize on you.
