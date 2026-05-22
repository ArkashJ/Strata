# Strata — Product Surface Brainstorm (v0.3 → v1.0)

> Builds directly on `docs/07-data-layer-brainstorm.md` (data layer Q1–Q38).
> This document locks the user-facing surface of Strata — routes, screens,
> rails, navigation patterns, URL state model — that turns the data layer
> into Sarah's 4-minute defensible TAM.

## Status

**Phase:** Product-surface brainstorm **COMPLETE.** 12 UX decisions resolved (U1–U12).
**Builds on:** `docs/07-data-layer-brainstorm.md` (data layer Q1–Q38).
**Parked for v0.5:** expert-layer mechanics (carried from data-layer brainstorm); contribution-flow internals beyond entry-point UX.

---

## TL;DR — decisions table

| #   | Question                       | Decision                                                                                                                                                                                                          |
| --- | ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| U1  | Central object on screen?      | **Pyramid graph** is the always-on centerpiece. Everything else orbits it in side panels / drill-in pages.                                                                                                        |
| U2  | Right rail organization?       | **Collapsible accordion.** Frameworks + Scenarios expanded by default; Independence + Lineage collapsed to one-line summary chips. Banners + Export pinned at bottom. (Annotations do **not** live in the rail — see U8.) |
| U3  | Entry point?                   | **Search-first landing.** Single centered query box; LLM parses to a constraint set.                                                                                                                              |
| U4  | Post-parse handling?           | **Multi-interpretation cards.** 2–3 distinct constraint-set + concept-bundle readings, user picks one before pyramid loads. Definitional ambiguity is a first-class step.                                         |
| U5  | Drill-in navigation?           | **Hybrid: hover preview + click routes.** Hover shows ghost card (value, source, snapshot); click navigates to dedicated `/c/`, `/p/`, `/f/`, `/tam/` page. Back button is lossless because of auto-mint URLs.    |
| U6  | URL minting?                   | **Auto-mint on every meaningful state change.** Every constraint add/remove, framework toggle, assumption tweak, or re-pin generates a new content-hash-pinned URL. Observable / Figma model.                     |
| U7  | Concept page layout?           | **Side-by-side measurement cards** with range bar at top, independence summary at bottom, lineage modal button.                                                                                                   |
| U8  | Annotation UI?                 | **Red dots in context only.** Dot next to annotated item; hover → preview; click → inline expand. No aggregated rail section.                                                                                     |
| U9  | Framework picker?              | **Auto-suggest 2–5 compatible** in rail (per Q18) + **`+ Browse all`** modal with compatible-on-top, incompatible-greyed (per Q16).                                                                               |
| U10 | Primitive / Framework pages?   | **Single-column with anchored sections.** Header → source/formula → details → consumers → annotations → propose-update button.                                                                                    |
| U11 | Public registry?               | **`/browse` page of promoted TAMs.** Separate `is_promoted` flag from the auto-mint URLs; promotion is an explicit author action.                                                                                 |
| U12 | Contribution entry?            | **Inline `+ Propose update` buttons + `/contribute` splash.** PR template for records (per Q23); inline web form for annotations.                                                                                 |

---

## Context

The data layer brainstorm locked 38 decisions about **what** Strata stores and
how the layers compose. This document locks **how** the user interacts with it.

Two existing docs partially specify this surface — `02-network-graph.md` and
`04-user-journey.md` — but both predate load-bearing data-layer decisions:
scenario trees (Q1), concepts as first-class (Q9), content-hash-pinned URLs
(Q38), independence scoring (Q7), competing measurements, regime modifiers,
and the 5-layer model. **This spec supersedes those two docs for v0.3+**;
they remain useful as historical context.

The interaction surface ships in three roadmap chunks:

- **v0.3 — Graph renderer:** landing, interpretation cards, workhorse view, concept/primitive/framework pages, URL state model, hover preview, annotations.
- **v0.4 — Calculator + export:** scenario drill-in, independence + lineage surfaces, sensitivity banners, synthetic/modeled banners, export, TAM artifact.
- **v0.5 — Contribution:** `/contribute` splash, inline propose-update buttons, annotation web form, LLM PR review wiring, expert-layer mechanics.
- **v1.0 — Public beta:** `/browse` with semantic search, promotion mechanics, forking, public-registry indexing.

---

## Information architecture (routes + surfaces)

