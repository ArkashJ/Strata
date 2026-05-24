# Strata data collection — final synthesis (W4 + MD lens edition)

> Brainstorm-finalised data-collection strategy for v0.2 → v1.0. Builds on
> top of [`execute.md`](execute.md) (the substrate ingestion architecture —
> fetch / snapshot / extract / validate / tier-gate) and treats it as a
> dependency. Where the two conflict, **this document wins** for the v0.2
> scope decisions; `execute.md` remains canonical for the substrate
> pipeline plumbing.

## Context

Strata's defensibility is the primitive library. The data-layer brainstorm
([`docs/07`](../07-data-layer-brainstorm.md)) locked **what** a primitive
looks like; [`execute.md`](execute.md) locked **how** atomic numbers are
fetched and validated. What was still missing — and what a critic brainstorm
closed — is **how a real VC analyst actually starts a sizing**, and how
Strata's schema accommodates the *math shape* of modern software / fintech /
AI / marketplace TAMs (not just the substitution and budget-capture shapes
the v0.1 sketches assumed).

Three brainstorm decisions framed this synthesis:

1. **Primary workflow → W4 (VC TAM, cost-eff vs rev-gen).** Defers the
   sector-deep-dive (W1), startup-validation (W2), and IB-comparable (W3)
   workflows to v0.5+.
2. **User entry shape → concept-slug via pyramid nav.** Defers the
   startup-name mapper and the LLM-thesis parser to v1.0+.
3. **Capture / replacement rate → slider + annotation, NOT a new primitive
   type.** Defers `qualitative_claim` until expert-call infrastructure lands
   at v0.5. Schema surface area at v0.2 stays minimal.

An MD-mode pass on the lens taxonomy concluded **2 lenses cannot size most
modern companies** (Stripe, Notion, Copilot, Salesforce, OneTrust, Wise,
Uber, Shopify). Expanded to **6 lenses + 4 modifiers** covering the canonical
math shapes.

---

## Six first-class TAM lenses

| Lens | Math (sketch) | Canonical examples | Distinct from L1/L2 because |
|---|---|---|---|
| **L1 `cost_efficiency`** | `persona_pool × addressable_share × replacement_rate × cost_per_persona` | Harvey (paralegals), Glean, Decagon | Substitution baseline |
| **L2 `revenue_generation`** | `target_segment × spend_per_target × capture_rate` | Brex, Rippling, Ramp | Budget-capture baseline |
| **L3 `latent_demand`** | `addressable_population × adoption_rate_curve × willingness_to_pay` | Uber, Duolingo, ChatGPT consumer | No existing budget; demand is **created**, not redirected |
| **L4 `platform_throughput`** | `gmv_or_volume × take_rate` (formalises `marketplace_concept` Q19) | Stripe, Shopify, Twilio, Plaid, Visa | Revenue is a slice of **volume**, not budget |
| **L5 `bundle_consolidation`** | `Σ(n tool spends) × consolidation_rate × pricing_discount` | Notion, Linear, Rippling, Monday | **Sums N budgets** then prices below sum |
| **L6 `productivity_uplift`** | `persona_count × productivity_gain_pct × value_split × pricing_capture` | GitHub Copilot, Cursor, Glean, Harvey-for-associates | Persona **stays employed**; capture share of uplift |

These six are the **structurally distinct math shapes**. Anything else folds
into a modifier on one of these.

## Four composable modifiers (fields, not lenses)

| Modifier | Effect | Schema home | Examples |
|---|---|---|---|
| `opex_conversion` | Pricing multiplier when capex/one-time → recurring | `pricing_premium: <float>` | Salesforce vs on-prem, Adobe CC, MS 365 |
| `margin_capture` | L2 with `target_spend` swapped for middleman margin pool | `middleman: <concept_slug>` | Wise (FX), Robinhood (PFOF), Affirm |
| `regulatory_unlock` | Demand is non-optional; penetration curve event-driven | `driver: <regulation_slug>, effective_date` | OneTrust (GDPR), Drata (SOC 2), Carta |
| `risk_transfer` | L2 specialisation: target_spend = loss-absorbed | `loss_basis: <primitive_slug>` | Coalition, Lemonade, CoverGenius |

