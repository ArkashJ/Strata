# 05 — Roadmap

Phased plan from docs-only (v0.1) to a usable v1.0. Versions are SemVer.
**Pre-1.0**, minor bumps are allowed to ship breaking spec/schema changes.

## v0.1.0 — Thesis & spec (this release)

- [x] Apache-2.0 license
- [x] README, CLAUDE.md, CHANGELOG, VERSION
- [x] `docs/00-vision.md` — thesis
- [x] `docs/01-primer.md` — three layers, five-layer data model, pyramid graph (consolidated from original 01/02/03 sketches in v0.2)
- [x] `docs/04-user-journey.md` — P&C doc-gen walkthrough
- [x] `docs/05-roadmap.md` — this file
- [x] `docs/06-glossary.md`
- [x] `docs/07-data-layer-brainstorm.md` — Q1–Q38 schema decisions (added in v0.2)
- [x] `docs/08-product-surface-brainstorm.md` — U1–U12 UX decisions (added in v0.2)
- [x] `docs/09-expert-layer-brainstorm.md` — E1–E5 annotation schema (added in v0.2)
- [x] `docs/10-v0.2-backend-spec.md` — implementation blueprint (added in v0.2)

**Exit criteria:** A reader who has never seen this project understands the
thesis, the three layers, the data model, and the user journey in < 20 min.

---

## v0.2.0 — Seed library & schema lock

- [x] Lock the YAML schemas — see
      [`07-data-layer-brainstorm.md`](07-data-layer-brainstorm.md) §"Final design"
      (atomic_primitive, composite_primitive, framework, concept,
      marketplace_concept, company_concept, tam_output) +
      [`09-expert-layer-brainstorm.md`](09-expert-layer-brainstorm.md) (annotation).
- [x] **Lens taxonomy locked** (Q39): six first-class lenses + four modifiers
      on Concept; `analyst-paraphrase` source tier added (Q40). See
      [`plans/data-collection-strategy.md`](plans/data-collection-strategy.md).
- [x] Pydantic v2 models in `backend/src/strata/models/` for each record type,
      including the lens enum + modifiers + `required_primitive_roles` map.
      <!-- DONE 2026-05-24: all 6 record types + Unit, Geo, Source DU, Annotation. InputUsed enriched with value/name/unit. -->
- [x] **Five of six canonical frameworks** (L3 latent_demand deferred — needs analog field):
  - `bottoms_up_cost_efficiency` (L1)
  - `top_down_revenue_capture` (L2)
  - ~~`adoption_curve_latent_demand` (L3)~~ — deferred, needs analog field + concept with latent_demand lens
  - `throughput_take_rate` (L4)
  - `consolidation_sum_then_discount` (L5)
  - `productivity_uplift_value_split` (L6)
- [x] **Six seed concepts**, one per lens, exercising every source tier:
      `doc-gen-pc-insurance` (L1+L2), `gtm-ops-tooling-na` (L1),
      `midmarket-saas-spend-na` (L2), `payments-throughput-pc-insurance` (L4),
      `workplace-suite-consolidation` (L5), `software-eng-productivity` (L6).
      <!-- DONE 2026-05-24: 14 primitives, 15 sources, all validate clean. BLS headcounts Exa-verified. -->
- [ ] Ingest substrate per [`plans/execute.md`](plans/execute.md): BLS / FRED /
      EDGAR / NAIC direct-API connectors + snapshot store + validator pipeline.
      <!-- PARTIAL: Exa deep-search connector built (scripts/exa_source_lookup.py + /resolve endpoint). Direct API connectors (FRED, BLS, EDGAR) not yet built. See docs/11-api-catalog.md for full API list. -->
- [x] Build a minimal CLI: `strata validate data/` (lints YAML against schemas).
      <!-- DONE: strata version, strata validate, strata size all wired. -->
- [ ] CONTRIBUTING.md for primitives + frameworks + annotations.
- [ ] Takedown endpoint for the `analyst-paraphrase` tier (Q40 requirement).

**Exit criteria:** Three reviewers can independently submit a primitive in
YAML, have it lint-pass, and have it referenced by an existing framework.

---

## v0.3.0 — Static graph renderer

- [ ] Pick the render stack (`vis-network` vs `cytoscape.js`). Decision doc
      in `docs/`.
- [ ] Build a read-only web UI that:
  - loads `data/` at build time
  - renders the pyramid for one root question ("TAM for GTM market")
  - lets the user click nodes to narrow constraints
  - shows the compatible frameworks in a side panel
- [ ] No backend yet — pure static site (Vite or Next.js static export).

**Exit criteria:** Sarah's user journey from `04-user-journey.md` works
end-to-end, manually, for the doc-gen-in-P&C build.

---

## v0.4.0 — Calculator & export

- [ ] Implement the formula evaluator for frameworks (parse `formula:`,
      pull primitives, expose assumption sliders).
- [ ] Range sweep visualization (tornado / sensitivity chart per assumption).
- [ ] Export build to Markdown + PDF + permalink JSON.
- [ ] Annotation rendering inline on primitives and frameworks (read-only).

**Exit criteria:** A user can pick a framework, see the range, export the
build, and reopen it from a permalink.

---

## v0.5.0 — Contribution flow

- [ ] Backend: minimal API + Postgres for primitives, frameworks, annotations.
- [ ] Auth + contributor profiles (start with GitHub OAuth).
- [ ] Submit-a-primitive form with schema validation in browser.
- [ ] Annotation posting with credential tiering.
- [ ] Moderation queue for `proposed → active`.

**Exit criteria:** A new contributor can sign up and submit a primitive
without touching YAML.

---

## v1.0.0 — Public beta

- [ ] 250+ primitives, 25+ frameworks across 5+ verticals.
- [ ] Search across the pyramid by natural-language query.
- [ ] LLM-assisted primitive ingestion (paste a regulator PDF, get a draft
      primitive YAML to review).
- [ ] Hosted at a public domain. Documented contribution + governance model.

**Exit criteria:** Three external operators / investors publicly cite a
Strata build in something they shipped (memo, deck, blog post).

---

## Non-goals (explicitly out of scope, possibly forever)

- **Forecasting / projections.** We size what is, not what will be.
- **Private / paywalled data sources.** Primitives must be reproducible by
  anyone with internet access.
- **Custom segment definitions per user.** The taxonomy is shared and
  contested; per-user forks defeat the network effect.
- **General-purpose research tool.** This is market sizing. Sector trends,
  competitive landscapes, and deal screening are different products.

## Versioning rules

- Tags: `vX.Y.Z`, annotated (`git tag -a`).
- `VERSION` file and the `[X.Y.Z]` section of `CHANGELOG.md` move together
  with the tag, in the same commit.
- Schema changes between v0.x bump MINOR. Once v1.0 ships, schema breaking
  changes bump MAJOR.
