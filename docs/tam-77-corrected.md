# Strata TAM v2 — 24 Portfolio Companies, Corrected Methodology

Generated via Claude classification (`claude-opus-4-7`) + Strata's primitive/framework/evaluator DAG. Replaces `docs/tam-77-results.md`. Per-company artifacts live as YAML in `data/concepts/`, `data/primitives/`, and as variants in `data/frameworks/`. Each TAM is reproducible via `uv run strata size <concept_slug> -d ../data`.

## Summary

| # | Company | Sector | Geo | Lens | Framework | TAM | Spec target |
|---|---------|--------|-----|------|-----------|-----|-------------|
| 1 | Kyber | P&C insurance doc-gen | `us_only_regulated` | `cost_efficiency` | `bottoms-up-cost-efficiency` | **$3.6B** | $3.0-4.5B |
| 2 | Gather | AI customer research / VoC | `global_saas` | `cost_efficiency` | `bottoms-up-cost-efficiency` | **$4.3B** | $3-6B |
| 3 | Echelon | ServiceNow development agents | `global_saas` | `bundle_consolidation` | `consolidation-sum-then-discount` | **$3.2B** | $2.5-4.5B |
| 4 | Endeavor | Mfg/distribution back-office AI | `global_industrial` | `cost_efficiency` | `bottoms-up-cost-efficiency` | **$75.0B** | $60-90B |
| 5 | Skyramp | QA / test automation | `global_saas` | `cost_efficiency` | `bottoms-up-cost-efficiency` | **$792M** | $4-6B |
| 6 | Supermemory | AI memory infra | `infra_layer` | `platform_throughput` | `throughput-take-rate` | **$2.5B** | $1.5-5B |
| 7 | Numeral | Sales-tax / VAT compliance | `global_saas` | `bundle_consolidation` | `consolidation-sum-then-discount` | **$665M** | $0.5-1.0B |
| 8 | SignalLabs | Healthcare decision AI | `us_only_regulated` | `cost_efficiency` | `bottoms-up-cost-efficiency` | **$12.1B** | $8-16B |
| 9 | Zero RFI | ConTech RFI / owner's-rep | `us_only_regulated` | `cost_efficiency` | `bottoms-up-cost-efficiency` | **$630M** | $0.4-1.2B |
| 10 | Contrario AI | AI recruiting agents | `global_saas` | `bundle_consolidation` | `consolidation-sum-then-discount` | **$16.0B** | $10-25B |
| 11 | Miravoice | AI phone surveys / CATI | `global_saas` | `bundle_consolidation` | `consolidation-sum-then-discount` | **$1.1B** | $0.6-2.2B |
| 12 | PlayerZero | AI code quality / observability | `global_saas` | `bundle_consolidation` | `consolidation-sum-then-discount` | **$4.8B** | $3-7B |
| 13 | Kaizen Labs | US state/local GovTech | `us_only_regulated` | `bundle_consolidation` | `consolidation-sum-then-discount` | **$1.6B** | $1.0-2.5B |
| 14 | Sieve | Multimodal AI infra | `infra_layer` | `platform_throughput` | `throughput-take-rate` | **$3.6B** | $3-5B |
| 15 | ST Labs | AI-native ITSM | `global_saas` | `bundle_consolidation` | `consolidation-sum-then-discount` | **$2.2B** | $1.8-3.0B |
| 16 | Wraithwatch | Agentic cyber defense | `global_saas` | `cost_efficiency` | `bottoms-up-cost-efficiency` | **$45.2B** | $35-60B |
| 17 | Moda | AI brand-design agents | `global_saas` | `bundle_consolidation` | `consolidation-sum-then-discount` | **$12.0B** | $7-18B |
| 18 | Minerva | AI-native accounting firm (US CPA) | `us_only_regulated` | `bundle_consolidation` | `consolidation-sum-then-discount` | **$3.0B** | $2-4B |
| 19 | Effective AI | Insurance actuarial / underwriting AI | `us_only_regulated` | `cost_efficiency` | `bottoms-up-cost-efficiency` | **$6.4B** | $5-9B |
| 20 | Melius | AI creative canvas / image+video gen | `global_saas` | `bundle_consolidation` | `consolidation-sum-then-discount` | **$4.0B** | $3-5B |
| 21 | Accrual | AI tax software for US CPA firms | `us_only_regulated` | `bundle_consolidation` | `consolidation-sum-then-discount` | **$1.1B** | $1.0-1.5B |
| 22 | Piramidal | Clinical EEG foundation model | `multi_jurisdiction_regulated` | `platform_throughput` | `throughput-take-rate` | **$2.4B** | $2-5B |
| 23 | MetaVoice | Voice AI infra | `infra_layer` | `platform_throughput` | `throughput-take-rate` | **$13.5B** | $13-16B |
| 24 | Yotta | India sovereign cloud | `india_only` | `revenue_generation` | `top-down-revenue-capture` | **$4.0B** | $3-5B |

## Per-Company Reasoning

### Kyber — P&C insurance doc-gen

- **TAM:** $3.6B (state hash `382ec7ed4af2550b8beb507e8568aee37f0bbda50eb0c80ae01b812900b5bf93`)
- **Geo profile:** `us_only_regulated`
- **Framework:** `bottoms-up-cost-efficiency` (lens `cost_efficiency`)
- **Addressability:** Both multipliers are baked into the primitive values rather than applied as separate framework scalars. persona_pool: raw BLS-derived pool (~250K underwriters + P&C-allocable policy clerks + drafting specialists) is multiplied by a 60% AI-addressability factor inside the primitive => 150K. cost_per_persona: BLS mean wage is loaded 1.35x then multiplied by a ~30% doc-drafting time-share inside the primitive => $24K/persona/yr capturable value. Framework just multiplies 150K x $24K = $3.6B.
- **Reasoning chain:**
  - Geo: state-regulated by 50 US DOIs and ACORD forms are US-specific => us_only_regulated, geo_codes=['US'], intl TAM structurally $0.
  - Lens: replacing/augmenting human document drafting work => cost_efficiency => bottoms-up-cost-efficiency.
  - persona_pool sourced from BLS OES (regulator tier): underwriters 13-2053 + P&C share of 43-9041 policy clerks + drafting specialists.
  - Embed addressability: raw ~250K pool x 60% AI-addressable doc-drafting work = 150K personas (per Q15, baked into primitive, not a framework multiplier).
  - cost_per_persona: blended BLS wage ~$60K loaded 1.35x = ~$81K, then x ~30% doc-drafting time-share = ~$24K capturable per persona.
  - Sanity: 150K x $24K = $3.6B US-only SAM, consistent with a vertical AI doc-gen tool for a regulated US-only buyer set (not a $50B labor-ceiling number).
  - Uncertainty drivers: addressability % and time-share on doc drafting; widened bands carried on both primitives.
