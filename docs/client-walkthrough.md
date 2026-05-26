# Strata Platform Walkthrough

A client-facing guide to navigating the Strata market-sizing engine.

---

## Overview

Strata is a platform for building defensible market-size estimates (TAMs) for venture investment decisions. Instead of relying on outdated reports from Gartner or Statista, Strata lets you:

- **Search a curated library** of market concepts backed by real data
- **Build custom market sizes** by combining multiple measurement approaches
- **Explore the data** behind each number — see sources, methods, and underlying primitives
- **Share results** with a shareable URL and download PDF reports

The platform is designed for **VCs and operators** who need numbers fast and want to understand exactly where they come from.

---

## Page-by-Page Map

### 1. Landing Page (`/`)

**What you see first:**

A clean search interface with the Strata logo (pyramid symbol) and a single centered search box.

**Key elements:**

- **Strata logo + name** (top left) — clickable to return home from any page
- **Navigation menu** (top right) with links to:
  - `/data` — explore individual data primitives
  - `/browse` — browse public TAM results (coming v0.3)
  - `/contribute` — submit new data or corrections (coming v0.5)
- **Search box** (main content area)
  - Placeholder text: "Doc-gen tooling for P&C insurance carriers, US"
  - Auto-focused when you land on the page
- **Suggested queries** below the box:
  - "Doc-gen tooling for P&C insurance carriers, US"
  - "Stripe TAM"
  - "AI agents marketplace 2027"
- **Version badge** (footer) — "v0.2.0a — backend in progress"
- **Footer tagline** — "github · for · TAM"

**How to use it:**

1. Type your market question into the search box (e.g., "HR software for mid-market")
2. Press Enter or click a suggestion
3. You'll either see a pre-built TAM (if the market is in the registry) or a dynamic analysis (if it's new)

**Navigation flow:**

- Search → `/build?q=your-query` (pre-built TAM) or `/build?q=your-query` (dynamic resolution)

---

### 2. Build Page (`/build?q=<query>`)

**What you see first:**

The main TAM result page. If the market exists in Strata's registry, you see a fully calculated market size. If not, you see a streaming resolution experience where Claude and Exa search the web in real-time.

**Key elements:**

**Header:**
- **← Strata button** (top left) — returns to search
- **State hash** (top right, monospace font) — e.g., `/build/3f8a2b1c` — unique identifier for this TAM state, used to generate shareable URLs

**Main content (left side):**

- **TAM label** — shows "TAM · {Geo} · {Time}" (e.g., "TAM · US · 2026")
- **Market name** (large heading) — e.g., "Doc-Gen Tooling for P&C Insurance Carriers"
- **Three key numbers:**
  - **Median TAM** — the middle-of-the-road estimate (e.g., "$2.4B")
  - **Conservative estimate** — low-end scenario
  - **Optimistic estimate** — high-end scenario
  - Each displayed with a currency symbol and formatted for readability

- **Scenario graph** (interactive visualization)
  - Shows multiple calculation paths to the final market size
  - Three scenarios (frameworks) typically displayed as nodes
  - Hover to see details; click to drill into assumptions
  - Example frameworks:
    - *Cost Efficiency* — "personas × cost"
    - *Revenue Generation* — "segment × spend"
    - *Productivity Uplift* — "personas × value split"

- **Banners** (conditional warnings)
  - **"Modeled composite"** — appears if a calculation uses an estimated (rather than sourced) number
  - Message: "One scenario uses an analog-penetration composite. Result depends on the analog assumption."
  - Color coded (orange tint) to draw attention

**Right sidebar:**

Collapsible sections that expand/collapse with a ▸/▾ indicator:

1. **Frameworks** (default open)
   - Lists all measurement approaches used
   - Example: "Cost Efficiency (4 scenarios)" → shows framework name and resulting TAM value
   - Badge shows count of scenarios (e.g., "3")
   - Each framework shows the lean it belongs to (e.g., "cost_efficiency", "revenue_generation")

2. **Independence** (collapsed by default)
   - Shows a score (e.g., "0.87") indicating how independent the scenarios are
   - Explanation: "3 method families · 4 scenarios. Higher is better."
   - Helps you understand if results are corroboration or just repeated assumptions

