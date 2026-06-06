# Strata, explained in plain English (with analogies you can repeat)

> No jargon. Every concept is a kitchen / everyday analogy. If someone asks "how
> does it work," say the analogy first, then the one-line technical version.

---

## The big picture: we're a "nutrition label + recipe" for market-size numbers

When a restaurant says "this dish is healthy," you just have to trust them. When
a packaged food says it, there's a **nutrition label** (every ingredient) and you
could in principle re-make it from the **recipe**.

Everyone else in market research is the restaurant: "the AI market is $50B, trust
us." **Strata is the nutrition label + recipe.** We show every ingredient (where
each number came from), the exact recipe (how they combine), and a tamper-proof
seal so you can check it yourself.

> Technical: every TAM exposes its sourced primitives, the framework formula, and
> a content hash.

---

## Layer 1 — Primitive = "one grocery item with a receipt"

A **primitive** is a single fact with proof of purchase. Not "flour-ish, about a
bag" — it's *"2 lbs of flour, bought at Store X, receipt #123, on March 3rd."*

In our world: not "the sales-rep market is big" — it's *"1,460,000 US
wholesale/manufacturing sales reps, from the Bureau of Labor Statistics, 2024,"*
with a link and a tamper seal.

One item. One source. You could go re-buy it and get the same thing.

> Technical: `AtomicPrimitive` = value + unit + source_url + snapshot_sha256.

---

## Layer 2 — Composite = "you can add flour to flour, never flour to eggs"

Sometimes you combine ingredients of the **same kind**. 2 cups flour + 1 cup
flour = 3 cups flour. Fine. That's a **composite**.

But you can **never** say "3 cups flour + 2 eggs = 5 things." Different units.
That's nonsense. Strata forbids it by design.

Real example: "software-publisher engineers (people) + computer-systems-design
engineers (people) = total engineers (people)." Both are *people*, so you can add
them. ~3.0M engineers.

> Technical: composites do same-unit set operations only (union/filter). No
> unit-crossing math here — ever.

---

## Layer 3 — Framework / "lens" = the recipe (where units are *allowed* to cross)

The **recipe** is the only place you're allowed to combine different things into
something new: *"3 eggs × 2 minutes per egg = 6 minutes."* Eggs and minutes-per-egg
crossed to make minutes.

Our recipe: *"3.0M engineers × $300 per engineer per year = $900M market."*
People × dollars-per-person = dollars. **That** crossing is the math that produces
a TAM.

**The crucial rule:** a Strata recipe has **no secret amounts.** A normal recipe
might say "add a pinch of salt" — unsourced, made up. Ours can't. *Every* quantity
in the recipe must point to a labeled, sourced ingredient. You cannot sneak in
"assume 20% adoption" — that 20% has to be a real primitive with a receipt.

> Technical: frameworks do all unit-crossing arithmetic; every input is a citable
> primitive slug; no scalar defaults; the validator rejects bad unit-wiring at load.

### Why "six lenses"? = six standard recipe shapes for six kinds of business

You don't bake bread and grill steak the same way. Different dishes, different
methods. Same in markets:

| Lens (recipe shape) | Plain meaning | Like sizing… |
|---|---|---|
| cost_efficiency | how many workers × cost per worker | Copilot, Glean |
| revenue_generation | how many companies × what they spend | Brex, Rippling |
| latent_demand | population × how many adopt × what they'd pay | Uber |
| platform_throughput | money flowing through × the cut you take | Stripe, Visa |
| bundle_consolidation | total spend × how much one tool absorbs | Notion, Linear |
| productivity_uplift | workers × the value the tool adds | Cursor |

> Technical: `AnalysisLens` enum — 6 structurally distinct math shapes. The
> formula is a real string run through a safe calculator that knows `min`, `max`,
> and S-curve functions, so "adoption ramps then saturates" is expressible without
> anyone typing a magic number.

---

## Layer 4 — TAM = "measure the room twice and show both numbers"

Most people give you **one** market number and hide how they got it. That's a
single tape-measure reading you can't check.

Strata measures the room with a **tape measure AND a laser** and shows you both.
If they agree (10.0 ft and 10.2 ft) → you're confident. If they wildly disagree
(10 ft vs 150 ft) → something's wrong, and *that's worth knowing*.

Real example — AI sales-ops, sized two independent ways:
- **Method A** (count the workers): 1.46M reps × $1,400 = **$2.0B**
- **Method B** (count the companies): 120,000 firms × $260k = **$31.2B**

A 15× gap. A GPT wrapper would confidently pick one and hide the other. **We show
both and explain the gap:** Method A only counted *wholesale* reps (left out
services reps), Method B only counted *mid-size* firms (left out small + huge).
Neither is wrong — **they measured different rooms.** We say so on the page.

