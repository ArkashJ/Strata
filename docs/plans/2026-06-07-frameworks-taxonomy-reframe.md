# Frameworks taxonomy reframe — 6 shapes + subframeworks + signals + perspectives

**Status:** IMPLEMENTED (Option A), 2026-06-07 — schema fields
(`Framework.parent_lens_shape` + `realism_modifiers`, the `RealismModifier`
enum), all 25 frameworks tagged (6 canonical + 19 subframeworks), the
cross-record validator gate (`_framework_taxonomy`: exactly one canonical per
lens), and `backend/tests/test_framework_taxonomy.py` (7 tests). Signals +
Perspectives needed no code — they already exist (the Q20 signal quarantine; the
convergence / independence / method-directions / scope / sensitivity views) —
this doc names them as first-class tiers. Supersedes the "5 → 25 frameworks =
the real IP" framing in
[`docs/STRATEGY-REVIEW-2026-06-06.md`](../STRATEGY-REVIEW-2026-06-06.md) and the
PR-5 "Frameworks 5 → 25" item in [`docs/TODO_june6.md`](../TODO_june6.md).
**Date:** 2026-06-07.

## The question

> Keep the 6 frameworks instead of 25, but divide into subframeworks because some
> of them are redundant — they can be signals and perspectives.

## The finding (this is already true in the tree)

