# Strata — Brand Kit

Design tokens extracted from `docs/design/Strata Design - Standalone.html` (v0.42 mockup).
Use these verbatim when implementing the product so the build matches the mockup pixel-for-pixel.

The mockup ships a single `:root` block — there is no light/dark fork. The palette is a **light-default** UI on `#FAFAFA` paper with deep ink (`#0A0A0B`) type, accented by an indigo accent (`#5B5BD6`). A `[data-theme="light"]` selector exists in CSS but is currently empty — treat as a hook for a future dark theme, not a live mode.

## 1. Color

### 1.1 Surfaces (greys, paper → chrome)
| Token | Hex | Use |
|---|---|---|
| `--bg-0` | `#FAFAFA` | Page paper (default canvas) |
| `--bg-1` | `#FFFFFF` | Card / panel / modal surfaces |
| `--bg-2` | `#F4F4F5` | Hover, subtle fill, table zebra |
| `--bg-3` | `#E9E9EC` | Pressed / selected fill |

### 1.2 Ink
| Token | Hex | Use |
|---|---|---|
| `--fg-1` | `#0A0A0B` | Primary text, headings, numbers |
| `--fg-2` | `#52525B` | Secondary text, labels |
| `--fg-3` | `#7E7E86` | Tertiary text, metadata, captions |
| `--fg-4` | `#B4B4BA` | Disabled, placeholder |

### 1.3 Borders / dividers
| Token | Hex | Use |
|---|---|---|
| `--border-1` | `#E8E8EC` | Default hairline |
| `--border-2` | `#D4D4D8` | Card edge, input |
| `--border-3` | `#A1A1AA` | Emphasized edge |

### 1.4 Accent (Strata indigo)
| Token | Value | Use |
|---|---|---|
| `--accent` | `#5B5BD6` | Primary CTA, selected nav, links, TAM node, axis-Quantitative |
| `--accent-hover` | `#6E6EE0` | CTA hover |
| `--accent-active` | `#4848C4` | CTA active / pressed |
| `--accent-fg-on` | `#FFFFFF` | Foreground on `--accent` |
| `--accent-tint` | `rgba(91, 91, 214, 0.12)` | Selected-row background, soft chip |
| `--accent-ring` | `rgba(91, 91, 214, 0.35)` | Focus ring, hover halo |

### 1.5 Semantic
| Token | Hex | Use |
|---|---|---|
| `--success` | `#4ADE80` | Positive deltas, "verified" |
| `--warning` | `#C99846` | Synthetic / community-tier banner |
| `--danger` | `#E5484D` | Destructive, error |
| `--info` | `#3B7BD9` | Neutral information |

### 1.6 Source-tier palette (load-bearing — see [`docs/03-data-model.md`](../03-data-model.md))
Each primitive is stamped with one tier; this palette is referenced wherever sources appear (badges, scenario-tree leaves, "Source tier mix" donut on the TAM page, axis ticks).

| Tier | Token | Fill (solid) | Tint (background) |
|---|---|---|---|
| Regulator | `--tier-regulator` | `#3FA66B` | `rgba(63, 166, 107, 0.14)` |
| Aggregator | `--tier-aggregator` | `#2BA39A` | `rgba(43, 163, 154, 0.14)` |
| Analyst | `--tier-analyst` | `#C99846` | `rgba(201, 152, 70, 0.14)` |
| Community | `--tier-community` | `#7A7A82` | `rgba(122, 122, 130, 0.16)` |
| On-chain | `--tier-onchain` | `#8B5CD6` | `rgba(139, 92, 214, 0.14)` |
| Prediction | `--tier-prediction` | `#D97849` | `rgba(217, 120, 73, 0.14)` |

> First-party tier is referenced in the UI (see search palette `FIRS.` badge) but inherits the accent palette in the mockup. When adding the token to CSS, alias `--tier-first-party` → `--accent`.

### 1.7 Axis colors (pyramid)
The three pyramid axes share the accent + two tier hues so the eye reads "qualitative vs. quantitative vs. industry" at a glance:

| Axis | Color | Source |
|---|---|---|
| Qualitative | `--fg-2` (`#52525B`) | grey — definitional, no measurement |
| Quantitative | `--accent` (`#5B5BD6`) | indigo — counted things |
| Industry | `--tier-analyst` (`#C99846`) | ochre — sector codes |

## 2. Typography

### 2.1 Families
| Token | Stack | Purpose |
|---|---|---|
| `--font-ui` | `'Geist', 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif` | Default UI |
| `--font-display` | `'Instrument Serif', 'Tiempos Headline', 'Editorial New', Georgia, serif` | H1 / display — the "editorial" feel that distinguishes Strata from generic SaaS |
| `--font-mono` | `'Geist Mono', 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace` | Numbers (TAM values, primitive counts, version hashes) |

The mockup bundles **Inter Variable** (woff2) as the resilient fallback — keep it self-hosted alongside Geist so first paint never falls back to system serif on the H1.

### 2.2 Scale
| Token | Value |
|---|---|
| `--fs-11` | 11px (eyebrow, table header) |
| `--fs-12` | 12px (caption) |
| `--fs-13` | 13px (small body, mono) |
| `--fs-14` | 14px (body — default) |
| `--fs-16` | 16px (h4, lead body) |
| `--fs-20` | 20px (h3) |
| `--fs-24` | 24px (h2) |
| `--fs-32` | 32px (h1, big number) |
| `--fs-48` | 48px (display) |