```
/                          Search-first landing
/?q=<query>                Interpretation cards (post-parse, pre-pyramid)
/build/<state-hash>        Workhorse view (auto-minted per meaningful state)
/tam/<hash>                TAM artifact (workhorse view frozen + Fork button)
/c/<concept-slug>          Concept page (disagreement view)
/p/<primitive-slug>        Primitive page (source snapshot, history)
/f/<framework-slug>        Framework page (formula, variants, applicability)
/browse                    Registry of promoted TAMs
/contribute                PR-flow splash + schema docs
```

`/tam/<hash>` is a **vanity alias** for `/build/<state-hash>` records where
`is_promoted = true` OR the author has explicitly published. The underlying
state is identical; the route triggers the frozen/Fork UI affordance.

Top bar on every page: logo · search box · `/browse` · `/contribute` · auth.

---

## Surface 1 — Search-first landing (`/`)

Minimal centered search box. Placeholder example: _"Doc-gen tooling for P&C
insurance carriers, US"_. Below the box: 6–8 recently promoted TAMs as
preview cards (a teaser of `/browse`). Footer: links to `/browse`,
`/contribute`, vision/docs.

On submit → navigate to `/?q=<url-encoded-query>`.

---

## Surface 2 — Interpretation cards (`/?q=...`)

The LLM query parser produces 2–3 distinct constraint-set + concept-bundle
interpretations. Each rendered as a card.

```
┌──────────────────────────────────────────────┐
│ NARROW: Sales tech = CRM only                │
│ ─────────────────────────────────────────────│
│ Qual:     B2B SaaS                           │
│ Quant:    Enterprise + Midmarket             │
│ Industry: cross-vertical                     │
│ Concept:  us-crm-spend-2024                  │
│ Preview range: $4B – $7B  (3 frameworks)     │
│                                              │
│                            [ Use this  → ]   │
└──────────────────────────────────────────────┘
```

Card content:

- Definitional label (the bundle name)
- Constraint chips (Qual / Quant / Industry / Geo / Time)
- Target concept slug
- Preview value range computed by running the 3 most-compatible frameworks
- "Use this" button → navigates to `/build/<state-hash>` with constraints pre-set

Special states:

- **No concept match:** single card "We don't have a concept that covers this yet" with `[ Propose a concept ]` → `/contribute`.
- **Low LLM confidence:** each card explicitly labelled "best guess" with editable constraint chips before the user commits.

---

## Surface 3 — Workhorse view (`/build/<state-hash>`)

The home of the product. Two-column layout, ~70% / ~30%.

### Main canvas (left): pyramid graph

Per `02-network-graph.md` updated for the data-layer decisions:

- Three pillars (Qualitative / Quantitative / Industry), tier 0 root at top, tier 3 leaves at base.
- Geo and time live as **filter chips above the graph** (per Q12), not pillars.
- Click node → constraint added; greys incompatible siblings in other pillars.
- Shift-click → OR within same pillar/tier.
- Click again → remove constraint.
- Right-click → context menu (Expand children · Annotate · Suggest framework).
- Node anatomy per `02-network-graph.md` §"Node anatomy" — extend with red-dot annotation indicator (U8).

### Right rail: collapsible accordion (U2)

```
TARGET (always visible)
  Doc-gen × P&C × Enterprise × US
  as_of 2026-05-21              [copy link]

▼ FRAMEWORKS
  ✓ bottoms-up-by-seat
  ✓ top-down-it-spend
  ✓ analog-doc-gen
  + Browse all                  ← opens modal

▼ SCENARIOS
  ▸ $47M   bottoms-up (narrow)
  ▸ $213M  top-down
  ▸ $80M   analog
  ▼ $11M   bottoms-up (broad)   ← expanded
       Definition: incl. captive carriers
       Inputs (5):  n_pc_carriers_us … [snapshot ✓]
                    avg_seats_per_carrier_addressable … ✓
                    …
       [→ open primitive]   [⚠ method-family overlap]
  Triangulated: $80M – $200M

▶ INDEPENDENCE   0.82 ●●○
▶ LINEAGE GRAPH                     [open modal]
▶ BANNERS  (e.g. "uses modeled composite")

[ Export → URL / PDF / MD ]
```

