# Strata — Data-Layer Brainstorm (Live Checkpoint)

> This document is the live transcript of the data-layer brainstorm for Strata.
> It captures every decision, the alternatives considered, the trade-offs, and
> the rationale — so the user can stop at any question and resume with full context.
> Final implementation plan lives at the bottom.

## Status
**Phase:** Data-layer brainstorm **COMPLETE.** 38 questions resolved (Q1–Q38).
**Mode:** Plan mode. Only this file is being edited.
**Parked for a follow-up session:** Expert layer mechanics (credentialing, COI, decay, annotator gates) — better resolved closer to v0.5 with real contributor data informing parameters.

---

## TL;DR — decisions table (scannable)

| # | Question | Decision |
|---|---|---|
| 1 | What shape is a TAM? | **Scenario tree** of definitional choices, not a number with error bars |
| 2 | Primitive atomicity? | **Two-tier:** atomic (one source, one number) + composite (definitional bundles) |
| 3 | Composite vs Framework boundary? | **Hard line at units:** composites = set ops, same-unit-in/out; frameworks = all unit-crossing arithmetic |
| 4 | Unit modeling + currency? | **Structured unit type** (kind/dimension/denominator/currency/basis); store nominal, normalize at query time |
| 5 | Source mutation? | **Content-hash pinned citations** + **mandatory source snapshots** + **sensitivity-aware** change notifications + source-class refresh cadence |
| 6 | Temporal extrapolation? | **A+B hybrid:** user controls window; extrapolation is a framework; growth indices + regime modifiers are first-class primitives with roles |
| 7 | Defending against fake triangulation? | **Method-family tag** mandatory + **source-lineage edges** opt-in→mandatory + **independence score** surfaced (honest broker, not refused) |
| 8 | Geography model? | **Two parallel fields** (`geo_supply`, `geo_demand`) + ISO 3166 + named aggregates with member-list history + **sub-national first-class** |
| 9 | Cross-source disagreement? | **Concept layer** as first-class (5-layer model: concept → atomic → composite → framework → output) |
| 10a | Concept promotion flow? | **Hybrid:** hand-curated seed concept library + LLM-assisted clustering for the long tail; humans gate publication |
| 10b | Concept identity test? | **Narrow initially** — same population scope + definition. Broader bundling deferred until usage shows it's needed |
| 11 | What is a node? | **Three node types:** taxonomy stub (navigation, no data), concept-bearing leaf (data attached), saved-query node (dynamic, user-pinnable, shareable) |
| 12 | Axis count? | **3 axes (keep current)** — geo + time become global filter overlays / chips, not pillars |
| 13 | Cross-cutting markets? | **Auto-promote to named "intersection Concepts"** when usage frequency crosses a threshold; gets its own URL, citations, frameworks |
| 14 | Who curates the taxonomy? | **LLM-suggested + human-approved** (same flow as Concept promotion in Q10) |
| 15 | Framework default values? | **Frameworks have NO scalar defaults** — every input must point to a citable primitive |
| 16 | Framework misuse prevention? | **Whitelist + blacklist** (`applicable_to` + `not_applicable_to`); validator warns when neither covers a node |
| 17 | Framework forking? | **Single framework with declared regional/sector variants** — variants attach default *primitive pointers* (not values), preserving Q15 |
| 18 | Framework re-suggestion logic? | **Explicit `compatible_with` primary + unit-signature inference fills gaps** |
| 19 | Two-sided / marketplace markets? | **Single Concept with scenarios per side** (rides / drivers / GMV / take-rate) — consistent with Q1 scenario-tree |
| 20 | Synthetic / emerging markets? | **Two paths combined:** (default) analog-penetration with modeled Composites traced to analogs; (escape hatch) synthetic atomics allowed with hard guards — tier=community-modeled, mandatory range, 12-month expiry, prominent banner downstream. **LLM-projected primitives explicitly rejected.** |
| 21 | Multi-product companies? | **Company concepts exist + mandatory segment decomposition** pointing to category concepts where primitives live. Constraint prevents 'company TAM = flagship product TAM' shortcuts. |
| 22 | Wedge vs platform TAM? | **Frameworks take an `expansion_stage` parameter** (`wedge \| adjacent \| platform`); single framework emits scenarios for each |
| 23 | Contribution channel? | **Tiered:** PR-based for primitives/frameworks/concepts/taxonomy (schema-validated in CI); web form for annotations |
| 24 | Moderation pipeline? | **Claude Code-style LLM PR review** (schema, units, citations, snapshot, sanity-envelope) + **human spot-checks** + post-publication community flagging |
| 25 | LLM-assisted ingestion? | **LLM auto-publishes** for tier=first_party/regulator **only if all strict validators pass** (schema, unit type, snapshot-hash match, URL liveness, sanity envelope ±N%, as_of-in-past, sig-fig sanity); human spot-checks are the safety net |
| 26 | Licensing policy? | **Tier-determines-treatment:** full reproduction + snapshots for public-domain/open (BLS, Census, regulators); cite-only metadata-stub for paywalled (Gartner, IBISWorld, Statista) — link + access date, no value reproduction |
| 27 | Storage model? | **YAML-on-disk in git** = source of truth + provenance; **Postgres mirror** rebuilt on merge for query/search (from v0.3) |
| 28 | Search layer? | **Hybrid:** full-text + tag-faceted + semantic embeddings — three layers compose |
| 29 | Validator pipeline? | **Layered fast-fail:** structural → semantic → cross-record → LLM review → human spot-check |
| 30 | Schema versioning? | **Versioned schema + migration scripts in CI** — records declare schema version, migrations run atomically on bumps |
| 31 | Power-law markets? | Primitives carry **`distribution_shape`** (`uniform \| normal \| power_law \| bimodal \| other`); frameworks reason about it and refuse silent-mean operations on power-law primitives |
| 32 | Embedded delivery? | Primitives carry **`delivery_mode`** (`direct \| embedded \| bundled \| platform_passthrough`); frameworks filter on it explicitly |
| 33 | Subsidy-distorted markets? | Subsidies as **`regime_modifier` primitives** (Q6 mechanism); TAM shows base + subsidy as separate scenarios |
| 34 | Dual-economy markets? | **Unit type extended** to non-fiat (ETH, BTC, in-game tokens, ad impressions); cross-economy frameworks must cite a conversion primitive |
| 35 | OSS-as-product markets? | **Company concept with explicit OSS-user vs paid-services segments** (reuses Q21 machinery); free adoption is a separate category concept from realized revenue |
| 36 | Access-regulated markets? | **`requires_clearance: [list]`** on concepts + frameworks reuse Q16's `applicable_to` to enforce regulatory gates; TAM = addressable-given-clearance, not gross-pool |
| 37 | Dark / private estimates? | **Allowed** with mandatory uncertainty range + lineage + tier=community/analyst. **Source-tier system extended** with two new tiers: `onchain` (first-party-equivalent for crypto/DeFi) and `prediction_market` (community-modeled, must cite specific market + liquidity). Hyperliquid-class onchain data and Kalshi/Polymarket-class prediction markets become first-class primitive sources for dark/forward-looking TAMs. |
| 38 | TAM artifact / persistence? | **Permanent URL per TAM** with content-hash pinned inputs + PDF/markdown export embedding the URL. Citable in memos; reproducible forever; verifiable by anyone with the link. |

