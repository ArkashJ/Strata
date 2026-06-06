---
name: Strata
description: Community-curated market-sizing engine where the methodology is the interface.
colors:
  accent: "#5b5bd6"
  accent-hover: "#6e6ee0"
  accent-active: "#4848c4"
  accent-fg-on: "#ffffff"
  bg-0: "#fafafa"
  bg-1: "#ffffff"
  bg-2: "#f4f4f5"
  bg-3: "#e9e9ec"
  fg-1: "#0a0a0b"
  fg-2: "#52525b"
  fg-3: "#7e7e86"
  fg-4: "#b4b4ba"
  border-1: "#e8e8ec"
  border-2: "#d4d4d8"
  border-3: "#a1a1aa"
  success: "#4ade80"
  warning: "#c99846"
  danger: "#e5484d"
  info: "#3b7bd9"
  tier-regulator: "#3fa66b"
  tier-aggregator: "#2ba39a"
  tier-analyst: "#c99846"
  tier-community: "#7a7a82"
  tier-onchain: "#8b5cd6"
  tier-prediction: "#d97849"
  night-bg: "#080b16"
  night-accent: "#8b8bf5"
typography:
  display:
    fontFamily: "Instrument Serif, Tiempos Headline, Georgia, serif"
    fontSize: "48px"
    fontWeight: 400
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "32px"
    fontWeight: 500
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "24px"
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "-0.01em"
  label:
    fontFamily: "Geist, Inter, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 500
    lineHeight: 1
    letterSpacing: "0.04em"
  mono-num:
    fontFamily: "Geist Mono, JetBrains Mono, ui-monospace, monospace"
    fontSize: "32px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "-0.005em"
    fontFeature: "tnum 1, lnum 1"
rounded:
  r-1: "4px"
  r-2: "6px"
  r-3: "8px"
  r-4: "12px"
  round: "999px"
spacing:
  s-1: "4px"
  s-2: "8px"
  s-3: "12px"
  s-4: "16px"
  s-6: "24px"
  s-8: "32px"
  s-12: "48px"
  s-16: "64px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.accent-fg-on}"
    rounded: "{rounded.r-3}"
    padding: "0 16px"
    height: "36px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
    textColor: "{colors.accent-fg-on}"
    rounded: "{rounded.r-3}"
  button-primary-active:
    backgroundColor: "{colors.accent-active}"
    textColor: "{colors.accent-fg-on}"
    rounded: "{rounded.r-3}"
  button-ghost:
    backgroundColor: "{colors.bg-1}"
    textColor: "{colors.fg-1}"
    rounded: "{rounded.r-3}"
    padding: "0 16px"
    height: "36px"
  input-field:
    backgroundColor: "{colors.bg-1}"
    textColor: "{colors.fg-1}"
    rounded: "{rounded.r-2}"
    padding: "0 12px"
    height: "36px"
  chip-filter:
    backgroundColor: "{colors.bg-2}"
    textColor: "{colors.fg-2}"
    rounded: "{rounded.round}"
    padding: "2px 8px"
  tier-badge:
    backgroundColor: "{colors.bg-2}"
    textColor: "{colors.fg-2}"
    rounded: "{rounded.r-1}"
    padding: "2px 8px"
  canvas-card:
    backgroundColor: "{colors.bg-1}"
    textColor: "{colors.fg-1}"
    rounded: "{rounded.r-3}"
    padding: "16px"
---

# Design System: Strata

## 1. Overview

**Creative North Star: "The Sourced Ledger"**

Strata is a market-sizing engine for VCs and operators who have been burned by a
$50B-because-the-deck-said-so figure and now ask, of every number, "where did
that come from?" The interface answers that question by design. Every figure is
an object you can open to its source filing; competing methods sit side by side
with their disagreement named, not hidden. The visual system exists to make a
number feel **audited** rather than asserted: composed, legible, and quietly
certain. It reads closer to a finance publication than a SaaS dashboard, which
is the point.

