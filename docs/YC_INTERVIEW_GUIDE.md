# Strata — YC Interview Guide

Interview: **Sunday, June 7, 2:30 PM PDT, Zoom**. Join 10 min early.
Interviewers: Arkash + Tushar. Format: ~10 min, rapid-fire, partners interrupt.

> The interview is not a pitch. It's a stress test. They're checking: do you
> understand your market, are you fast, are you honest, will you keep going.
> Answer in **one sentence, then stop.** Let them drive.

---

## 0. The one-liner (memorize, say it the same way every time)

> **"Strata is the open, sourced data layer for market sizing — every TAM number
> traces back to a regulator-grade source, and AI agents can build sizings
> against it through an MCP."**

If they want it shorter: **"Plaid for market data — sourced primitives that
agents and analysts compose into defensible TAMs."**

---

## 1. What makes Strata good (the core question you asked)

Five things, in priority order. Lead with #1 and #2 — they're the moat.

**1. Every number is sourced and hash-pinned — it cannot lie.**
IBISWorld/Statista/Gartner hand you a PDF with a number and no way to check it.
Strata's atomic unit is a *primitive*: one source, one number, a `source_url`,
a source tier (regulator > aggregator > analyst), and a `snapshot_sha256` of the
page it came from. A TAM isn't a scalar — it's a scenario tree where you can
click any input and walk to the government filing it came from. **The product's
whole architecture is built so a number can't misrepresent itself.** That's the
thing the incumbents structurally cannot do.

**2. We separate the *number* from the *recipe*.**
- **Primitives** = atomic sourced facts (214 of them, live-ingested from 13
  regulator/aggregator APIs: FRED, Census, BLS, EDGAR, World Bank, CMS, EIA,
  openFDA…).
- **Frameworks** = parameterized recipes that combine primitives into a TAM
  (e.g. `personas × cost`, `volume × take_rate`). No scalar defaults — every
  input is a citable primitive.

This means a TAM is *recomputable and forkable*. Swap one input, get a new
hash-pinned sizing. Incumbents sell you a frozen conclusion; we sell you the
machine that made it.

**3. We size the *scope*, not just the number.**
A `MarketScope` object (NAICS vertical, SOC persona, firm-size segment, ISO
geo). A scope guard flags when a number's real scope is narrower/broader than
the market you declared. On our demo this explains a $2.0B-vs-$31.2B spread:
one input is wholesale-only, the others are mid-market-only. **We make
disagreement legible** — that's what an analyst actually pays for.

**4. The AI-agent wedge — "Statista for agents."**
12 MCP tools. An agent (Claude, etc.) can `list_primitives`, `build_tam`,
`get_connector_data` live. As VCs/operators move to agent-driven research, the
bottleneck is *sourced, structured, machine-readable* market data. We're the
supply.

**5. Open-source + community-curated → compounding moat.**
Apache-2.0. Contributions are validator-gated (regulator/first-party
auto-accept; rest queue for review). Every primitive added makes every
framework more powerful. The data bank grows; the incumbents' PDF library
doesn't.

> **If you only get one sentence:** *"Strata is good because every TAM number is
> traceable to a regulator-grade source and recomputable — incumbents sell a
> frozen PDF, we sell the sourced machine that built it, and agents can drive it."*

---

## 2. The standard YC questions — crisp answers

**"What do you make?"**
> A sourced data layer for market sizing. Analysts and AI agents compose
> regulator-grade primitives into TAMs where every number links to its source.

**"Who's the customer / who pays?"**
> VCs and operators doing TAM work. Today they pay $20k–$50k/yr for IBISWorld or
> Statista and still can't audit the number. (Have a real seat/price target
> ready — see §5.)

