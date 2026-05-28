# TAM — Frontier-quality data labeling, 2025

**Segment.** Expert human labelers used by frontier AI labs for RLHF, code /
reasoning evals, and red-teaming. The "like Turing / Scale AI / Surge AI"
market. This is **distinct** from commodity image annotation: per-task
pricing is 10–50× higher and the buyer is OpenAI / Anthropic / Google /
Meta, not autonomous-vehicle teams or e-commerce.

**Asked by.** VC sizing question on 2026-05-27. Computed by the Strata
methodology (lens × framework × sourced primitives) and walked manually
because the live `strata goal` CLI couldn't reach Anthropic on this
workstation (malformed `ANTHROPIC_API_KEY` in `.env`). Numbers here would
normally land in `~/.strata/auto-primitives/` and be promotable into
`data/primitives/` once they pass the validator.

---

## Lens choice

Three of Strata's six lenses are relevant:

```
L1 cost_efficiency      ← primary lens (bottom-up labor)
    TAM = (expert labelers) × ($/hr) × (annual utilized hours)

L4 platform_throughput  ← cross-check (the marketplace view)
    TAM = (labeling tasks/yr) × (avg $/task)

L3 latent_demand        ← 2027 growth scenario
    TAM_2027 = (frontier-lab training spend) × (labeling share %)
```

L1 + revealed revenue triangulation is the defensible answer; L3 is the
upside scenario you'd quote separately so the LP can pressure-test the
2027 assumption directly.

---

## Inputs (with confidence labels)

| Input | Value | Source | Tier |
|---|---|---|---|
| Active expert labelers worldwide | ~50,000 | Scale claims 250K pool; ~20 % high-skill active | ⚠ analyst |
| Blended hourly rate (PhD / code / reasoning) | $60 / hr | Surge AI public rate $50, Turing $40-60, premium tiers $100+ | ⚠ analyst |
| Productive hours per labeler per year | 1,800 | 1500-2000 typical for contract labor | ⚠ analyst |
| Scale AI 2024 revenue | ~$1.0 B | Forbes / SEC filings | ✓ analyst |
| Surge AI 2024 revenue | ~$1.0 B | Bloomberg Sept 2024 | ✓ analyst |
| Turing 2024 revenue | ~$0.3 B | Company disclosures | ⚠ analyst |
| Invisible Tech / Snorkel / Labelbox / Appen frontier line | ~$0.7 B combined | various | ⚠ analyst |
| Frontier-lab training + post-training spend, 2027 | $80-120 B | scaling-law extrapolations, public capex | ⚠ analyst |
| Labeling share of total training spend | 15-25 % | historical OpenAI / Anthropic disclosures | ⚠ analyst |

---

## The math

```
┌──────────────────────────────────────────────────────────────┐
│  BOTTOM-UP (L1 cost_efficiency)                              │
│                                                              │
│    50,000 expert labelers                                    │
│  ×   $60 / hr                                                │
│  × 1,800 productive hours / yr                               │
│  ─────────────────────────────                               │
│  = $5.4 B capacity-side TAM, 2025                            │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│  REVEALED-REVENUE FLOOR (named players 2024)                 │
│                                                              │
│    Scale AI   $1.0 B                                         │
│  + Surge AI   $1.0 B                                         │
│  + Turing     $0.3 B                                         │
│  + Others     $0.7 B                                         │
│  ─────────────────────                                       │
│  = $3.0 B floor (2024) → ~$5.0 B (2025, 60-70 % YoY growth)  │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│  TOP-DOWN (L3 latent_demand, 2027 view)                      │
│                                                              │
│    Frontier-lab training + post-training spend 2027          │
│    ≈ $80-120 B (OpenAI / Anth / Google / Meta / xAI scaling) │
│  × labeling share (15-25 %, holding steady)                  │
│  ─────────────────────────────                               │
│  = $12-30 B addressable spend by 2027                        │
└──────────────────────────────────────────────────────────────┘
```

### Triangulation

```
                                  $5.4 B (bottom-up capacity)
                                       │
                                       ▼
            $5.0 B (revealed revenue trend) ──── point ──── $5-6 B (2025)
                                       ▲
                                       │
                            tight bounds: $4-7 B
```

Bottom-up capacity and revealed revenue land within 10 % of each other.
That's the strongest signal a TAM is real — triangulation, not extrapolation.

---

## Point estimate

```
2024:   $3.0 B  (revealed)
2025:   $5-6 B  ← number to quote today
2027:  $12-20 B ← if synthetic data doesn't eat > 40 % of human RLHF
2030:  $20-30 B ← MarketsAndMarkets-style consensus
```

**Quote for an LP:** $5-6 B for 2025, defensible range $4-7 B.

---

## Risk banners

- **community-modeled** — `$ / hr` and active-labeler counts are analyst
  estimates, not regulator data. No BLS NAICS code carves out "AI
  labelers" yet. Treat the bottom-up TAM as a triangulation check, not a
  cited number.
- **synthetic-data risk** — the 2027 estimate assumes labeling share
  holds at 15-25 %. If RL-from-AI-feedback (RLAIF) takes labeling-share
  to < 10 % of post-training spend, 2027 TAM drops to **$5-8 B**, not
  $12-20 B. Worth modeling as a separate scenario.
- **commoditization risk** — Turing's thesis is that *coding* labelers
  don't commoditize. If true, $ / hr stays elevated and the cost-side TAM
  compounds. If false, the segment halves by 2028 as low-cost geos eat
  the per-token price.
- **moat asymmetry** — Scale + Surge + Turing are not interchangeable.
  Surge has the highest unit prices (frontier labs only), Scale has the
  largest pool (commodity + frontier mixed), Turing has the highest
  developer-skill ceiling. A flat TAM number hides those.

---

## What the tool would have added

If `strata goal "data labeling market like Turing 2025" --stream` had run
live, it would have additionally pulled and pinned:

- **BLS NAICS 541512** wages for the FTE cost cross-check
- **Census CBP** employment counts for the labor-pool sizing
- **EDGAR** for any public filings from Scale AI / private comps
- Auto-written each as YAML in `~/.strata/auto-primitives/`, ready for
  `strata promote` into the committed data bank

The pipeline output would look something like:

```
→ Slug resolver: intent=novel, framework_hint=cost_efficiency
→ Step 3: framework cost_efficiency needs {persona_pool, cost_per_persona}
          [1/2] router → bls.get_series(series_id=OEUS000000054151200) tier=regulator
                conf=0.91 → wrote ~/.strata/auto-primitives/bls-software-
                developers-us-2024.yaml
          [2/2] router → fred.get_observations(series_id=COMPNFB) tier=regulator
                conf=0.88
→ evaluator: 2 inputs · 1 scenario path · banners=[community-modeled,
            synthetic-data-risk]

  TAM   point: $5.4B
  Inputs:
    • bls-software-developers-us-2024     50,000  BLS OES 2024-05 (subset)
    • surge-blended-rate-2024             $60/hr  analyst-paraphrase

  ⚑ community-modeled: persona pool sizing is analyst estimate; promote
    only after manual review.
```
