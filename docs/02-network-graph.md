# 02 — The Network Graph

The user-facing surface. Renders the **pyramid** sketch as an interactive,
modifiable graph where each node represents a constraint (a slice of the
market) and edges represent containment / inheritance.

## The pyramid

Three pillars converging at the top:

```
                       ┌──────────────────────┐
                       │   TAM for GTM market │       ← Root: the question
                       └──────────┬───────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        ▼                         ▼                         ▼
   ┌─────────┐               ┌─────────┐               ┌─────────┐
   │ B2C/B2B │               │  Ent.   │               │   ...   │   ← top tier
   └────┬────┘               │ sales/  │               └────┬────┘     (coarse)
        │                    │ defense │                    │
   ┌────┴────┐               └────┬────┘                    │
   │ GTM for │               ┌────┴────┐                ┌───┴───┐
   │engineers│               │Midmarket│                │       │   ← middle tier
   └────┬────┘               └────┬────┘                └───┬───┘
        │                         │                        │
   ┌────┴─────┐             ┌─────┴──────┐           ┌─────┴──────┐
   │ GTM for  │             │   SMB /    │           │  industry  │   ← base tier
   │ bio tools│             │  consumer  │           │   slices   │     (granular)
   └──────────┘             └────────────┘           └────────────┘
     Qualitative              Quantitative              Industry
```

## Pillars

| Pillar | What it slices by | Examples |
|---|---|---|
| **Qualitative** | Buyer / user persona, motion, product shape | "GTM for engineers", "GTM for bio tools", "B2C vs B2B" |
| **Quantitative** | Customer size band, contract size, geo | "Enterprise", "Midmarket", "SMB", "Consumer" |
| **Industry** | Vertical / NAICS-style | "P&C Insurance", "Logistics", "Healthcare payers" |

A TAM is almost always a **conjunction** of constraints across pillars —
e.g. "GTM tooling × Midmarket × P&C Insurance". The graph makes that
selection geometric: click one node per pillar (or none, to stay broad).

## Node anatomy

Each node carries:

- **label** — short human name ("Midmarket")
- **constraint** — the filter it applies (`company_size in [100, 1000]`)
- **pillar** — Qualitative / Quantitative / Industry
- **tier** — 0 (root) → 3 (most granular)
- **child_count** — how many sub-segments exist below
- **primitive_links** — primitives that quantify this node ("# of US midmarket companies")
- **framework_compat** — which frameworks apply at this node

## Interactions

| Action | Effect |
|---|---|
| **Click node** | Add as active constraint; gray out incompatible nodes in other pillars |
| **Shift-click** | OR into existing constraint at same level (e.g. "Midmarket OR Enterprise") |
| **Click again** | Remove constraint |
| **Hover** | Show primitive count + sample sources in side panel |
| **Drag node** | Re-layout (cosmetic only; doesn't change semantics) |
| **Right-click → Expand** | Reveal next tier of children |
| **Right-click → Annotate** | Add an expert comment to this node |
| **Right-click → Suggest framework** | Open framework picker pre-filtered for this constraint set |

## Modifiability

The graph is **community-editable**, with guardrails:

- New nodes (segments) can be proposed by any contributor; promoted from
  `proposed` → `active` after either (a) a verified-expert vouch or (b) N
  primitive links exist that quantify it.
- Edges (parent-child containment) can be re-suggested; ambiguous taxonomies
  (e.g. "biotech tooling" — is that Qualitative or Industry?) get two nodes
  with a cross-link rather than a single forced choice.
- Renames and moves are versioned; the constraint slug is the stable
  identifier (`midmarket-100-to-1000-employees`), not the label.

## Layout

Force-directed with **pillar lanes**: x-position is constrained by pillar
(left=Qualitative, center=Quantitative, right=Industry), y-position is
constrained by tier (root=top, base=bottom). Within those constraints,
forces push siblings apart and pull parents to their children's center of
mass.

This keeps the pyramid recognisable while letting the user pan/zoom.

## Rendering target

For v0.1 of the implementation, render with `vis-network` or `cytoscape.js` —
both handle 100–500 node graphs at 60fps and support pinning, custom layouts,
and event handlers. Decision deferred to implementation phase; not load-bearing
on the spec.

## What this is NOT

- **Not an org chart.** Edges are containment / inheritance of constraints,
  not reporting lines or causal links.
- **Not a knowledge graph in the RDF sense.** No formal ontology; the schema
  is intentionally small and pragmatic.
- **Not infinitely deep.** Tier 3 is the floor for v1.0 — deeper than that and
  the per-node primitive count drops to zero and the graph becomes noise.
