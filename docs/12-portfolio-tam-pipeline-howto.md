# Portfolio TAM Pipeline — How to Run Any Portfolio Through Strata's DAG

This guide describes the reusable pattern for sizing a portfolio of companies
(VC fund, accelerator cohort, strategy-desk universe — any list of named
companies) using Strata's primitive/framework/evaluator DAG and a Claude-
driven classifier.

The pattern was developed for the Benmore TAM-77 deliverable (PR #44, 24
portfolio companies) and is implemented at `backend/scripts/tam_77_pipeline.py`.
It is intentionally portfolio-agnostic: feed it a different YAML catalog and
get a different set of TAMs.

## End-to-end flow

```
┌────────────────────┐      ┌────────────────────┐
│ Portfolio YAML     │      │ Strata data/ bank  │
│ (24 companies +    │      │ (concepts +        │
│  short descriptions│      │  frameworks +      │
│  + spec_notes)     │      │  primitives +      │
└──────────┬─────────┘      │  sources)          │
           │                └──────────┬─────────┘
           ▼                           │
┌──────────────────────────────────────┴─────────┐
│  scripts/tam_77_pipeline.py                    │
│  --portfolio data/portfolios/<name>.yaml        │
│                                                │
│  for each company:                             │
│    1. Claude classifies onto 1 of 5 frameworks │
│       and emits 2 input primitives with        │
│       geo / unit / source tier metadata.       │
│    2. Optional: enrich any primitive flagged   │
│       with a connector_hint against the live   │
│       BLS / Census / FRED / openFDA / WB API.  │
│       SHA256 of the response body becomes the  │
│       primitive's snapshot_sha256.             │
│    3. Render concept YAML, 2 primitive YAMLs,  │
│       and append a variant to the chosen       │
│       framework YAML.                          │
│    4. Reload registry; size_concept(slug);     │
│       persist TAMOutput state hash + scenario. │
└──────────┬─────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────┐
│ backend/tam_77_results_v2.json                       │
│ docs/tam-77-corrected.md                             │
│ data/concepts/<slug>.yaml         × N companies      │
│ data/primitives/<slug>.yaml       × ~2N primitives   │
│ data/frameworks/<framework>.yaml  (in-place variants)│
└──────────────────────────────────────────────────────┘
```

## What stays the same across portfolios

- The 5 framework slugs in `data/frameworks/` (you pick from these).
- The Pydantic record schemas (concept, atomic primitive, framework variant).
- The evaluator entrypoint `size_concept(registry, concept_slug)` and the
  scenario-tree output shape (Q1).
- Source tier handling: `regulator`, `aggregator`, `analyst`,
  `analyst-paraphrase`, `community-modeled`.

## What changes per portfolio

- The YAML catalog at `data/portfolios/<your-portfolio>.yaml`.
- The concepts + primitives + framework variants emitted into `data/`.
- The TAMs in the output bundle.

## Sizing a new portfolio in 5 steps

1. **Author the portfolio YAML**

   ```yaml
   # data/portfolios/<your-fund>.yaml
   portfolio_name: "Acme Capital — Vintage 2027"
   companies:
     - name: "ExampleCo"
       slug: "exampleco-thing-it-sells"
       sector: "What sector it's in"
       short_desc: "1-3 sentence description of what the company does and who it sells to."
       spec_notes: "Any methodology constraints — geographic regime, regulatory regime, sizing caveats."
   ```

   Every field except `name` and `slug` is optional but improves classification.
   `slug` must be kebab-case-lowercase and unique within the data bank.

2. **(Optional) Set up methodology constraints**

   If your portfolio has special methodology rules (e.g. some companies are
   infra layers, some are multi-jurisdiction-regulated), encode them in
   `spec_notes` per company. Claude reads them.

3. **Run the pipeline**

   ```sh
   cd backend/
   export ANTHROPIC_API_KEY=...
   export STRATA_BLS_API_KEY=...     # optional but improves enrichment
   export STRATA_FRED_API_KEY=...    # optional
   export STRATA_CENSUS_API_KEY=...  # optional
   uv run python scripts/tam_77_pipeline.py \
       --portfolio ../data/portfolios/your-fund.yaml \
       --include-handcrafted
   ```

   Each company costs ~$0.50 in Claude Opus API spend and 30-40s wall time.
   The pipeline writes YAML idempotently — rerunning skips already-classified
   companies' framework variants.

