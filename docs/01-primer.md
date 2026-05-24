# 01 — Primer

> A conceptual on-ramp to Strata. Covers the product layers, the five-layer
> data model, and the pyramid network graph — enough to understand the system
> before reading the decision records in [`07`](07-data-layer-brainstorm.md) /
> [`08`](08-product-surface-brainstorm.md) / [`09`](09-expert-layer-brainstorm.md).

## What Strata is

Strata is an open-source, community-curated market-sizing engine. The thesis
([`00-vision.md`](00-vision.md)): IBISWorld / Statista / Gartner-lite reports
sell **defensibility**, not freshness or insight. The number is cheap; the
chain of custody from primitive → calculation → output is expensive. Open the
inputs, let a community correct them, and you eat the bottom 80% of the
market-sizing use case.

The user is a VC analyst or operator who needs a defensible TAM range fast,
with a source trail they can paste into a memo. The deliverable is a permanent
URL that anyone with the link can reproduce.

The interaction surface is a clickable **pyramid network graph** with three
axes (Qualitative · Quantitative · Industry); clicking a node narrows scope
and re-suggests frameworks. See [`04-user-journey.md`](04-user-journey.md) for
a worked end-to-end session.

---

## The three product layers

```
┌──────────────────────────────────────────────────────────────┐
│  Layer 3 — Expert Layer                                      │
│  Annotations: pure commentary. Never auto-applied to math.   │
├──────────────────────────────────────────────────────────────┤
│  Layer 2 — Framework Library                                 │
│  Parameterized recipes: unit-crossing arithmetic.            │
├──────────────────────────────────────────────────────────────┤
│  Layer 1 — Primitives Library                                │
│  Atomic figures with source, snapshot, and credibility tier. │
└──────────────────────────────────────────────────────────────┘
```

### Layer 1 — Primitives Library

Atomic, sourced figures. Each primitive answers a single question with a
single value: "# of GTM professionals in North America", "Average ACV per
seat for sales-engagement SaaS in 2024", "Number of FMCSA-registered active
P&C carriers".

Every primitive carries a slug, a structured value (with unit), an `as_of`
date, a source (with credibility tier), and a content-hash-pinned snapshot
of the underlying document. Source mutations don't silently change downstream
TAMs — pinned hashes make every citation immutable.

**Source-tier enum** (eight tiers, per Q26 + Q37 in
[`07`](07-data-layer-brainstorm.md)):

| Tier | Definition | Examples |
|---|---|---|
| `first_party` | The entity reporting on itself | Stripe blogs, S-1 / 10-K filings |
| `regulator` | Mandatory disclosure | BLS, Census, FMCSA, FDIC |
| `aggregator` | Neutral cross-source normalization | World Bank, OECD, FRED |
| `analyst` | Paid research | Gartner, Forrester, IBISWorld |
| `onchain` | Direct blockchain transaction data | Hyperliquid, Uniswap |
| `prediction_market` | Community-aggregated probability estimates | Polymarket, Kalshi |
| `community` | Vetted contributor submission | A Strata contributor |
| `community-modeled` | Synthetic / modeled values | Analog-penetration models |

`onchain` is treated as first-party-equivalent for crypto/DeFi (the chain
*is* the source). `prediction_market` is community-modeled with a mandatory
link to the specific market URL and liquidity depth.

### Layer 2 — Framework Library

Reusable, parameterized recipes that turn primitives into a TAM. Tagged on
two axes — **function** (Finance, GTM, Ops, ...) and **method family**
(`top_down_spend | bottoms_up_seats | comparable_revenue | analog_penetration
| value_chain`). The method-family tag is load-bearing: a TAM that
"triangulates" from two frameworks in the same family isn't really
independent, and Strata surfaces this with an independence score.

**Frameworks have no scalar defaults.** Every input points to a citable
primitive slug. Change a default → it's a visible, attributable, versionable
change. Regional/sector variants attach default *pointers*, not values.

Seed target for v0.2: ~10 canonical frameworks (bottoms-up by seat, top-down
from category spend, comparable-revenue sum, analog penetration, value-chain
slice, headcount × wage, asset × yield, households × ARPU, transactions ×
take-rate, fleet × spend-per-unit).

### Layer 3 — Expert Layer

Annotations on primitives, frameworks, concepts, or TAMs. **Pure commentary:
the math layer never auto-applies an annotation** ([`09`](09-expert-layer-brainstorm.md)
E1). A user reads the annotation and decides whether to tweak a slider; the
annotation never reaches into the calculation. This eliminates the COI risk
of a biased expert quietly poisoning every TAM that uses their primitive.