The register is **product** (the work is the `/build` workhorse, the
`/tam/<hash>` artifact, `/portfolio`, `/connectors`) carried by an **editorial**
voice. An Instrument Serif display sets that voice on headlines and TAM titles;
a tuned Geist sans does all the working UI; Geist Mono carries every number so
the figures line up and read as data. The tension the system must hold:
editorial *feel*, operator *speed*. A partner pulling a number twenty minutes
before a meeting should read the restraint as clarity, never as ceremony.

This system explicitly rejects three things. It is not a **generic SaaS
template** (Inter-for-everything, purple-to-blue gradients, the rounded icon
tile above every heading, the hero-metric block); the editorial serif and the
mono-number discipline exist to escape that lane. It is not a **legacy research
report** (IBISWorld / Statista / Gartner: opaque "our analysts estimate"
methodology, stock-photo gloss, zero provenance you can click); Strata inverts
that by making the derivation the interface. And it is not **academic or dry**
(wall-of-text, no hierarchy, rigor performed rather than delivered); the
audience is on a clock.

**Key Characteristics:**
- Light `#FAFAFA` paper, deep `#0A0A0B` ink, a single indigo accent used sparingly.
- Editorial serif display + technical sans body + tabular mono numbers.
- A load-bearing source-tier color system: every number wears its provenance.
- Flat by default; shadow is a response to state, never decoration.
- A separate "night canvas" world for the signed-out marketing and auth surfaces.

## 2. Colors

A near-neutral light surface system with one indigo voice and a small, meaningful
provenance palette. Color is information here, not garnish.

### Primary
- **Strata Indigo** (`#5B5BD6`): The single brand voice. Primary actions, the
  current selection, links, the Quantitative pyramid axis, and the TAM node.
  Hover lifts to `#6E6EE0`, pressed drops to `#4848C4`. On a dark surface it
  lifts to `#7C7CF0` for contrast.

### Tertiary — Source-tier palette (load-bearing)
Each primitive is stamped with exactly one source tier, and these hues are how a
tier is read at a glance on badges, scenario-tree leaves, and the "source-tier
mix" donut. This palette is contractual, the same token names live in CSS
(`globals.css`) and in `docs/design/brand-kit.md` §1.6. Do not repurpose these
hues for decoration.
- **Regulator Green** (`#3FA66B`): regulator-tier sources (FRED, BLS, EDGAR).
- **Aggregator Teal** (`#2BA39A`): aggregator-tier (World Bank, OECD, Comtrade).
- **Analyst Ochre** (`#C99846`): analyst-tier sources, and the Industry pyramid axis.
- **Community Gray** (`#7A7A82`): community-modeled inputs.
- **On-chain Violet** (`#8B5CD6`): on-chain sources.
- **Prediction Orange** (`#D97849`): prediction-market signals (quarantined, never feed a TAM).

### Neutral
- **Paper** (`#FAFAFA`): the default page canvas. **Surface** (`#FFFFFF`): cards,
  panels, modals. **Fill** (`#F4F4F5`) and **Pressed** (`#E9E9EC`): hover and
  selected states.
- **Ink ramp**: Primary text `#0A0A0B`, secondary `#52525B`, tertiary/metadata
  `#7E7E86`, disabled/placeholder `#B4B4BA`.
- **Borders**: hairline `#E8E8EC`, card/input edge `#D4D4D8`, emphasized `#A1A1AA`.

### Semantic
- **Success** `#4ADE80` (positive deltas, "verified"), **Warning** `#C99846`
  (synthetic / community-tier banner), **Danger** `#E5484D` (destructive,
  error), **Info** `#3B7BD9` (neutral information).

### Night Canvas (signed-out surfaces only)
The public landing, `/sign-in`, and `/sign-up` render on a fixed deep-navy world
(`#080B16`) with an infinite indigo grid and frosted-glass panels, intentionally
independent of the light/dark app theme. Accent lifts to `#8B8BF5`.

### Named Rules
**The One Voice Rule.** Indigo is the only brand color and appears on ≤10% of any
app screen. Its rarity is what makes a selected node or a primary CTA read
instantly. Everything else is neutral or a provenance hue.