### 2.3 Line-height & tracking
| Token | Value |
|---|---|
| `--lh-tight` | 1.15 |
| `--lh-snug` | 1.35 |
| `--lh-body` | 1.5 |
| `--tracking-tight` | -0.02em |
| `--tracking-snug` | -0.01em |
| `--tracking-normal` | 0 |
| `--tracking-wide` | 0.04em (eyebrow, tier badge) |
| `--tracking-mono` | -0.005em |

### 2.4 Composed roles
Use these in preference to assembling font + size + weight by hand.

| Token | Shorthand |
|---|---|
| `--type-display` | `400 48px/1.15 Instrument Serif` |
| `--type-h1` | `500 32px/1.15 Instrument Serif` |
| `--type-h2` | `600 24px/1.35 Geist` |
| `--type-h3` | `600 20px/1.35 Geist` |
| `--type-h4` | `600 16px/1.35 Geist` |
| `--type-body` | `400 14px/1.5 Geist` |
| `--type-body-sm` | `400 13px/1.5 Geist` |
| `--type-caption` | `400 12px/1.35 Geist` |
| `--type-eyebrow` | `500 11px/1 Geist`, tracking-wide, uppercase |
| `--type-mono` | `500 13px/1.4 Geist Mono` |
| `--type-mono-sm` | `500 12px/1.4 Geist Mono` |
| `--type-mono-num` | `600 32px/1 Geist Mono` — the headline TAM number |

## 3. Spacing

4px base grid. Use the named tokens — don't write raw `padding: 14px`.

| Token | Value |
|---|---|
| `--space-1` | 4px |
| `--space-2` | 8px |
| `--space-3` | 12px |
| `--space-4` | 16px |
| `--space-5` | 20px |
| `--space-6` | 24px |
| `--space-8` | 32px |
| `--space-10` | 40px |
| `--space-12` | 48px |
| `--space-16` | 64px |

## 4. Radii

| Token | Value | Use |
|---|---|---|
| `--r-1` | 4px | Chip, tier badge |
| `--r-2` | 6px | Input, small button |
| `--r-3` | 8px | Card, modal, primary button |
| `--r-4` | 12px | Hero CTA, large panel |
| `--r-round` | 999px | Pill, axis filter chip, avatar |

## 5. Elevation

| Token | Value |
|---|---|
| `--shadow-pop` | `0 4px 14px rgba(0,0,0,0.08), 0 1px 0 rgba(0,0,0,0.02) inset` — cards, popovers |
| `--shadow-overlay` | `0 16px 48px rgba(0,0,0,0.14), 0 1px 0 rgba(0,0,0,0.02) inset` — modal, ⌘K palette |

## 6. Motion

| Token | Value |
|---|---|
| `--ease-out` | `cubic-bezier(0.16, 1, 0.3, 1)` (enter, hover-in) |
| `--ease-in-out` | `cubic-bezier(0.65, 0, 0.35, 1)` (route / state) |
| `--t-fast` | 120ms (chip select, hover) |
| `--t-base` | 180ms (default) |
| `--t-slow` | 240ms (modal, route change) |

## 7. Layout primitives

| Token | Value | Notes |
|---|---|---|
| `--sidebar-w` | 240px | Left rail |
| `--sidebar-w-collapsed` | 56px | Icon-only mode |
| `--topbar-h` | 48px | Search + actions row |
| `--right-rail-w` | 320px | Pyramid explorer / TAM detail side panel |
| `--content-max` | 1280px | Center column cap |

## 8. Logo

The mark is a triangle (qualitative apex, quantitative + industry base nodes) sized to the same indigo as `--accent`. SVG embedded in the mockup:

```svg
<svg viewBox="0 0 1200 800" xmlns="http://www.w3.org/2000/svg">
  <path d="M 0 -160 L 180 140 L -180 140 Z" fill="none"
        stroke="#5B5BD6" stroke-width="6" stroke-linejoin="round"
        transform="translate(600 400)"/>
  <circle cx="600" cy="330" r="14" fill="#5B5BD6"/>
  <circle cx="510" cy="480" r="14" fill="#0A0A0B"/>
  <circle cx="690" cy="480" r="14" fill="#0A0A0B"/>
</svg>
```

Wordmark uses `--font-display` (Instrument Serif) italic. The tagline lockup is `GITHUB · FOR · TAM` set in `--font-mono` at 16px, letter-spacing `4`, color `--fg-3`.

## 9. Implementation contract

When the codebase lands:

1. Drop these tokens into a single `src/styles/tokens.css` file. Never inline hexes in components.
2. Self-host Inter Variable + Geist + Instrument Serif. The 7.9MB mockup proves the bundle works offline; downstream we should serve from `/static/fonts/`.
3. Refer to the source-tier colors via `var(--tier-{slug})` keyed off the tier enum — the same token name lives in CSS and in `data-model.md`.
4. The pyramid's three axes (Qualitative / Quantitative / Industry) must use the axis-color mapping in §1.7; this is the only place axis identity is communicated when the labels are dropped (small viewport).

See [`docs/design/component-catalog.md`](component-catalog.md) for the components built on top of these tokens, with screenshots.
