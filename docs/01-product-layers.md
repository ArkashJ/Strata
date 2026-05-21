# 01 — Product Layers

Three layers, stacked. Each is independently valuable, but compounding.

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 3 — Expert Layer                                     │
│  Annotations, alt-framings, blind-spot flags, reputation    │
├─────────────────────────────────────────────────────────────┤
│  Layer 2 — Framework Library                                │
│  Reusable recipes: primitives → TAM, by function & approach │
├─────────────────────────────────────────────────────────────┤
│  Layer 1 — Primitives Library                               │
│  Atomic figures with value, date, methodology, source tier  │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 1 — Primitives Library

### What

A repository of atomic, credible figures. Each primitive answers a single
question with a single value.

Examples:

- "# of GTM professionals in North America"
- "Average IT spend per US SMB"
- "% of US households with auto insurance"
- "Number of FMCSA-registered active P&C carriers"
- "Average ACV per seat for sales-engagement SaaS in 2024"

### Required fields

Every primitive carries:

- **slug** — stable identifier (`gtm-pros-north-america`)
- **value** — number + unit (`6_400_000 people`)
- **as_of** — date the figure represents
- **methodology** — 1–3 sentences on how it was derived or where it came from
- **source** — citation with credibility tier
- **uncertainty** — optional explicit range (e.g. `±10%`)

See [`03-data-model.md`](03-data-model.md) for the full schema.

### Credibility tiers

Ordered from highest to lowest:

| Tier | Definition | Examples |
|---|---|---|
| `first_party` | The entity in question publishing about itself | Stripe on payments, Visa on card volume, S-1 / 10-K filings |
| `regulator` | A government body required to collect the data | BLS, Census, FMCSA, FDIC |
| `aggregator` | A neutral third party normalizing across sources | World Bank, OECD, Federal Reserve econ data |
| `analyst` | Paid research, brokerage notes, or industry analyst estimates | Gartner, Forrester, IBISWorld |
| `community` | Crowdsourced or expert-submitted figures, not yet independently corroborated | Submitted by a vetted Strata contributor |

The tier is a property of the **source**, not the primitive. A primitive can
have multiple sources of different tiers — UI surfaces the best available.

### Why this is the moat

Anyone can write a framework. The library of vetted, dated, source-trailed
primitives is the asset that compounds. Every TAM build in the system creates
incentive to add or correct primitives, which makes the next build better.

---

## Layer 2 — Framework Library

### What

Reusable, parameterized recipes for getting from primitives to a TAM.

### Organization

Frameworks are tagged on two axes:

- **Function** — Finance, Marketing, Sales/GTM, Ops, HR, Eng/Infra, Legal, ...
- **Approach** — `top_down`, `bottoms_up`, `comparable_revenue`, `analog_penetration`, `value_chain`

### Anatomy of a framework

A framework is a templated calculation:

```yaml
slug: bottoms-up-gtm-tooling
name: "Bottoms-up GTM tooling TAM"
approach: bottoms_up
function: sales_gtm
formula: |
  tam = gtm_professionals
      * pct_addressable_by_category
      * avg_acv_per_seat
      * penetration_assumption
inputs:
  - name: gtm_professionals
    primitive: gtm-pros-north-america
    description: "# of GTM seats in the geography"
  - name: pct_addressable_by_category
    type: assumption
    default: 0.40
    description: "Share of GTM seats relevant to this tool category"
  - name: avg_acv_per_seat
    primitive: avg-acv-gtm-saas-2024
  - name: penetration_assumption
    type: assumption
    default: 0.25
    description: "Realistic mature penetration of category among addressable seats"
notes: |
  Sensitive to penetration_assumption — show the full 10%-60% sweep.
```

When the user picks this framework, the system pre-fills `primitive` slots from
Layer 1 and exposes `assumption` slots as sliders.

### Seed set (target for v0.2.0)

A first cut of ~10 canonical frameworks covering:

1. Bottoms-up by seat (GTM, finance ops, HR)
2. Top-down from category spend (IT spend, marketing spend)
3. Comparable-revenue sum (sum public + private cap-table proxies)
4. Analog penetration (mature category × penetration delta)
5. Value-chain slice (% of GMV captured by tool)
6. Headcount × wage (services TAM)
7. Asset × yield (financial-services TAM)
8. Households × ARPU (consumer TAM)
9. Transactions × take-rate (payments / marketplace TAM)
10. Vehicle / unit fleet × spend-per-unit (industrial / fleet TAM)

### Why limit the count

Frameworks are not a long tail — they're a finite, learnable set. The library
is more useful if it's curated than if it's exhaustive.

---

## Layer 3 — Expert Layer

### What

Comments, annotations, and alternative framings attached to figures and
frameworks.

### Examples

- On a primitive: *"This BLS number undercounts by ~20% because it excludes
  captive insurance agents. For P&C-only sizing, multiply by 1.25 or use NAIC
  filings."* — by `@alice`, P&C carrier exec, 15 years
- On a framework: *"Bottoms-up by seat doesn't work for usage-priced tools —
  use the value-chain slice instead."* — by `@bob`, ex-CRO at a usage-priced
  vendor
- Alt-framing on a TAM: *"This sizing assumes broker channel; if you sell
  direct, the addressable set is 3x smaller because of captive distribution."*

### Reputation and credentialing

Annotations carry contributor weight:

- **verified domain expert** — credentials checked (LinkedIn + bio + optional
  vouch from another verified expert)
- **active practitioner** — currently working in the domain, self-attested
- **community** — uncredentialed but participating

Weight affects sort order and visibility, not whether comments exist. The
system is contested-but-civil by default; downvoted-into-oblivion is not the
mechanism.

### Why this matters

Static PDF reports cannot be corrected when reality moves. A living layer of
expert commentary is what turns a primitives library into something
**defensible to a partner meeting** — the user can answer "where did this
number come from and who has disagreed with it?" in one click.
