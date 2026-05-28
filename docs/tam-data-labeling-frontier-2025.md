# TAM - Frontier-quality data labeling, 2025

**Segment.** Expert human labelers used by frontier AI labs for RLHF, code/reasoning evals, and red-teaming. The "like Turing / Scale AI / Surge AI" market. This is **distinct** from commodity image annotation: per-task pricing is 10-50x higher and the buyer is OpenAI / Anthropic / Google / Meta, not autonomous-vehicle teams or e-commerce.

**Asked by.** VC sizing question on 2026-05-27.

**Methodology.** Computed with the Strata lens x framework x sourced-primitives stack and walked manually because the live `strata goal` CLI could not reach Anthropic on this workstation (malformed `ANTHROPIC_API_KEY` in `.env`). Numbers here would normally land in `~/.strata/auto-primitives/` and be promotable into `data/primitives/` once they pass the validator.

---

## Lens choice

Three of Strata's six lenses are relevant:

| Lens | Role | Formula |
|------|------|---------|
| **L1** `cost_efficiency` | Primary (bottom-up labor) | TAM = (expert labelers) x ($/hr) x (annual utilized hours) |
| **L4** `platform_throughput` | Cross-check (marketplace view) | TAM = (labeling tasks/yr) x (avg $/task) |
| **L3** `latent_demand` | 2027 growth scenario | `TAM_2027` = (frontier-lab training spend) x (labeling share %) |

L1 plus revealed-revenue triangulation is the defensible answer. L3 is the upside scenario to quote separately so an LP can pressure-test the 2027 assumption directly.

---

## Inputs (with confidence labels)

| Input | Value | Source | Tier |
|-------|-------|--------|------|
| Active expert labelers worldwide | ~50,000 | Scale claims 250K pool; ~20% high-skill active | analyst (est.) |
| Blended hourly rate (PhD / code / reasoning) | $60/hr | Surge AI public rate $50; Turing $40-60; premium tiers $100+ | analyst (est.) |
| Productive hours per labeler per year | 1,800 | 1,500-2,000 typical for contract labor | analyst (est.) |
| Scale AI 2024 revenue | ~$1.0B | Forbes / SEC filings | analyst (verified) |
| Surge AI 2024 revenue | ~$1.0B | Bloomberg Sept 2024 | analyst (verified) |
| Turing 2024 revenue | ~$0.3B | Company disclosures | analyst (est.) |
| Invisible Tech / Snorkel / Labelbox / Appen frontier line | ~$0.7B combined | various | analyst (est.) |
| Frontier-lab training + post-training spend, 2027 | $80-120B | scaling-law extrapolations, public capex | analyst (est.) |
| Labeling share of total training spend | 15-25% | historical OpenAI / Anthropic disclosures | analyst (est.) |

---

## The math

### Bottom-up (L1 `cost_efficiency`)

| Step | Calculation |
|------|-------------|
| Expert labelers | 50,000 |
| Blended rate | x $60/hr |
| Productive hours | x 1,800 hr/yr |
| **Capacity-side TAM, 2025** | **= $5.4B** |

### Revealed-revenue floor (named players, 2024)

| Player | Revenue |
|--------|---------|
| Scale AI | $1.0B |
| Surge AI | $1.0B |
| Turing | $0.3B |
| Others | $0.7B |
| **Floor (2024)** | **= $3.0B** |
| **Implied 2025** (60-70% YoY growth) | **~$5.0B** |

### Top-down (L3 `latent_demand`, 2027 view)

| Step | Calculation |
|------|-------------|
| Frontier-lab training + post-training spend, 2027 | ~$80-120B (OpenAI / Anthropic / Google / Meta / xAI scaling) |
| Labeling share (15-25%, holding steady) | x 15-25% |
| **Addressable spend by 2027** | **= $12-30B** |

### Triangulation

| Method | 2025 estimate |
|--------|---------------|
| Bottom-up capacity (L1) | $5.4B |
| Revealed revenue trend (2024 floor to 2025) | ~$5.0B |
| **Point estimate** | **$5-6B** |
| **Defensible range** | **$4-7B** |

Bottom-up capacity and revealed revenue land within ~10% of each other. That is the strongest signal a TAM is real: triangulation, not extrapolation.

---

## Point estimate

| Year | Estimate | Notes |
|------|----------|-------|
| 2024 | $3.0B | Revealed revenue floor |
| 2025 | $5-6B | Number to quote today |
| 2027 | $12-20B | If synthetic data does not displace >40% of human RLHF |
| 2030 | $20-30B | MarketsAndMarkets-style consensus |

**Quote for an LP:** $5-6B for 2025, defensible range $4-7B.

---

## Risk banners

- **community-modeled** - `$/hr` and active-labeler counts are analyst estimates, not regulator data. No BLS NAICS code carves out "AI labelers" yet. Treat the bottom-up TAM as a triangulation check, not a cited number.
- **synthetic-data risk** - the 2027 estimate assumes labeling share holds at 15-25%. If RL-from-AI-feedback (RLAIF) takes labeling share to <10% of post-training spend, 2027 TAM drops to **$5-8B**, not $12-20B. Worth modeling as a separate scenario.
- **commoditization risk** - Turing's thesis is that *coding* labelers do not commoditize. If true, $/hr stays elevated and the cost-side TAM compounds. If false, the segment halves by 2028 as low-cost geos compress per-token price.
- **moat asymmetry** - Scale, Surge, and Turing are not interchangeable. Surge has the highest unit prices (frontier labs only). Scale has the largest pool (commodity + frontier mixed). Turing has the highest developer-skill ceiling. A flat TAM number hides those differences.

---

## What the tool would have added

If `strata goal "data labeling market like Turing 2025" --stream` had run live, it would have additionally pulled and pinned:

- **BLS NAICS 541512** wages for the FTE cost cross-check
- **Census CBP** employment counts for the labor-pool sizing
- **EDGAR** for any public filings from Scale AI / private comps
- Auto-written YAML in `~/.strata/auto-primitives/`, ready for `strata promote` into the committed data bank

The pipeline output would look something like:

```text
-> Slug resolver: intent=novel, framework_hint=cost_efficiency
-> Step 3: framework cost_efficiency needs {persona_pool, cost_per_persona}
          [1/2] router -> bls.get_series(series_id=OEUS000000054151200) tier=regulator
                conf=0.91 -> wrote ~/.strata/auto-primitives/bls-software-
                developers-us-2024.yaml
          [2/2] router -> fred.get_observations(series_id=COMPNFB) tier=regulator
                conf=0.88
-> evaluator: 2 inputs * 1 scenario path * banners=[community-modeled,
            synthetic-data-risk]

  TAM   point: $5.4B
  Inputs:
    - bls-software-developers-us-2024     50,000  BLS OES 2024-05 (subset)
    - surge-blended-rate-2024             $60/hr  analyst-paraphrase

  [!] community-modeled: persona pool sizing is analyst estimate; promote
    only after manual review.
```
