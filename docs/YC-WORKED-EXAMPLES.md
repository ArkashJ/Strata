# Strata — Real Worked Examples (the five layers, instantiated)

> Three actual TAMs from the committed data bank, traced layer-by-layer with the
> real numbers, slugs, and arithmetic the evaluator runs. Every value below is
> from a real `data/*.yaml` file — nothing invented. Use these to *show* how the
> spine works instead of describing it.

---

## Example 1 — AI coding assistants (US) · single-method `cost_efficiency`

The cleanest end-to-end: a composite feeds a 4-input framework that crosses units.

```
CONCEPT   ai-coding-assistants-us            data/concepts/ai-coding-assistants-us.yaml
          lens: cost_efficiency
          scope: US engineers in NAICS 5112 ∪ 5415, excl. consumer/non-US
   │ measured-by
   ▼
COMPOSITE us-software-engineering-workforce   data/composites/…  (SET OP, same unit)
          census-cbp-5112-employees-2022  (software publishers)  ┐ union
          census-cbp-5415-employees-2022  (computer sys design)  ┘  → ~3.0M people
          unit {stock, people} · both members are people-counts → legal union
   │ consumed-by
   ▼
PRIMITIVE ai-coding-assistant-acv-per-engineer-2024   value=$300/seat-yr
          unit {intensive, currency, USD, per-seat-year}
          tier=community-modeled (anchored to Copilot $228/yr + Cursor tiers)
          range [150, 600] · expiry 2027 · sha256-pinned  ← MODELED, fenced
   +  two modeled structural defaults:
          addressable-share-of-persona-pool-default-2024 = 0.60  {percent}
          incumbent-replacement-rate-default-2024        = 0.35  {percent}
   │
   ▼
FRAMEWORK cost-efficiency-full-displacement    lens=cost_efficiency
          formula: persona_pool × addressable_share × replacement_rate × cost_per_persona
          each input declares a unit_signature; validator parsed this at load
   │ emits
   ▼
TAM       3,000,000 × 0.60 × 0.35 × $300  =  ~$189M / yr
          unit {flow, currency, USD, per-year}   ← people × $/seat = $, units crossed legally
          /tam/<hash>  · banner: MODELED (cost_per_persona is community-modeled)
```

**What this shows:** the composite is a *same-unit union* (two people-counts →
one people-count). The framework is where units actually cross
(`people × $/seat-year → $/year`). The ACV is `community-modeled`, so the whole
TAM wears a **MODELED banner automatically** — derived from the tier, the YAML
can't hide it.

---

## Example 2 — Voice-AI infrastructure (global) · single-method `platform_throughput`

The Stripe-analog "infra captures a basis-point share of the stack it enables."

```
CONCEPT   voice-ai-infra-global                lens: platform_throughput
          "TTS/STT/voice APIs — ElevenLabs, Cartesia, Deepgram, …"
   │
   ▼
PRIMITIVE voice-ai-application-stack-revenue-global-2024   value=$108B/yr
          unit {flow, currency, USD, per-year} · power_law
          tier=analyst-paraphrase  → carries a ≤280-char paraphrase + reviewer
          (sum of 8 sub-markets: contact-center $20B, CS agents $15B,
           QSR voice $5B, outbound $8B, audiobooks $5B, dubbing $50B,
           accessibility $2B, game voice $3B)
PRIMITIVE voice-ai-infra-layer-share-global-2024          value=0.125 {percent}
          tier=community-modeled · range [0.10, 0.15]
          (cloud-IaaS-share analog: AWS/Azure capture ~10–15% of cloud spend)
   │
   ▼
FRAMEWORK throughput-take-rate     lens=platform_throughput · method=value_chain
          formula: gmv_or_volume × take_rate
   │ emits
   ▼
TAM       $108B × 0.125  =  ~$13.5B / yr
          unit {flow, currency, USD, per-year}   ← $ × percent = $
          banner: MODELED (take_rate is community-modeled)
```

**What this shows:** the *same throughput framework* (`gmv × take_rate`) sizes
voice AI, payments, EEG diagnostics, memory infra, and multimodal infra — one
recipe, five markets, each just re-binding two slugs (see the `variants:` block
in `throughput_take_rate.yaml`). That reuse is the framework-IP moat.

---

## Example 3 — AI sales-ops (US) · TWO methods → CONVERGENCE + scope spread

This is the demo. Same concept, two independent method families, a ~15× spread —
and the scope guard explains *why* they disagree instead of hiding it.