3. **Lineage Graph** (collapsed by default)
   - Button: "Open lineage modal →"
   - Clicking opens a full-screen network graph showing:
     - All primitives (colored blue) — the atomic data points
     - All frameworks (colored green) — the calculation recipes
     - Edges showing which primitives feed into which frameworks
     - Hover over nodes to see details
     - Shared primitives are highlighted to show dependencies
     - Close with Escape key

**Action buttons** (top of main content):

- **Copy URL** — copies the `/build/{hash}` URL to clipboard for sharing
- **Download PDF** — exports the TAM result as a formatted PDF report
- **Download Markdown** — exports as markdown for editing or embedding

---

### 3. Data Explorer (`/data`)

**What you see first:**

A detailed breakdown of how the TAM is calculated. Shows the specific data points (primitives) and formulas (frameworks) used.

**Key elements:**

**Scenario selector:**
- Tabs for each framework/scenario (e.g., "Cost Efficiency", "Revenue Generation")
- Click a tab to see that scenario's calculation
- Selected tab is highlighted with accent color

**Waterfall chart:**
- Visual representation of how inputs multiply to the final result
- Shows each primitive's value, unit, and role in the calculation
- Example:
  - "Personas: 45,000 people"
  - "Average software spend: $50K/year"
  - "Market adoption rate: 12%"
  - "= TAM: $27.0B"

**Inputs table** (if no scenario selected):
- Columns: Primitive Name | Value | Unit | Role | Framework
- Shows all data points used in the selected scenario
- Each row is filterable/sortable (styling for future interactivity)
- Example role badges: "numerator", "denominator", "multiplier"
- Framework column shows which calculation uses this primitive

**Sources panel** (below):
- Lists the original data sources (e.g., "BLS Employment Data", "Census Bureau")
- Shows source tier (e.g., "regulator", "analyst")
- Links to source snapshots (content-hashed for reproducibility)

---

### 4. Browse Page (`/browse`)

**Current status:** Placeholder — coming in v0.3

**What you see:**

- **Large heading:** "Browse"
- **Subtitle:** "A public registry of promoted TAMs will live here. Coming in v0.3."
- **Back to search link** (accent color)

**What it will be (v0.3):**

A public gallery of high-quality market-size estimates the community has vetted and promoted. Users will be able to:
- Filter by industry, year, or search term
- See community voting/ratings
- Fork a TAM to create a new version
- View trending analyses

---

### 5. Contribute Page (`/contribute`)

**Current status:** Placeholder — coming in v0.5

**What you see:**

- **Large heading:** "Contribute"
- **Subtitle:** "PR-based contribution flow, validator pipeline, and web form for annotations. Coming in v0.5."
- **Back to search link** (accent color)

**What it will be (v0.5):**

A way for users to submit corrections, new primitives, or annotations to the data bank:
- PR-based workflow (GitHub integration) for code-like rigor
- Web form for quick annotations
- Community reputation and attribution system
- LLM-assisted validation to catch errors

---

### 6. Dynamic Resolution (Streaming View)

**When you see this:**

If you search for a market that doesn't exist in Strata's registry, instead of an error you get a **ResolveView** — a live streaming experience where Claude thinks through your question and Exa searches the web.

**What you see:**

- **Query input** (top) — your search question
- **Thinking progress** (real-time SSE stream)
  - Shows Claude's chain-of-thought as it breaks down the market
  - Example thoughts:
    - "Breaking down doc-gen for P&C carriers..."
    - "Searching for: number of insurance carriers in US"
    - "Found: 5,000 P&C carriers from NAIC data"
    - "Estimating software spend per carrier: $200K–$500K"
  - Continues streaming until the calculation completes
- **Final TAM** — appears once calculation is done
- Same action buttons as Build page (Copy, Download PDF, Download Markdown)

**Navigation flow:**

- Press Escape or click back to return to search
- Results are temporary (not saved unless you explicitly promote them to `/browse`)

---

## Navigation Map