Contributors carry one of three tier badges: `verified-expert` ·
`active-practitioner` · `community`. Annotations are append-only — no expiry,
no supersedes link, readers sort and judge. Operational mechanics
(credentialing, reputation algorithm, moderation pipeline) are deferred to
v0.5.

---

## The five-layer data model

The brainstorm in [`07`](07-data-layer-brainstorm.md) refined the original
three-layer sketch into a five-layer model — concepts and composites are
first-class objects between the original primitive and framework tiers:

```
Concept                   — curated identity object (e.g., "US developer headcount")
  ↓ measured-by
Atomic Primitive          — one source, one number, reproducible
  ↓ bundled-into
Composite Primitive       — same-unit set ops (union/filter/restrict)
  ↓ consumed-by
Framework                 — unit-crossing arithmetic, no scalar defaults
  ↓ emits
TAM Output                — scenario tree, permanent URL, content-hash pinned
```

**Concept** — a curated identity object representing a measurable thing
("US software developer headcount"). Multiple atomic primitives can attach
to a concept (BLS OEWS, LinkedIn Economic Graph, Stack Overflow Survey
extrapolation, ...). The concept's page surfaces them side-by-side as a
structured **disagreement view** with each measurement's methodology and
population. Frameworks consume concepts, not raw primitives — so disagreement
gets a home, not a footnote.

**Atomic Primitive** — one source, one number, narrowly defined,
reproducible. Carries `value`, structured `unit`, `as_of`, `geo_supply` /
`geo_demand`, `distribution_shape` (e.g., `power_law` for hedge-fund tech),
`delivery_mode` (e.g., `embedded` for Stripe-via-Shopify revenue), and a
content-hash-pinned source snapshot.

**Composite Primitive** — same-unit set operations (union, intersection,
filter, restrict). **No unit-crossing math** lives here — that's the hard
line between composites and frameworks. Composites are cheap to
auto-generate; frameworks need human review.

**Framework** — all unit-crossing arithmetic. Takes structured inputs with
role tags (`base_value | growth_index | regime_modifier |
conditional_adjustment`). Declares unit signatures (e.g.,
`stock[people] × intensive[USD/people/year] → flow[USD/year]`); the validator
statically rejects bad wiring.

**TAM Output** — a **scenario tree**, never a scalar + error bars. Each
scenario is a fully specified definitional choice with its own value,
sources, and assumptions. Every TAM gets a permanent `/tam/<hash>` URL with
content-hash-pinned inputs — citable in memos, reproducible forever.

The canonical YAML shapes for all five layers (and for `marketplace_concept`,
`company_concept`, `annotation`, etc.) live in
[`07-data-layer-brainstorm.md`](07-data-layer-brainstorm.md) §"Final design".
Treat that doc as the single source of truth for record schemas.

---

## The pyramid network graph

Three pillars converging at the top — the TAM question is the root.

```
                          ┌────────────────────────┐
                          │  TAM for GTM tooling × │       ← Root: the question
                          │  P&C × Midmarket NA    │
                          └────────────┬───────────┘
                                       │
            ┌──────────────────────────┼──────────────────────────┐
            ▼                          ▼                          ▼
       ┌─────────┐                ┌─────────┐                ┌─────────┐
       │  B2C/   │                │ Enterprise│              │   ...   │   ← top tier
       │  B2B    │                │ / Defense │              └────┬────┘    (coarse)
       └────┬────┘                └────┬────┘                     │
            │                          │                          │
       ┌────┴─────┐               ┌────┴────┐                ┌────┴────┐
       │ GTM for  │               │Midmarket│                │  P&C    │   ← middle tier
       │ engineers│               │         │                │Insurance│
       └────┬─────┘               └────┬────┘                └────┬────┘
            │                          │                          │
       ┌────┴─────┐              ┌─────┴─────┐              ┌─────┴──────┐
       │ GTM for  │              │   SMB /   │              │  Doc-gen   │   ← base tier
       │ bio tools│              │ consumer  │              │  for P&C   │     (granular)
       └──────────┘              └───────────┘              └────────────┘
        Qualitative              Quantitative                 Industry
```

### Three axes

| Pillar | What it slices by | Examples |
|---|---|---|
| **Qualitative** | Buyer / user persona, motion, product shape | "GTM for engineers", "GTM for bio tools", "B2C vs B2B" |
| **Quantitative** | Customer size band, contract size | "Enterprise", "Midmarket", "SMB", "Consumer" |
| **Industry** | Vertical / NAICS-style | "P&C Insurance", "Logistics", "Healthcare payers" |

