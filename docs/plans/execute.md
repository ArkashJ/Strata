# Plan: Primitives ingestion architecture

## Context

Strata's defensibility *is* the primitive library: atomic numbers, sourced,
content-hash-pinned, with a transparent chain of custody. The data-layer
brainstorm ([`docs/07`](../../Desktop/work/VC_stuff/docs/07-data-layer-brainstorm.md))
locked **what** a primitive looks like — eight source tiers (Q26 + Q37), pinned
snapshots (Q5), no LLM-projected values (Q20), tier-gated auto-publish (Q25),
source-class-aware refresh (Q5), licensing-by-tier (Q26). It did **not**
specify **how** we actually get the data.

Codebase is a clean slate (Explore confirmed): no HTTP clients, no API
wrappers, no LLM-extraction code, no scrapers; `data/` directories are empty
placeholders; `httpx` is only in dev deps. This plan designs the ingestion
pipeline from scratch — vendors to pick, modules to build, sequencing across
v0.2 → v0.5.

User explicitly asked about **Parallel · Exa · Perplexity · Yutori** + open
databases. All four belong in different slots, not as alternatives to each
other.

---

## Source tier → ingestion method matrix

The eight source tiers from 07 Q26 + Q37, mapped to *how* we actually fetch.
Each row is a distinct ingestion path with its own validator profile.