---

## Context

Strata is an open-source, community-curated market-sizing engine. Today (v0.1.0)
it's docs-only: thesis, glossary, data-model sketch, network-graph UX spec, roadmap.

The product thesis: market-sizing reports (IBISWorld, Statista, Gartner) sell
**defensibility**, not freshness. By exposing the **primitives** (atomic sourced
numbers) and the **frameworks** (parameterized recipes that combine them into
TAM), plus an **expert layer** for community correction, Strata can beat
incumbents on both cost and trust.

The interaction surface is a clickable pyramid graph with three axes
(Qualitative / Quantitative / Industry); clicking nodes narrows scope and
re-suggests frameworks.

**This brainstorm** is specifically about the data layer: what we ingest, how we
represent it, how we keep it honest, how the layers compose. The goal is to
make every load-bearing schema decision *before* committing to v0.2 (the seed
library). Schema rot at v0.2 is fixable; schema rot at v1.0 is fatal.

---

## Resolved decisions (with rationale)

### Q1 — What shape is "a TAM"?

**Decision:** A TAM is a **scenario tree**, not a number with error bars.
Each leaf is a fully-specified definitional choice with its own value, sources,
and assumptions.

**Why:** In real VC work, the "answer" often *is* the range — and not because of
measurement error, but because of definitional choice. "Sales tech TAM in NA"
spans ~10x depending on whether you include CRM only vs CRM + sales engagement
+ RevOps + conversational intelligence + revenue intelligence. None of those
are wrong; they answer subtly different questions. A scalar `value` with
`uncertainty` would silently bury the definitional choice that's doing most of
the work.

**Implication for schema:** Output-level `value` is
`{scenarios: [{definition, value, sources, assumptions}]}`, never a scalar.

