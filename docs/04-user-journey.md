# 04 — User Journey: "Size doc-gen for P&C insurance"

A worked walkthrough that mirrors the user's flow in `00-vision.md`. This is
the **golden path** the product is designed around. If this isn't fast and
defensible, nothing else matters.

## The user

Sarah, a Series A investor. Has heard a pitch from a doc-gen startup
targeting P&C insurance carriers. Needs a defensible TAM range for the IC
memo by tomorrow morning. Doesn't want to buy an IBISWorld seat for one
question.

## Step 1 — Frame the question

Sarah lands on Strata, types or selects:

> "Doc-gen tooling for P&C insurance carriers, US"

The system parses this into a constraint set across the three pillars:

```
Qualitative:  GTM motion = enterprise, persona = ops/IT, product = doc-gen
Quantitative: company size = enterprise carriers, geo = US
Industry:     P&C insurance (NAICS 524126)
```

The pyramid renders with these three nodes highlighted. Greyed-out: anything
incompatible (e.g. "consumer", "EMEA").

## Step 2 — Pick frameworks

A side panel suggests 2–3 frameworks compatible with this constraint set:

| # | Framework | Approach | Why it fits |
|---|---|---|---|
| 1 | **Bottoms-up by carrier seat** | bottoms_up | We have carrier counts + per-carrier IT seats |
| 2 | **Top-down from insurtech IT spend** | top_down | NAIC reports total IT spend by carriers |
| 3 | **Analog from doc-gen in adjacent verticals** | analog_penetration | Healthcare and legal doc-gen have public penetration curves |

Sarah picks **all three** — she'll triangulate.

## Step 3 — Inspect the pre-fills

For framework #1 (bottoms-up by carrier seat), the system has pre-populated:

| Input | Value | Source |
|---|---|---|
| `n_pc_carriers_us` | 2,800 | NAIC 2024 annual report (`regulator`) |
| `avg_seats_per_carrier_addressable` | 350 | NAIC IT staffing supplement (`regulator`) |
| `pct_addressable_by_doc_gen` | 0.40 (default assumption) | — |
| `avg_acv_per_seat` | $480/yr | Public S-1 filings, weighted avg (`first_party`) |
| `mature_penetration` | 0.25 (default assumption) | — |

Calculated point estimate: `2,800 × 350 × 0.40 × $480 × 0.25 = $47M`.

Range from the slider sweep: **$14M – $113M**.

## Step 4 — Read the annotations

A red dot on `n_pc_carriers_us` indicates an expert annotation:

> *"NAIC's carrier count includes ~600 single-state captive carriers
> that don't run independent IT. For doc-gen sizing, subtract them or
> apply a 0.78 adjustment."* — `@alice`, P&C carrier exec, 15 years

Sarah applies the adjustment. New range: **$11M – $88M**.

A second annotation on the framework itself:

> *"Doc-gen vendors in this space usually price per-document, not
> per-seat. Cross-check with framework #2 before trusting #1."*
> — `@bob`, ex-CRO at a P&C insurtech

## Step 5 — Triangulate

Sarah opens framework #2 (top-down). Pre-filled:

- US P&C carrier total IT spend: $14.2B (NAIC 2024)
- % of IT spend on document automation: 1.5–3.5% (analog from healthcare)
- → **$213M – $497M**

And framework #3 (analog):

- US healthcare doc-gen TAM, scaled by relative document volume ratio
  (P&C claims-doc volume / healthcare claims-doc volume = 0.18)
- → **$80M – $260M**

Three independent angles give her: **$11M – $497M**, with the bottoms-up
seat-count framework on the low end (because doc-gen pricing is shifting to
usage), and the IT-spend framework on the high end (because not all
document-automation IT spend will flow to vendors).

Realistic midpoint: ~$80M–$200M.

## Step 6 — Export

Sarah clicks **Export build**. Gets:

- A PDF / Markdown memo with all three frameworks, all primitives, all
  source citations, and the annotations she relied on.
- A permalink (`strata.example/build/abc123`) that anyone can open and
  fork.
- A CSV of the underlying primitives for the appendix.

She drops the permalink and the $80M–$200M range into the IC memo. The
partner asks where the number came from; she clicks the link and shows
the full chain in 10 seconds.

## What made this work

1. **Frameworks pre-suggested** by the constraint set — Sarah didn't have
   to know which TAM recipe to use.
2. **Primitives pre-filled** — she didn't have to find the NAIC report.
3. **Annotations surfaced inline** — the captive-carrier blind spot would
   have been invisible in a static PDF.
4. **Triangulation by default** — three frameworks side-by-side beats one
   point estimate.
5. **Source trail exportable** — defensibility is the deliverable, not the
   number.

## What would fail without the product

Without the network graph, Sarah would type "doc gen P&C insurance TAM"
into Google, get a $4,995 IBISWorld report behind a paywall, give up, ask
ChatGPT, get a hallucinated $1.2B figure with no source, and either
believe it or spend half her day in BLS / NAIC sites. The product
collapses a 4-hour task into a 4-minute one *with better sourcing.*