**Frameworks section:** auto-suggested 2–5 compatible frameworks per Q18.
`+ Browse all` opens a modal listing every framework — compatible-with-target
on top, incompatible greyed and labelled with the failing `not_applicable_to`
clause (per Q16).

**Scenarios section:** one row per scenario. Click to inline-expand. Expanded
shows: definitional choice (per Q1 scenario tree), inputs with snapshot
indicators, computed value, sub-scenarios from `expansion_stage` (Q22) or
narrow/broad definitional splits (Q1). Triangulated range at bottom is the
union of all leaf scenarios (with the same caveats Q7 surfaces as warnings).

**Independence (collapsed):** chip shows score + dot rating. Click expands to
show: method-family decomposition, lineage-overlap matrix, dot-product math.

**Lineage Graph (collapsed):** click → opens modal using the
`network-graph-modal` skill (per Q7). Shows `derives_from` edges among the
primitives used in the current scenarios.

**Banners section:** banners surfaced from data-layer decisions —
synthetic-atomic banner (Q20), modeled-composite banner (Q20),
subsidy-regime banner (Q33), regulated-access banner (Q36),
dark-estimate banner (Q37). Banners are prose explanations; export-time they
become footnotes on the artifact.

**Export button (bottom):** opens a small popover with three options:
"Copy URL" (just the auto-mint URL), "Download PDF", "Download Markdown".

### Cross-cutting interactions on this surface

- **Hover preview (U5):** hovering any concept / primitive / framework name shows a 250ms-delayed ghost card with key fields. Esc dismisses.
- **Click navigates (U5):** click on the name routes to the dedicated page. Back-button restores the workhorse view at the URL it left from (lossless thanks to U6 auto-mint).
- **Red-dot annotations (U8):** anywhere a primitive / framework / concept / node has annotations attached, a red dot appears. Hover dot → top-weighted annotation snippet. Click dot → inline expand with all annotations on that item, sorted by contributor weight (expert-layer mechanics parked: weighting rules TBD at v0.5).
- **Sensitivity-aware change banner (Q5):** when a cited primitive has a fresher upstream version that would move the TAM >Δ% (default 5%), a banner at the top of the rail offers `[Re-pin to latest]` / `[Keep current]`. Black-swan (>25%) banner is louder.
- **Method-family conflict warning (Q7):** if two selected frameworks share a `method_family`, an inline warning appears under the Frameworks section: _"These frameworks share method family `top_down_spend` — triangulation independence reduced."_

### URL state model (U6)

Every **meaningful** state change auto-mints a new content-hash-pinned URL.
Meaningful = adds/removes a constraint, toggles a framework, tweaks a
framework assumption, re-pins a primitive.

Non-meaningful = pan/zoom, hover, accordion open/close, scroll. These do
**not** mint URLs.

Browser history records minted URLs in order. Back/forward navigate state.
"Copy link" copies the current pinned URL.

Rate limiting: anonymous users capped at ~50 minted URLs / day to prevent
spam. Authed users have higher caps. Detailed numbers TBD.

---

## Surface 4 — TAM artifact (`/tam/<hash>`)

Identical to the workhorse view, **frozen**:

- All inputs content-hash pinned; no edits possible.
- Banner across the top: _"TAM pinned 2026-05-21 by @sarah · [Fork to edit]"_.
- Rail's "Export" button replaced with `[ Fork ]` → creates a new `/build/<state-hash>` with same starting constraints and frameworks, editable.
- All hover preview / click-navigate / annotation-dot interactions remain active (read-only).

`/tam/<hash>` and `/build/<state-hash>` are the same underlying state; the
route distinction triggers the frozen / Fork UI mode.

This is the surface that gets pasted into VC memos.

---

## Surface 5 — Concept page (`/c/<slug>`) — U7

The defensibility centerpiece. Side-by-side measurement cards.