**Alternatives rejected:** (a) scalar + error bars — buries the choice;
(b) flat range `[low, high]` — implies one underlying distribution when really
there are several distinct definitional models.

---

### Q2 — Are primitives atomic or do they suffer the same definitional disease?

**Decision:** Two-tier primitives. **Atomic primitives** = one source, one code,
one number, narrowly defined, reproducible by anyone. **Composite primitives** =
explicit definitional bundles assembled from atomics. Frameworks consume both.

**Why:** "GTM headcount in NA" suffers from at least 8 defensible BLS-bundle
definitions. Forcing the choice into the atomic primitive turns it into "a
primitive that's actually 8 primitives in a trenchcoat." Forcing it into the
framework layer fights it too late (after units have been crossed). The right
place to fight definitional bundling is its own layer.

**Implication for schema:** Two record types, distinguished by a `kind` field
(or by separate directories). Composites reference atomics by slug.

**Alternatives rejected:** (a) primitives stay scalar, framework picks bundle —
proliferates near-identical primitives; (b) primitives become scenario trees
themselves — heavyweight and pushes definitional choice into every primitive
including ones that genuinely are atomic.

---

### Q3 — Where exactly is the boundary between Composites and Frameworks?

**Decision:** A **hard line at units**.
- **Composites** do set operations only (union, intersection, filter, re-cut)
  and are **same-unit-in/same-unit-out**.
- **Frameworks** do all arithmetic that **crosses units** (multiply, divide,
  ratio, penetration, allocation).

**Why:** Without a hard line, composites can do arithmetic, which makes them
indistinguishable from frameworks, and the data layer rots within a year — two
ways to express the same calculation. The unit-crossing line is the cleanest
test: it's mechanical, automatable, and matches how analysts actually think
about the steps.

**Implication for engineering:** Composites are cheap to auto-generate (LLM-safe,
because the validator can confirm same-unit-in/out). Frameworks require human
review.

**Alternatives rejected:** Letting composites do simple arithmetic (e.g.,
weighted averages across geos) — sounds harmless, but every codebase that
allowed this kind of "small math creep" ended up with two parallel calculation
systems.

---

### Q4 — How do we model units, and how do we handle currency?

**Decision:** Units are a **structured type**:
```yaml
unit:
  kind: stock | flow | intensive | dimensionless
  dimension: people | currency | transactions | events | percent | ...
  denominator: ~ | per-year | per-month | per-seat | per-policy
  currency: USD | EUR | ...                                # if dimension=currency
  basis: nominal | real-2026USD                            # if dimension=currency
```

Frameworks declare unit signatures (`stock[people] × intensive[USD/people/year]
→ flow[USD/year]`) and the validator **statically rejects** invalid wiring.

Currency primitives are stored **nominal, pinned to `as_of`**. CPI/FX
normalization happens at query time and the UI surfaces normalization assumptions
+ resulting error explicitly.

**Why:** The single largest silent-error class in VC memos is mixing stocks
with flows, or comparing nominal-2018-USD to nominal-2025-USD without
adjustment. A structured unit type makes both impossible to commit by accident.
Storing nominal preserves reproducibility (normalization assumptions are explicit
and re-runnable); storing pre-normalized loses defensibility (which CPI series
did we use? buried).

**Implication for engineering:** A small dimensional-analysis library, and a
query-time normalization service (CPI tables, FX tables — both themselves
primitives in the library).

---

### Q5 — Sources mutate. What do we do?

**Decision (compound):**
1. **Citations are content-hash pinned.** Every framework/TAM stores the sha256
   of the primitive snapshot it cited. Primitives can update in-place but no
   downstream calc silently changes.
2. **Source snapshots are mandatory at ingest.** The actual PDF/CSV/HTML lives
   as a content-addressed blob alongside the YAML. URL alone is never enough.
3. **Sensitivity-aware change notifications.** When upstream revises, the
   system computes downstream impact on every TAM that cites the primitive.
   Only TAMs that move >Δ% (default ~5%) get flagged. Sub-Δ revisions logged
   silently. Black-swan revisions (>~25%) get a louder alert.
4. **Refresh cadence is source-class-aware.** Regulators polled frequently;
   S-1s checked at filing event; analyst reports never re-fetched; community
   sources never auto-refreshed.

**Why:** "Defensible chain of custody" survives 5 years of URL rot, PDF
replacements, S-1 restatements, and methodology changes only if the snapshot
is ours, the citation is hash-pinned, and the user is alerted to changes that
*matter* (not every change). Crying wolf on every BLS preliminary→revised
revision destroys trust faster than ignoring revisions does.