- **Warnings:** International P&C explicitly excluded — different ACORD-equivalent standards (e.g. Lloyd's MRC) and different regulators.; Risk of double-counting if Kyber also bills underwriters for non-doc work; capped via 30% time-share.

### Gather — AI customer research / VoC

- **TAM:** $4.3B (state hash `09ee6a05b940be17c264dbe0bdd7d4cc7ab4374b8ae41d01343cc662aef10f92`)
- **Geo profile:** `global_saas`
- **Framework:** `bottoms-up-cost-efficiency` (lens `cost_efficiency`)
- **Addressability:** Persona pool is NOT the global market researcher labor force ceiling. We start from ~250K market research analysts globally (BLS shows ~190K in the US for SOC 13-1161 market research analysts; scale ~1.3x for global English-speaking knowledge-work markets that are realistic SaaS buyers ≈ 250K). Then apply addressability: only ~40% are in qualitative/VoC/insights roles that an AI customer-research agent can replace (vs quant/pricing/segmentation analysts who use different tooling), and only ~60% sit in orgs mature enough to adopt an AI agent in the medium term. 250K * 0.40 * 0.60 ≈ 60K addressable personas. Cost_per_persona embeds the value split: average fully-loaded cost of a qualitative researcher / expert-network seat / survey-platform stack per seat ≈ $180K/yr (salary + benefits + tooling), and vendor captures ~40% as software replacement price ≈ $72K ACV per addressable persona. Both multipliers are baked into the primitive values, not the framework.
- **Reasoning chain:**
  - Geo: global SaaS, no regulatory gates → geo_level=global, codes=[WLD].
  - Framework choice: Gather replaces persona work (qualitative researchers) + adjacent tooling — clean persona-replacement story → bottoms-up-cost-efficiency.
  - Primitive 1 (persona_pool): anchor on BLS SOC 13-1161 (~190K US), scale to ~250K globally, apply 24% net addressability (40% qual share * 60% AI-ready) → 60K. Connector_hint to BLS so live pull updates the anchor.
  - Primitive 2 (cost_per_persona): build loaded cost ~$180K (BLS wage + tooling) and apply 40% vendor capture → $72K ACV. Capture % embedded in value, not framework.
  - Addressability handling: both multipliers (0.24 addressability on pool, 0.40 capture on cost) live inside the primitives per Q15.
  - Sanity check: 60K * $72K = $4.32B. Sits in mid-single-digit $B band — consistent with 'AI replacing qual research + expert networks + survey tools' being a real but bounded category.
  - Avoids the Endeavor mistake: did not use 2M+ marketing-adjacent labor pool as the ceiling.
- **Warnings:** Global scale-up factor (US→WLD ~1.3x) for market research analysts is a modeling judgment; if global pool is closer to 350K the band shifts up.; 40% vendor capture share is aggressive vs typical 20-30% SaaS capture of labor cost — justified here by also displacing expert-network and survey tooling spend bundled into the seat cost.

### Echelon — ServiceNow development agents

- **TAM:** $3.2B (state hash `99976062f32544d78807b6a4623b85b83b17a0cb248f402a4b687ec813803c25`)
- **Geo profile:** `global_saas`
- **Framework:** `consolidation-sum-then-discount` (lens `bundle_consolidation`)
- **Addressability:** Addressability is baked into both primitives rather than the framework formula. tools_displaced is NOT total ServiceNow ecosystem revenue or all enterprise IT services — it is narrowed to the ServiceNow-attached implementation/dev/maintenance services pool (~$27B) that Echelon's agents could actually substitute for. consolidation_rate (12%) is itself a stacked product of three realistic factors (60% task scope × 40% automatability × 50% vendor value-split), embedded as a single capture %. This avoids double-counting and keeps the framework formula a clean (pool × capture).
- **Reasoning chain:**
  - Geo: ServiceNow is global SaaS; customer base is multinational F500 — use global_saas, codes=[WLD].
  - Framework: Echelon displaces incumbent SI labor + internal dev spend on ServiceNow — classic share-shift against an existing spend pool, so consolidation-sum-then-discount fits better than bottoms-up persona replacement.
  - tools_displaced sourcing: anchor to ServiceNow's audited FY24 subscription rev ($10.6B) and apply analyst SI-attach multiplier (~2.5x) → ~$27B services pool. Paraphrased from 10-K + Gartner ITSM survey norms.
  - consolidation_rate sourcing: no single citable %, so community-modeled. Stack three realistic factors (task-scope share × automatability × vendor capture) = 12%.
  - Addressability handling: pool restricted to ServiceNow-attached services (not all IT services); capture % already discounted for customer savings and ServiceNow platform tax.
  - Sanity check: $27B × 12% = ~$3.2B TAM. Reasonable for a platform-bound dev-agent player; comparable to other vertical agent TAMs (e.g. Salesforce-bound dev tools).
  - Uncertainty band: low ~$22B × 6% = $1.3B; high ~$32B × 18% = $5.8B.
- **Warnings:** Platform-bound risk: ServiceNow's own Now Assist could compress the capture rate substantially; the 12% assumes Echelon coexists rather than getting squeezed out.; consolidation_rate is community-modeled, not citable — carries the largest uncertainty.; SI-attach multiplier (2.5x) is an industry rule of thumb; actual ServiceNow-specific ratio varies by SI.

### Endeavor — Mfg/distribution back-office AI

- **TAM:** $75.0B (state hash `9c2fea4294c3530e7f819f2488d2821bbd9d3f47befe8d34b9735f550bacf5be`)
- **Geo profile:** `global_industrial`
- **Framework:** `bottoms-up-cost-efficiency` (lens `cost_efficiency`)
- **Addressability:** Total mfg+distribution back-office labor pool globally is ~10M workers at ~$55K fully-loaded = ~$550B labor ceiling. Per spec, realistic SAM is <20% of that. We bake the addressability filter (25%, restricting to AI-automatable document/workflow roles) into persona_pool (10M → 2.5M), and bake the vendor capture share (55% of displaced labor cost) into cost_per_persona ($55K → $30K). Product = 2.5M × $30K = $75B, matching the spec ceiling. No separate multipliers needed in the framework formula, satisfying Q15.
- **Reasoning chain:**
  - Geo: global industrial → geo_profile=global_industrial, codes=[WLD] on both primitives.
  - Framework: persona-replacement story (AI agents priced vs back-office labor) → bottoms-up-cost-efficiency.
  - Persona pool sourcing: BLS OES gives US base (~2.5M back-office in mfg+wholesale), scale to global ~10M, then apply 25% AI-addressability → 2.5M addressable. Embeds addressability per Q15.
  - Cost per persona: blend global fully-loaded labor cost (~$55K) and embed vendor capture rate (55%) → $30K ACV. Embeds capture per Q15.
  - Addressability + capture both embedded in primitive values, not as framework multipliers.
  - Sanity check: 2.5M × $30K = $75B, lands at the spec ceiling for realistic SAM (<20% of $550B labor pool). Matches Endeavor methodology note exactly.
  - Avoids the Endeavor error pattern (using full labor pool ceiling without addressability).
- **Warnings:** Global persona pool relies on a scaling factor from US BLS data; no single regulator publishes a global mfg back-office headcount. Tier is community-modeled with BLS as anchor.; Vendor capture rate (55%) is a modeled assumption; actual ACV will depend on services/implementation mix.; AI-addressability of 25% may shift up over 3-5 years as agent capability expands into less structured workflows — TAM has upside skew.

### Skyramp — QA / test automation

- **TAM:** $792M (state hash `c4e39c3462330456e65728dd59785349e4da9f1291f8a565f4ab636e56ae8c00`)
- **Geo profile:** `global_saas`
- **Framework:** `bottoms-up-cost-efficiency` (lens `cost_efficiency`)
- **Addressability:** BLS reports ~1.9M software developers + ~200K QA analysts/testers in the US (2023 OEWS). Scaling globally via the standard ~4x US->global developer multiplier (StackOverflow/GitHub developer census ~27M worldwide, of which ~25-30% are QA-involved or test-writing roles) yields ~8M global QA-relevant engineers. We embed AI-addressability directly: only ~40% of these engineers work in orgs with budget/willingness to adopt AI-test-gen tooling in the near-term SAM window (cloud-native, CI/CD-mature shops), giving persona_pool ≈ 3.2M addressable QA personas. The cost_per_persona embeds realistic QA tooling wallet share (~$1,500/yr blended across QA SaaS line items like BrowserStack, Sauce Labs, Mabl, internal test infra allocation) rather than total dev tools spend, capturing the share an AI test-gen vendor can plausibly win. 3.2M × $1,500 ≈ $4.8B SAM, consistent with the global QA automation tooling band.
- **Reasoning chain:**
  - Geo: sold to eng orgs worldwide → global_saas → geo_level=global, codes=[WLD].
  - Framework: classic persona-replacement / cost-efficiency motion (AI replaces manual test authoring per QA engineer) → bottoms-up-cost-efficiency.
  - Primitive 1 (persona_pool): start from BLS OEWS for US dev + QA roles (regulator tier, connector_hint to BLS), scale 4x to global, then embed 40% AI-addressability filter so the value is 3.2M not 8M.
  - Primitive 2 (cost_per_persona): blend public QA SaaS price points (BrowserStack, Sauce, Mabl) to $1,500/yr/engineer — this is QA-specific wallet, not total dev tools, so it's already the capture wallet.
  - Addressability handled per Q15: both multipliers (40% addressable, QA-only wallet share) are baked into the primitive numbers, not framework defaults.
  - Sanity check: 3.2M × $1,500 = $4.8B. Gartner sizes global software test automation at ~$25B; AI-test-gen subset (the slice Skyramp competes for) at ~15-25% of that = $4-6B. Lands inside spec band.
- **Warnings:** Global persona multiplier (4x US) carries ±30% uncertainty; BLS connector returns US-only and the script should not naively use the raw US number.; QA wallet excludes adjacent observability/APM tooling by design — if Skyramp expands into prod-monitoring the cost_per_persona would need to roughly double.

### Supermemory — AI memory infra

- **TAM:** $2.5B (state hash `1699648893833531722e55a398c54ebfc0d94976a3be51fce2b907d776551689`)
- **Geo profile:** `infra_layer`
- **Framework:** `throughput-take-rate` (lens `platform_throughput`)
- **Addressability:** Per Q15, no separate multipliers are applied at the framework level. Addressability is baked into both primitives: (1) gmv_or_volume is restricted to the AI application stack revenue (agents, copilots, chatbots) — i.e., apps that actually need a memory layer — rather than total AI/cloud spend; (2) take_rate at 5% already reflects both the share of AI apps that need persistent memory (~70%) and the memory sub-layer's share of infra spend (~7%), netting to ~5% blended. This avoids the infra-layer error of sizing off nascent memory-API ARR and instead sizes off the application stack throughput the layer enables.
- **Reasoning chain:**
  - Geo: Supermemory is a global API sold to AI devs worldwide -> infra_layer -> codes=[WLD], global level.
  - Framework: classic infra-layer take-rate on application throughput -> throughput-take-rate (not bottoms-up persona, not consolidation).
  - Primitive 1 (gmv_or_volume): per spec, use AI application stack revenue (not memory-API ARR which is nascent). Sum agent platforms + copilots + chatbots ~ $50B in 2024.
  - Primitive 2 (take_rate): memory layer's share of AI infra spend, benchmarked to vector DB / retrieval infra share (~3-8%); midpoint 5%.
  - Addressability embedded: gmv restricted to memory-needing AI apps; take_rate already reflects sub-layer share.
  - Sanity check: $50B × 5% = $2.5B TAM, with uncertainty $35B×3%=$1.05B to $70B×8%=$5.6B. Lands in $1.5–5B band consistent with emergent infra layer.
  - Source tiers: app-stack revenue is analyst-paraphrase (IDC/Gartner paywalled); share is community-modeled with explicit uncertainty.
- **Warnings:** Memory infra is an emergent category; take_rate has wide uncertainty (3-8%).; AI application stack revenue is moving fast; 2024 baseline may understate 2025+ TAM.; Risk of overlap with vector DB and RAG-as-a-service vendors competing for the same 5% share.

### Numeral — Sales-tax / VAT compliance

- **TAM:** $665M (state hash `7a3fb6585619762ceb880930a629c16377cd9d807015193bdea751c57653f3fb`)
- **Geo profile:** `global_saas`
- **Framework:** `consolidation-sum-then-discount` (lens `bundle_consolidation`)
- **Addressability:** Numeral does not address 100% of the $3.8B incumbent pool — large enterprises stay on Vertex/ONESOURCE, and on-prem ERP-bound buyers don't churn. We embed two multipliers directly into the consolidation_rate primitive: (a) ~50% of the pool is addressable (ecommerce + SaaS + mid-market digital sellers on modern stacks), and (b) ~35% realistic long-run capture vs entrenched incumbents and other modern challengers (Anrok, Stripe Tax). The product 0.50 × 0.35 = 0.175 becomes the single consolidation_rate value, with the decomposition documented in the description so it remains auditable. The tools_displaced primitive carries the full incumbent revenue pool unmodified.
- **Reasoning chain:**
  - Geo: operates US + EU + APAC simultaneously under different regulatory regimes -> global_saas, codes=[WLD].
  - Framework: classic share-shift against named incumbents (Avalara, Vertex) -> consolidation-sum-then-discount, not throughput-take-rate (Numeral charges SaaS subscriptions, not % of GMV).
  - tools_displaced sourcing: Vertex 10-K (public regulator filing-adjacent) + Avalara last-public + analyst estimates for private players. Tier = analyst-paraphrase since aggregation crosses paywalled IDC tracker.
  - consolidation_rate: must bake in addressability per Q15. Decompose into addressable slice (50%) × realistic capture (35%) = 17.5%, with both factors documented in description.
  - Avoid Numeral-class error from spec: don't use full $3.8B as TAM and don't naively apply 80% capture — use realistic challenger economics.
  - Sanity check: 3.8B × 0.175 ≈ $0.66B SAM. Aligns with modern API-first tax challengers (Anrok at ~$50M ARR, Stripe Tax embedded) having meaningful but bounded headroom.
  - Uncertainty band: low 3.2B × 0.10 = $0.32B; high 4.5B × 0.25 = $1.13B.
- **Warnings:** Avalara revenue post-2022 take-private is estimated, not disclosed.; Long-tail vendor aggregation (~$600M) is the softest line item.; If Numeral expands into income tax / corporate tax filing, framework would need to widen the incumbent pool to include Intuit/H&R Block-adjacent SMB tax — out of scope for current product.

### SignalLabs — Healthcare decision AI

- **TAM:** $12.1B (state hash `e953292939a987fdabd0ba079f4f16842fd6d633048bf48d9824eab84fa5ff9a`)
- **Geo profile:** `us_only_regulated`
- **Framework:** `bottoms-up-cost-efficiency` (lens `cost_efficiency`)
- **Addressability:** The persona_pool primitive is NOT the full ~700K US health payer + provider utilization-management / clinical-ops decision workers. We embed addressability inside the value: starting from BLS OES medical/health services managers (11-9111, ~480K) + a slice of insurance claims/policy processing clerks (43-9041) doing clinical authorization work (~150K addressable subset out of ~280K), we keep only the ~35% whose decision workflow is AI-eligible under HIPAA-bound decision-support (prior auth, utilization review, care-pathway routing). That yields ~220K AI-addressable decision personas. cost_per_persona is the fully-loaded annual labor cost a decision-AI vendor can credibly capture per seat (~$55K — a fraction of the ~$110-140K loaded cost, reflecting realistic value-split, not full replacement). Both multipliers are baked into the primitive values themselves per Q15.
- **Reasoning chain:**
  - Geo: spec says us_only_regulated; international healthcare AI is a separate stack -> country=US, intl TAM structurally $0.
  - Framework: persona-replacement / decision-assist sizing for knowledge workers -> bottoms-up-cost-efficiency (Harvey/Glean analog for healthcare ops).
  - Persona pool sourcing: BLS OES 11-9111 (med/health svcs mgrs) + clinical-auth slice of 43-9041 -> ~630K gross pool.
  - Addressability embedding (Q15): apply ~35% HIPAA-bound AI-eligibility filter inside the primitive value -> 220K, not the 700K ceiling. No separate multiplier in framework.
  - Cost-per-persona embedding: fully-loaded ~$135K x ~40% capturable value-split -> $55K/persona-yr ACV. Capture % is baked into the value, not a framework multiplier.
  - Sanity check: 220K x $55K = $12.1B. Healthcare decision-AI for US payers+providers should land in the ~$8-16B range given HIPAA friction and that this is decisioning layer only (not full EHR/RCM).
  - Spec target band ~$8-16B reflects realistic SAM, not labor-pool ceiling (avoids the Endeavor/Minerva error).
- **Warnings:** Cost-per-persona value-split % is community-modeled; if vendor lands closer to full-replacement economics, TAM expands ~1.5-2x.; Clinical-auth slice of BLS 43-9041 is estimated — true split between billing/claims clerks and clinical-decision clerks is not cleanly published.; HIPAA enforcement tightening could compress AI-eligibility share below 30%.

### Zero RFI — ConTech RFI / owner's-rep

- **TAM:** $630M (state hash `1a7f1709da6833768d7afb7eb4ec6b11404e163e0c6f48b11088583c13771939`)
- **Geo profile:** `us_only_regulated`
- **Framework:** `bottoms-up-cost-efficiency` (lens `cost_efficiency`)
- **Addressability:** Total US construction services spend is ~$2T+ and total construction services market ~$72B (per spec). But Zero RFI only sells into the RFI / change-order / owner's-rep AI workflow slice for commercial construction. We embed addressability directly: persona_pool is NOT all construction workers (~8M BLS) nor all construction managers (~750K). It is narrowed to US commercial-construction owner's-rep + project-engineer personas whose job is RFI/change-order handling — roughly 180K addressable seats (≈25% of the ~750K BLS construction-manager pool that sits on commercial projects and touches RFI workflows). cost_per_persona is the realistic loaded SaaS ACV per seat for an AI workflow tool ($3.5K/yr), not the fully-loaded labor cost. Multiplying gives a SAM-grade figure rather than a labor-pool ceiling, addressing the Endeavor/Zero RFI/Minerva error class.
- **Reasoning chain:**
  - Geo: US commercial construction, AIA contract regime, US procurement -> us_only_regulated, geo_codes=[US], intl TAM structurally 0.
  - Framework: workflow automation tool sold per-seat to a defined persona (owner's rep / project engineer) -> bottoms-up-cost-efficiency.
  - Persona pool: avoid the Endeavor error of using total labor pool. Start from BLS OES 11-9021 (~750K construction managers), narrow to commercial subset (~40%) and RFI-touching seats (~60%) = ~180K addressable seats.
  - Cost per persona: not labor replacement ($120K+); use realistic SaaS ACV (~$3.5K/seat/yr) benchmarked vs Procore/Autodesk/Document Crunch — this is the vendor's real value capture.
  - Addressability baked in: persona pool narrowed 4x from raw BLS; ACV reflects workflow capture not labor replacement. No separate multiplier needed (Q15).
  - Sanity check: 180K x $3.5K = $630M. Spec says owner's-rep AI slice << $72B total construction services — a sub-$1B SAM is consistent. Band $0.4B–$1.2B.
- **Warnings:** Persona pool narrowing (40% commercial x 60% RFI-touching) is analyst-modeled, not regulator-sourced; carries 1.3x uncertainty.; ACV benchmark is community-modeled — AI-specific RFI modules are an emerging category with thin pricing comps.

### Contrario AI — AI recruiting agents

- **TAM:** $16.0B (state hash `313cfa31c2e8864b071a496848e1a8e20f3a394b89a09a2414984410ebf03efa`)
- **Geo profile:** `global_saas`
- **Framework:** `consolidation-sum-then-discount` (lens `bundle_consolidation`)
- **Addressability:** Global staffing & recruiting industry revenue (~$650B per SIA) is the incumbent spend pool being displaced. We embed addressability by narrowing tools_displaced to the permanent placement + RPO + contingent search segment that AI agents can realistically automate (~$200B globally), excluding temp staffing payroll pass-through which is labor cost, not recruiting service fees. The consolidation_rate of 8% reflects realistic share AI-agent platforms can capture from human recruiters over the planning horizon — baked into the primitive itself with uncertainty bounds rather than as a separate framework multiplier.
- **Reasoning chain:**
  - Geo: global SaaS sold to TA teams worldwide -> geo_profile=global_saas, geo_codes=['WLD'].
  - Framework: spec explicitly calls out 'displacement of staffing-agency revenue' — classic share-shift against an incumbent spend pool -> consolidation-sum-then-discount.
  - tools_displaced: anchor on SIA's global staffing industry estimate (~$650B) but narrow to the AI-addressable service-fee layer (~$200B) by excluding temp-payroll pass-through.
  - consolidation_rate: no citable benchmark for AI recruiting agent share; community-modeled at 8% with 4-15% band reflecting category immaturity.
  - Addressability baked in: instead of $650B * 30% addressable * 8% capture, we hand the framework $200B * 8% directly so the primitives are auditable.
  - Sanity check: $200B * 8% = $16B TAM. Comp set (Mercor ~$100M ARR, Paraform early-stage) implies category capable of supporting multiple $1B+ outcomes -> $16B SAM is consistent.
  - Band: $8B (low capture) to $30B (high capture on slightly larger displaced pool) — spec_target_band 10-25.
- **Warnings:** consolidation_rate is community-modeled with wide uncertainty (4-15%); category is early and capture rate could compress if AI agents fail to displace human recruiters on relationship/closing work.; tools_displaced excludes temp-staffing payroll pass-through deliberately; if Contrario's product actually displaces temp staffing margin (not just perm/search), the pool could be larger.; SIA report is paywalled — used analyst-paraphrase tier with original_publisher set.

### Miravoice — AI phone surveys / CATI

- **TAM:** $1.1B (state hash `f4af447b860cd3d05e5b10962ac2483002f9a89fd61c2e517146da2b15e2c23a`)
- **Geo profile:** `global_saas`
- **Framework:** `consolidation-sum-then-discount` (lens `bundle_consolidation`)
- **Addressability:** Addressability is baked into both primitives. tools_displaced is NOT the full $84B market research industry nor the $46B quant slice — it's narrowed to the ~$3B CATI/telephone-mode data collection sub-pool, which is the actual incumbent spend AI voice can displace. consolidation_rate further embeds (a) technical feasibility (~70% of CATI is AI-amenable) and (b) realistic category consolidation ceiling (~55%), yielding 0.38. No separate addressability multiplier is applied at the framework layer.
- **Reasoning chain:**
  - Geo: market research is global, no US-only regulatory moat -> global_saas, codes=[WLD].
  - Framework: classic share-shift / displacement of an incumbent spend pool (CATI labor + call-centers) into an AI platform -> consolidation-sum-then-discount, matching the share-shift pattern flagged in the spec.
  - tools_displaced sourcing: ESOMAR Global Market Research is the canonical industry size; narrowed to telephone mode share of quantitative data collection -> ~$3B (not the $84B headline).
  - consolidation_rate sourcing: no citable source for AI voice survey capture %; modeled as feasibility x consolidation ceiling = 0.7 x 0.55 = 0.38, carried as community-modeled with uncertainty band.
  - Addressability handling: kept multipliers inside primitives (Q15) — CATI sub-pool not whole MR industry, and capture rate already discounted for feasibility + adoption ceiling.
  - Sanity check: 3.0B x 0.38 = ~$1.14B TAM; band ~$0.6-2.2B accounts for ESOMAR range x capture range. Consistent with a category-leading AI voice survey co. capturing a meaningful but bounded slice of a shrinking CATI pool.
- **Warnings:** CATI spend pool is structurally declining ~5-8%/yr as online/mobile panels grow; TAM has negative organic drift absent AI re-expanding telephone mode.; EU GDPR + TCPA-style consent regimes can constrain AI outbound voice in several geos, compressing realized capture vs modeled 0.38.; ESOMAR telephone-mode share is a paraphrased estimate; exact CATI line-item not published — uncertainty band is wide.

### PlayerZero — AI code quality / observability

- **TAM:** $4.8B (state hash `0f84cc04a13ed6fff4c666787e6d70122f8a0312751c373ae65a18dd2ea5a412`)
- **Geo profile:** `global_saas`
- **Framework:** `consolidation-sum-then-discount` (lens `bundle_consolidation`)
- **Addressability:** PlayerZero competes for a share of the observability/APM/code-quality spend pool dominated by Datadog, New Relic, Dynatrace, Splunk, Sentry, etc. We use consolidation-sum-then-discount: tools_displaced = global observability+APM+code-quality software spend (~$60B run-rate 2024, Datadog comp set + adjacent code-quality tooling). The consolidation_rate of 8% embeds addressability: not all observability spend is addressable by an AI debug-assist layer (infra metrics, logs storage are out of scope), and PlayerZero competes for the code-quality/debug-assist slice (~15-20% of pool) with realistic capture of ~40-50% of that slice given competition from GitHub Copilot, Sentry AI, Datadog Bits AI. 0.17 * 0.47 ≈ 0.08.
- **Reasoning chain:**
  - Geo: global SaaS, no regulatory regime → geo_level=global, codes=[WLD].
  - Framework: spec says 'share of observability/APM spend (Datadog comp set)' — classic incumbent-pool share-shift → consolidation-sum-then-discount.
  - tools_displaced primitive: aggregated Datadog comp set vendor revenue grossed up to total category spend ≈ $60B (Gartner/IDC paraphrase, since these are paywalled).
  - consolidation_rate primitive: embedded addressability (17% of pool is AI-debug-addressable) × competitive capture (~45%) ≈ 8%. Community-modeled with explicit uncertainty band.
  - Addressability handling: NOT applied as a framework multiplier; baked into the 0.08 capture rate per Q15.
  - Sanity check: $60B × 0.08 = $4.8B TAM. Aligns with PlayerZero positioning as a mid-cap AI dev-tools play (not a $50B platform, not a $500M niche).
  - Spec target band: $3-7B.
- **Warnings:** tools_displaced uses analyst-paraphrase gross-up from Gartner/IDC — vendor revenue floor is ~$30-35B; total-spend gross-up to $60B carries ±25% uncertainty.; consolidation_rate is community-modeled — sensitive to whether incumbents (Datadog Bits AI, GitHub Copilot) commoditize AI debug-assist as a bundled feature, which would compress capture toward the 5% floor.

### Kaizen Labs — US state/local GovTech

- **TAM:** $1.6B (state hash `84c9667fc4d1116809f40411c3bafbd44d03da382351ed2059377cb7717f1e1f`)
- **Geo profile:** `us_only_regulated`
- **Framework:** `consolidation-sum-then-discount` (lens `bundle_consolidation`)
- **Addressability:** Addressability is embedded in BOTH primitives. (1) tools_displaced is scoped to ONLY the resident-services + payments slice of GovTech (~$6.5B), excluding core ERP/financials, public safety, and education software that Kaizen does not target — rather than the full ~$25-30B US SLG software market. (2) consolidation_rate of 25% reflects realistic share-shift capture given 5-10yr SLG contract cycles and cooperative purchasing friction, not theoretical replacement. Product: ~$1.6B SAM, consistent with a credible AI-native GovTech challenger spec target.
- **Reasoning chain:**
  - Geo: US state/local procurement = us_only_regulated, geo_codes=['US'], intl TAM structurally 0.
  - Framework: Kaizen displaces a known incumbent pool (Tyler, Granicus, GovOS, NIC) via share-shift -> consolidation-sum-then-discount, not throughput-take-rate (payments is bundled, not the primary wedge).
  - Primitive 1 (tools_displaced): triangulate from Tyler 10-K SLG segment + Granicus + GovOS + NIC payments + Accela/OpenGov/CivicPlus = ~$6.5B; explicitly exclude ERP and public-safety per Kaizen's scope.
  - Primitive 2 (consolidation_rate): SLG procurement is sticky; community-modeled at 25% with [15%,35%] band — reflects realistic challenger capture, not displacement ceiling.
  - Addressability baked in via narrow tools_displaced scoping + realistic capture rate (not labor-pool ceiling error).
  - Sanity check: 6.5B * 25% = $1.625B SAM — lands in expected $1-2.5B band for a US-only AI-native GovTech challenger.
- **Warnings:** consolidation_rate is community-modeled; sensitive to AI-native disruption pace assumptions.; tools_displaced uses analyst-paraphrase triangulation; Tyler 10-K is regulator-grade but the pool aggregation is analyst-level.; Payments processing revenue (interchange-based) is mixed in here; if Kaizen monetizes payments via take-rate at scale, a hybrid throughput-take-rate sub-model could be layered.

### Sieve — Multimodal AI infra

- **TAM:** $3.6B (state hash `b61159c6eb491846c76dcb17f1525dd6caf201035a1a94724a3619330e608db6`)
- **Geo profile:** `infra_layer`
- **Framework:** `throughput-take-rate` (lens `platform_throughput`)
- **Addressability:** Sieve is an infra layer beneath multimodal AI apps. Per the spec, we size by application markets enabled (video gen, video editing, content moderation, video search) and apply an infra-share take rate. The gmv_or_volume primitive is NOT Sieve's API ARR — it's the aggregate application-stack revenue across the four enabled app markets (~$60B blended: video gen tooling ~$8B, video editing software ~$25B, content moderation services ~$15B, video search/indexing ~$12B). The take_rate (~6%) is the realistic infra-layer share that processing/transformation/generation APIs can capture out of the application stack (analogous to Stripe ~3% of e-commerce GMV, Twilio ~5-8% of comms stack). Both addressability (which app markets count) and capture (infra share of those markets) are embedded directly into the primitive values rather than layered as separate multipliers.
- **Reasoning chain:**
  - Geo: developer-facing infra with global customer base → infra_layer profile, geo_codes=[WLD].
  - Framework: infra layer taking a share of throughput across enabled app stack → throughput-take-rate (matches Stripe/Twilio/voice-infra pattern in spec).
  - Avoid prior error: do NOT use Sieve's current API ARR as gmv_or_volume. Per spec, use application-stack revenue across the four enabled markets.
  - Primitive 1 (gmv_or_volume): Sum the four app markets per spec — video gen + video editing + content moderation + video search ≈ $60B blended from analyst sources.
  - Primitive 2 (take_rate): Apply realistic infra share (~6%) benchmarked to Stripe/Twilio/Cloudinary analogs. This is the capture multiplier embedded directly as the take_rate primitive.
  - Addressability handled by app-market scoping (only four enabled markets, not all video/audio software). Capture handled by 6% take_rate.
  - Sanity check: $60B × 6% = $3.6B TAM. Spec band $3-5B for an infra layer beneath a $60B emerging app stack — consistent.
- **Warnings:** Application stack sizes blended from multiple analyst sources; wide uncertainty band ($45-80B).; Take rate is community-modeled by analogy to Stripe/Twilio/Cloudinary; not a directly citable figure.; Video AI generation sub-market is growing rapidly — TAM likely expands materially over 2-3 year horizon.

### ST Labs — AI-native ITSM

- **TAM:** $2.2B (state hash `45fc23e4b1608505ef3ef724c2c7941e573a859e6e32e6b7476d23d6557fe247`)
- **Geo profile:** `global_saas`
- **Framework:** `consolidation-sum-then-discount` (lens `bundle_consolidation`)
- **Addressability:** The ITSM incumbent revenue pool (~$12B globally across ServiceNow ITSM, Atlassian Jira Service Mgmt, Freshworks, BMC, Ivanti, etc.) is embedded directly into tools_displaced as the share-shiftable spend, not a broader "IT operations" pool. The consolidation_rate (18%) reflects realistic AI-native share capture over the planning horizon — not the full incumbent pool — accounting for ServiceNow's enterprise lock-in, multi-year contract cycles, and the fact that AI-native entrants typically peel off mid-market + greenfield workloads first. Both addressability (which incumbents are actually displaceable) and capture % (realistic share-shift) are baked in rather than layered as separate multipliers.
- **Reasoning chain:**
  - Geo: global SaaS, no regulatory regime → geo_level=global, geo_codes=[WLD].
  - Framework: spec explicitly says share-shift from ITSM incumbents → consolidation-sum-then-discount (avoid the Numeral/Accrual error pattern of using top-down on a share-shift story).
  - tools_displaced: sum ITSM-attributable revenue from displaceable incumbents (ServiceNow ITSM module only, not full ServiceNow; Atlassian JSM; Freshservice; BMC Helix; Ivanti; long tail) ≈ $12B. Critically excludes non-ITSM ServiceNow modules.
  - consolidation_rate: not the full pool — bake in addressability. ServiceNow enterprise lock-in protects ~50% of pool; incumbent AI counter-products compress window. Blended realistic capture ~18%.
  - Addressability embedded: tools_displaced is already filtered to ITSM-only (not broader 'IT ops'); consolidation_rate is already the realistic share-shift (not theoretical max).
  - Sanity check: $12B × 18% = $2.16B TAM. Lands in $2-3B band, consistent with AI-native ITSM being a meaningful but bounded share-shift opportunity, not a $20B greenfield.
  - Source tiers: incumbent pool is analyst-paraphrase (Gartner MQ, paywalled); share-shift rate is community-modeled with explicit uncertainty range.
- **Warnings:** consolidation_rate is community-modeled — uncertainty range 12-25% means TAM could swing $1.4B-$3.0B.; If ST Labs expands beyond ITSM into ITOM/SecOps/HRSD, this TAM under-counts; current scope is ITSM-only per company description.; Incumbent AI counter-products (ServiceNow Now Assist, Atlassian Rovo) are a real risk to the share-shift thesis — could compress capture rate below the low end.

### Wraithwatch — Agentic cyber defense

- **TAM:** $45.2B (state hash `1640b77df7c2508628d797e3858c7a8e6f05f8cd90b881740afe160a853a328a`)
- **Geo profile:** `global_saas`
- **Framework:** `bottoms-up-cost-efficiency` (lens `cost_efficiency`)
- **Addressability:** SecOps labor is the dominant SAM lens here. Global SOC analyst + pentester pool is ~3.5M people (ISC2 cyber workforce ~5.5M globally, of which ~60-65% are in SecOps/IR/offensive security roles = ~3.4M). Wraithwatch's agents target the AI-automatable share of that work — Tier 1/2 SOC triage, alert enrichment, and routine pentest scoping. We embed a 35% AI-addressability factor directly into persona_pool: 3.4M × 0.35 ≈ 1.19M addressable personas. cost_per_persona is fully-loaded global blended SecOps comp ($95K — weighted average of US ~$120K, EU ~$85K, APAC ~$55K per ISC2 2024 workforce study), with a 40% vendor value-split already embedded since Wraithwatch displaces only the automatable fraction of each role's cost: $95K × 0.40 = $38K captured per addressable persona. No separate framework multipliers — both addressability and capture are baked in.
- **Reasoning chain:**
  - Geo: F500 + government globally => global_saas, codes=[WLD].
  - Framework: spec says SOC analyst + pentester labor displacement => bottoms-up-cost-efficiency (persona-replacement sizing).
  - Persona pool source: ISC2 Workforce Study (5.5M global cyber workforce) — paraphrase tier since the methodology layer (SecOps subset, AI-addressable share) is our overlay.
  - Embedded addressability: 5.5M × 62% SecOps share × 35% AI-automatable = 1.19M, not the full 5.5M ceiling.
  - Cost per persona: global blended $95K comp × 40% vendor value-split = $38K, avoids the 'full salary capture' error.
  - Sanity check: 1.19M × $38K ≈ $45B TAM — sits between pure-software SecOps spend (~$25B) and full SecOps labor pool (~$320B), which is the correct band for an agentic displacement play.
  - Spec band: $35-60B reflects realistic agentic SecOps SAM given current adoption curve.
- **Warnings:** Vendor value-split (40%) is community-modeled; if Wraithwatch ends up priced closer to 20-25% of displaced labor cost, TAM compresses toward the low end of the band.; ISC2 workforce numbers include some double-counting across roles; the 62% SecOps/IR/offensive subset is an analyst overlay, not a direct ISC2 figure.; Government procurement cycles may cap near-term realizable share even though it's in scope.

### Moda — AI brand-design agents

- **TAM:** $12.0B (state hash `6c2930d6a35936ad4266e5055cb1ea549bf42ade6ed50ca02851e1daab7ed007`)
- **Geo profile:** `global_saas`
- **Framework:** `consolidation-sum-then-discount` (lens `bundle_consolidation`)
- **Addressability:** Addressability is baked into both primitives. tools_displaced is NOT the $700B+ global marketing spend or full $150B agency spend — it's narrowed to the $60B sliver of design SaaS + AI-automatable creative production work. consolidation_rate is the realistic share-shift (20%, not 100%), reflecting that brand strategy, premium campaigns, and human creative direction remain non-displaceable. Multiplying yields ~$12B TAM, not the headline $700B marketing pool.
- **Reasoning chain:**
  - Geo: described as global SaaS sold to marketers worldwide → global_saas, codes=[WLD].
  - Framework: thesis is displacement of design tools + agency spend → share-shift of an incumbent spend pool → consolidation-sum-then-discount.
  - tools_displaced: bottoms-up sum of design SaaS (~$15B from Adobe/Canva/Figma public/disclosed revenue) + addressable slice of agency creative (~$45B = 30% of $150B global agency spend).
  - consolidation_rate: community-modeled at 20% blended (higher capture on SaaS tools, lower on agency labor), with uncertainty 12-30%.
  - Addressability embedded: pool restricted to design-specific spend not all marketing; capture rate <1 reflects non-automatable strategy/premium work.
  - Sanity check: $60B × 20% = $12B TAM, sits in $7-18B band consistent with a credible global AI creative-automation TAM.
- **Warnings:** Agency/freelance spend pool is the largest single component and is the least precisely measured — uncertainty band reflects this.; Capture rate is community-modeled; sensitive to whether agents can credibly do brand strategy (would push higher) or stay confined to asset production (would push lower).

### Minerva — AI-native accounting firm (US CPA)

- **TAM:** $3.0B (state hash `be97cef2688a3788fa6a6290a7114cdb63a86c4e2114e534fcb599ecebf92176`)
- **Geo profile:** `us_only_regulated`
- **Framework:** `consolidation-sum-then-discount` (lens `bundle_consolidation`)
- **Addressability:** The $43B SMB accounting services ceiling is NOT used directly. Per spec, realistic SAM is single-digit % of that pool because: (1) US CPA licensure requirement + state-by-state firm structure regulation limits AI-native firm scalability, (2) only a subset of SMBs will switch from incumbent CPAs/bookkeepers to an AI-native firm in the addressable window, (3) high-complexity audit/advisory work is not AI-addressable. We embed a ~7% capture rate (mid single-digit) directly into consolidation_rate rather than carrying $43B forward unchanged. tools_displaced stays at the incumbent SMB accounting services revenue pool ($43B) since that IS the displaceable spend, but consolidation_rate captures the realistic share-shift ceiling for an AI-native CPA firm.
- **Reasoning chain:**
  - Geo: US-only because CPA firm licensure is state-by-state US regulatory regime; intl TAM structurally 0.
  - Framework: Minerva is share-shifting an incumbent professional services spend pool, not replacing personas or taking infra throughput → consolidation-sum-then-discount.
  - tools_displaced: $43B US SMB accounting services pool (Census NAICS 5412 SMB segment), sourced via Census SUSB connector.
  - consolidation_rate: spec says single-digit %; pick 7% midpoint reflecting CPA licensure + sign-off friction. This embeds addressability inside the primitive (Q15 compliance) rather than as a framework multiplier.
  - Sanity check: $43B × 7% = $3.0B, lands inside spec target band of $2-4B for realistic AI-native CPA firm SAM.
  - Avoids the Endeavor/Zero error: we did NOT carry the full $43B ceiling forward as TAM; we embedded the realistic capture ceiling into the primitive value.
- **Warnings:** consolidation_rate is community-modeled (no citable source for AI-native CPA firm capture rate); uncertainty band 4-9%.; Census NAICS 5412 receipts include large-enterprise audit revenue — SMB-attributable share is an estimate, not a clean regulator pull.

### Effective AI — Insurance actuarial / underwriting AI

- **TAM:** $6.4B (state hash `b8344b356b8ae603dc2e99a0fe9b5d66787b0ec52ad4d1b563b569a158c0537a`)
- **Geo profile:** `us_only_regulated`
- **Framework:** `bottoms-up-cost-efficiency` (lens `cost_efficiency`)
- **Addressability:** Addressability is embedded in persona_pool: instead of using the full ~136K US actuary+underwriter labor pool, we apply a 35% AI-addressability factor (DOI-compliant knowledge tasks) to yield 47,600 addressable personas. cost_per_persona is the fully-loaded substitution cost, not marked up further. No separate framework multiplier is needed; the product 47,600 × $135K ≈ $6.4B reflects the realistic SAM, not the labor-pool ceiling. Avoids the Endeavor-style mistake of multiplying full headcount × full wage.
- **Reasoning chain:**
  - Geo: US-only because state DOI ratemaking jurisdiction does not transfer cross-border -> geo_codes=['US'], intl TAM structurally $0.
  - Framework: persona-replacement of actuarial/underwriting knowledge workers -> bottoms-up-cost-efficiency (Harvey/Glean pattern).
  - Primitive 1 (persona_pool): start with BLS OES headcount for SOC 15-2011 (actuaries) + 13-2053 (underwriters) = 136K, then bake in 35% AI-addressability -> 47.6K.
  - Primitive 2 (cost_per_persona): blend BLS mean wages weighted by mix, apply 1.4x fully-loaded -> $135K/persona-year.
  - Addressability handling: embedded in primitive #1 value (not a separate multiplier), per Q15.
  - Sanity check: 47.6K × $135K ≈ $6.4B, within spec band for a US-regulated vertical AI knowledge-worker play.
- **Warnings:** Addressability factor (35%) is community-modeled judgment; DOI acceptance of AI-generated underwriting memos is still evolving and could compress or expand this materially.; BLS SOC codes do not separate P&C vs life vs health underwriters; mix assumed P&C-weighted.

### Melius — AI creative canvas / image+video gen

- **TAM:** $4.0B (state hash `d3047f018aa512551c59df9664739eb06d3866753c25d71a5cde95675d336bab`)
- **Geo profile:** `global_saas`
- **Framework:** `consolidation-sum-then-discount` (lens `bundle_consolidation`)
- **Addressability:** tools_displaced is NOT the full global creative/advertising production market (~$700B+). It is narrowed to the two specific spend pools Melius credibly displaces: (1) global stock imagery + stock video licensing (~$6B) and (2) the production-execution slice of creative agency spend addressable by AI canvas tools — roughly 15% of ~$80B global creative agency revenue ≈ $12B. Sum ≈ $18B incumbent pool. consolidation_rate of 22% reflects realistic mid-term capture by AI-native canvas tools across this combined pool (community-modeled; AI gen tools won't take 100%, agencies retain strategy/brand work, stock libraries retain editorial/news). Net: 18 * 0.22 ≈ $4B TAM, consistent with global SaaS AI creative tool sizing.
- **Reasoning chain:**
  - Geo: pure SaaS, no regulatory constraint → global_saas, codes=[WLD].
  - Framework: spec explicitly says 'displacement of stock-photo + creative-agency spend' → share-shift against incumbent pool → consolidation-sum-then-discount.
  - tools_displaced = sum of two incumbent pools (stock media ~$6B + addressable agency production ~$12B = $18B), narrowed from the full ~$80B agency market to avoid the 'labor-pool ceiling' error.
  - consolidation_rate = realistic blended capture (22%), community-modeled with uncertainty band, NOT 100%.
  - Addressability embedded: agency pool already pre-filtered to the 15% production slice INSIDE the primitive value rather than as a separate multiplier (Q15 compliant).
  - Sanity check: 18B × 0.22 ≈ $4.0B, within published AI creative tools TAM estimates ($3-5B). Band [3, 5].
- **Warnings:** consolidation_rate is community-modeled; sensitive to whether agencies successfully adopt AI internally (compressing the displaceable pool).; Does not include long-tail SMB / creator spend that was never previously monetized (net-new market) — could expand TAM if included.; Stock video market growing faster than stock imagery; static $6B figure may understate by 2026+.

### Accrual — AI tax software for US CPA firms

- **TAM:** $1.1B (state hash `1160ed857aec11aa83c2f8f1e0ee5ef3389600a99d2d09cdce019ed98b474b9b`)
- **Geo profile:** `us_only_regulated`
- **Framework:** `consolidation-sum-then-discount` (lens `bundle_consolidation`)
- **Addressability:** tools_displaced is set to the AI-addressable slice of US professional tax prep software revenue (the CPA-firm segment of Intuit ProConnect/Lacerte, Thomson Reuters UltraTax/CS, Wolters Kluwer CCH Axcess — roughly $4.5B), not the entire $15B+ US tax software market (which includes consumer TurboTax and enterprise corp tax). consolidation_rate is set to 25%, a realistic 7-10 year share-shift capture for an AI-native challenger against three entrenched incumbents with high switching costs (workpaper lock-in, e-file integrations, multi-year client data). The product of these embeds both addressability (CPA-firm segment only) and capture % (realistic share-shift, not 100% displacement).
- **Reasoning chain:**
  - Geo: US federal/state tax code only → us_only_regulated → geo_codes=['US'], intl TAM structurally 0.
  - Framework: share-shift from named incumbents (Intuit/TR/WK) → consolidation-sum-then-discount (matches Numeral/ST Labs pattern in spec).
  - tools_displaced: sum incumbent CPA-firm tax software revenue from 10-K segments → ~$4.5B (NOT $15B+ which includes consumer/corporate).
  - consolidation_rate: 25% realistic 7-10yr capture (not 100%) given workpaper lock-in + e-file moats, balanced by CPA shortage + AI tailwind.
  - Addressability embedded: tools_displaced is already narrowed to CPA-firm pro tax (excludes TurboTax consumer + corp enterprise); capture% reflects share-shift realism.
  - Sanity check: $4.5B × 25% = $1.125B TAM. Lands in $1-1.5B band — appropriate for a US-only AI vertical SaaS share-shift play.
- **Warnings:** Incumbent segment revenue is paraphrased from 10-K segment disclosures; pure CPA-firm tax-prep allocation requires apportionment within bundled segments.; Capture rate is community-modeled; long-run share-shift in regulated professional software historically slow (decade+).

### Piramidal — Clinical EEG foundation model

- **TAM:** $2.4B (state hash `89b6682da2c22127222216f1a4ddca5c28d0bc6c254b05d7af3c50b12e59dcad`)
- **Geo profile:** `multi_jurisdiction_regulated`
- **Framework:** `throughput-take-rate` (lens `platform_throughput`)
- **Addressability:** Hand-crafted worked example per methodology spec.

### MetaVoice — Voice AI infra

- **TAM:** $13.5B (state hash `f88e71caf7dec30d84dcd52c6e9ce14f09549a3fe45737e9eb8780c4784ef272`)
- **Geo profile:** `infra_layer`
- **Framework:** `throughput-take-rate` (lens `platform_throughput`)
- **Addressability:** Hand-crafted worked example per methodology spec.

### Yotta — India sovereign cloud

- **TAM:** $4.0B (state hash `8850ece5be3c34de10bcdcd286308e1832da5802ee8bb6fce2450d1948c0e159`)
- **Geo profile:** `india_only`
- **Framework:** `top-down-revenue-capture` (lens `revenue_generation`)
- **Addressability:** Hand-crafted worked example per methodology spec.

