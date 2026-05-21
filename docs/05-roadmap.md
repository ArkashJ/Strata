# 05 — Roadmap

Phased plan from docs-only (v0.1) to a usable v1.0. Versions are SemVer.
**Pre-1.0**, minor bumps are allowed to ship breaking spec/schema changes.

## v0.1.0 — Thesis & spec (this release)

- [x] Apache-2.0 license
- [x] README, CLAUDE.md, CHANGELOG, VERSION
- [x] `docs/00-vision.md` — thesis
- [x] `docs/01-product-layers.md` — three layers
- [x] `docs/02-network-graph.md` — pyramid UI spec
- [x] `docs/03-data-model.md` — entity schemas (draft)
- [x] `docs/04-user-journey.md` — P&C doc-gen walkthrough
- [x] `docs/05-roadmap.md` — this file
- [x] `docs/06-glossary.md`

**Exit criteria:** A reader who has never seen this project understands the
thesis, the three layers, the data model, and the user journey in < 20 min.

---

## v0.2.0 — Seed library & schema lock

- [ ] Lock the YAML schemas in `03-data-model.md` (resolve the 5 open
      questions at the bottom).
- [ ] Add `schemas/` directory with JSON Schema / Pydantic models for each
      entity (Source, Primitive, Framework, Annotation, GraphNode).
- [ ] Hand-seed ~50 primitives covering the GTM, P&C insurance, and SMB-SaaS
      slices used in `04-user-journey.md`.
- [ ] Write the first 10 frameworks from the seed list in `01-product-layers.md`.
- [ ] Build a minimal CLI: `strata validate data/` (lints YAML against schemas).
- [ ] CONTRIBUTING.md for primitives + frameworks + annotations.

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