A TAM is almost always a conjunction across pillars — e.g.,
"GTM tooling × Midmarket × P&C Insurance".

**Geo and Time are filter chips above the graph, not pillars** (Q12 / U1).
Promoting them to pillars tetrahedralizes the cognitive load; they're
orthogonal scoping dimensions that apply to every node.

### Three node types

Per Q11 in [`07`](07-data-layer-brainstorm.md), nodes are heterogeneous:

- **Taxonomy stub** — pure label, navigation-only, no data attached.
- **Concept-bearing leaf** — has an attached concept (and through it,
  primitives + frameworks).
- **Saved-query node** — dynamic, user-pinnable, shareable; resolves at
  runtime to a live set matching its filter (e.g., "all GTM-tooling concepts
  in NA published in the last 12 months").

### Interaction model

| Action | Effect |
|---|---|
| **Click node** | Add as constraint; grey out incompatible siblings; re-suggest frameworks |
| **Shift-click** | OR within same pillar / tier ("Midmarket OR Enterprise") |
| **Click again** | Remove constraint |
| **Hover** | 250ms-delayed ghost card with value, tier badge, snapshot indicator, 1-line description |
| **Right-click → Expand** | Reveal next tier of children |
| **Right-click → Annotate** | Add an expert comment |
| **Right-click → Suggest framework** | Open framework picker pre-filtered for the constraint set |

Layout is force-directed with **pillar lanes** — x-position is locked to
pillar, y-position to tier; siblings push apart, parents pull to children's
centre of mass. The pyramid stays recognisable while the user pans / zooms.

The full UX surface (URL structure, page types, right-rail accordion,
annotation display, export model) is locked in
[`08-product-surface-brainstorm.md`](08-product-surface-brainstorm.md).

---

## A worked tiny example

Goal: size doc-gen software for P&C insurance carriers in the US.

1. **Concept** `us-pc-carriers-active` — "Active P&C insurance carriers
   filing with state insurance departments in the US." Three attached
   atomic primitives: NAIC carrier directory (`tier: regulator`), AM Best
   listing (`tier: aggregator`), Insurance Information Institute count
   (`tier: aggregator`). Three values, three methodologies, on one
   side-by-side page.
2. **Atomic primitive** `naic-active-pc-carriers-2024`:
   `value: 2_650`, `unit.kind: stock`, `unit.dimension: organizations`,
   `as_of: 2024-12-31`, `geo_demand: us`, `source.tier: regulator`,
   `source.snapshot_sha256: <hash>`.
3. **Framework** `bottoms-up-vertical-saas-tam`: takes `carrier_count` (a
   concept), `pct_addressable` (a primitive — modal-carrier addressable
   share), `avg_acv_per_carrier` (a primitive), and emits
   `flow[USD/year]`. No scalar defaults — every input is a citable slug.
4. **TAM Output** `/tam/abc123` — scenario tree with three scenarios:
   narrow-bundle (~$80M), broad-bundle (~$150M), platform-stage
   (~$220M). All inputs hash-pinned. Independence score surfaced because
   only one method-family was used. Permanent URL exportable to PDF /
   Markdown.

Sarah pastes the URL into her memo. Six months later, a reader clicks
through and sees the exact primitives she cited — even if NAIC has since
revised its carrier count, the pin makes her build reproducible.

---

## Where to go next

| Doc | When to read |
|---|---|
| [`00-vision.md`](00-vision.md) | "Why does this exist? What's the moat?" |
| [`04-user-journey.md`](04-user-journey.md) | "What does a real session look like?" |
| [`05-roadmap.md`](05-roadmap.md) | "What ships at v0.2, v0.3, v0.5, v1.0?" |
| [`06-glossary.md`](06-glossary.md) | "What does *X* mean in Strata?" |
| [`07-data-layer-brainstorm.md`](07-data-layer-brainstorm.md) | "What are the data-schema rules and why?" (Q1–Q38) |
| [`08-product-surface-brainstorm.md`](08-product-surface-brainstorm.md) | "What are the UX decisions?" (U1–U12) |
| [`09-expert-layer-brainstorm.md`](09-expert-layer-brainstorm.md) | "What's the annotation schema?" (E1–E5) |
| [`10-v0.2-backend-spec.md`](10-v0.2-backend-spec.md) | "How is v0.2 actually being built?" |
| `CLAUDE.md` (repo root) | "What rules apply when AI assists in this repo?" |
