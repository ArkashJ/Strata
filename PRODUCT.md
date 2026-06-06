# Product

## Register

product

## Users

VCs and operators doing TAM and market-sizing work. They arrive with a market
in mind ("AI sales-ops agents, US, mid-market") and a deadline: a partner
meeting, an IC memo, a board deck. Their context is high-stakes and
time-boxed. They are numerate and skeptical, they have been burned by a
$50B-because-the-deck-said-so figure before, and the first thing they do with
any number is ask "where did that come from?"

The job to be done: get to a market size they can **defend in the room** in
minutes, with the sourcing and the method visible enough to survive scrutiny.
Not a research project. A decision input.

## Product Purpose

Strata is a community-curated market-sizing engine that replaces IBISWorld /
Statista / Gartner-lite reports by exposing the primitives (atomic sourced
numbers) and the frameworks (parameterized recipes that combine them into TAM),
plus an expert layer for correction.

It exists because market sizing today is either a black box (a number with no
visible derivation) or a slog (weeks of analyst spreadsheet work). Strata makes
the derivation the product: pick a market, pin its scope, watch competing
methods triangulate, and walk away with a hash-pinned, forwardable artifact
where every figure links to its source.

Success looks like an operator pasting a `/tam/<hash>` link into a memo and the
recipient being able to click any number down to a regulator filing, then
disagree with a specific assumption instead of the whole figure.

## Brand Personality

**Editorial, considered, quietly authoritative.** Three words: rigorous,
composed, candid.

The voice is that of a sharp analyst who respects your time: states the number,
shows the work, names the disagreement, and stops. The Instrument Serif display
type already sets this register, premium and intellectual, closer to a finance
publication than a SaaS dashboard. Calm confidence, never hype.

The defining tension to hold: the *feel* is editorial and unhurried, but the
*job* is fast. Considered design must never read as slow or precious. A
fund partner pulling a number 20 minutes before a meeting should feel the
restraint as clarity, not ceremony. Premium restraint that still gets out of
the way.

Emotional goal: the reader trusts the number because they can see why it is
trustworthy, not because the UI insists on it.

## Anti-references

- **Generic SaaS template.** Inter for everything, purple-to-blue gradients,
  cards nested in cards, the rounded icon tile above every heading, the
  hero-metric template. This is the 2026 AI-slop default and the fastest way to
  read as untrustworthy to a numerate audience. Strata's editorial type system
  exists precisely to escape this lane.
- **Legacy research reports (IBISWorld / Statista / Gartner).** Dense PDF walls,
  opaque "our analysts estimate" methodology, stock-photo corporate gloss, zero
  provenance you can click. Strata is the inversion of this: the methodology is
  the interface.
- **Academic / dry.** Wall-of-text, joyless, no hierarchy, rigor performed
  rather than delivered. The audience is operators on a clock, not reviewers of
  a thesis. Hierarchy and pace are not optional.

Not on the list but worth stating: not crypto/web3 either, no neon-on-black or
speculative hype. Strata is sourced and sober.

## Design Principles

1. **Provenance is the product.** The number and its source are one object, not
   a figure with a footnote somewhere else. If a figure cannot show its
   derivation, it should not assert itself like one that can.
2. **Disagreement gets a page, not a footnote.** When methods or sources
   conflict, surface the spread as a first-class view ("lower $X, higher $Y,
   N× apart, here's why"). Triangulation visible beats a false single number.
3. **Honest about limits.** Never fabricate a figure to fill a slot. "Unsizable",
   "dark estimate", "modeled input", and "world-aggregate needs a paid key" are
   shown plainly. Candor is a feature for this audience, not a weakness.
4. **Fast to a defensible answer.** Optimize the path from market query to a
   number the user can stand behind. Editorial restraint serves speed and
   clarity; it never adds ceremony between the operator and the figure.
5. **Restraint as authority.** Earn trust through composure: tight hierarchy,
   deliberate type, no decoration that does not carry meaning. The interface
   should feel like it knows the answer, not like it is selling one.

## Accessibility & Inclusion

Target **WCAG 2.2 AA**. Body text ≥4.5:1, large text ≥3:1, against the light
`#FAFAFA` paper, including the muted `--fg-3` metadata tier (verify, do not
assume). Full keyboard navigation and a visible focus ring on every
interactive element, including the ReactFlow pyramid graph nodes. `prefers-
reduced-motion` honored everywhere, this is load-bearing given the count-up
TAM headline, sensitivity tornado, and graph/scenario-tree animations: each
needs a crossfade or instant-state alternative. Do not encode meaning in color
alone (source-tier badges already pair hue with a label, keep that invariant).