**User's contribution:** "One primitive should not skew our math by too much
unless it's a black-swan event (CPI noted 0.2% but was 10% — very rare)." This
is the sensitivity-aware framing — most revisions are noise, only the rare
ones matter.

**Implication for engineering:** Content-addressed blob store (S3 or git-LFS
or just plain git for small artifacts). A change-detection job per source
class. A sensitivity calculator that runs at re-pin time.

---

### Q6 — Who does the time-travel math, and where?

**Decision:** **A+B hybrid.**
- **User controls the time window.** Can pin a TAM to a primitive's native
  `as_of` (no extrapolation), or invoke a time-shift framework.
- **Extrapolation is a first-class framework family.** Growth indices, FX, CPI
  are themselves primitives. Time-shift frameworks take `(base_value,
  growth_index, regime_modifier[], horizon)` → projected scenario tree.
- **Primitive `role` tags.** Inputs to a framework declare a role:
  `base_value | growth_index | regime_modifier | conditional_adjustment`. UI
  uses this to show extrapolation assumptions transparently.
- **Regime modifiers are first-class.** Long-horizon extrapolation (>~2y)
  requires regime modifiers (AI productivity, persistent inflation, demographic
  shift). Short-horizon may skip them.
- **Horizon-aware framework variants.** Short (≤2y, naive compound) vs long
  (>2y, regime-conditional) are different recipes; the long variant forces
  contributors to declare regime assumptions.
- **Strata does not model stochastic short-term shocks** (floods, rate spikes).
  Those are forecasting, which is out of scope per the v1.0 non-goals.

**Why:** Almost every primitive is historical; almost every TAM is "today" or
"+1y." Time-travel is the daily operation, not the edge case. Treating it as a
framework (with its own primitives for growth rates) keeps chain-of-custody
intact. The regime-modifier distinction is the user's contribution: short-window
naive compounding is fine, but extrapolating across the AI/inflation regime
break of 2022–2026 without modifiers is dishonest.

**User's contribution:** "Things like AI or persistent inflation will impact
long-term extrapolation, so you do care about today but things to consider
(another unit??)" — yes, regime modifiers are a new *role*, not a new layer.

---

### Q7 — How do we defend against fake triangulation (correlated sources)?

**Decision:** **Move 3 (lineage + method-family) + honest-broker stance.**
- **Method-family tag mandatory on frameworks** (`top_down_spend |
  bottoms_up_seats | comparable_revenue | analog_penetration | value_chain`).
  Validator warns when a TAM "triangulates" using two frameworks from the
  same family.
- **Source-lineage edges (`derives_from: [...]`) opt-in for contributors,
  mandatory above a popularity threshold.** Sources gradually accumulate
  lineage as primitives mature.
- **Strata computes an "independence score"** for every multi-framework TAM
  and surfaces it visibly with the math behind it.
- **Honest-broker stance.** Strata does not refuse to display low-independence
  TAMs — it warns prominently and lets the user override with an
  acknowledgement. (Refusing would be too paternalistic for an open library.)
- **Visualization:** the lineage graph is a natural fit for the
  `network-graph-modal` skill — to be wired in during implementation.

**Why:** Convergence is the entire defensibility signal in market sizing. If
convergence can be faked (because the three "independent" sources share a root),
the product fails. Surfacing the structure (without refusing to display) is
the Wikipedia move — it's the kind of feature that earns VC trust over
Statista, because nobody else does this.

---

### Q8 — How do we model geography, and the supply-vs-demand landmine?

**Decision:** **Two parallel geo fields + ISO 3166 + named aggregates +
sub-national first-class.**

- **Two parallel fields per primitive:** `geo_supply` (where supplier/reporter
  sits) and `geo_demand` (where buyers are). Most primitives fill one;
  analyst aggregates may declare both. TAM frameworks (buyer-side by
  definition) consume `geo_demand` primitives; the validator rejects mixing.
- **Geo type:**
  ```yaml
  geo:
    level: country | subnational | supranational | global
    codes: [iso-3166-2 codes]                   # us, us-ca, ca-on, de
    aggregate: ~ | na | eu27 | mena | apac | ...
    aggregation_rule: union | sum | allocated_by:<primitive_slug>
  ```
- **Sub-national is first-class** — US states, EU NUTS-2, Chinese tiered
  cities, Canadian provinces. Coast/region skew can move demand by 60%+
  (US east+west coasts are ~60% of GDP); country-only granularity hides this.
- **Named aggregates are curated objects** with their own slugs,
  member-list history (Brexit, Crimea, EU enlargements), and versioning. A
  primitive tagged `geo.aggregate: eu27` resolves through the aggregate's
  member list **at its `as_of` date**.

