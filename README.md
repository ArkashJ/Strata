# Strata

> **Provisional codename.** A community-curated, open-source library of market-sizing
> primitives, frameworks, and expert annotations — rendered as an interactive pyramid
> graph that lets VCs and operators build credible TAMs without buying a $20k report.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
![Version](https://img.shields.io/badge/version-0.1.0-informational)
![Status](https://img.shields.io/badge/status-pre--alpha-orange)

---

## The one-line thesis

Market sizing today is gated by expensive low-quality reports, when in reality the
underlying exercise is just **credible primitives + a transparent framework**. Make
both free, sourced, and community-curated, and you eat the bottom 80% of the
IBISWorld / Statista / Gartner-lite use case.

## What this is

A tool for VCs (and operators) to **cut through the noise**:

1. Pick a segment in a clickable **pyramid graph** — Qualitative ↓ Quantitative ↓ Industry.
2. The graph surfaces **frameworks** that fit the segment.
3. Each framework is pre-populated with **primitives** from the library.
4. Adjust assumptions, see the range, export the build with a full source trail.
5. Optionally read **expert annotations** that flag blind spots.

See [`docs/00-vision.md`](docs/00-vision.md) for the full thesis.

## The three product layers

| Layer | Name | What's in it |
|------:|------|--------------|
| 1 | **Primitives Library** | Atomic, sourced figures (e.g. "# of GTM professionals in N. America", "avg IT spend per SMB"). Each has a value, date, methodology, and credibility-tiered source. |
| 2 | **Framework Library** | Reusable, parameterized recipes for going primitives → TAM. Organized by function (Finance, GTM, Ops...) and approach (top-down, bottoms-up, comparable, analog). |
| 3 | **Expert Layer** | Comments, annotations, and alternative framings on top of figures and frameworks. Reputation-weighted. |

Full breakdown: [`docs/01-product-layers.md`](docs/01-product-layers.md).

## The pyramid graph

The Qualitative / Quantitative / Industry pyramid in the sketch:

```
                       ┌──────────────────────┐
                       │   TAM for GTM market │
                       └──────────┬───────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        ▼                         ▼                         ▼
   ┌─────────┐               ┌─────────┐               ┌─────────┐
   │ B2C/B2B │               │  Ent.   │               │   ...   │   ← top tier
   └────┬────┘               │ sales/  │               └────┬────┘
        │                    │ defense │                    │
   ┌────┴────┐               └────┬────┘                    │
   │ GTM for │               ┌────┴────┐                ┌───┴───┐
   │ engineers│              │Midmarket│                │       │  ← middle tier
   └────┬────┘               └────┬────┘                └───┬───┘
        │                         │                        │
   ┌────┴─────┐             ┌─────┴──────┐           ┌─────┴──────┐
   │ GTM for  │             │   SMB /    │           │  industry  │  ← base tier
   │ bio tools│             │  consumer  │           │   slices   │
   └──────────┘             └────────────┘           └────────────┘
     Qualitative              Quantitative              Industry
```

Each node is a **constraint** — clicking expands children, narrows the segment, and
re-suggests frameworks. Spec: [`docs/02-network-graph.md`](docs/02-network-graph.md).

## Repository layout

```
.
├── LICENSE              Apache 2.0
├── VERSION              0.1.0
├── CHANGELOG.md         Keep a Changelog format
├── CLAUDE.md            Notes for AI assistants working on this repo
├── README.md            You are here
└── docs/
    ├── 00-vision.md
    ├── 01-product-layers.md
    ├── 02-network-graph.md
    ├── 03-data-model.md
    ├── 04-user-journey.md
    ├── 05-roadmap.md
    └── 06-glossary.md
```

## Status

**Pre-alpha — docs only.** No code yet. v0.1.0 is a thesis + spec snapshot to
anchor design before implementation begins. See [`docs/05-roadmap.md`](docs/05-roadmap.md)
for phasing.

## License

Apache License 2.0 — see [`LICENSE`](LICENSE). Choice of license is deliberate:
patent-grant + permissive, so research orgs, funds, and vendors can adopt the
schema and seed the library without fear of relicensing traps.

## Contributing

Not yet open for external contributions — schema is still landing. Once v0.2.0
ships the primitive schema, contribution guidelines will follow.
