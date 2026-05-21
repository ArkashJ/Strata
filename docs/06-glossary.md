# 06 — Glossary

Domain terms used throughout the docs. Add to this file in the same change
that introduces a new term elsewhere.

---

**Annotation**
Expert commentary attached to a primitive, framework, or graph node. Carries
the contributor's credential weight. See [`01-product-layers.md`](01-product-layers.md#layer-3--expert-layer).

**Approach**
The style of a framework's calculation: `top_down`, `bottoms_up`,
`comparable_revenue`, `analog_penetration`, `value_chain`.

**Assumption**
A framework input that is *not* a primitive — a sliderable parameter
(penetration %, addressable share %). Each has a default and an allowed range.

**Constraint**
A filter applied by a graph node (e.g. `company_employees between 100 and
1000`). The active TAM build is the conjunction of all clicked constraints.

**Credibility tier**
A property of a `Source`, ranked: `first_party` > `regulator` > `aggregator`
> `analyst` > `community`. Surfaces in the UI as a colored badge.

**Framework**
A reusable, parameterized recipe that turns primitives + assumptions into a
TAM number. Tagged by function and approach. See [`01-product-layers.md`](01-product-layers.md#layer-2--framework-library).

**Function**
The business function a framework is built for: Finance, Sales/GTM,
Marketing, Ops, HR, Eng/Infra, Legal, etc.

**Pillar**
One of the three axes of the pyramid graph: **Qualitative** (persona /
motion / product shape), **Quantitative** (size band / contract size / geo),
**Industry** (vertical / NAICS).

**Primitive**
An atomic, sourced figure: one value, one date, one methodology, one or more
credibility-tiered sources. The base of the library. See [`01-product-layers.md`](01-product-layers.md#layer-1--primitives-library).

**Range sweep**
Showing the TAM output as a range (low / point / high) by sweeping each
assumption across its allowed range. A point estimate alone is considered
insufficient by the product.

**Source**
A citation. Carries a credibility tier. Reused across primitives. See
[`03-data-model.md`](03-data-model.md#source).

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