The "25 frameworks" the roadmap wanted **already exist** — `data/frameworks/`
holds **25 framework files × 84 variants** (CLAUDE.md's "5 frameworks / 30
variants" is stale). But they are **not 25 distinct math shapes.** They are the
**6 lens shapes × a small set of "realism modifiers"** applied to the formula.

Proof — the four L1 `cost_efficiency` "frameworks" are one shape + a modifier:

```
full-displacement      persona_pool · addressable_share · replacement_rate · cost_per_persona     ← base shape
bounded-displacement   persona_pool · clamp(addressable_share·replacement_rate,0,1) · cost_per…   ← + CLAMP
adoption-gated         persona_pool · addressable_share · curve(replacement_rate,steep) · cost_…  ← + CURVE
bottoms_up (degenerate) persona_pool · cost_per_persona                                            ← reduced 2-term
```

The same modifier axis recurs in every lens: `-full` / `-bounded` / `-adoption-gated`
(L1, L2, L4, L6), `-saturating` / `-curve` (L3), `-net-of-discount` (L5). So the
25 collapse to **6 shapes × ~4 realism modifiers**, plus a few degenerate
reduced forms. Counting them as 25 frameworks overstates distinctness — and the
"every framework is structurally distinct" validator gate (TODO_june6 PR-5) is
not actually being met.

## Why the reframe is *more* defensible, not less

The strategy review's own thesis is that Strata's moat is the **verification
layer** ("defensible-assumption layer"), not data volume. A claim of "25 distinct
recipes" is brittle — a reviewer who notices they're 6 shapes restated reads it
as inflated IP. The honest, stronger claim:

> **6 rigorous math shapes × a sourced, guarded library of realism variants,
> fenced from a signals layer (corroborators) and surfaced through perspectives
> (cross-checks).**

The depth is in the *guarded variants + the fence*, exactly where the strategy
review says the fork-proof assets are.

## Proposed taxonomy — one shape tier, two fenced tiers

```
FRAMEWORK (6)          the canonical multiplication shapes — the IP
  L1 cost_efficiency   persona_pool · addressable_share · replacement_rate · cost_per_persona
  L2 revenue_gen       target_segment_count · spend_per_target · capture_rate
  L3 latent_demand     addressable_population · adoption_rate_curve · willingness_to_pay
  L4 platform_through  gmv_or_volume · take_rate · market_share_assumption
  L5 bundle_consolid   tools_displaced · spend_per_tool · consolidation_rate · (1−pricing_discount)
  L6 productivity_up   persona_count · productivity_gain_pct · value_split_to_vendor
        │
        ├─ SUBFRAMEWORK  = shape × realism modifier (CHANGES the number → stays in the math tier)
        │     realism modifiers (composable, cross-lens):
        │       full         no bounding (raw product)
        │       bounded      clamp(share·rate, 0, 1)        — can't displace >100%
        │       adoption-gated  curve(rate, steepness)       — S-curve adoption
        │       saturating   logistic ceiling                — L3 demand ceiling
        │       net-of-discount (1 − pricing_discount)       — L5 bundling
        │     + variant bindings (Q15/Q17): {input_name → primitive_slug} per concept
        │
SIGNAL (fenced)        corroborates, NEVER multiplies into a TAM (Q20)
        202 Kalshi prediction-market primitives, quarantined to data/signals/
        candidates to add: hiring velocity, sentiment, web traffic — all read-only
        │
PERSPECTIVE (fenced)   a VIEW on an already-computed TAM — introduces NO new number
        convergence (≥2 families agree) · independence score · method-directions
        (top-down ∧ bottoms-up) · scope report · sensitivity/tornado
```

### The two tests that sort everything

1. **Does it change the computed number?**
   - New multiplication structure → **Framework** (rare; there are ~6).
   - Same structure, different realism treatment or primitive binding → **Subframework**.
   - No → not in the math tier at all (go to test 2).
2. **Does it feed a TAM at all?**
   - It's an indicator that corroborates but never multiplies in → **Signal**.
   - It's a way to view / cross-check an existing TAM → **Perspective**.

## Bucketing the current 25

| Lens | Keep as the 1 Framework (shape) | Collapse to subframeworks (realism modifier) |
|---|---|---|
| L1 cost_efficiency | `cost-efficiency-full-displacement` (canonical) | bounded, adoption-gated, bottoms_up(degenerate) |
| L2 revenue_generation | `top_down_revenue_capture` | capture-addressable, capture-bounded, capture-full, adoption-gated |
| L3 latent_demand | `latent-demand-adoption-curve` | addressable-logistic, saturating-addressable, saturating-curve |
| L4 platform_throughput | `throughput-take-rate-with-share` | take_rate(degenerate), adoption-gated, bounded-yield |
| L5 bundle_consolidation | `consolidation-net-of-bundling-discount` | bounded-net, sum_then_discount |
| L6 productivity_uplift | `productivity_uplift_value_split` | uplift-addressable, -bounded, -full, adoption-gated |

Net: **25 framework records → 6 frameworks + ~19 subframeworks.** No recipe is
deleted; the math is preserved. Only the *classification* changes — and with it,
the count we claim and the way the UI groups them.

## Schema / validator implications (for the build phase, not now)

The data model already has most of the bones
(`backend/src/strata/models/framework.py`): `Framework{lens, method_family,
formula, variants}` and `FrameworkVariant{scope, default_inputs}`. Two viable
implementations:

- **Option A — relabel + group (low cost, no schema change).** Add an optional
  `parent_lens_shape: Slug` + `realism_modifier: Literal[full|bounded|adoption_gated|saturating|net_of_discount]`
  to `Framework`. The 6 canonical shapes have no parent; the other 19 point at
  their shape. Validator gains a check: *every non-canonical framework declares a
  parent shape and a modifier; exactly one canonical framework per lens.* UI/report
  group by shape → modifier. Recipes and YAML stay where they are.
- **Option B — collapse into one record per shape (higher cost).** Fold the
  modifier into the variant: `FrameworkVariant` gains `realism_modifier`, and the
  6 Framework records carry all formulas as modifier-keyed alternates. More
  faithful to "6 frameworks," but a bigger migration and a formula-selection rule
  at eval time.

**Recommendation: Option A.** It makes the taxonomy true and checkable without
rewriting the evaluator or the 84 variant bindings, and the validator gate
finally means something ("structurally distinct" now applies only to the 6
shapes, which genuinely are).

Signals and Perspectives need **no new code** — both layers exist
(`registry.signals` + the Q20 quarantine; `Convergence` / `independence_score` /
`MethodDirections` / `ScopeReport` / sensitivity). This doc just names them as
first-class tiers so the docs, the `/agents` + report surfaces, and the strategy
narrative describe the same four-tier model.

## What this changes in the story

- `docs/STRATEGY-REVIEW-2026-06-06.md`: "5 → 25 frameworks" becomes "6 shapes +
  a guarded subframework/variant library + signals + perspectives."
- `docs/TODO_june6.md` PR-5 "Frameworks 5 → 25 (each structurally distinct)":
  retire — the distinctness claim was never met; replace with "classify the
  existing 25 into 6 shapes + modifiers; enforce via validator."
- `CLAUDE.md` lens table already lists the 6 shapes — it's the right altitude;
  the "5 frameworks / 30 variants" line is stale and should read 6 shapes.

## Open questions for review

1. **Option A vs B** — relabel-and-group, or physically collapse to 6 records?
   (Recommend A.)
2. **Modifier vocabulary** — is `{full, bounded, adoption_gated, saturating,
   net_of_discount}` the complete realism axis, or is there a 6th?
3. **Degenerate forms** (`bottoms_up_cost_efficiency` = 2-term, `throughput_take_rate`
   = no share) — keep as a `reduced` modifier, or drop as not-defensible?
4. **Signals roadmap** — beyond Kalshi, which corroborators are worth ingesting
   as read-only signals (hiring, traffic, sentiment)?
5. Does the count claim matter externally — i.e. do we *want* to say "6 frameworks"
   publicly, or keep "25 recipes" for the variant library?