| Tier | Examples | Fetch method | Snapshot artifact | Auto-publish (Q25)? |
|---|---|---|---|---|
| `regulator` | BLS, Census, FRED, FMCSA, EDGAR/SEC, NAIC, CMS, FDA, EUROSTAT | **Direct API** (free, JSON/XBRL) | Pretty-printed JSON, sha256 | **Yes** if all validators pass |
| `first_party` | S-1 / 10-K / 10-Q filings, Stripe/Visa blogs, conference disclosures | **Direct API** (EDGAR) or **PDF/HTML extraction** | Raw PDF/HTML + extracted MD, both hashed | **Yes** for EDGAR-sourced; PR review for blog/PDF |
| `aggregator` | World Bank, OECD, IMF, FRED-derived, Eurostat aggregates | **Direct API** (free, JSON) | Pretty-printed JSON, sha256 | PR review (aggregator may re-cut sources) |
| `analyst` | Gartner, IBISWorld, Statista, S&P, Forrester | **Cite-only metadata stub** per Q26 — no value reproduction | Link + access date, no body | PR review only |
| `onchain` | Hyperliquid, Uniswap (Dune SQL, The Graph, RPC) | **Dune API** + **The Graph** subgraphs + **viem/web3** RPC | Query + result JSON, sha256 | **Yes** — chain is the source |
| `prediction_market` | Polymarket, Kalshi, PredictIt | **REST API** | Market snapshot JSON + liquidity, sha256 | PR review (liquidity must be checked) |
| `community` | Vetted contributor PR | **PR-submitted YAML** | Whatever the contributor cited | PR review |
| `community-modeled` | Analog-penetration models | **Composite-primitive derivation** (no external fetch — it's a model) | The model recipe itself | PR review + 12-mo expiry per Q20 |

The hard ingestion question is **regulator / first_party / aggregator** where
the data exists but the bridge from source → structured primitive is what's
expensive. That's where Parallel / Exa / Perplexity / Yutori come in — as
the **discovery + extraction** layer feeding the structured pipeline, never
as the source of truth itself.

---

## Vendor selection

Per the web research (May 2026), each vendor occupies a different slot.
**This is not a pick-one decision.** They compose.

### Parallel AI — primary deep-research engine

**Use for:** "Find the latest authoritative value for `<concept>` from
public sources, with structured JSON output and per-field citations."

- **Task API** structures markdown into a JSON schema with **per-field
  citations + confidence scores + reasoning chains**. Exactly the shape
  Strata's primitive record needs (`value` + `source.url` + tier hint).
- Reported **48% accuracy** on deep-research benchmarks vs Perplexity 8%,
  GPT-4 browsing 1% — the strongest available for "extract a verified
  fact from the web."
- **Pricing:** $5/1000 lite runs; $1/1000 URLs on Extract API. Cheap
  enough to run on every concept we want to populate.
- **SOC 2 Type 2 + zero data retention** — fine for an open-data project,
  irrelevant for licensing.
- **Slot:** auto-fill new concepts (Q10 long-tail clustering), backfill
  competing measurements (Q9 disagreement view).

### Exa — semantic discovery + content extraction

**Use for:** "What URLs exist on the web for this concept, and what do
they actually say?" — the *discovery* layer that finds candidate sources
before Parallel extracts from them.

- Semantic search (neural, not keyword) trained on link-prediction;
  better recall than Google CSE for "find me primary sources about X."
- **Content Extraction API** returns clean parsed text + highlights — the
  raw material for our snapshot blobs.
- **Research API** also handles end-to-end with citations (overlaps with
  Parallel; cheaper per-query but less accurate).
- **Slot:** source-discovery for a new concept ("list me 5 candidate URLs
  for US P&C carrier count"). Hand Parallel the URLs for structured
  extraction.

### Perplexity Sonar Pro — cheap commodity layer

**Use for:** spot-checks, second opinions, redundant validation runs,
"is this primitive still current?" checks.

- Inline citations on every answer; **JSON mode** + structured output;
  search-context-level knob (Low/Med/High).
- **Sonar tier (lightweight):** sub-second factual lookups, cents per
  query — perfect for refresh-cadence "has this number moved?" probes
  before triggering an expensive Parallel re-run.
- **Slot:** the cheap probe in the **refresh-cadence loop** (Q5). If
  Sonar says "the latest BLS OES is unchanged," skip the expensive
  Parallel run. If Sonar reports a delta, trigger Parallel for the
  authoritative re-extract.

### Yutori — scheduled monitoring + browser automation niche

**Use for:** two specific cases, otherwise skip.

1. **Scouting API** (`$0.35/scout-run`): continuous monitoring of a
   specific URL or query with a configurable schedule. Maps cleanly onto
   Q5's "refresh cadence is source-class-aware" — regulator URLs get a
   weekly Scout; analyst URLs never. This is the only vendor with a
   first-class *scheduled monitoring* primitive.
2. **n1 + Browsing API**: state-of-the-art browser-automation model
   (91% Navi-Bench v1, beats Claude Opus). Used **only** for sources that
   require login / heavy JS / multi-step interaction (rare for our
   regulator-heavy diet). Most data is public + scrapeable without this.

- **Slot:** Scout for refresh-cadence; Browsing API kept on the shelf
  for awkward sources that other tools can't reach.

### Open-data direct APIs (no vendor)

These are the **bulk of the primitive library** by volume and the
cheapest by far — every one is free or near-free:

| Source | Type | Notes |
|---|---|---|
| **BLS** (bls.gov/developers) | API + JSON | OES, employment, wages. Free; rate-limited |
| **Census Bureau** | API + JSON | Demographics, business stats, ACS |
| **FRED** (St. Louis Fed) | API + JSON | Macro indicators, interest rates, CPI |
| **EDGAR / SEC** | API + XBRL + full-text | S-1 / 10-K / 10-Q + financial XBRL |
| **FMCSA** | API + bulk download | Carrier registration data |
| **NAIC** | bulk download | Insurance filings |
| **CMS / FDA / FCC / USPTO** | API or bulk | Healthcare, drugs, telecom, patents |
| **World Bank / OECD / IMF / Eurostat** | API + JSON | International aggregates |
| **OpenAlex** | API + JSON | Academic citations |
| **Wikidata** | SPARQL | Structured knowledge |
| **Dune** | SQL API | Onchain queries |
| **The Graph** | GraphQL subgraphs | DeFi protocol indices |
| **Polymarket / Kalshi** | REST API | Prediction markets |

Strata's bulk diet is these direct APIs. Parallel / Exa / Perplexity /
Yutori are for the long tail and the discovery step, not the staple.

### Supporting tooling

- **Firecrawl** or **Jina AI Reader** — URL → clean markdown. Used inside
  the Fetch step when a source is HTML/PDF and we want a deterministic
  snapshot independent of an LLM. Cheap, deterministic, good for
  reproducibility (Parallel/Exa may rerank differently across runs).
- **`pypdf`** + **`unstructured.io`** — PDF parsing for SEC filings,
  regulator PDFs, S-1s.
- **`httpx`** (already in dev deps) — promote to runtime dep for the
  direct-API path.

---

## Pipeline architecture

```
                  ┌─────────────────────────────────────────┐
                  │  TRIGGER                                │
                  │  • new concept created                  │
                  │  • Scout/Sonar detects upstream change  │
                  │  • scheduled refresh tick               │
                  │  • contributor PR (community tier)      │
                  └────────────────────┬────────────────────┘
                                       │
                  ┌────────────────────▼────────────────────┐
                  │  1. DISCOVER                            │
                  │  Exa search + tier hint                 │
                  │  → candidate (url, tier_guess) list     │
                  └────────────────────┬────────────────────┘
                                       │
                  ┌────────────────────▼────────────────────┐
                  │  2. FETCH                               │
                  │  • direct API for regulator/aggregator  │
                  │  • Firecrawl/Jina for HTML/PDF          │
                  │  • Dune/Graph/RPC for onchain           │
                  │  • Polymarket/Kalshi REST               │
                  └────────────────────┬────────────────────┘
                                       │
                  ┌────────────────────▼────────────────────┐
                  │  3. SNAPSHOT                            │
                  │  • sha256 over canonical bytes          │
                  │  • blob stored sha256-named             │
                  │  • licensing guard: paywalled →         │
                  │    metadata stub only (Q26)             │
                  └────────────────────┬────────────────────┘
                                       │
                  ┌────────────────────▼────────────────────┐
                  │  4. EXTRACT                             │
                  │  • API: structural pluck (no LLM)       │
                  │  • PDF/HTML: Parallel Task API w/       │
                  │    explicit JSON schema + citations     │
                  │  • produces draft primitive YAML        │
                  └────────────────────┬────────────────────┘
                                       │
                  ┌────────────────────▼────────────────────┐
                  │  5. VALIDATE (Q25 strict gate)          │
                  │  • schema  • unit-type  • snapshot-hash │
                  │  • URL liveness  • sanity envelope ±N%  │
                  │  • as_of in past  • sig-fig sanity      │
                  │  • licensing-class consistency          │
                  └────────────────────┬────────────────────┘
                                       │
                  ┌────────────────────▼────────────────────┐
                  │  6. TIER-GATE (Q25)                     │
                  │  if tier ∈ {first_party, regulator,     │
                  │              onchain} AND validators OK │
                  │    → auto-merge to data/primitives/     │
                  │  else → open PR for human review        │
                  └────────────────────┬────────────────────┘
                                       │
                  ┌────────────────────▼────────────────────┐
                  │  7. CONCEPT-ATTACH                      │
                  │  • match concept_slug (seed library)    │
                  │  • else: stage to unattached pool       │
                  │    (Q10 LLM clustering)                 │
                  └────────────────────┬────────────────────┘
                                       │
                  ┌────────────────────▼────────────────────┐
                  │  8. SCHEDULE NEXT REFRESH (Q5)          │
                  │  • regulator: weekly Yutori Scout       │
                  │  • first_party (filings): event-based   │
                  │    (EDGAR Atom feed)                    │
                  │  • analyst: never                       │
                  │  • onchain: hourly Dune                 │
                  │  • prediction_market: daily             │
                  └─────────────────────────────────────────┘
```

**Important non-rules** that fall out of this:
- **No LLM-projected primitives** (Q20). The Extract step never *generates*
  a value — it pulls one out of cited raw bytes. If Parallel's Task API
  returns a field without a citation, the validator rejects it.
- **Snapshot is always raw bytes**, not the LLM output. The Parallel
  extraction is a *parse* of the snapshot, not a replacement for it. If
  Parallel hallucinates, the snapshot still has the truth and human review
  catches it.
- **Refresh cadence is source-class-aware**, not per-primitive. A change
  in BLS OES triggers re-evaluation of *every* primitive citing it, with
  sensitivity-aware filtering downstream (Q5).

---

## Module layout (`backend/src/strata/ingest/`)

Build from scratch — clean slate per Explore. Recommended package:

```
backend/src/strata/ingest/
  __init__.py
  triggers.py        # CLI + cron entry points; emit IngestJob events
  discover.py        # Exa search wrapper → candidate URLs
  fetch/
    __init__.py
    api_client.py    # generic httpx + retry; per-source modules below
    bls.py           # BLS API
    fred.py          # FRED API
    edgar.py         # SEC EDGAR
    census.py        # Census Bureau
    world_bank.py    # World Bank
    dune.py          # Dune onchain SQL
    the_graph.py     # The Graph subgraphs
    polymarket.py    # Polymarket REST
    web.py           # Firecrawl/Jina fallback for HTML/PDF
  snapshot.py        # sha256 + blob store (filesystem at v0.2; S3 at v0.5)
  extract/
    __init__.py
    structural.py    # JSON/XBRL → primitive (no LLM)
    parallel.py      # Parallel Task API wrapper
    pdf.py           # pypdf + unstructured + LLM fallback
  validate.py        # Q25 layered gate (reuses validator/ from spec)
  tier_gate.py       # Q25 auto-publish decision
  refresh/
    __init__.py
    scout.py         # Yutori Scouting wrapper
    perplexity.py    # cheap Sonar probe for "did it move?"
    scheduler.py     # source-class cadence registry
  cli.py             # `strata ingest discover|pull|refresh|scout`
```

CLI surface:
- `strata ingest pull <source-slug>` — one-shot fetch + extract + validate
- `strata ingest discover <concept-slug>` — Exa+Parallel pipeline end-to-end
- `strata ingest refresh [--tier regulator]` — run all due refreshes
- `strata ingest scout add <url> --schedule weekly` — register Yutori Scout

New dependencies in `backend/pyproject.toml`:
- `httpx` → promote from dev to runtime
- `pypdf`, `unstructured` — PDF parsing
- official SDKs where they exist (`exa-py`, `dune-client`); HTTP-only for
  Parallel / Perplexity / Yutori (just typed httpx wrappers — vendor SDKs
  are early and may churn)

---

## v0.2 → v0.5 sequencing

| Milestone | Ingest scope | Vendors used |
|---|---|---|
| **v0.2** (current) | Hand-write 50 seed primitives. Build the **module skeleton + direct-API path** for BLS / FRED / EDGAR (the three highest-leverage regulators). Snapshot + validate + auto-publish wired for those three. | None (free APIs only) |
| **v0.3** | Add **Parallel Task API** as the extraction engine for the discovery path. Add **Exa** for source discovery. End-to-end "create concept → auto-populate primitives" works on regulator tier. | Parallel, Exa |
| **v0.4** | Add **Perplexity Sonar** as the cheap refresh probe. Add the remaining direct-API connectors (Census, World Bank, OECD, FMCSA, NAIC). | + Perplexity |
| **v0.5** | Add **Yutori Scouting** for scheduled monitoring. Add **Dune + The Graph + Polymarket** for onchain + prediction_market tiers. Wire the full sensitivity-aware change-notification loop (Q5). | + Yutori, Dune, Polymarket |
| **v1.0** | Yutori **n1 Browsing API** for awkward sources (login-walled, JS-heavy). LLM-assisted PDF extraction at scale for S-1 backfill. | + Yutori Browsing |

**Why v0.2 is direct-API-only:** before paying any vendor, prove the
pipeline works on the cheapest, most reliable, most reproducible sources.
BLS + FRED + EDGAR alone cover most regulator-tier primitives. Vendor
spend starts at v0.3 when the discovery flow demands it.

---

## Cost model (rough envelope at v0.5)

Assume the library grows to ~500 primitives, each refreshed weekly:

| Line item | Volume | Unit price | Monthly |
|---|---|---|---|
| Direct-API pulls (BLS/FRED/EDGAR/etc.) | 500 × 4 wk = 2k | free | $0 |
| Parallel Task (discovery + extraction) | 200 new/refresh runs | $5/1k | $1 |
| Exa search | 500 queries | ~$1/1k | $0.50 |
| Perplexity Sonar (refresh probes) | 500 × 4 = 2k | ~$1/1k | $2 |
| Yutori Scouts | 50 active scouts × 4 = 200 runs | $0.35 | $70 |
| Dune / Graph / Polymarket | within free tiers | free | $0 |
| **Total** | | | **~$75/mo at 500 primitives** |

Scales sub-linearly with primitives (most are refreshed via cheap Sonar
probes; only deltas trigger expensive Parallel runs). Even at 5,000
primitives the bill stays under $1k/mo.

---

## Critical files & references

- **Design constraints** (don't drift):
  - [`docs/07-data-layer-brainstorm.md`](../../Desktop/work/VC_stuff/docs/07-data-layer-brainstorm.md)
    Q5 (snapshots + refresh cadence), Q20 (no LLM projections), Q25
    (auto-publish gate), Q26 (licensing-by-tier), Q37 (onchain +
    prediction_market tiers).
  - [`docs/10-v0.2-backend-spec.md`](../../Desktop/work/VC_stuff/docs/10-v0.2-backend-spec.md)
    for the existing validator pipeline shape — Ingest reuses it.
- **New module:** `backend/src/strata/ingest/` (clean slate; see layout
  above).
- **Reuse:** validators in `backend/src/strata/validator/` (currently
  stubs per the v0.2 spec — Ingest's tier-gate step calls them).
- **Pydantic models** in `backend/src/strata/models/` (also stubs) —
  Source, AtomicPrimitive, Snapshot records the Ingest layer produces.
- **CLI:** wire new commands in `backend/src/strata/cli.py` (Typer).

---

## Verification

End-to-end smoke test once v0.3 lands:

1. `strata ingest discover us-pc-carriers-active` →
2. Exa returns 5 candidate URLs (NAIC, AM Best, III, state DOIs, ...) →
3. For the NAIC URL: Fetch → store raw HTML + sha256 → Parallel Task API
   extracts `{value: 2650, unit: organizations, as_of: 2024-12-31,
   source: naic-2024, citation_url: <NAIC URL>, confidence: 0.92}` →
4. Validators pass (schema OK, unit OK, snapshot hash matches, URL live,
   value within ±15% of last published, sig-figs sane, as_of past) →
5. Tier-gate: source.tier = `regulator` + all validators OK →
   **auto-merge** the primitive YAML to `data/primitives/` →
6. Concept-attach: matches seed concept `us-pc-carriers-active`
   automatically (slug-overlap) →
7. Scheduler registers weekly Yutori Scout on the NAIC URL →
8. Concept page now renders the new primitive on `/c/us-pc-carriers-active`.

Failure-mode smoke test:
- Same flow with an **analyst-tier** URL (e.g., a Gartner report): tier-gate
  rejects auto-publish (Q26 licensing), Snapshot stores metadata stub only,
  PR opened with the extraction draft for human review.
- Parallel returns a value with **no citation**: validator rejects (Q20 —
  no LLM-projected primitives).

---

## Open questions for follow-up

These are deferred — they only become real once ingestion has run for a
month and we have real signal:

1. **Sanity-envelope Δ%** — Q25 says ±N% but doesn't fix N. Start at ±15%
   for regulator tier, ±25% for first_party; tune from false-positive rate.
2. **Concept-match threshold** — Q10's seed-library overlap score for
   auto-attach vs unattached pool. Start at 0.8 tag-Jaccard; tune.
3. **Vendor SLA fallback** — if Parallel is down, do we fall back to Exa
   Research API or block? Block for now (correctness > availability).
4. **Snapshot store at scale** — local filesystem at v0.2 is fine for 1k
   blobs; S3 or git-LFS once we exceed ~10k. Decide at v0.5.
5. **PII / takedown policy** — community PRs may include sensitive
   data; need a quick redaction path. Defer to v0.5 with the
   contribution-flow spec.

---

## Sources (May 2026 web research)

- [Parallel — Task API Deep Research](https://docs.parallel.ai/task-api/task-deep-research) — per-field citations, confidence scores, structured JSON
- [Parallel — Deep Research API for Agents](https://parallel.ai/products/api) — 48% accuracy benchmark
- [Parallel — Data Extraction at Scale](https://parallel.ai/articles/ai-data-extraction-how-to-extract-structured-data-from-websites-at-scale) — Search/Extract/Task pipeline
- [Exa — Web Search API for AI Agents](https://exa.ai/) — semantic search + extraction
- [Exa — Research API](https://docs.exa.ai/reference/exa-research) — structured citations
- [Perplexity — Sonar API](https://docs.perplexity.ai/docs/sonar/quickstart) — search-grounded LLM with citations
- [Perplexity — Sonar Pro intro](https://www.perplexity.ai/hub/blog/introducing-the-sonar-pro-api) — JSON mode, 2× citations
- [Yutori — API overview](https://yutori.com/api) — Research + Scouting + Browsing APIs
- [Yutori — n1 introduction](https://yutori.com/blog/introducing-n1) — 91% Navi-Bench browser-automation model
- [Yutori — API docs](https://docs.yutori.com/) — endpoint reference + pricing
- [Firecrawl — Best Deep Research APIs 2026](https://www.firecrawl.dev/blog/best-deep-research-apis) — cross-vendor comparison