```
HEADER
  US software developer headcount
  narrow-test scope: paid employed devs in US
  sibling concepts: us-dev-broad · us-engineers   [+ link]
  ⚠ annotation: "Captive employment…" — @alice ●●●

RANGE BAR
  [sparkline: 1.69M ─●─●─●──● 4.10M]

MEASUREMENT CARDS (horizontal scroll if >4)
┌─ BLS OEWES ────┬─ LinkedIn EG ──┬─ SO Survey ────┐
│  REGULATOR     │  AGGREGATOR    │  AGGREGATOR    │
│  1.69M people  │  2.45M people  │  4.10M people  │
│  as_of 2024    │  as_of 2024    │  as_of 2024    │
│  employer-     │  self-reported │  annual self-  │
│  reported      │  titles        │  report extrap.│
│  snapshot ✓    │  snapshot ✓    │  snapshot ✓    │
│  2 annotations │  1 annotation  │  0 annotations │
│  [→ primitive] │  [→ primitive] │  [→ primitive] │
└────────────────┴────────────────┴────────────────┘

INDEPENDENCE: high (3 distinct methodologies, no shared lineage)
                                          [→ Lineage graph modal]

USED IN
  12 frameworks · 47 TAMs cite

ANNOTATIONS (on the concept itself, not its measurements)
  • @alice: "Captive agents are usually omitted from BLS…"

[+ Add measurement]   [+ Annotate]   [+ Propose concept update]
```

Each measurement card → click → `/p/<primitive-slug>`.

Sibling concepts (Q10b narrow-test) listed at the top; click navigates to
the sibling's page.

`competing_concepts` link is bidirectional — viewing `us-dev-narrow` shows
links to `us-dev-broad` and vice versa.

---

## Surface 6 — Primitive page (`/p/<slug>`) — U10

Single-column with anchored sections:

1. **Header** — name, value, structured unit (Q4), as_of, source-tier badge.
2. **Concept link** — _"measures: us-software-dev-headcount"_ → `/c/<slug>`.
3. **Source snapshot (Q5)** — source slug, tier, URL, accessed date, snapshot sha256, `[ Download snapshot ]` button.
4. **Methodology** — 1–3 sentence prose.
5. **Lineage (`derives_from`, Q7)** — list of upstream source slugs.
6. **Geography (Q8)** — level, codes, supply/demand perspective.
7. **Distribution shape (Q31)** and **delivery mode (Q32)**.
8. **Uncertainty range (Q1)** — explicit `[low, high]` + basis.
9. **Revision history (Q5)** — list of past pins: content-hash · as_of · change reason. Diff view between adjacent pins.
10. **Used in** — list of consuming frameworks + count of citing TAMs (with sample TAM links).
11. **Annotations** — red-dot-style, inline expand (U8 pattern).
12. **`[ + Propose update ]`** — opens GitHub PR template prefilled with the YAML record.

Composite primitives use the same template but show `inputs` and
`set_operation` (Q3) under §3 in place of a raw source.

---

## Surface 7 — Framework page (`/f/<slug>`) — U10

Single-column with anchored sections:

1. **Header** — name, method family (Q7), function tag.
2. **Formula** — prose summary + machine-readable expression (per `03-data-model.md`).
3. **Inputs** — list: name · role (Q6) · unit signature · required/optional.
4. **Variants (Q17)** — regional / sector variants, each with default primitive pointers (per Q15 no-scalar-defaults).
5. **Applicability (Q16)** — `applicable_to` whitelist + `not_applicable_to` blacklist.
6. **Requires clearance (Q36)** — if applicable.
7. **Horizon class** (Q6) + **`expansion_stage_parameter`** (Q22).
8. **Example TAMs** — 3–5 recent TAMs built with this framework, link to each.
9. **Annotations** — same pattern.
10. **`[ + Propose update ]`**.

---

## Surface 8 — Browse registry (`/browse`) — U11

Public registry of TAMs where the author or a moderator has flagged
`is_promoted = true`. Card grid:

```
┌─────────────────────────────────────┐
│ Doc-gen for P&C insurance, US       │
│ Industry: P&C insurance             │
│ Geo: US · Time: 2026-05-21          │
│ Range: $80M – $200M                 │
│ Independence: ●●○                   │
│ by @sarah · pinned 2026-05-21       │
└─────────────────────────────────────┘
```

Filters: pillar (Qual / Quant / Industry), vertical, framework, time range,
independence threshold.

Default sort: recently pinned + frequently cited.

Search box: hybrid search per Q28 — full-text + tag-faceted + semantic
embeddings (semantic ships v1.0).

---

## Surface 9 — Contribute splash (`/contribute`) — U12

Doc-style page. Sections:

