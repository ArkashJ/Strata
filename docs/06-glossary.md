# 06 — Glossary

Domain terms used throughout the docs. Add to this file in the same change
that introduces a new term elsewhere.

---

**Analysis lens**
The math shape a TAM is sized through. Six first-class lenses per
[`07`](07-data-layer-brainstorm.md) Q39 — every concept declares one as
`primary`, optionally one as `secondary`:
- **`cost_efficiency`** — substitute existing labor / spend.
  `persona_pool × addressable_share × replacement_rate × cost_per_persona`.
  (Harvey, Glean, Decagon.)
- **`revenue_generation`** — capture share of existing budget.
  `target_segment × spend_per_target × capture_rate`. (Brex, Rippling, Ramp.)
- **`latent_demand`** — activate demand that didn't exist.
  `addressable_population × adoption_rate_curve × willingness_to_pay`.
  Requires citable `analog:` (no bare exponentials). (Uber, Duolingo,
  ChatGPT consumer.)
- **`platform_throughput`** — slice of volume passing through.
  `gmv_or_volume × take_rate`. Formalises Q19 `marketplace_concept`.
  (Stripe, Shopify, Twilio, Plaid, Visa.)
- **`bundle_consolidation`** — replace N tools with 1.
  `Σ(n tool spends) × consolidation_rate × pricing_discount`. (Notion,
  Linear, Rippling, Monday.)
- **`productivity_uplift`** — humans stay, each is N× more productive,
  capture share of the uplift.
  `persona_count × productivity_gain_pct × value_split × pricing_capture`.
  (GitHub Copilot, Cursor, Glean.)

Stacks with **lens modifiers**.

**Analyst-paraphrase**
A source tier (Q40) between `analyst` and `community-modeled`. Allows
**paraphrased numerical claims** from paywalled analyst sources (Gartner,
IBISWorld, Statista, SemiAnalysis, FT) — fair-use transformative.
Mandatory: `original_publisher`, `accessed` date, `paraphrase_reviewer`,
paraphrase ≤ 280 chars, no body reproduction. Banner downstream: "Paraphrased
from {publisher}; verify against full text." Never auto-publishes (always
PR review per Q25). Per-publisher opt-out registry + takedown endpoint
required.

**Annotation**
Expert commentary attached to a primitive, framework, concept, or TAM.
**Pure commentary** — never auto-applied to the math
([`09`](09-expert-layer-brainstorm.md) E1). See
[`01-primer.md`](01-primer.md#layer-3--expert-layer).

**Approach** — see **Method family**.

**Assumption**
A framework input that is *not* a primitive — a sliderable parameter
(penetration %, addressable share %). Each has a default and an allowed range.

**Composite Primitive**
A primitive assembled from atomic primitives via **same-unit set
operations** (union, intersection, filter, restrict). No unit-crossing math
— that's the hard line vs Framework
([`07`](07-data-layer-brainstorm.md) Q3).

**Concept**
A curated identity object ("US software developer headcount"). Multiple
competing atomic primitives can attach to a concept; the concept page
surfaces them as a side-by-side disagreement view
([`07`](07-data-layer-brainstorm.md) Q9, Q10). Frameworks consume concepts,
not raw primitives.

**Constraint**
A filter applied by a graph node (e.g. `company_employees between 100 and
1000`). The active TAM build is the conjunction of all clicked constraints.

**Credibility tier**
A property of a `Source`. **Nine tiers** per
[`07`](07-data-layer-brainstorm.md) Q26 + Q37 + Q40: `first_party`,
`regulator`, `aggregator`, `analyst`, `analyst-paraphrase`, `onchain`,
`prediction_market`, `community`, `community-modeled`. Surfaces in the UI
as a coloured badge. Auto-publish gates (Q25) cover `first_party`,
`regulator`, and `onchain` only — all others require PR review.

**Framework**
A parameterized recipe that turns primitives into a TAM. Does
**unit-crossing arithmetic** and has **no scalar defaults** — every input
is a citable primitive slug. Tagged by function and method family. See
[`01-primer.md`](01-primer.md#layer-2--framework-library).

**Function**
The business function a framework is built for: Finance, Sales/GTM,
Marketing, Ops, HR, Eng/Infra, Legal, etc.

**Independence score**
A 0–1 score on a multi-framework TAM measuring how independent its inputs
are. Computed from method-family diversity and source-lineage edges
([`07`](07-data-layer-brainstorm.md) Q7). Surfaced in the UI; honest-broker
stance — never refuses display.

**Lens modifier**
A composable field on a Concept that conditions its `analysis_lens` without
adding a new lens (Q39). Four modifiers:
- **`opex_conversion`** — pricing multiplier when capex/one-time → recurring.
  (Salesforce vs on-prem, Adobe CC, MS 365.)
- **`margin_capture`** — `revenue_generation` with `target_spend` swapped
  for a middleman margin pool. (Wise, Robinhood, Affirm.)
- **`regulatory_unlock`** — demand is non-optional; penetration curve is
  event-driven. (OneTrust, Drata, Carta.)
- **`risk_transfer`** — `revenue_generation` specialisation where
  `target_spend` is current loss absorption. (Coalition, Lemonade,
  CoverGenius.)

**Method family**
The structural style of a framework's calculation: `top_down_spend`,
`bottoms_up_seats`, `comparable_revenue`, `analog_penetration`,
`value_chain`. Load-bearing for independence scoring.

**Pillar**
One of the three axes of the pyramid graph: **Qualitative** (persona /
motion / product shape), **Quantitative** (size band / contract size),
**Industry** (vertical / NAICS). Geo + Time are filter chips, **not**
pillars ([`07`](07-data-layer-brainstorm.md) Q12).

**Primitive**
An atomic, sourced figure: one value, one date, one structured unit, one
or more credibility-tiered sources, one content-hash-pinned snapshot. The
base of the library. See
[`01-primer.md`](01-primer.md#layer-1--primitives-library).

**Range sweep** — see **Scenario tree**.

**Scenario tree**
The shape of a TAM Output. **Not** a scalar + error bars — a tree of
fully-specified definitional choices, each with its own value, sources,
and assumptions ([`07`](07-data-layer-brainstorm.md) Q1).

**Source**
A citation. Carries a credibility tier and a content-hash-pinned
snapshot. Reused across primitives. Canonical YAML in
[`07-data-layer-brainstorm.md`](07-data-layer-brainstorm.md#primitive-record-canonical-yaml-shape).

**Strata**
The provisional codename for the project. Renamable.

**TAM** — Total Addressable Market
The size of the market a product could in principle serve, ignoring
realistic share constraints. (The product also surfaces SAM / SOM where
relevant, but TAM is the default deliverable.)

**Tier (graph)**
The depth of a graph node within its pillar. Tier 0 = root, tier 3 = base.
Floor of v1.0 is tier 3 — below that, per-node primitive counts collapse.

**Tier (source)** — see **Credibility tier**.