**Why:** Most modern markets (SaaS, payments, marketplaces) have supplier
geography ≠ buyer geography. A US SaaS company booking $500M in 2025 from
European buyers is *not* US demand. Without two fields, contributors will
silently mix them and TAMs will be 2–5x off.

---

### Q9 — When two independent sources disagree, what do we do?

**Decision:** **Concepts as first-class (5-layer model).**
- **Layers:** `concept → atomic primitive → composite primitive → framework → output (TAM scenario tree)`.
- A **concept** ("US software developer headcount") is a curated object.
  Multiple atomic primitives attach to a concept (BLS OEWS, LinkedIn Economic
  Graph, Stack Overflow Survey extrapolation, …).
- The concept object surfaces all attached primitives **as a structured
  disagreement view** — side-by-side values, methodologies, instruments,
  populations measured.
- Frameworks consume **concepts** (not raw primitives), and declare a
  measurement preference (which attached primitive to use, with a fallback
  chain).
- **Tentative — to confirm at next checkpoint:** Both the schema-level
  `concept → primitives` link *and* expert annotations carry interpretive
  prose. The concept layer is the *structural* surfacing of disagreement;
  annotations are the *interpretive* enrichment ("BLS undercounts captive
  agents by ~20%, here's why").

**Why:** Disagreement at the primitive level is the norm, not the exception.
Burying it under composites (or letting it surface only at framework time)
makes Strata look as opaque as the incumbents it's replacing. Making
disagreement a first-class object — its own page, its own URL, its own
annotation surface — is the defensibility move. The cost is a fifth layer;
the benefit is that "BLS vs LinkedIn vs SO Survey for US developer headcount"
becomes a citable, reusable object that any framework can consume.

**Alternatives rejected:** (A) multiple atomic primitives, composite picks
one — hides disagreement; (B) `competes_with: [...]` link without a parent
object — surfaces disagreement but doesn't give it a home / page / annotation
surface.

---

### Q10 — Who promotes a primitive cluster into a Concept?

**Decision (10a):** **(D) Hybrid — seed concepts + LLM-assisted long-tail clustering.**
- v0.2 ships a **hand-curated seed concept library** (~100 most-cited TAM
  concepts from VC memos: "US developer headcount", "global SaaS spend",
  "US auto insurance premiums", etc.). Seed concepts are precisely scoped
  by maintainers up front.
- New atomic primitives that match a seed concept (by tag overlap +
  declared `concept_slug` in the YAML) attach automatically on ingest.
- Atomic primitives that don't match a seed concept go into an **"unattached"
  pool** that an LLM clusters periodically; the LLM proposes new concept stubs;
  human moderators approve / reject / rename / merge.
- The LLM is anchored by the seed library — it preferentially proposes
  *"these primitives look like the existing 'X' concept"* (precise) rather
  than *"these primitives feel related"* (mushy). This is the explicit defense
  against fake-merge errors.

**Decision (10b):** *(still open — see open threads)*

**Why:** Concept-first (A) blocks contribution friction; primitive-first (B/C)
hides disagreement until promotion fires. Seed concepts solve cold-start;
LLM clustering scales the long tail; humans gate publication so the LLM never
laundering bundles unrelated measurements.

---

## Open threads (carried forward)

- **9b (tentative):** schema-level concept layer is *primary* surfacing of
  disagreement; expert annotations *enrich* it. Confirm at next checkpoint.
- **10b (resolved):** **Narrow test initially.** Same concept iff same population
  scope and definition. BLS narrow-bundle vs BLS broad-bundle vs LinkedIn are
  *three concepts*, linked as siblings ("competing concepts" relationship).
  This favors contributor precision over user one-stop convenience; broader
  bundling can be added later if real usage shows the narrow test creates too
  many sibling-concepts to navigate.
- **Source-lineage threshold for mandatory `derives_from`** — what popularity
  bar? TBD with real data in v0.2.
- **Default Δ% for sensitivity-aware notifications** — starting at 5%, TBD
  with real-user calibration.

---

## Q&A topics still to cover

- [ ] Cross-source reconciliation operational flow (who promotes a primitive
      cluster to a "concept"?)
- [ ] Framework identity over time (when do default assumption changes make
      it a new framework vs new version?)
- [ ] Expert layer: credentialing model, COI disclosure, decay, adverse
      selection, reputation algorithm
- [ ] Graph topology: who curates nodes, what's a node, where do geo/time
      live on the three-axis pyramid, what happens at the leaves
- [ ] Contribution model: PR-based (Wikipedia-style) vs API-based, gating,
      moderation pipeline
- [ ] LLM-assisted ingestion: safety, hallucination detection, attribution
- [ ] Licensing / redistribution: BLS, Statista, Gartner, scraping policy
- [ ] Niche edge cases: two-sided markets, synthetic/emerging markets, gray
      markets, open-source-as-product, wedge vs platform, multi-product
      decomposition, embedded vs standalone, aggregator marketplaces,
      regulated/subsidized markets, network-effect power laws

---

## Final design — Strata data layer (v0.2 → v1.0 blueprint)

This is the synthesis of all 38 decisions into an implementation-ready shape.
Each item below traces back to a specific Q above.

### Five-layer data model

```
Concept                       (Q9, Q10)  — curated identity object, narrow-test scope
  ↓ measured-by
Atomic Primitive              (Q2)       — one source, one number, reproducible
  ↓ bundled-into
Composite Primitive           (Q2, Q3)   — same-unit set ops (union/filter/restrict)
  ↓ consumed-by
Framework                     (Q3, Q15-18) — unit-crossing arithmetic, no scalar defaults
  ↓ emits
TAM Output                    (Q1, Q38)  — scenario tree, permanent URL, content-hash pinned
```

### Primitive record (canonical YAML shape)

```yaml
kind: atomic_primitive | composite_primitive
slug: <kebab-case, type-scoped>
schema_version: 1
concept_slug: <concept_this_measures>          # Q9, Q10b (narrow-test)
name: <human-readable>
description: <prose>

value: <number>                                 # nominal, point-in-time
unit:                                           # Q4
  kind: stock | flow | intensive | dimensionless
  dimension: people | currency | transactions | events | percent | tokens | impressions | ...
  denominator: ~ | per-year | per-month | per-seat | per-policy | ...
  currency: USD | EUR | ETH | BTC | ...        # if dimension=currency | tokens
  basis: nominal                                # always nominal at storage; query-time normalizes

as_of: <ISO date>                               # Q5 — point in time of measurement
expiry: ~ | <ISO date>                          # Q20 — required for synthetic primitives (12 mo default)

geo:                                            # Q8
  level: country | subnational | supranational | global
  codes: [iso-3166-2-codes]
  aggregate: ~ | <named_aggregate_slug>
  aggregation_rule: union | sum | allocated_by:<primitive_slug>
geo_perspective: supply | demand | mixed | unknown

distribution_shape: uniform | normal | power_law | bimodal | other   # Q31
delivery_mode: direct | embedded | bundled | platform_passthrough | n/a  # Q32

uncertainty:                                    # Q1 carried into primitives
  range: [low, high]                            # mandatory for tier in {community-modeled, prediction_market}
  basis: <reason>

source:                                         # Q5
  slug: <source_slug>
  tier: first_party | regulator | aggregator | analyst | community
       | onchain | prediction_market | community-modeled    # Q37 extended
  url: <retrieval URL>
  accessed: <ISO date>
  snapshot_sha256: <hash>                       # mandatory content-addressed blob

derives_from: [source_slugs]                    # Q7 — source-lineage edges

# Composite-only:
inputs: [atomic_primitive_slugs]                # Q3 — required if kind=composite
set_operation: union | intersection | filter | restrict_by_tag
```

### Framework record (canonical YAML shape)

```yaml
kind: framework
slug: <kebab-case>
schema_version: 1
name: <human-readable>
method_family: top_down_spend | bottoms_up_seats | comparable_revenue
              | analog_penetration | value_chain                     # Q7

inputs:                                         # Q6 — role tags + Q15 no scalar defaults
  - name: <param>
    role: base_value | growth_index | regime_modifier | conditional_adjustment
    unit_signature: <unit-type-template>        # for static validation
    required: true | false

formula: <prose description + machine-readable expression>

applicable_to: [taxonomy_node_slugs]            # Q16 whitelist
not_applicable_to: [taxonomy_node_slugs]        # Q16 blacklist
requires_clearance: [regulatory_gates]          # Q36

variants:                                       # Q17 — declared region/sector variants
  - scope: <e.g., us-saas | eu-saas | apac-fintech>
    default_inputs: { <param>: <primitive_slug> }   # pointers, not values (Q15)

expansion_stage_parameter: false | true         # Q22 — when true, framework emits wedge/adjacent/platform scenarios
horizon_class: snapshot | short_extrapolation | long_extrapolation  # Q6
```

### Concept record (canonical YAML shape)

```yaml
kind: concept | company_concept | marketplace_concept                # Q19, Q21
slug: <kebab-case>
schema_version: 1
name: <human-readable>
definition: <precise scope + population + boundaries>                # Q10b narrow test

measurements: [atomic_primitive_slugs]          # Q9 — multiple competing measurements live here
competing_concepts: [concept_slugs]             # Q10b — sibling concepts that measure related-but-not-same

# marketplace_concept only:                     # Q19
demand_side: <concept_slug>
supply_side: <concept_slug>
gmv: <concept_slug>
take_rate: <primitive_slug>

# company_concept only:                         # Q21
segments:                                       # mandatory — no company concept without decomposition
  - name: <segment name>
    category_concept: <concept_slug>
    revenue_share_basis: <primitive_slug>

requires_clearance: [regulatory_gates]          # Q36
```

### TAM Output record (canonical shape)

```yaml
kind: tam_output
slug: <hash-based permanent URL>                # Q38
schema_version: 1
created_by: <contributor>
created_at: <ISO datetime>

target:
  concept: <concept_slug>
  geo: <geo-filter>                             # Q12 — geo as filter overlay
  time: <as_of>                                 # Q12 — time as filter overlay
  expansion_stage: wedge | adjacent | platform | n/a   # Q22

scenarios:                                      # Q1 — scenario tree, not scalar
  - definition: <fully-specified definitional choice>
    value: <number>
    unit: <structured unit>
    framework: <framework_slug>
    framework_variant: <variant scope or null>
    inputs_used:
      - role: base_value | ...
        primitive_slug: <slug>
        snapshot_sha256: <hash>                 # Q5 — content-hash pinned
    assumptions: { <key>: <value> }

# Computed metadata:
method_families_used: [...]                     # Q7 — for independence scoring
independence_score: 0.0 - 1.0                   # Q7 — surfaced in UI
uses_synthetic_primitives: bool                 # Q20 — drives banner
uses_modeled_composites: bool                   # Q20
```

### Pyramid graph topology (Q11–Q14)

- **Three primary axes** stay: Qualitative, Quantitative, Industry.
- **Geo + Time** are global filter overlays / chips above the graph (not pillars).
- **Node types** are mixed:
  - **Taxonomy stub** — pure label, navigation-only, no data attached.
  - **Concept-bearing leaf** — has an attached concept (and through it, primitives + frameworks).
  - **Saved-query node** — dynamic, user-pinnable, shareable; resolves at runtime.
- **Cross-cutting markets** auto-promote to named **intersection Concepts** when usage frequency crosses a threshold.
- **Taxonomy curation:** LLM-suggested + human-approved (mirrors Q10 Concept promotion).

### Storage + infrastructure (Q27–Q30)

- **Source of truth:** YAML files in git, one entity per file, slug-keyed.
- **Query layer:** Postgres mirror rebuilt from git on every merge (from v0.3).
- **Blob store:** content-addressed source snapshots (sha256-named), committed
  alongside YAML or stored on a CDN; either way addressable by hash.
- **Search:** hybrid — full-text + tag-faceted + semantic embeddings.
- **Schema versioning:** records declare `schema_version`; migration scripts in CI
  bump records atomically when schema changes.

### Validator pipeline (Q24, Q29 — layered fast-fail)

1. **Structural** — YAML schema parse, required fields, slug uniqueness.
2. **Semantic** — unit type wiring, citation link liveness, source-snapshot hash match, sanity envelope (±N% of prior value), as_of-in-past, sig-fig sanity.
3. **Cross-record** — concept linking, source lineage independence, framework `applicable_to`/`not_applicable_to` honored.
4. **LLM review** — Claude Code-style PR review for semantic correctness.
5. **Human spot-check** — sample-based, post-publication for high-tier sources; pre-merge for low-tier.

### Contribution + ingestion (Q23, Q25, Q26)

- **PR-based** for primitives, composites, frameworks, concepts, taxonomy.
- **Web form** for annotations (and other low-stakes, low-structure content).
- **LLM auto-publish** allowed only for `tier in {first_party, regulator, onchain}` AND only when all strict validators pass.
- **Licensing:** full reproduction + snapshots for public-domain/open-licensed sources; cite-only metadata stubs for paywalled (Gartner, IBISWorld, Statista).

### Source mutability + change-noise (Q5)

- Citations are **content-hash pinned**.
- Source snapshots are **mandatory at ingest**.
- **Sensitivity-aware notifications:** only flag downstream TAMs whose answer moves >Δ% (default 5%); black-swan >25% gets louder alert; sub-Δ logged silently.
- **Refresh cadence is source-class-aware:** regulators polled frequently; S-1s checked at filing; analyst reports never re-fetched; community/prediction-market sources never auto-refreshed.

### Special-case handling (Q19–Q22, Q31–Q37)

- **Two-sided markets:** dedicated `marketplace_concept` with required demand/supply/GMV/take-rate fields.
- **Multi-product companies:** `company_concept` with mandatory segment decomposition into category concepts.
- **OSS-as-product:** company concept with OSS-user segment + paid-services segment.
- **Wedge / platform:** frameworks take `expansion_stage` parameter; emit scenarios.
- **Power-law markets:** `distribution_shape` field on primitives; frameworks refuse silent mean ops on power-law.
- **Embedded delivery:** `delivery_mode` tag; frameworks filter explicitly.
- **Subsidy-distorted markets:** subsidies are `regime_modifier` primitives; TAM shows base + subsidized scenarios.
- **Dual-economy markets:** unit type supports non-fiat; cross-economy frameworks must cite a conversion primitive.
- **Regulated markets:** `requires_clearance` on concepts; frameworks reuse `applicable_to` to enforce.
- **Dark / private estimates:** allowed with mandatory range, lineage, tier in {community, analyst, prediction_market, community-modeled}; surfaced with banner.
- **Synthetic / emerging markets:** prefer analog-penetration with modeled composites; escape hatch synthetic atomics carry hard guards (range, 12-mo expiry, banner, no LLM-projected).

### TAM artifact (Q38)

Every TAM run produces a **permanent URL** with content-hash pinned inputs +
exportable PDF/markdown that embeds the URL. Citable in memos, reproducible
forever, verifiable by anyone with the link.

---

## Build sequence (mapped to existing roadmap)

| Roadmap | This brainstorm delivers |
|---|---|
| v0.2 — Seed library + schema lock | All record schemas (atomic, composite, framework, concept, output), the unit type system, geo type, source-tier extension, validator-layer-1+2, seed concept library (~100 concepts), 50 primitives, 5 frameworks across 2 verticals — exercising marketplace + multi-product + subsidy paths to prove the schema holds |
| v0.3 — Graph renderer | Pyramid topology with three axes + geo/time overlays; three node types; Postgres mirror; full-text + faceted search |
| v0.4 — Calculator + export | Scenario-tree TAM outputs; content-hash pinning; permanent URLs; PDF/markdown export; method-family / independence scoring surfaced in UI |
| v0.5 — Contribution flow | PR-based contribution with full validator pipeline; LLM PR review (Claude Code-style); LLM auto-publish for high-tier sources; web form for annotations; **expert-layer brainstorm** (parked from this session) lands here |
| v1.0 — Public beta | Semantic embeddings search; 250+ primitives, 25+ frameworks, 5+ verticals; concept promotion flow operational; intersection-concept auto-promotion |

---

## What's NOT in this brainstorm (deferred to follow-up sessions)

- **Expert layer mechanics:** credentialing model, COI disclosure rules, reputation decay, adverse selection, annotator visibility tiers. Better resolved closer to v0.5 implementation with real contributor data.
- **Governance / contributor incentives:** how maintainers are chosen, conflict resolution, recognition.
- **External API / SDK design:** programmatic access, rate limits, attribution requirements.
- **Internationalization** of UI and primitive metadata (multi-language labels).
- **Specific seed concept list:** which 100 concepts ship in v0.2. Should be derived from a survey of recent VC memos.
- **Source-lineage threshold for mandatory `derives_from`** — what citation-count bar triggers mandatory lineage. Calibrate with real data.
- **Δ% defaults for sensitivity-aware notifications** — starting at 5%, calibrate with real user feedback.

---

## Verification plan (when implementation begins)

The schema is correct if these end-to-end scenarios work without contortions:

1. **P&C insurance doc-gen TAM** (the docs' worked example): builds a TAM from BLS carrier counts (atomic) + a "P&C carrier headcount" concept (with NAIC vs state-by-state competing measurements) + a bottoms-up framework with regional variants.
2. **AI agents marketplace TAM 2027** (synthetic market): analog-penetration framework anchored to mobile-app market 2010; modeled composites; banner surfaces.
3. **Stripe TAM** (two-sided + embedded): marketplace concept with demand/supply/GMV/take-rate; primitives carry `delivery_mode: embedded` for Shopify-mediated revenue.
4. **EV charging TAM 2026** (subsidy-distorted): base + IRA-subsidy regime modifier; two scenarios output.
5. **Hedge-fund tech TAM** (power-law): `distribution_shape: power_law` on the spend primitive; framework uses percentile decomposition, refuses silent average.
6. **Polymarket-implied private company valuation** (prediction-market source): primitive tier=prediction_market with mandatory uncertainty range and market URL.

If any of these requires "just one schema exception," the schema is not done.

