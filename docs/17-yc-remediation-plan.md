# Strata — YC Remediation Plan (sequenced waves)

> Companion to [`16-adversarial-yc-readiness-review.md`](16-adversarial-yc-readiness-review.md). Sequences the 19 critical + 36 high findings into execution waves. Principle from the audit: **ruthless depth on ONE wedge, not more breadth.** Make the demo undeniable and the thesis true on the surfaces a partner actually clicks, before adding connectors/concepts.


## Wave sequencing at a glance

```
WAVE 0  Demo-blockers (this week)     persist TAMs · /resolve→registry · scenario-tree on resolve
        mostly S/M                    quarantine Kalshi · 5-8 triangulated demo concepts · OG+SSR share
WAVE 1  AI defensibility + data rigor  eval harness · verifier/grounding · kill fake citations
        the credibility core          sha256 enforcement · independence > 0 · staleness signaling
WAVE 2  Motion & visual craft          recompute payoff animation · live graph · number count-ups
        the 'expensive' feel           tornado/sensitivity viz · skeleton→content morphs
WAVE 3  Architecture + trust + ops      auth/metering · rate-limit /resolve · observability · CI depth
WAVE 4  GTM, moat & narrative           programmatic SEO · embeddable widget · contribution loop · pitch
WAVE 5  Integrations · MCP · pipeline    Strata-as-MCP (connect to Claude) · OAuth data connectors
        the data network-effect moat     (Salesforce/HubSpot/Snowflake/Stripe) · /integrations gallery + brand icons
```


## Wave 0 — Demo-blockers (make the thesis TRUE on clicked surfaces)

_Every item here is something a partner discovers in 60 seconds. Mostly S/M. Ship before anything else._

| ID | Sev | Eff | Title | The move |
|---|---|---|---|---|
| R002 | crit | M | Make the dynamic resolver emit a real scenario tree, not a s | Run the resolved inputs through the same scenario-tree builder as the curated path (size_concept), propagating per-primitive uncertainty.range into low/base/high branches… |
| R003 | crit | M | Unit-check resolver-multiplied primitives before composing a | Before multiplying, assert a valid unit signature (one currency/people base × dimensionless multipliers), normalize percentages to decimals, reject same-dimension×same-di… |
| R004 | crit | M | Route /resolve through the curated registry before the LLM f | Run real slug resolution (resolver/slug.py) on /resolve: a registry hit returns the fully-composed unit-checked scenario tree; only genuinely novel queries fall to the st… |
| R005 | crit | S | Quarantine the 202 Kalshi prediction-market primitives out o | Move prediction-market data into a clearly separated 'signals' namespace (or drop it), report the honest sizing-grade count (~88 regulator / ~158 non-prediction), and add… |
| R006 | crit | M | Seed 5-8 hero concepts with genuinely competing measurements | For top demo concepts seed 4-6 genuinely competing sourced measurements each (e.g. US dev headcount: BLS OEWS vs LinkedIn vs Stack Overflow) and wire competing_concepts l… |
| R007 | crit | L | Give 5-8 demo concepts a second independent framework so tri | Author a second method-family-distinct framework (bottoms-up AND top-down) for each flagship concept so the UI shows two methods converging within Nx. Fewer concepts each… |
| R008 | crit | M | Replace fake strata.internal/strata.ai citation URLs with re | Either publish a real methodology page per modeled multiplier with reasoning + comparable anchors, or downgrade them to explicit user-adjustable assumption sliders clearl… |
| R010 | crit | L | Propagate primitive uncertainty.range into low/base/high bra | Sample/propagate each input's uncertainty.range through the multiplicative evaluator to emit true conservative/base/aggressive branches per scenario. Make uncertainty.ran… |
| R012 | crit | L | Ship bottoms-up vs tops-down convergence as the hero output | Add a triangulation layer that groups scenarios by method_family, computes the bottoms-up/tops-down ratio and a convergence score, and surfaces 'bottoms-up $X / tops-down… |
| R019 | crit | S | Feature triangulating concepts on the landing page, not slic | Hand-pick 3 featured slugs that triangulate (e.g. doc-gen-pc-insurance) showing a real low–high band and a lit donut, with 'triangulated from N independent methods' as th… |
| R026 | crit | L | Build an eval/golden-set harness for the resolver | Build a 20-40 query golden set with verified expected lens, primitive roles, source URLs, and a TAM order-of-magnitude band; run nightly with the real LLM scoring extract… |