**The Provenance-Color Rule.** The six tier hues mean exactly one thing each. A
green chip is always a regulator source, never a "success" decoration. Never
encode meaning in tier color alone, always pair the hue with its label.

## 3. Typography

**Display Font:** Instrument Serif (with Tiempos Headline, Georgia, serif)
**Body Font:** Geist (with Inter, system-ui, sans-serif)
**Number / Mono Font:** Geist Mono (with JetBrains Mono, ui-monospace)

**Character:** A high-contrast serif-display-over-grotesque-sans pairing. The
Instrument Serif gives headlines and TAM titles an editorial, considered air,
the thing that separates Strata from generic SaaS, while Geist keeps the working
UI crisp and dense. Numbers always live in Geist Mono with tabular figures so
columns of TAM values, primitive counts, and version hashes align to the digit.

### Hierarchy
- **Display** (400, 48px, 1.15, -0.02em, Instrument Serif): hero and section
  headlines, the editorial moments. Applied via the `.display` class.
- **Headline / H1** (500, 32px, 1.15, -0.02em): page titles. Instrument Serif on
  editorial surfaces, Geist on dense app screens.
- **Title / H2–H3** (600, 24px / 20px, 1.35, Geist): section and panel headers.
- **Body** (400, 14px, 1.5, -0.01em, Geist): the default. Prose capped at
  65–75ch; dense tables and labels may run tighter.
- **Label / Eyebrow** (500, 11px, 1, +0.04em, uppercase, Geist): tier badges and
  table headers only. Short labels (≤4 words), never a per-section kicker.
- **Mono Number** (600, 32px, 1, Geist Mono, `tnum`/`lnum`): the headline TAM
  value. Smaller mono (500, 12–13px) carries inline figures, hashes, and counts.

### Named Rules
**The Numbers-Are-Mono Rule.** Every figure a user might cite, a TAM value, a
primitive count, a percentage, a hash, is set in Geist Mono with tabular figures.
Numbers in the proportional sans is a defect; they fail to align and read as
prose, not data.

**The Serif-Is-Editorial Rule.** Instrument Serif is for display and headlines
only. A serif on a button label, an input, or a data cell is forbidden, it
signals "decoration" exactly where the product needs "instrument."

## 4. Elevation

Flat by default. Surfaces sit on the paper with a hairline border and no shadow
at rest; depth is conveyed by tonal layering (paper → surface → fill) and by
borders, not by ambient drop shadows. Shadow is reserved for things that float
above the page in response to state: popovers, the ⌘K command palette, modals,
and the hover lift on workflow-canvas cards.

### Shadow Vocabulary
- **Pop** (`box-shadow: 0 4px 14px rgba(0,0,0,0.08), 0 1px 0 rgba(0,0,0,0.02) inset`):
  popovers, cards on hover, the floating elements just above the page.
- **Overlay** (`box-shadow: 0 16px 48px rgba(0,0,0,0.14), 0 1px 0 rgba(0,0,0,0.02) inset`):
  modals and the command palette, things that own the screen.
- **Canvas-card hover** (`0 4px 12px rgba(15,23,42,0.08), 0 0 0 1px rgba(15,23,42,0.06)`):
  the Harvey-style workflow cards used for graph nodes and rail rows.

### Named Rules
**The Flat-By-Default Rule.** Surfaces are flat at rest. A shadow is a response
to state (hover, float, focus), never a decoration applied to a static card. If
a card has a resting drop shadow, remove it and let the border and tonal layer
carry the separation.

## 5. Components

### Buttons
- **Shape:** 8px radius (`--r-3`); inputs and small buttons use 6px (`--r-2`).
- **Primary:** solid indigo (`#5B5BD6`) with white text, 36px tall, 16px
  horizontal padding. Hover `#6E6EE0`, active `#4848C4`, transition ~120ms.
- **Ghost / Secondary:** white surface, ink text, 1px `#D4D4D8` border. Hover
  fills to `#F4F4F5`. No drop shadow.