## Lens-selection decision tree

```
Q1: Does revenue exist in the target market today?
 ├─ NO  → L3 latent_demand
 └─ YES → Q2: Is the product mediating volume (payments/messages/listings/orders)
          rather than selling capability?
          ├─ YES → L4 platform_throughput
          └─ NO  → Q3: Does the target persona stay employed?
                   ├─ NO  → L1 cost_efficiency
                   └─ YES → Q4: Is the user buying capability the persona
                            already has, but faster/better?
                            ├─ YES → L6 productivity_uplift
                            └─ NO  → Q5: Replacing multiple tools with one?
                                     ├─ YES → L5 bundle_consolidation
                                     └─ NO  → L2 revenue_generation

then layer modifiers as fields (opex_conversion, margin_capture,
regulatory_unlock, risk_transfer).
```

One lens dominates for most concepts. Allow at most one `secondary` lens; the
validator warns if the two scenarios land within 30% of each other (means
`secondary` isn't doing real strategic work).

---

## Schema deltas (the full Section 1)

```yaml
# Concept record additions
analysis_lens:
  primary: cost_efficiency | revenue_generation | latent_demand
         | platform_throughput | bundle_consolidation | productivity_uplift
  secondary: ~ | <one of the above>

modifiers:
  opex_conversion: ~ | { pricing_premium: <float> }
  margin_capture:  ~ | { middleman: <concept_slug> }
  regulatory_unlock: ~ | { driver: <regulation_slug>, effective_date: <ISO> }
  risk_transfer:   ~ | { loss_basis: <primitive_slug> }

required_primitive_roles:
  cost_efficiency:      [persona_pool, addressable_share, replacement_rate, cost_per_persona]
  revenue_generation:   [target_segment_count, spend_per_target, capture_rate]
  latent_demand:        [addressable_population, adoption_rate_curve, willingness_to_pay]
  platform_throughput:  [gmv_or_volume, take_rate, market_share_assumption]
  bundle_consolidation: [tools_displaced[], spend_per_tool[], consolidation_rate, pricing_discount]
  productivity_uplift:  [persona_count, productivity_gain_pct, value_split_to_vendor]
```

### Additional schema work (kept minimal)

1. **New source tier `analyst-paraphrase`** between `analyst` and
   `community-modeled`. Numerical claim only, paraphrased (fair-use
   transformative). Mandatory: `original_publisher`, `accessed` date,
   `paraphrase_reviewer`. Banner downstream: "Paraphrased from {publisher};
   verify against full text."
2. **Slider-with-annotation convention** for capture / replacement / capture
   rates. The slider's default is itself a `community-modeled` primitive with
   mandatory wide `range:` — preserves Q15 ("no scalar defaults") because the
   framework input still points at a citable slug.
3. **No new primitive type** at v0.2. `qualitative_claim` deliberately
   deferred until expert-call infrastructure lands at v0.5.

---

## Six primitive families

The MD lens expansion adds three families on top of the W4 baseline:

| Family | Source path | Used by | Confidence | New schema? |
|---|---|---|---|---|
| **F1 Persona / segment count** | BLS / Census / NAIC / FMCSA — direct API | L1, L2, L6 | High | No |
| **F2 Spend benchmark** | EDGAR segment data OR `analyst-paraphrase` | L2, L5 | Medium | **`analyst-paraphrase` tier** |
| **F3 Cost per target** | BLS OES + multipliers, vendor pricing pages | L1 | High | No |
| **F4 GMV / volume / throughput** | EDGAR 10-K segment (Visa/MA/Stripe S-1s) + analyst-paraphrase | L4 | Medium | No |
| **F5 Adoption-curve analogs** | Hand-seeded set of ~15 historical curves (mobile apps 2010, cloud 2010, SaaS 2005) | L3 | High (historical) | No |
| **F6 Productivity-uplift benchmark** | Community-modeled at v0.2 → analyst-paraphrase + expert-call at v0.5 | L6 | Low-medium | No |

Capture / replacement / capture rate is NOT a sourcing family — it's a
slider with linked annotations.

---

## Six canonical frameworks at v0.2

| Lens | Framework slug | Variants needed by v0.3 |
|---|---|---|
| L1 | `bottoms_up_cost_efficiency` | + healthcare, + legal, + GTM variants |
| L2 | `top_down_revenue_capture` | + vertical SaaS, + horizontal SaaS variants |
| L3 | `adoption_curve_latent_demand` | + consumer, + prosumer, + enterprise variants |
| L4 | `throughput_take_rate` | + payments, + marketplace, + messaging variants |
| L5 | `consolidation_sum_then_discount` | + workplace, + dev-tools, + HR variants |
| L6 | `productivity_uplift_value_split` | + software-eng, + knowledge-work, + sales variants |

Sector variants live as Q17 `variants:` on each base framework — single
framework, declared region/sector sub-recipes with default primitive
pointers. Framework count by v0.3: ~15. By v1.0: ~30.

---

## Six seed concepts (one per lens, v0.2 launch)

Exercises every lens, every source tier, every primitive family. If any seed
breaks the schema or the validator, **stop seeding and fix** — bad schema at 6
is fixable; at 50 it isn't.

| # | Concept | Lens | Tier exercised | Primitive families |
|---|---|---|---|---|
| 1 | `doc-gen-pc-insurance` | L1 + secondary L2 | regulator (NAIC) | F1, F2, F3 |
| 2 | `gtm-ops-tooling-na` | L1 | regulator (BLS) | F1, F3 |
| 3 | `midmarket-saas-spend-na` | L2 | **analyst-paraphrase** | F1, F2 |
| 4 | `payments-throughput-pc-insurance` | **L4** | first_party (EDGAR S-1s) | F1, F4 |
| 5 | `workplace-suite-consolidation` | **L5** | first_party + analyst-paraphrase | F2 |
| 6 | `software-eng-productivity` | **L6** | community-modeled + paraphrase | F1, F3, F6 |

Concept #4 doubles as the canonical `marketplace_concept` (Q19) test.
Concept #6 stress-tests F6, the lowest-confidence family — if
`software-eng-productivity` can't be defended at v0.2 launch, L6 stays behind
a "beta" banner until v0.5.

---

## Vendor stack (sequencing)

| Milestone | Vendor work | Lens/family unlocked |
|---|---|---|
| **v0.2** | Direct-API connectors: BLS / FRED / EDGAR / NAIC bulk. No vendor spend. Six seed concepts hand-finished. | F1, F3, F4 baseline + L1/L2/L4 partial |
| **v0.3** | **Parallel Task API** for analyst-paraphrase extraction; **Exa** for source discovery. Expand to ~20 concepts. | F2, F5, F6 (light) |
| **v0.4** | **Perplexity Sonar** as the cheap refresh probe. Census / OECD / World Bank connectors. | Refresh-cadence loop (Q5) |
| **v0.5** | **Yutori Scouting** for scheduled monitoring; **expert-call infrastructure** (interview tier) → unlocks W2 startup-validation workflow. Promote F6 confidence. | Expert calls, F6 promoted |
| **v1.0** | LLM-thesis parser + startup-name mapper (W1, W2 entry points). Onchain + prediction_market primitives. | W1, W2, dark/forward-looking |

Cost envelope (~500 primitives @ v0.5): ~$75/mo. ~$1k/mo at 5,000 primitives.

---

## Critic notes (what could go wrong)

1. **L4 vs L5 overlap on Rippling.** Rippling is both bundle (L5: ADP +
   Gusto + Okta + Jira displacement) and throughput (L4: payroll volume × take).
   Resolution: allow `primary: L5, secondary: L4`; the scenario tree surfaces
   both numbers because they answer different strategic questions.
2. **L3 latent_demand is LLM-projection-prone.** Adoption curves for "AI
   agents for X" are educated guesses. **Hard guard:** every L3 framework
   requires an `analog:` field pointing at a citable, completed historical
   adoption curve (the F5 family) — no bare exponentials, ever.
3. **L6 productivity_uplift is contestable.** What's `value_split_to_vendor`?
   Copilot at $10/mo to a $200k engineer is 0.06% capture. The lens is honest
   *because* this number is explicit instead of buried in a framework default.
4. **`secondary` lens is a Trojan horse.** Validator warns if both scenarios
   land within 30% — means `secondary` isn't doing real strategic work and
   should be deleted.
5. **`analyst-paraphrase` is legally untested for an open-source crawl-able
   site.** Worst case: publisher sends a takedown for a paraphrase. Mitigation:
   per-publisher opt-out registry, conservative paraphrase length, clean
   takedown endpoint at v0.2 launch.
6. **Six concepts is fragile — but that's the point.** Resist the temptation
   to seed 50 because "BLS is wired." Six exercises every lens; 50 amortises
   schema bugs across an order of magnitude more cleanup.

---

## Critical files / references

- **Constraints (don't drift):**
  - [`docs/07-data-layer-brainstorm.md`](../07-data-layer-brainstorm.md) —
    Q1, Q5, Q15, Q17, Q19, Q20, Q22, Q25, Q26, Q31, Q32, Q36, Q37 all
    informed this synthesis.
  - [`docs/09-expert-layer-brainstorm.md`](../09-expert-layer-brainstorm.md)
    — E1 (pure-commentary) is why the slider-with-annotation pattern works
    instead of `qualitative_claim`.
  - [`docs/10-v0.2-backend-spec.md`](../10-v0.2-backend-spec.md) — validator
    pipeline shape; the lens-aware concept fields plug in here.
- **Substrate (where this layers on top):** [`execute.md`](execute.md) — the
  fetch / snapshot / extract / validate / tier-gate pipeline. Unchanged.
- **Existing scaffold:** `backend/src/strata/models/`,
  `backend/src/strata/validator/`, `backend/src/strata/cli.py` — all stubs
  today; lens schema goes into `models/concept.py` once business logic
  lands.

---

## Verification scenarios

End-to-end at v0.2:

1. **Concept #1 — `doc-gen-pc-insurance`, `analysis_lens.primary: L1`,
   `secondary: L2`.** Seed primitives from NAIC + BLS via direct API. Build a
   TAM. Scenario tree emits two siblings: cost-efficiency ($X) and
   revenue-generation ($Y). Both reproducible from `/tam/<hash>`.
2. **Concept #3 — `midmarket-saas-spend-na`, lens `L2`.** Source path runs
   through `analyst-paraphrase` tier. Paraphrase reviewer field populated.
   Downstream TAM carries the "verify against full text" banner.
3. **Concept #4 — `payments-throughput-pc-insurance`, lens `L4`.**
   Materialises as a `marketplace_concept` with `gmv`, `take_rate`. Sized
   through `throughput_take_rate` framework. Banner if `take_rate` primitive
   is `distribution_shape: power_law`.
4. **Concept #6 — `software-eng-productivity`, lens `L6`.** Slider for
   `productivity_gain_pct` with default 1.4× and range [1.1×, 2.0×]. At least
   3 annotations attached (GitHub Copilot study, Cursor productivity claims,
   counter-evidence from an independent measurement). User adjusts slider; TAM
   updates. Build artifact records the slider value.

Failure-mode verification:
- Concept marked `analysis_lens.primary: L1, secondary: L2` where both
  scenarios land at $48M and $52M → validator warning "secondary lens not
  doing strategic work."
- `analyst-paraphrase` primitive with no `original_publisher` → validator
  rejects.
- L3 framework instance with no `analog:` → validator rejects.

---

## Suggested follow-ups (not in this plan)

These are natural next steps once this synthesis is committed; each is its
own ticket:

1. **Add as Q39 / Q40 addendum to [`docs/07-data-layer-brainstorm.md`](../07-data-layer-brainstorm.md)**
   — the lens model and `analyst-paraphrase` tier are material schema
   additions and belong in the decision record alongside Q1–Q38.
2. **Add the six canonical framework slugs to
   [`docs/05-roadmap.md`](../05-roadmap.md)** under v0.2 deliverables.
3. **Update the [`06-glossary.md`](../06-glossary.md)** with `analysis_lens`,
   each of the 6 lenses, the 4 modifiers, and `analyst-paraphrase`.
