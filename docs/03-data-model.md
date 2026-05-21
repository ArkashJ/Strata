# 03 — Data Model

Draft schemas for the four core entities. **This is a spec draft**, not a
locked schema — expect changes through v0.2.x as the seed library is built.

Storage format target: **YAML files** in `data/`, one entity per file, keyed
by slug. YAML over JSON because primitives carry methodology prose that reads
better in YAML; trivial to load into a relational store later.

---

## Source

A citation. Reused across many primitives.

```yaml
slug: bls-oes-2024
name: "BLS Occupational Employment Statistics, May 2024"
publisher: "U.S. Bureau of Labor Statistics"
tier: regulator              # first_party | regulator | aggregator | analyst | community
url: "https://www.bls.gov/oes/"
accessed: 2026-05-15         # ISO date
notes: |
  National-level OES data. Excludes self-employed and contract labor —
  see methodology note on captive vs. broker agents.
```

### Tier semantics

`tier` is intrinsic to the source, not the use:

- `first_party` — the entity reporting on itself (Stripe, S-1)
- `regulator` — mandatory disclosure (BLS, FMCSA, EDGAR)
- `aggregator` — neutral cross-source normalization (World Bank)
- `analyst` — paid research (Gartner, IBISWorld)
- `community` — Strata contributor submission

---

## Primitive

An atomic, sourced figure.

```yaml
slug: gtm-pros-north-america
name: "GTM professionals in North America"
description: |
  Headcount of professionals in sales, marketing, customer success,
  sales engineering, and revenue ops roles across the US and Canada.

value: 6_400_000
unit: "people"
as_of: 2024-12-31
uncertainty:
  range: [5_800_000, 7_000_000]
  basis: "Range reflects definitional differences across LinkedIn vs BLS counts."

methodology: |
  Sum of BLS OES headcounts for SOC codes 41-3000 (sales reps),
  13-1161 (marketing analysts), 11-2021 (marketing managers),
  43-4051 (CS reps tagged B2B), cross-checked against LinkedIn
  Talent Insights for "Revenue Operations" titles.

sources:
  - bls-oes-2024
  - linkedin-talent-insights-2024-q4

annotations:
  - annotation/bls-undercounts-captive-roles

tags:
  - persona:gtm
  - geo:north-america

version: 3                   # bumped on any value/methodology change
updated_by: "@arkash"
```

---

## Framework

A parameterized recipe.

```yaml
slug: bottoms-up-gtm-tooling
name: "Bottoms-up GTM tooling TAM"
approach: bottoms_up         # top_down | bottoms_up | comparable_revenue | analog_penetration | value_chain
function: sales_gtm

formula: |
  tam = gtm_professionals
      * pct_addressable_by_category
      * avg_acv_per_seat
      * penetration_assumption

inputs:
  - name: gtm_professionals
    kind: primitive
    primitive_slug: gtm-pros-north-america
  - name: pct_addressable_by_category
    kind: assumption
    default: 0.40
    range: [0.10, 0.80]
    description: "Share of GTM seats relevant to this tool category"
  - name: avg_acv_per_seat
    kind: primitive
    primitive_slug: avg-acv-gtm-saas-2024
  - name: penetration_assumption
    kind: assumption
    default: 0.25
    range: [0.05, 0.60]
    description: "Mature category penetration of addressable seats"

compatible_with:             # graph nodes this framework can be anchored to
  - node:qualitative.gtm-tooling
  - node:quantitative.midmarket
  - node:quantitative.enterprise

notes: |
  Avoid for usage-priced categories — use value-chain slice instead.
  Sensitivity: penetration_assumption dominates output; always show
  the full range, not the point estimate.
```

---

## Annotation

Expert commentary on a primitive, framework, or graph node.

```yaml
slug: annotation/bls-undercounts-captive-roles
target:
  kind: primitive
  slug: gtm-pros-north-america

author:
  handle: "@alice"
  credential: verified_domain_expert    # verified_domain_expert | active_practitioner | community
  bio_snippet: "15 years in P&C carrier ops"

body: |
  The BLS OES figure undercounts captive insurance agents by roughly
  20% because OES surveys excluding employer-paid commission-only roles.
  For P&C-only sizing, multiply by 1.25 or cross-reference NAIC carrier
  filings.

posted: 2026-04-12
weight: 1.0                  # derived from credential + community votes
disagreed_by:                # threading
  - annotation/captive-claim-overstated
```

---

## Graph Node

The constraint nodes that make up the pyramid.

```yaml
slug: quantitative.midmarket
label: "Midmarket"
pillar: quantitative         # qualitative | quantitative | industry
tier: 2                      # 0=root, 1=top, 2=middle, 3=base

constraint:
  field: company_employees
  op: between
  value: [100, 1000]

parents:
  - quantitative.commercial
children:
  - quantitative.midmarket.us
  - quantitative.midmarket.emea

primitive_links:
  - n-us-midmarket-companies
  - avg-saas-spend-midmarket

framework_compat:
  - bottoms-up-gtm-tooling
  - top-down-it-spend

status: active               # proposed | active | deprecated
```

---

## Open schema questions

These are deliberately unresolved at v0.1:

1. **Versioning** — bump `version` on any change, or only on value changes?
   Currently leaning toward bump-on-any-change with a `change_kind` field.
2. **Unit canonicalization** — do we enforce SI / canonical currencies, or
   accept native and normalize at query time?
3. **Time-series primitives** — a single `value` works for point-in-time
   facts. For "auto insurance penetration over time" we'll need
   `values: [{as_of, value}, ...]`.
4. **Geo hierarchy** — flat tags (`geo:us`) or structured (`geo: {country: US,
   region: northeast}`)? Probably structured, with the geo taxonomy as its
   own concern.
5. **Framework composition** — can a framework call another framework? Useful
   for "TAM = sum of sub-TAMs" but adds significant complexity. Defer.

Track resolution in `[Unreleased]` of `CHANGELOG.md` as decisions land.