- **Why contribute** — short paragraph of the open-library thesis.
- **What you can contribute** — tiered list (per Q23): primitives, composites, frameworks, concepts, taxonomy nodes (all via PR); annotations (via inline web form).
- **Schema docs** — links to `03-data-model.md`, `07-data-layer-brainstorm.md`, and the JSON-schema files (when they land).
- **LLM PR review** (Q24, Q25) — explainer for what auto-approves (high-tier sources passing strict validators), what gets human spot-check.
- **Licensing policy** (Q26) — public-domain/open sources reproduced fully + snapshot; paywalled sources cite-only with metadata stub.
- **Two big buttons:**
  - `[ Open a PR on GitHub ]` → repo URL.
  - `[ Add an annotation ]` → web-form (slug-selectable target).

---

## Interaction patterns (cross-cutting)

### Hover preview (U5)

Every link to a concept / primitive / framework / TAM shows a hover card
after a 250 ms delay. Hover-card content:

- Name + tier badge
- Value + unit (if applicable)
- `as_of` + snapshot indicator
- 1-line description / methodology snippet

Dismissed on mouseleave or Esc. Tab-focus reveals the same card (a11y).

### Click navigates (U5)

The link itself routes to the dedicated detail page. Back button restores
the workhorse view at exactly the URL it left from — lossless because of U6
auto-mint URLs.

### Annotation dots (U8)

A red dot appears next to:

- Primitive name in the right rail
- Framework name in the right rail
- Concept name in any context
- Pyramid node (in the graph)
- Scenario row in the rail
- The TAM artifact itself (rail Target chip)

Hover dot → preview snippet of top-weighted annotation. Click dot →
inline-expand panel beneath the item with all annotations sorted by
contributor weight (weighting rules parked for v0.5 expert-layer brainstorm).

### Sensitivity-aware change banner (Q5)

When any primitive currently pinned in the build has a fresher upstream
version that would move the triangulated range by >Δ% (default 5%), the
workhorse view shows a banner at the top of the rail:

> _"`n_pc_carriers_us` was revised on 2026-05-18. Your build uses the
> 2024-09-15 pin. New value would shift bottoms-up scenario by +8%.
> [Re-pin to latest] [Keep current]"_

Black-swan (>25%) banner gets a louder visual treatment.

### Synthetic / modeled / regulated banners

Surface in rail's **Banners** section with prose explanation. Persist into
the exported artifact as footnotes.

- **Synthetic primitive (Q20):** _"This TAM uses 1 community-modeled atomic primitive (`agent-orchestration-2027`) with mandatory 12-month expiry."_
- **Modeled composite (Q20):** _"This TAM uses 2 analog-penetration composites; results depend on the analog assumption."_
- **Subsidy regime (Q33):** _"Subsidy modifier `ira-ev-credit-2026` active; base scenario also shown."_
- **Regulated access (Q36):** _"This concept requires clearance. TAM = addressable-given-clearance, not gross pool."_
- **Dark estimate (Q37):** _"Source tier = `community-modeled` / `prediction_market`. Range mandatory."_

### Method-family conflict warning (Q7)

If two or more selected frameworks share the same `method_family`, an
inline warning appears under the Frameworks section explaining that
triangulation independence is reduced.

---

## URL state model (U6) — extended

```
/build/<state-hash>      Auto-mint, content-hash-pinned, retrievable forever
/tam/<hash>              Vanity alias when is_promoted = true OR published

State payload (hashed):
  target_concept_slug
  geo_filter
  time_filter
  constraint_set (pyramid nodes selected)
  frameworks_selected[]
  framework_assumptions{}
  primitive_pins{ slug -> snapshot_sha256 }
```

State payload is canonicalized (sorted keys, normalized whitespace) before
hashing so equivalent states collide.

`is_promoted` flag is a separate boolean stored outside the state hash —
flipping it does not mint a new state, only changes registry visibility.

---

## Verification plan

The product surface is correct if these flows work without contortions:

1. **Sarah's golden path** (updates `04-user-journey.md`): search _"Doc-gen for P&C insurance, US"_ → see 2 interpretation cards (narrow incl. captive / broad excl. captive) → pick narrow → workhorse loads with constraints + 3 auto-suggested frameworks → reads BLS captive-carrier annotation via red dot → triangulates → "Copy URL" → drops `/build/<hash>` in IC memo.

2. **Citation flow:** Open a `/tam/<hash>` URL from a memo → see frozen build → click `n_pc_carriers_us` in expanded scenario → hover preview shows source tier + snapshot indicator → click → `/p/...` → snapshot downloadable → back-button restores `/tam/<hash>` intact.