> Technical: a TAM is a *scenario tree*, never a scalar. When ≥2 independent
> methods size the same concept, the evaluator emits a `convergence` object
> ("lower $X · higher $Y · spread N×"), and the scope guard explains the spread.

**This is the whole pitch in one line:** *disagreement gets a page, not a footnote.*

---

## Hashing = "a tamper-proof tracking number" (there are two)

**Seal #1 — the wax seal on the source (snapshot hash).** When we grab a source
document, we press a unique wax seal onto it. If anyone later edits that document,
the seal won't match — we instantly know the number drifted from its source.

**Seal #2 — the fingerprint of the whole calculation (state hash).** Take the
entire recipe + all the exact ingredients, run it through a fingerprint machine,
and you get a unique code that becomes the permanent link: `/tam/abc123…`.

The magic: **same inputs always make the same fingerprint** (so the same market
math gives you the same shareable link), and **changing any single number gives a
totally different fingerprint** (a new link). It's exactly like a git commit hash,
or a package tracking number that's unique to that exact package.

> Technical: `mint_state_hash` = sha256 of the canonicalized (sorted-keys) math
> payload. Display-only fields are excluded so cosmetic changes don't change the link.

---

## Source tiers = "how much do you trust who told you?"

Not all sources are equal. We label every number by who said it:

```
Government data        = a notarized legal document   (regulator)  ← trust most
Analyst quote          = a journalist paraphrase       (analyst-paraphrase)
Educated estimate      = clearly stamped "MODELED"     (community-modeled)
Betting-market odds    = interesting, NEVER used in math (prediction_market) ← quarantined
```

Two honesty rules people love:
1. **Betting odds and random web comments are quarantined** — they're shown but
   *physically can't* enter a TAM calculation.
2. An estimate **can't disguise itself as hard data.** The "MODELED" stamp is
   applied *automatically from the source type*, not chosen by whoever wrote the
   file. The file literally cannot lie about how soft its number is.

> Technical: 9 tiers; `NON_SIZING_TIERS` are blocked from the evaluator;
> `ProvenanceClass` is *derived* from the tier, so a loud MODELED banner is forced.

---

## The guards = "a bouncer who won't let a made-up number into the club"

The scary version of an AI tool is one that confidently invents a number and
sources it to a fake website. Our bouncer stops that at the door:

1. **Real address?** The source's website must be a real, known place (gov site,
   known data provider). "strata.internal" or a hallucinated URL → rejected.
2. **Does the math even make sense?** A market size must have *exactly one* dollar
   amount in it. Zero dollars = "that's not a market." Two dollar amounts
   multiplied = "you double-counted money" → rejected.
3. **Is the number sane?** Negative, infinite, or absurdly huge → flagged.
4. **If it's a guess, it wears a stamp.** Anything the AI synthesized gets a loud
   "ESTIMATE" banner so nobody downstream mistakes it for fact.

The point: **an AI hallucination can never quietly become a trusted, citable
number.** That's the single most important thing we built.

> Technical: host allowlist (`citations.py`) → tier-from-host → unit guard
> (`units.py`) → plausibility verifier (`verify.py`). No LLM-projected primitives, ever.

---

## MCP = "a drive-through window built for robots"

Humans use a website. **AI agents** (Claude, Cursor, etc.) need a window built for
them — that's **MCP**. An agent pulls up and asks "is this market claim true?" and
gets back either a sourced, hash-pinned answer or an honest *"I don't have that"* —
it will not make something up.

Why it matters strategically: **AI agents are the customers who restock our
pantry.** They ask questions all day, propose numbers, our bouncer checks them, and
the good ones grow the data bank — without us hiring a single analyst. Humans
won't contribute at scale; agents will.

> Technical: 12 MCP tools; `resolve_market` is registry-first and LLM-free
> (matched: true/false, never invents).

---

## Connectors = "the supply trucks that restock the pantry"

Where do the real ingredients come from? **Connectors** are delivery trucks
wired into government and data APIs — Bureau of Labor Statistics, the Fed, Census,
the SEC, World Bank, etc. They drive out, pick up fresh official data, seal it,
and stock the pantry. 23 trucks built, 13 actively delivering today.

> Technical: 23 typed connectors → disk-cached → sha256-pinned → promoted to the
> committed data bank.

---

## If you only remember five sentences

1. **We're the nutrition label + recipe for market numbers** — every figure shows
   its source and its math, sealed so you can check it.
2. **Primitives are sourced facts; composites add same-kind facts; frameworks are
   the recipes that cross units into a dollar TAM** — and recipes have no secret
   made-up amounts.
3. **A TAM isn't one number — it's the room measured several ways, with the
   disagreements explained** (that's "convergence").
4. **Two tamper-proof seals** — one on each source, one on the whole calculation —
   make every answer reproducible and every source verifiable.
5. **A bouncer stops AI hallucinations from ever becoming trusted numbers**, and
   **AI agents (via MCP) are the flywheel that grows the pantry.** That's the moat.