```
CONCEPT  demo-ai-sales-ops-us     primary=cost_efficiency · secondary=revenue_generation
         declared scope: ALL US B2B sales reps (SOC 41-3000 ∪ 41-4000), all firms

   ┌──────────────── METHOD A : cost_efficiency (bottoms-up seats) ───────────┐
   │  persona  demo-bls-sales-reps-us-2024 = 1,460,000  (regulator, BLS OEWS)  │
   │           ⚠ SOC 41-4012 — WHOLESALE/MFG reps ONLY (narrower than declared)│
   │  × ACV    demo-ai-sales-ops-acv-per-seat-2024 = $1,400/seat-yr            │
   │  ───────────────────────────────────────────────────────────────────────│
   │  1,460,000 × $1,400  =  ~$2.0B / yr                                       │
   └───────────────────────────────────────────────────────────────────────────┘

   ┌──────────────── METHOD B : revenue_generation (segment × spend) ─────────┐
   │  firms   demo-census-midmarket-firms-us-2022 = 120,000  (regulator, SUSB)│
   │          ⚠ 100–999 employees ONLY — mid-market (narrower on segment)      │
   │  × spend demo-midmarket-ai-sales-spend-2024 = $260,000/firm-yr           │
   │  ───────────────────────────────────────────────────────────────────────│
   │  120,000 × $260,000  =  ~$31.2B / yr                                      │
   └───────────────────────────────────────────────────────────────────────────┘
   │
   ▼
TAM   scenarios: [ $2.0B (cost_efficiency), $31.2B (revenue_generation) ]
      ┌─ CONVERGENCE  lower $2.0B · higher $31.2B · spread ~15× (WIDE)
      │   (fires because ≥2 INDEPENDENT method families sized the same concept)
      └─ SCOPE REPORT  why they disagree, snap-to-truth:
            • Method A persona = wholesale/mfg reps only  → NARROWER (excludes
              services reps, SOC 41-3000)
            • Method B segment = mid-market firms only    → NARROWER (excludes
              SMB + enterprise)
         → neither is "wrong" — they size different slices, and the page SAYS SO
```

**What this shows — the whole thesis in one screen:**
- A TAM is a **tree of competing scenarios**, never one number.
- **Convergence** is the trust signal: two independent methods, a stated spread.
- The **scope guard** turns a scary 15× disagreement into an *explanation*
  (different slices of the market), instead of a GPT wrapper that would confidently
  pick one and hide the rest.
- Note the **tier mix**: persona/firm counts are `regulator` (hard, BLS/Census),
  the ACV/spend are `analyst-paraphrase` (softer) — the UI shows that mix so the
  reader knows which inputs to trust.

---

## What-if (Strata Live) on any of these

Click a node → override → re-runs live, mints a *new* `/tam/<hash>`:

```
build_tam(concept=demo-ai-sales-ops-us,
          primitive_overrides={ demo-ai-sales-ops-acv-per-seat-2024: $2,000 })
   → Method A: 1,460,000 × $2,000 = ~$2.9B   (was $2.0B)
   → banner: USER_OVERRIDE · uses_synthetic=true
   → NEVER persisted as a primitive (Q20 wall) · new hash, shareable
```

Or re-point an input to a *different sourced primitive* (`framework_assumptions`)
— e.g. swap the wholesale-only persona for the broad 1.9M sales-rep count
(`demo-acs-sales-reps-us-2024`, analyst-paraphrase) and watch Method A jump while
the banner flips from regulator to analyst-paraphrase.

---

## The reuse table (why frameworks are the IP)

One framework, many markets — each variant just re-binds slugs, zero new code:

| Framework | Lens | Markets it sizes today (via `variants:`) |
|---|---|---|
| `cost-efficiency-full-displacement` | cost_efficiency | coding assistants · legal AI · PC doc-gen · GTM ops · QA automation · cyber · insurance knowledge · 2 demos |
| `throughput-take-rate` | platform_throughput | PC payments · voice-AI infra · EEG diagnostics · memory infra · multimodal infra |

25 frameworks total in `data/frameworks/`, across all 6 lenses. Adding a market =
write a concept + bind primitives to an existing framework variant. **No bespoke
math per company** — that's the leverage.

---

*Grounding: every number above is from `data/concepts/`, `data/composites/`,
`data/primitives/`, `data/frameworks/`. Arithmetic is the literal framework
`formula` applied to the variant's bound primitive values.*