3. **Concept disagreement (Q9 delivery):** From rail, click `us-software-dev-headcount` concept name → `/c/<slug>` → 4 measurement cards side-by-side with spread visible at glance → click a card → `/p/<slug>` → back-button restores the workhorse view (lossless).

4. **Synthetic market (Q20):** Search _"AI agents marketplace TAM 2027"_ → low-confidence interpretation cards with _"Propose concept"_ link → analog-penetration framework auto-suggested → modeled-composite banner appears in rail → exported PDF carries the banner as footnote.

5. **Forking:** Open another user's `/tam/<hash>` → click `[ Fork ]` → new `/build/<state-hash>` opens with same constraints + frameworks, editable → tweak `pct_addressable_by_doc_gen` slider → URL updates → new permanent URL is its own TAM.

6. **Contribution flows:**
   - From `/p/<slug>`, click `[ + Propose update ]` → opens GitHub PR template prefilled with the YAML record.
   - From a red dot, click `[ + Add annotation ]` → inline web form opens with target slug pre-filled → submit goes to moderation queue.

If any of these requires "just one UX exception," the surface is not done.

---

## Build sequence (mapped to roadmap)

| Roadmap                           | This brainstorm delivers                                                                                                                                                                                                          |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| v0.3 — Graph renderer             | Surfaces 1 (landing), 2 (interpretation cards), 3 (workhorse with all rail sections), 5 (concept page), 6 (primitive page), 7 (framework page). Hover preview + click navigates. Annotation dots. URL state model. Top bar.        |
| v0.4 — Calculator + export        | Scenario tree drill-in. Independence + lineage surfacing. Lineage modal (network-graph-modal skill). Sensitivity / synthetic / modeled banners. Export (PDF / MD). Surface 4 (artifact + Fork).                                    |
| v0.5 — Contribution flow          | Surface 9 (`/contribute`). Inline `+ Propose update` buttons. Annotation web form. LLM PR review wiring. Expert-layer mechanics brainstorm (parked from data layer) lands here.                                                   |
| v1.0 — Public beta                | Surface 8 (`/browse`) with semantic search. Promotion mechanics. Public-registry indexing. Hyperlink-able citation polish.                                                                                                        |

---

## Open threads (carry-forward)

- **Mobile / responsive layout** — desktop-first through v1.0; phone shape decided when there's UX data on what users do on phones.
- **Auth model** — needed for `is_promoted` author attribution, rate limiting, annotation moderation. Spec at v0.5.
- **Theme / brand identity** — type, color, dark mode, logo. Polish at implementation phase.
- **Internationalization** — punted (carried from data-layer brainstorm).
- **Specific LLM model + prompts** — query parser (Surface 2), hover preview formatting, PR review (per Q24/Q25). Implementation detail; spec stays vendor-flexible.
- **Pyramid depth cues** — whether to add 3D / perspective at v0.3 is a polish decision.
- **Rate-limit numbers** — anonymous URL-mint cap, anonymous annotation-form cap, registry-promotion cap. Calibrate at v0.5.
- **Δ% default for sensitivity banner** — starting at 5%; calibrate with real-user feedback (carried from data-layer brainstorm).
- **Source-lineage threshold for mandatory `derives_from`** — citation-count bar (carried from data-layer brainstorm).
- **U9b — multi-tab build comparison:** opening multiple `/build` URLs side-by-side. Useful for analysts; not in v0.3 scope but worth considering at v0.4.
- **U13 — keyboard shortcuts** — power-user accelerators (Cmd-K to search, Tab through scenarios, J/K to navigate measurements). Polish at v0.4+.

---

## What's NOT in this brainstorm

- **Implementation-stack choices** (frontend framework, backend, graph library). Defer to `writing-plans`. `02-network-graph.md` notes vis-network / cytoscape.js as candidates.
- **Storage backend details** — covered by data-layer brainstorm Q27 (YAML in git + Postgres mirror).
- **Specific seed concepts and frameworks for v0.2** — content question, not surface question.
- **Expert-layer mechanics** (credentialing, reputation decay, COI disclosure) — parked for v0.5 (carried from data-layer brainstorm).
- **Governance / contributor incentives** — how maintainers are chosen, conflict resolution, recognition.
- **External API / SDK design** — programmatic access for third parties. Post-v1.0.
