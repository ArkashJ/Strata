# CLAUDE.md

Notes for AI assistants (and future-me) working in this repo.

## What this project is

Codename **Strata**. Open-source, community-curated market-sizing tool. Three layers:

1. **Primitives Library** — sourced atomic numbers.
2. **Framework Library** — parameterized recipes that turn primitives into a TAM.
3. **Expert Layer** — annotations and alternative framings.

The interaction surface is a **clickable pyramid network graph** with three axes:
Qualitative, Quantitative, Industry. Clicking a node narrows the segment and
re-suggests frameworks.

Full thesis: [`docs/00-vision.md`](docs/00-vision.md).

## Repo state (as of v0.1.0)

- **Docs-only.** No source code, no build system, no tests yet.
- License: Apache-2.0.
- Version pinned in `VERSION`; tags follow `vX.Y.Z` (SemVer).
- `CHANGELOG.md` is in Keep-a-Changelog format. Update **every** notable change
  under `[Unreleased]`; cut a versioned section + git tag when releasing.

## Conventions

### Versioning
- SemVer: `MAJOR.MINOR.PATCH`.
- Pre-1.0: minor bumps for any spec/schema change; patch for docs-only fixes.
- Tag with `git tag -a vX.Y.Z -m "..."` and update both `VERSION` and `CHANGELOG.md`
  in the same commit as the tag.

### Docs
- All design docs live under `docs/`, numbered (`NN-title.md`) so they sort in
  reading order.
- Use plain Markdown. ASCII diagrams over Mermaid where the diagram is small —
  ASCII renders everywhere without a toolchain.
- Cross-link liberally between docs with relative paths.

### Naming
- Project codename: **Strata** (provisional — the user may rename; do not invent a
  different name).
- Domain terms: see [`docs/06-glossary.md`](docs/06-glossary.md). When introducing
  a new term, add it to the glossary in the same change.

### Data (when it lands)
- Primitives will live as JSON / YAML files under `data/primitives/`, one file per
  primitive, keyed by stable slug.
- Frameworks under `data/frameworks/`, similarly slugged.
- Source credibility tiers are an enum: `first_party`, `regulator`, `aggregator`,
  `analyst`, `community`. See [`docs/03-data-model.md`](docs/03-data-model.md).

## What NOT to do

- **Don't invent figures.** Every number in docs that purports to be real must have a
  source. Illustrative examples should be clearly labelled "illustrative" or use
  obviously fake values (e.g. `$X` / `N`).
- **Don't pick a stack yet.** v0.1.0 is intentionally pre-implementation; resist
  scaffolding a frontend, backend, or schema validator until the data model in
  `docs/03-data-model.md` is reviewed by the user.
- **Don't rename the project** without an explicit request — `Strata` is provisional
  but the user may keep it.
- **Don't add CI, package manifests, or build tooling** until there's code to build.

## When you start a new session

1. Read `README.md`, this file, and `docs/05-roadmap.md` to orient.
2. Check `git log --oneline -10` and the `[Unreleased]` section of `CHANGELOG.md`
   for in-flight work.
3. Tags are the source of truth for released versions: `git tag --sort=-v:refname`.

## User context

- User is **Arkash Jain** (`arkash@benmore.tech`).
- Working from `/Users/arkashjain/Desktop/work/VC_stuff`.
- Audience for this product is **VCs and operators doing TAM work** — write docs
  with that reader in mind (they want defensible numbers fast, not academic rigor).