## Wave 1 — AI defensibility + data rigor (the credibility core)

_Make 'defensible numbers' survive diligence: grounding, verifier, eval harness, integrity enforcement._

| ID | Sev | Eff | Title | The move |
|---|---|---|---|---|
| R009 | high | L | Ship the L3 latent_demand framework (population × adoption × | Build the 3-input L3 framework with sourced/ranged population, adoption, and WTP inputs. Add 2-3 more frameworks per vertical to credibly claim a 'library' rather than 5 … |
| R011 | high | M | Build a sensitivity / tornado chart on the existing recomput | Perturb one input at a time across its low/mid/high and render a tornado chart in the /build right rail ranking inputs by their swing on the final TAM, reusing the recomp… |
| R015 | high | S | Stop fabricating source-tier sparklines on concept cards | Expose a real per-concept tier breakdown from the backend, or drop the sparkline until you have it. A product about provenance must not fake provenance visuals. |
| R023 | high | L | Add auth + per-key metering on the API, starting with /resol | Add an APIKeyHeader dependency + usage_events table (copy the audit pattern) keyed by key/tenant, and a token-bucket limiter + query length cap on /resolve. Gate it behin… |
| R024 | high | M | Add request-ID tracing, error reporting, and latency/cost me | Add a request-ID middleware into structlog contextvars, wire Sentry on FastAPI + Next.js with release tagging, emit timing around each resolver pipeline step, and alert o… |
| R027 | high | L | Ground-check extracted numbers against captured source snaps | Capture+hash the snippet/URL content at extract time, reject hits whose digit-string isn't substring-present in the snapshot, extract from top-3 results independently and… |
| R028 | high | S | Derive source_tier from the resolved domain, never from the  | Map source_tier deterministically from the domain (allowlist of .gov/regulator, known aggregators); default unknown to 'community'; never let the model upgrade a tier. |
| R030 | high | M | Let parsed lens determine primitive arity instead of hardcod | Derive arity from the lens, bind primitives to named framework roles from the registry's framework definitions, and reject when required roles are unfilled — instantiate … |
| R039 | high | M | Use semantic concept matching on the registry-hit hot path | Route the query through resolver/slug.py (already used by the CLI) or add embedding-based concept matching on the registry-hit path too. |
| R042 | high | S | Enforce unit-checking on the interactive primitive swap path | After resolving a re-pointed/overridden input, assert resolved.unit.kind/dimension == input_def.unit_signature and raise EvaluatorError on mismatch. |
| R043 | high | S | Add freshness/staleness signaling on primitives and TAMs | Compute data age at render, show a 'stale / N years old' badge above a threshold and on expired primitives, and propagate a worst-case freshness indicator to the TAM resu… |
| R080 | high | L | Replace the fake fuzzy interpretation cards with real LLM co | Either show real per-concept $ range previews under each interpretation (cheap, you have buildQuery) or wire the actual LLM parse for ambiguous queries; drop the arbitrar… |
| R085 | high | L | Wire orphan primitives into frameworks or remove them | Wire orphans into frameworks (real depth) or remove them, and add a CI check that fails on unreferenced non-prediction primitives so the corpus stays load-bearing. |
| R091 | high | M | Drop raw XBRL frame sums as primitives and fix broken metada | Remove XBRL frame sums as primitives (not addressable markets), fix 'unknown-sum' sources, and set as_of to the data period. |

## Wave 2 — Motion & visual craft (the 'expensive' feel)

_The founder's explicit worry. Move beyond entrance animations to the recompute payoff + a live centerpiece graph._

| ID | Sev | Eff | Title | The move |
|---|---|---|---|---|
| R013 | crit | M | Add the recompute number-tween payoff moment | Animate the headline value with a Motion spring from old→new over ~500ms, crossfade the independence donut arc, add an accent border pulse on the fresh value, a ±% delta … |
| R031 | high | L | Animate the scenario graph: entrance stagger, hover lift, da | Wrap nodes in motion.div with a tier-depth-staggered fade+scale entrance, spring scale-1.03 on hover, and a stroke-dash flow animation on edges feeding a just-overridden … |
| R032 | high | M | Adopt AnimatePresence for all modals and the override panel | Build a shared Motion <Modal> with backdrop fade+blur and a panel spring from scale 0.96/y:8, with proper exit animation. Migrate the native <dialog> palette to it or use… |
| R060 | high | M | Add detail/density hierarchy to the build view layout | Make the headline+graph a visually dominant 'result' zone, group the two charts side-by-side on wide screens, demote trajectory to a lighter treatment, and vary padding/b… |
| R061 | high | M | Establish a real 4-5 step type scale with weight/color contr | Define a 4-5 step scale and use weight/color (not just size) to separate primary content from metadata; promote at least one number/label per card to high-contrast fg-1. |
| R062 | high | M | Make the scenario graph responsive and add fullscreen/mobile | Make height responsive (min 60vh desktop), add fit/expand-to-fullscreen, auto-scale node size to viewport, and give mobile a stacked list fallback of the same scenario tr… |
| R067 | high | M | Morph skeletons into content with a directional shimmer | Crossfade skeleton→content via AnimatePresence (~200ms), upgrade pulse to a translateX gradient shimmer, and match skeleton shapes to the final layout. |

## Wave 3 — Architecture, trust & ops (company substrate)

_Turn the single-player demo into a fundable product: auth/metering, rate-limit the paid LLM endpoint, observability._

| ID | Sev | Eff | Title | The move |
|---|---|---|---|---|
| R014 | crit | S | Remove the hardcoded fake 'j.vega · verified · 27 contribs'  | Wire to the real Clerk user when signed in; show a 'Sign in' affordance or nothing when signed out. Never ship a fabricated verified contributor. |
| R021 | high | S | Wire the configured DB pool into create_async_engine | Pass **settings.engine_pool_kwargs() into create_async_engine. One-line fix. |
| R022 | high | M | Load composites/annotations/tam_outputs from DB in Registry. | Load composites/annotations/tam_outputs from DB in from_db(); add an auth-gated POST /admin/reload-registry or a short-TTL cache so 'strata db seed' takes effect without … |
| R041 | crit | L | Enforce SHA256 snapshot integrity against stored source cont | Store fetched source snapshots content-addressed (data/snapshots/<hash>), add a validator that recomputes sha256 over stored bytes and fails CI on mismatch/missing, and s… |

## Wave 4 — GTM, moat & narrative

_Growth loop + defensibility story: programmatic SEO on persisted TAMs, embeddable widget, contribution loop, crisp pitch._

| ID | Sev | Eff | Title | The move |
|---|---|---|---|---|
| R020 | high | M | Rename portfolio-codename concepts to the markets a VC actua | Set the public name to a clean market term ('AI cybersecurity tooling, US') with the codename as internal metadata, and add query aliases so common markets route determin… |
| R036 | high | S | Wire Fork to a working pre-populated /build state | Wire Fork to /build/<hash>?s=<encoded BuildState> using the existing encodeState/BuildState machinery so it lands in the editable workspace pre-populated. |
| R037 | high | M | Ship an embeddable /embed/<hash> TAM widget + oEmbed | Add /embed/<hash> (minimal chrome: midpoint + band + provenance footer + 'sized by Strata' backlink) and an oEmbed endpoint so Notion/Substack auto-unfurl. Document GET /… |
| R056 | high | M | Surface the provenance moat instead of leaving it a TODO | Expose per-input source_tier on inputs_used and render the stacked tier bar + 'N regulator / M analyst / K community, every number reproducible from these sources' + one-… |
| R057 | high | M | Narrow to the portfolio-TAM wedge and instrument the funnel | Lead with 'paste your portfolio, get a defensible TAM-per-company deck in 10 minutes,' instrument the landing→query→/tam→share funnel with PostHog, and capture a willingn… |
| R058 | high | L | Prepare a crisp 'why not just ask ChatGPT' answer with a liv | Make the curated layer win on verifiability + freshness: continuously-refreshed regulator series with snapshot pins and a 'show me the exact BLS series and date' trail, d… |
| R059 | high | M | Curate a small set of TAMs that provably beat a public alter | Curate 5-8 TAMs where the bottoms-up number is tight and beats a public source, show the side-by-side, and explain why yours is better (fresher source, visible math). Don… |
| R064 | high | M | Add the right-click context menu and 250ms hover ghost cards | Add a right-click menu (Expand children / Suggest framework) and a 250ms-delayed hover ghost card showing value+source+snapshot. Cheap, demo-able, promised. |
| R075 | high | M | Add clickable example-query chips and a /demo autoplay route | Add 3-4 clickable example chips under the hero routing to triangulating concepts, and a /demo route that autoplays query→range→node edit→recompute→share. Rehearse it as T… |
| R079 | high | M | Wire /browse to a real is_promoted curation endpoint | Add an is_promoted flag and GET /tams?promoted=true with trending/most-forked ordering so /browse is a crawlable hub and a reason to return. |
| R108 | high | M | Guarantee the resolver path on the public demo (funded key + | Ensure a funded key in prod, pre-compute and cache resolved TAMs for the top 100 likely VC queries, and make the fallback graceful-but-impressive so cold demos always hit… |
| R111 | high | M | Make the recompute loop the landing hero, not a buried /buil | Lead the landing with an autoplaying real interactive 'change this developer-count assumption, watch the $129B TAM move and citations update' as the first thing seen. |
| R116 | high | M | Reframe the market from 'cheaper reports' to an expanding wo | Reframe to a pull wedge: embedded TAM inside the VC workflow (Affinity/Harmonic) or auto-refreshed sizing for every company in a fund's pipeline (the TAM-77 pipeline is t… |

---

## Recommended first PR (Wave 0 vertical slice)

One coherent branch that makes the demo undeniable end-to-end:

1. **Persist TAMs** — add `upsert_tam` + `tam_outputs` store + `GET /tam/{hash}` so permalinks resolve (today they 404).
2. **Route `/resolve` through the registry first** — exact/fuzzy concept hit returns the real composed scenario tree; LLM path is fallback only.
3. **Scenario tree on the resolve path** — feed multiplied inputs through `size_concept` so the dynamic answer is narrow/base/broad, not a single point.
4. **Quarantine Kalshi** — move 202 prediction-market primitives into a `signals/` namespace; recompute the honest sizing-grade count.
5. **Seed 5–8 triangulated demo concepts** — each with ≥2 competing measurements (wire `competing_concepts`) and real low/base/high spread, so the disagreement view is live.
6. **Share-ready `/tam/<hash>`** — OG tags + SSR + a screenshot-worthy result so the link is the growth loop.

That slice alone moves the four 'biggest risks' that block YC and turns the genuinely-strong evaluator core into a narrative that survives diligence.

---

## Wave 5 — Integrations, MCP & the data-pipeline moat

_Why this is a wave, not a feature: it is the only item that turns "thin LLM wrapper" into a **data network effect**. Inbound connectors let a fund pipe its own CRM/portfolio data in to size **their** TAM (private primitives → stickiness + proprietary data). Outbound MCP makes Strata a **tool inside Claude** (distribution where the users already are). Both directly answer the YC moat question and the "enhance the data pipeline" goal._

### 5A — Strata as an MCP server ("Connect to Claude") — `critical` for distribution

Expose the registry + evaluator as MCP tools so any Claude / Claude Code / Desktop user can pull sourced TAMs without leaving their chat.

- `strata-mcp` server (Python, `mcp` SDK) exposing tools: `search_concepts`, `get_primitive`, `size_tam(concept|query)`, `list_frameworks`, `resolve_market(query)`. Each returns the **sourced, hash-pinned** payload — the anti-hallucination story becomes "Claude's numbers now carry Strata citations."
- Read-only by default; auth via the same API key as Wave 3 metering.
- Ship a one-click `claude mcp add` snippet + a hosted remote MCP endpoint.
- **YC line:** "We're the sourced-market-data layer for every AI agent" — rides the agent wave instead of competing with PitchBook head-on.

### 5B — Inbound OAuth data connectors ("Connect your data sources") — the moat

A second connector class beside the 15 public-data clients: **per-user/org private sources** that enrich the pipeline.

- OAuth connector framework (`connectors/saas/`): **Salesforce, HubSpot, Snowflake, Stripe, QuickBooks, Google Sheets, Segment, Notion, Airtable** to start.
- Each maps tenant data → **private primitives** (scoped, never published to the public bank; tier `first_party`; banner `private`). E.g. HubSpot pipeline → bottoms-up revenue primitive; Stripe MRR → market-share denominator.
- Pipeline: `OAuth → fetch → normalize → private primitive → feeds the same evaluator`. Reuse the existing dispatch/convert pattern (`connectors/_dispatch.py`).
- Strict isolation: private primitives live in a per-org namespace, RLS in Postgres, never leak into `/browse` or other tenants.
- **YC line:** "Every fund that connects its portfolio data makes its own TAMs sharper and can't easily leave — that's the data network effect."

### 5C — `/integrations` gallery + brand-icon system — the surface (use the reference images)

A first-class page modeled on the three reference mockups:

- **Brand-icon registry** (`web/src/components/icons/brands/`): circular white/dark chips like the OpenCap card — GitHub, Slack, Gmail, Notion, Jira, Linear, Teams, Salesforce, HubSpot, Snowflake, Stripe, QuickBooks, Google Sheets, Segment, Airtable, Claude/Anthropic, plus the 15 gov sources (BLS, FRED, Census, EDGAR, World Bank, Kalshi, OECD, Eurostat, Comtrade, FDIC, CMS, EIA, NASS, FAA, openFDA). Source via `simple-icons` (SVG) + a few hand-traced marks; one `<BrandIcon name=… />` component with a tier ring.
- **Integrations gallery**: grid of cards `[icon · name · status(connected/available/coming-soon) · Connect button]`, grouped Inbound (data sources) / Outbound (Claude, Slack, export) / Public data bank (the 15).
- **"Old way vs new way" comparison card** (image 1 style): "Numbers without provenance" (red, broken) vs "Strata-sourced, agent-ready" (green, working) with the icon clusters.
- **Data-pipeline flow viz** (images 2 & 3 style): animated `sources → Strata engine (Documents/Web/Data-Analysis nodes + processing bar) → analyst/verifier review → outputs (TAM / report / API / MCP)`. Reuse the ReactFlow + motion stack already in `web/src/components`.
- **Connection wizard**: OAuth handshake modal → pick objects/tables → map to primitive roles → preview the private primitive → "now sizing with your data" banner.

### 5D — Brand & asset polish (the "add icons" ask, broadened)

- Replace remaining text-only nav/section markers with a coherent icon set (lucide for UI, `BrandIcon` for vendors).
- Connector status dots, source-tier ring colors, the MCP "live" pulse, animated edges between pipeline nodes.

### Wave 5 build order

1. `BrandIcon` registry + `/integrations` static gallery (icons + status, no live OAuth) — ships the visual immediately.
2. Strata MCP server (5A) — highest distribution leverage, read-only, no per-tenant data.
3. The pipeline flow viz + old/new comparison card (5C visuals).
4. One inbound OAuth connector end-to-end (HubSpot **or** Stripe) as the pattern, then fan out the rest.
5. Tenant isolation + private-primitive namespace hardening (gate before any real customer data).