4. **Validate + persist**

   ```sh
   uv run strata validate ../data        # 0 errors, only v0.2 simplification warnings
   uv run strata stats -d ../data        # see new primitives / concepts / variants
   uv run strata db seed --data-dir ../data   # push to Postgres (Railway prod or local)
   ```

5. **Audit per-company TAMs**

   ```sh
   uv run strata size exampleco-thing-it-sells -d ../data
   ```

   Returns a `TAMOutput` with permanent `/tam/<state-hash>` URL, the chosen
   framework's scenario, each primitive's sha256-pinned snapshot, and any
   analyst-paraphrase banners that travel with the TAM.

## The 5 frameworks Claude picks from

| Slug | Lens | Inputs | When |
|------|------|--------|------|
| `bottoms-up-cost-efficiency` | cost_efficiency | persona_pool × cost_per_persona | persona-replacement (Harvey / Glean) |
| `top-down-revenue-capture` | revenue_generation | target_segment_count × spend_per_target | enterprise spend capture (Brex / Rippling) |
| `productivity-uplift-value-split` | productivity_uplift | persona_count × value_split_to_vendor | per-seat productivity (Copilot / Cursor) |
| `consolidation-sum-then-discount` | bundle_consolidation | tools_displaced × consolidation_rate | replacing incumbent spend (M365 / share-shift) |
| `throughput-take-rate` | platform_throughput | gmv_or_volume × take_rate | infra / platform basis-point yield (Stripe / voice infra) |

To add a 6th framework (e.g. `latent-demand-capacity` for physical-capacity
plays the way Yotta could have been modeled), write a new YAML in
`data/frameworks/` declaring the lens, input unit signatures, formula, and
applicable concepts. The evaluator picks it up on next registry reload.

## How addressability / capture multipliers are handled

Frameworks have no scalar defaults (Q15). Addressability % and capture % are
embedded **inside primitive values**, not as separate framework multipliers.
This keeps the framework formula pure and makes every multiplier auditable as
its own primitive record.

Example (Endeavor — mfg back-office):
- `global-mfg-distribution-ai-addressable-backoffice-personas-2024` carries
  a `value` of 2.5M (= 10M total × 25% addressability). The description and
  source paraphrase document the 25% addressability decision.
- `global-mfg-backoffice-vendor-capture-per-persona-2024` carries a `value`
  of $30K (= $55K fully-loaded × 55% capture). The capture % is documented
  in the description.

To revise the addressability or capture assumption, edit the primitive YAML
and rerun `strata size <slug>`. The state hash changes; the audit trail
remains intact.

## Why "ephemeral /resolve" is not the right shape for this

Strata's `POST /resolve` endpoint also calls Claude + Exa and runs the
evaluator, but its output is ephemeral — it streams back to the caller and
nothing lands in `data/`. That works for ad-hoc analyst questions, not for
sizing a curated portfolio where every TAM needs a permanent state hash, a
URL, and a place in the data bank that other analyses can reference.

The pipeline script is the persistent counterpart: same Claude classifier,
same evaluator, but every artifact lands as YAML + (optional) Postgres.

## Acceptance criteria for any new portfolio

These are baked into `backend/tests/test_tam_v2_acceptance.py` and apply to
any portfolio run:

1. Every concept resolves through the evaluator DAG (no orphans).
2. Every concept's chosen framework lens matches the concept's declared lens.
3. Concepts tagged `us_only_regulated` carry geo codes restricted to US on
   their bound primitives (zero international TAM by construction).
4. No concept uses the `latent_demand` lens (no v0.2 framework supports it
   yet — add a framework or change the lens).
5. Validator passes with only the documented v0.2 simplification warnings.

## See also

- `docs/superpowers/specs/2026-05-26-tam-77-corrected-methodology.md` —
  the design spec that drove this pipeline (12 methodology errors and the
  corrected approach).
- `docs/tam-77-corrected.md` — generated output for the Benmore 24-company
  portfolio.
- `data/portfolios/benmore-tam-77.yaml` — the catalog the pipeline consumed.
