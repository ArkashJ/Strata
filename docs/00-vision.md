# 00 — Vision

> Market sizing today is gated by expensive low-quality reports, when in reality
> the underlying exercise is just **credible primitives + a transparent framework**.
> Make both free, sourced, and community-curated, and you eat the bottom 80% of
> the IBISWorld / Statista / Gartner-lite use case.

## The problem

VCs and operators size markets constantly:

- "How big is doc-gen for P&C insurance carriers?"
- "What's the TAM for GTM tooling aimed at biotech founders?"
- "If we own midmarket SaaS expense management, how much revenue is on the table?"

The current options are bad:

| Source | Cost | Quality | Transparency |
|---|---|---|---|
| IBISWorld / Statista / Gartner | $$$ | Mixed; often dated; black-box | Low — you can't see the math |
| Analyst-written substacks | $ – $$ | Variable; one author's POV | Medium — usually shows assumptions |
| First-party / regulator data (BLS, Census, S-1s, Stripe blogs) | Free | High but raw | Total — but you do the work |
| Build-your-own in a spreadsheet | Time | As good as your inputs | Total |

The bottom 80% of the use case is **"give me a defensible range fast, with a
source trail."** Today that's a 3-day task or a $5k subscription. There's no reason
it should be either.

## The insight

The thing being sold by IBISWorld et al. is **not** a number — it's the chain of
custody from primitive → calculation → output. The number is cheap; the
**defensibility** is expensive.

So:

1. **Primitives** (atomic, sourced) — these exist for free, scattered across BLS,
   Census, regulator filings, S-1s, payment-processor blogs, and so on. The work is
   *collecting and crediting* them, not generating them.
2. **Frameworks** (parameterized recipes) — finite in count. There are maybe ~30
   canonical TAM recipes covering 90% of segments (bottoms-up by seat, top-down
   from spend, comparable-revenue sum, analog/penetration, etc.). Once written,
   they're reusable.
3. **Expertise** — the layer that separates "directionally right" from "actually
   defensible." A domain expert can tell you BLS undercounts captive agents by 20%.
   That commentary, attached to the primitive, is the real upgrade over a static
   PDF report.

Together: a living, contested, source-trailed market-sizing engine. Wikipedia
beat Britannica on the same logic — open the inputs, let the network correct
itself, win on freshness and depth.

## Why a network graph

Linear nav ("pick industry → pick sub-segment → pick approach") doesn't match
how sizing actually works. In practice you triangulate from multiple angles:
qualitative segmentation, quantitative slicing, and industry context. A graph
lets the user **pivot across axes** without restarting.

The pyramid in the sketch is the right primitive UI:

- **Three pillars** (Qualitative, Quantitative, Industry) all converge on the
  TAM at the top.
- **Each pillar widens at the base** — more granular constraints as you descend.
- Clicking a base node propagates the constraint up and across, re-narrowing the
  available frameworks.

See [`01-primer.md`](01-primer.md) for the topology and
[`08-product-surface-brainstorm.md`](08-product-surface-brainstorm.md) for the
full UX surface.

## Why now

- LLMs make the "collect + normalize + tag with source" task tractable at scale.
- Open-data initiatives (BLS APIs, Census Bureau, EDGAR full-text) are richer
  than they were 5 years ago.
- VC + operator workflows are increasingly tool-mediated (Notion, Affinity,
  Harmonic) — there's a wedge for an embedded "size this segment" widget.
- IBISWorld / Statista pricing has drifted up while quality has plateaued; the
  gap between "what they cost" and "what you actually need" keeps widening.

## What success looks like

**v1.0**: a VC analyst can land on the site, click into a sector, pick a
framework, see a pre-populated range with sources in under 60 seconds, and
export the build.

**v2.0**: every primitive has at least one expert annotation; every framework has
been used to build a public sizing that some operator or investor publicly
cites. Strata becomes the default citation in pitch deck appendices.

## What this is NOT

- Not a forecasting tool. We size what is, not what will be.
- Not a CRM or deal-flow tool — pairs with one, doesn't replace one.
- Not an LLM chatbot wrapper. The LLM helps ingest and normalize; the user-facing
  product is the graph + the data.
- Not closed-source. The library only works if the schema and seed data are open;
  monetization (if any) is on hosted, collaboration, or enterprise features.
