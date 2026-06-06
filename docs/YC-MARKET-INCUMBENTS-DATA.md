# Strata — Market · Incumbents · Data (YC, succinct)

> Answers the market-size / competition / data cluster of the YC bank. Industry
> $ figures are **public ballparks — verify before quoting precisely** (our own
> rule: don't state invented numbers as fact). Data-moat numbers are real repo state.

---

## How big is the market? (How many $B · how fast · how do you become $1B)

**Layered, the way we'd size it on our own platform:**

```
TAM  Market & competitive intelligence (IBISWorld/Statista/Gartner/CBI/PitchBook
     replacement)                                          ~$80–100B / yr*
       └─ + the new layer: every AI agent that emits a market
          claim needs it verified → grows with agent adoption
SAM  VCs, corp-dev, strategy/ops teams + AI products that
     surface market numbers (English-speaking, API-reachable)  ~$5–10B*
SOM  Seats + API/MCP metering we can win in 3 yrs               ~$50–150M*
```
\* ballpark, needs real sourcing before a pitch.

**The one-liner:** legacy research is a **$80B+ report business growing low-single-digit**;
the wedge underneath it — **verifying AI-generated market claims via MCP** — grows
with **AI agent adoption (30%+/yr)**, not with analyst headcount. We ride the fast curve.

**$1B path:** seats → API/MCP metering (per-verification) → become the **default
trust layer every AI agent calls** before asserting a market number. Usage scales
with agents, not with our sales team.

---

## Who are the incumbents / competitors? (different · better · easy to copy · why now)

```
                         What they sell          Where they break
IBISWorld / Statista     static PDF reports      stale, unsourced at the number
Gartner / Forrester      analyst opinion         $$$, slow, not machine-readable
CB Insights / PitchBook  private-market data     no defensible public-TAM math
GPT / Perplexity wrapper instant answers         CONFIDENTLY HALLUCINATES, no pin
```

**What's different (one breath):** they sell *a number in a PDF*; we expose the
**primitives + the recipe + a content hash**, so the number is *reproducible and
checkable*. The math is transparent (every framework input is a citable slug, no
hidden assumptions), and disagreement between methods **gets a page, not a footnote**.

**Why better:** an LLM gives you a number you can't trust; an analyst report gives
you a number you can't *re-derive*. We give a number you can **verify line-by-line
and re-run** — `snapshot_sha256` pins the source, `state_hash` pins the computation.

**Competitor we fear most:** a foundation-model lab bolting "cited market sizing"
onto their agent. Our defense is the **trust fence + the framework IP** (the recipes),
not the raw data — data is commodity, *defensible assumptions are not*.

**Why isn't someone already doing this / easy to copy?** The hard part isn't
scraping numbers — it's the **guards that refuse to let a hallucination become a
citable primitive** (host-derived tier, unit guard, verbatim guard, no
LLM-projected numbers). That's the unsexy, load-bearing work nobody wants to do.
Copying the UI is a weekend; copying the *honesty fence* is the whole company.

---

## The data (what we actually have — real repo state)

```
293   atomic primitives        each: value + unit + source_url + sha256 pin
 25   frameworks (5→25)         6 distinct lens math-shapes, zero scalar defaults
 30+  concepts                  competing measurements per concept
 87   sources                   tier derived from host class, never the LLM
 23   typed connectors          13 producing committed primitives, live-verified
  9   source tiers              2 quarantined, modeled tiers loudly fenced
202   prediction-market signals quarantined — NEVER feed a TAM (honesty by design)
```

**The moat in the data isn't volume — it's structure + provenance:**
- Every number is **atomic, sourced, and content-hash pinned** (re-derivable).
- The **frameworks are the IP** — parameterized TAM recipes, not scraped figures.
- **Agents are the contributor flywheel:** they query via MCP, propose numbers,
  the guards gate them → the bank grows without us hiring analysts.

**Key thing outsiders don't get:** the *most valuable* numbers (capture rate,
ACV, adoption) are inherently *modeled*, not sourced — so a binary "every number
is sourced" fence makes the best numbers look the worst. The real product is a
**graded trust fence**: own the *defensible-assumption layer*, not just the
already-public regulator data everyone can scrape.

---

## Rapid-fire (drop-in answers)

- **How big?** ~$80–100B legacy research TAM*, but we ride the *AI-verification*
  wedge underneath it, which grows with agent adoption, not analyst headcount.
- **How fast growing?** Legacy: low single digits. Our layer: tracks AI-agent
  adoption (~30%+/yr)*.
- **How different?** We ship the primitives + recipe + hash, not a PDF. Verifiable
  and re-runnable, not just readable.
- **Better how?** LLM = untrustworthy, analyst report = un-re-derivable. We're both
  trustworthy *and* re-derivable.
- **Easy to copy?** UI yes, the trust fence no — that's the company.
- **Why now?** Agents now emit market claims at scale and nobody can verify them.
  That demand didn't exist 2 years ago.
- **Competition feared most?** A model lab adding cited sizing to its agent — we
  beat it on framework IP + the honesty fence, not raw data.

\* public ballpark — source properly before quoting in the application.