**"How big is the market?"** *(yes, they'll ask you to size your own market —
this is the meta-test, nail it)*
> Market research is a ~$80B+ industry; the syndicated-data slice (IBISWorld,
> Statista, Gartner, Forrester) is several billion. Our wedge is the VC + corp-dev
> + strategy-desk seat. **And we'll size it live in the product if you want.**
> *(Know your bottoms-up: # of VC firms × seats × price.)*

**"Why now?"**
> Two things just became true: (1) regulator APIs are finally rich enough to
> auto-build a sourced data bank, and (2) AI agents need structured market data
> and have nowhere to get it. We sit exactly on that intersection.

**"Why you two?"**
> [Arkash + Tushar — your actual background: shipping speed, domain, why this
> problem.] Point at velocity: 798 backend tests, 23 connectors, full product
> shipped solo/duo. *(Fill this in honestly before the call.)*

**"What's your unfair advantage / moat?"**
> The sourced, hash-pinned data bank compounds with every contribution and every
> connector, and it's the only market-data source built to be machine-consumed by
> agents. A PDF library can't be forked or recomputed; ours can.

**"How do you make money?"**
> Open core. The data + framework engine is open; we charge for hosted access,
> private connectors (your CRM/HubSpot data → org-private primitives), agent/MCP
> metering, and team seats. *(Phase 2 in the roadmap: API keys + metering +
> subscriptions.)*

**"What have you learned / what's the traction?"**
> [Be honest. If pre-revenue: say what you've validated, what's deployed, who
> you've shown it to and what they said.] Deployed on Railway + Vercel, live MCP,
> 13 producing connectors.

---

## 3. The 60-second demo (have it loaded and ready)

If they ask to see it, **don't narrate the codebase — show the payoff:**

1. `/build?q=` a market → pin the scope.
2. Hit Size → `/tam/<hash>`. Point at the **convergence banner**: "two
   independent method families, spread 3×."
3. Click one input → walk to the **regulator source URL**.
4. Re-bind an input on `/build/graph`, recompute → new shareable hash.
5. One line: *"Every number here links to a government filing, and an agent can
   do this same thing through our MCP."*

Have the prod URL open in a tab **before** the call. Test it 30 min prior —
note the prod-seed/redeploy caveat in CLAUDE.md, make sure the demo surface is
actually live.

---

## 4. Hard questions — and honest answers

**"Isn't this just a wrapper on free government APIs?"**
> The APIs are free and unusable raw — they're 23 incompatible schemas, no unit
> system, no provenance, no way to compose them. The value is the typed connector
> layer, the unit-checked framework engine, and the scope guard that makes a
> sizing defensible. Plumbing free water is still a business.

**"Can't an LLM just do this?"**
> An LLM *hallucinates* market numbers — that's the exact failure we designed
> against. We have a hard rule: no LLM-projected primitives, ever. The LLM helps
> *navigate*; it never invents a number. That honesty is the product.

**"Why open source — won't you get cloned?"**
> Open source is the distribution and trust strategy — analysts won't trust a
> black-box number. The moat isn't the code, it's the curated sourced data bank
> and the contribution flow, which compound. AWS didn't lose to "Postgres is open."

**"Market research feels like a slow, sleepy market."**
> It's sleepy because the incumbents sell frozen PDFs to humans. The unlock is
> agents — there's a brand-new buyer (autonomous research agents) that needs
> structured sourced data and literally cannot use a PDF.

**"What stops Statista/Gartner from doing this?"**
> Their business *is* the opaque PDF — sourced, forkable numbers cannibalize the
> thing they sell. Classic innovator's dilemma. And they have no agent surface.

**Trap: if you don't know a number, say so.**
> "I don't have that number in front of me — I'd rather not make one up." YC
> respects this enormously, and it's literally your product's whole thesis.

---

## 5. Pre-call homework (do these before Sunday)

- [ ] **Fill in the founder story** (§2 "Why you two") — Arkash + Tushar, real
      backgrounds, why this problem is yours.
- [ ] **Nail one bottoms-up market number**: (# target firms) × (seats) ×
      (price). Write it on a sticky note.
- [ ] **One concrete price point**: what does a seat cost? ($X/seat/mo or
      $Y/yr). Have a number.
- [ ] **Traction sentence**: deployed where, shown to whom, what they said. One
      sentence, true.
- [ ] **Load the live demo** in a browser tab; verify prod seed is up.
- [ ] **Answer the extra YC application questions** at apply.ycombinator.com
      *(required before the interview).*
- [ ] **Decide who answers what.** Two founders: one leads each answer, the
      other adds only if it helps. Never both talk at once. Never contradict
      each other.
- [ ] Re-read the official **YC Interview Guide** (linked in the email).

---

## 6. Interview behavior — the meta-rules

- **Answer in one sentence, then stop.** They'll ask for more if they want it.
  Rambling is the #1 way founders blow this.
- **Speed > polish.** Talk fast, think fast, no preamble. Skip "great question."
- **Don't fight the question.** If they push, concede the real point and show
  you've thought past it.
- **Know your numbers cold** — TAM, price, growth, tests-as-proof-of-velocity.
- **Be honest about what's not built.** "Not yet — here's the plan" beats
  overselling. Your product's entire pitch is honesty; embody it.
- **Two-founder discipline:** decide the division of labor in advance; never
  talk over each other; never visibly disagree.
- **Don't post on social media** about the interview (YC asked).

---

## TL;DR — the three sentences that win this

1. *"Strata is the sourced, open data layer for market sizing — every TAM number
   links to a regulator-grade source and is recomputable."*
2. *"Incumbents sell a frozen PDF you can't audit; we sell the sourced machine
   that built the number, and it compounds with every contribution."*
3. *"AI agents need structured market data and have nowhere to get it — we're
   the supply, exposed through an MCP."*