```
Landing (/)
    │
    └──→ Search query
         │
         ├─→ [Found in registry]
         │   └──→ Build (/build?q=...) [pre-built TAM]
         │       ├─→ Data (/data) [scenarios & inputs]
         │       ├─→ Copy URL [share]
         │       ├─→ Lineage modal [dependencies graph]
         │       └─→ Download PDF/Markdown
         │
         └─→ [Not in registry]
             └──→ ResolveView (streaming)
                 ├─→ Claude thinks + Exa searches
                 ├─→ Live chain-of-thought
                 └─→ Copy / Download / Share

Header Navigation (all pages):
    Logo → / [home]
    Data → /data [explorer]
    Browse → /browse [gallery, v0.3]
    Contribute → /contribute [submissions, v0.5]
```

---

## Key Concepts for Users

### What is a TAM?

Total Addressable Market — the total annual revenue opportunity in a market. Strata calculates it by combining multiple real-world data points (from government agencies, analysts, prediction markets) and measurement frameworks.

### What is a "Framework"?

A calculation recipe that defines how primitives multiply together. Example:

- **Framework:** "Cost Efficiency"
- **Definition:** "personas × cost per persona"
- **Primitives:**
  - "Number of software engineers in US" (persona count)
  - "Average software spend per engineer" (cost)
- **Result:** TAM value

### What is a "Primitive"?

A single, sourced data point from a trusted provider (BLS, FRED, Census, EDGAR, World Bank, or Kalshi prediction markets). Examples:

- "US employment: 160M people"
- "Enterprise software market: $150B"
- "Probability of AI agents taking >50% of software roles: 45%"

### What do the banners mean?

- **"Modeled composite"** — Strata estimated this number using an analog (e.g., "similar market + adjustment factor"). It's labeled so you know where the estimation uncertainty comes from.

---

## Common Workflows

### Workflow 1: Find a Pre-Built TAM

1. Go to `/`
2. Search for your market (e.g., "Stripe TAM")
3. If found, you see the full build page with scenarios, graph, and all inputs
4. Click scenarios to see how each framework calculates the result
5. Share via URL or download PDF

### Workflow 2: Size a New Market

1. Go to `/`
2. Search for something not yet in Strata (e.g., "autonomous delivery robots in SF")
3. See ResolveView with live streaming analysis
4. Claude and Exa search the web, break down the market in real-time
5. Get a TAM estimate with cited sources
6. Download or share the result

### Workflow 3: Understand the Calculation

1. From any Build page, scroll to **Right Sidebar**
2. Open **Lineage Graph** to see all primitives and frameworks as a network
3. Go to **Data Explorer** (`/data`) to see the exact inputs for each scenario
4. Click framework tabs to switch between calculation methods
5. See the waterfall showing how each input multiplies

---

## Design & Accessibility Notes

### Visual Design

- **Color tokens:** Light backgrounds (`--bg-0`, `--bg-1`, `--bg-2`), dark text (`--fg-1`), muted secondary text (`--fg-3`), accent color for CTAs and highlights
- **Typography:** Geist Sans for body, Instrument Serif for display headings, monospace for code/hash values
- **Spacing:** Consistent gap/padding using CSS variables (`--r-1`, `--r-2` for border-radius)
- **Responsive:** Sidebar (right rail) stacks below main content on mobile/tablet; graphs remain full-width

### Keyboard & Mobile

- All buttons are keyboard-accessible
- Escape key closes modals (Lineage Graph)
- Search box is auto-focused on landing page
- Tab order follows left-to-right, top-to-bottom

---

## Known Limitations (v0.2)

1. **Browse & Contribute** are placeholders — full implementation in v0.3 and v0.5
2. **Lineage graph** shows all primitives/frameworks but doesn't yet support filtering or zoom (coming in future release)
3. **Data Explorer** shows one scenario at a time; side-by-side scenario comparison coming in v0.4
4. **PDF export** is basic — detailed formatting coming in v0.4
5. **Geo & Time slicing** (U1 in product spec) not yet exposed in UI — all results show global/latest

---

## Support & Feedback

For questions or feedback:
- Check the GitHub repo: `github.com/strata/strata`
- Open an issue with reproducible examples
- For v0.5+, use the `/contribute` page to submit data corrections or new insights

---

## Version Info

- **Current version:** v0.2.0a (alpha)
- **Status:** Beta-ready for internal use
- **Next milestone:** v0.3 (Browse gallery + Postgres data store)
- **Roadmap:** See `docs/05-roadmap.md` in the repo