- **Focus:** a 3px indigo ring (`box-shadow: 0 0 0 3px rgba(91,91,214,0.35)`), no
  UA outline. This focus treatment is global and consistent across every control.

### Chips
- **Filter chip:** pill (`--r-round`), `#F4F4F5` fill, `#52525B` text; selected
  uses the accent tint `rgba(91,91,214,0.12)` with `#4848C4` text.
- **Tier badge:** 4px-radius (`--r-1`) label set in the 11px uppercase eyebrow
  style, colored by the source-tier palette and always paired with the tier name.

### Cards / Containers
- **Corner style:** 8px (`--r-3`); large hero panels 12px (`--r-4`).
- **Background:** white surface on `#FAFAFA` paper.
- **Shadow strategy:** flat at rest, "Pop" shadow on hover only (see Elevation).
- **Border:** 1px hairline (`#E8E8EC`), or the canvas-card's `rgba(10,10,11,0.06)`.
- **Internal padding:** 16px (`--space-4`) default, on the 4px grid.

### Inputs / Fields
- **Style:** white surface, 1px `#D4D4D8` border, 6px radius, 36px tall.
- **Focus:** the global 3px indigo ring; the border does not also thicken.
- **Placeholder:** must meet 4.5:1, do not drop it to the `#B4B4BA` disabled tier.

### Navigation
- **Left sidebar** (240px, 56px collapsed): the persistent app rail with live
  library counts. Current route uses the accent tint fill and indigo text.
- **Top bar** (48px): search + ⌘K command palette + actions.
- **Right rail** (320px): the pyramid explorer / TAM detail accordion.

### Signature Component — The Pyramid Graph
The always-on ReactFlow centerpiece. Three axes are color-coded so identity
survives when labels drop at small sizes: **Qualitative** = `#52525B` (gray,
definitional), **Quantitative** = `#5B5BD6` (indigo, counted), **Industry** =
`#C99846` (ochre, sector codes). Nodes are keyboard-focusable and carry the
global focus ring. Hover shows a 250ms ghost-card preview.

### Signature Component — The TAM Headline
A large Geist Mono number (`--type-mono-num`, 600/32px, tabular) that counts up
on load. The count-up, the sensitivity tornado, and graph/scenario animations
must all degrade to an instant final state under `prefers-reduced-motion`.

## 6. Do's and Don'ts

### Do:
- **Do** set every citable figure in Geist Mono with tabular figures (`tnum`).
- **Do** keep indigo to ≤10% of any screen (The One Voice Rule); let neutrals carry the surface.
- **Do** pair every source-tier color with its label, never rely on hue alone.
- **Do** keep surfaces flat at rest; add the "Pop" shadow only on hover/float/focus.
- **Do** cap cards at 8px radius (`--r-3`), 12px (`--r-4`) for large hero panels only.
- **Do** verify the `#7E7E86` metadata tier hits 4.5:1 on `#FAFAFA` before shipping body-sized text in it.
- **Do** give every interactive element the global 3px indigo focus ring and a reduced-motion fallback.
- **Do** reserve Instrument Serif for display and headlines.

### Don't:
- **Don't** ship the **generic SaaS template**: Inter-for-everything, purple-to-blue gradients, cards nested in cards, the rounded icon tile above every heading, or the hero-metric block. These are the anti-references PRODUCT.md names first.
- **Don't** drift toward the **legacy research report**: opaque methodology, stock-photo gloss, or any number without a clickable source. Provenance is the product.
- **Don't** ship **academic/dry** walls of text with no hierarchy; the audience is operators on a clock.
- **Don't** put numbers in the proportional sans, or a serif on a button, input, or data cell.
- **Don't** use a colored `border-left`/`border-right` greater than 1px as an accent stripe on cards, list items, or callouts.
- **Don't** use gradient text (`background-clip: text`) or decorative glassmorphism inside the app (the night canvas is the one sanctioned, deliberate glass surface).
- **Don't** give resting cards a drop shadow, or round any card past 12px.
- **Don't** add a tiny uppercase tracked eyebrow above every section; the 11px label style is for tier badges and table headers, not per-section kickers.
