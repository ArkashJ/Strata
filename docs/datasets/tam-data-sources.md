# TAM training data — where it comes from (global source catalog)

Scoping doc for the `data/tam-training-dataset` branch. "Training dataset for
TAM" is three different artifacts; this catalog covers all three and marks which
global sources Strata already ingests vs. which are gaps.

---

## First: which dataset?

| # | Dataset | Shape | Trains / evaluates | Strata status |
|---|---|---|---|---|
| **A** | **Resolver eval set** | `query → expected_concept · lens · magnitude` | the query→framework mapping (the LLM slug resolver + lens pick) | **exists**: `backend/src/strata/evals/golden.yaml` (CI ≥ 0.8), ~16 cases. The 77-query diligence set (`docs/sample-queries.md`, on `docs/brainstorm-transcripts`) is the natural expansion corpus. **No global data needed — needs labeled queries.** |
| **B** | **Sourced-primitive supply** | atomic primitives: `value · unit · scope · source(url, tier, sha256)` | the *inputs* a framework multiplies (persona pools, ACVs, spend, rates) | **partial**: 293 primitives from ~13 connectors. This is where "global sources" matters most. |
| **C** | **Ground-truth TAM labels** | `market → defensible TAM range + method` | the *output* — benchmark whether a sized TAM is right | **doesn't exist**, and is the hardest: credible TAM figures are paywalled & analyst-tier (see honesty caveat). |

> **Recommendation:** B is the real leverage (better inputs → better TAMs → the
> bank grows), and A is the cheapest win (expand the eval set). C is a trap if
> done naively — see below.

---

## The honesty caveat on "TAM ground truth" (C)

Published TAM numbers (Statista, IBISWorld, Gartner, IDC, Forrester, Grand View,
MarketsandMarkets, Mordor) are **analyst-tier** — Strata's fence treats them as
`analyst` / `analyst-paraphrase`, i.e. *modeled, not sourced* (Q20). Training the
sizer to reproduce them would re-anchor on the exact unverifiable numbers the
product exists to replace ("competing on the losing axis", STRATEGY-REVIEW
2026-06-06). So ground truth should be **bottoms-up sourced primitives + a small
human-curated set of defensible TAMs with their method**, never scraped analyst
headlines. Analyst figures are fine only as a *cross-check banner*, fenced.

---

## Global open-data source catalog (for B — the sourced-primitive supply)

Trust order (Strata tiers): `first_party · regulator · aggregator · analyst · community · onchain · prediction_market · community-modeled`.

### Multilateral / global (regulator + aggregator tier)
| Source | What it gives a TAM | Free API | Strata connector |
|---|---|---|---|
| **World Bank** Open Data | GDP, population, adoption rates, by country | ✅ | ✅ wired (`worldbank`) |
| **OECD**.Stat (SDMX) | 38-country GDP, labour, trade, health, R&D | ✅ | ✅ wired (`oecd`) |
| **Eurostat** | EU sector stats, demographics, energy, health spend | ✅ | ✅ wired (`eurostat`) |
| **UN Comtrade** | bilateral trade flows by HS code | ✅ (key for bulk) | ✅ wired (`comtrade`) |
| **IMF** (WEO / IFS / BOP) | macro, fiscal, balance-of-payments, by country | ✅ | ❌ gap |
| **ILOSTAT** (ILO) | global labour force / employment by occupation — *persona pools worldwide* | ✅ | ❌ gap (high value for L1/L6) |
| **WHO** GHO | health workforce, disease burden, health spend | ✅ | ❌ gap |
| **FAO**STAT | agriculture/food production, prices | ✅ | ❌ gap |
| **ITU** | telecom/internet/mobile penetration globally | ✅ | ❌ gap |
| **UNCTAD** / UN Data / UNESCO UIS | trade & dev, education | ✅ | ❌ gap |
| **BIS** | global banking, credit, FX | ✅ | ❌ gap |

### National statistical offices (regulator tier — beyond the US)
UK **ONS**, Statistics **Canada**, Australia **ABS**, Germany **Destatis**,
France **INSEE**, Japan **e-Stat**, India **MOSPI / data.gov.in**, China **NBS**,
Brazil **IBGE**. — *all ❌ gaps.* Most expose JSON/SDMX APIs. These are the
non-US persona/firm/spend denominators for international markets.

### US (already strong — regulator tier)
BLS, FRED, Census (CBP/SUSB/ABS), SEC EDGAR, FDIC, CMS, EIA, USDA NASS, FAA,
openFDA — **all ✅ wired**.

### Firm / company level (for comparable-revenue & bottoms-up)
| Source | Use | Free | Connector |
|---|---|---|---|
| SEC **EDGAR** (XBRL frames) | US public-co financials, segment revenue | ✅ | ✅ wired |
| **GLEIF** (LEI) | global legal-entity registry (firm counts) | ✅ | ❌ gap |
| **OpenCorporates** / Companies House (UK) | company registries | ✅/freemium | ❌ gap |
| Crunchbase · PitchBook · Dealroom | private-co funding/rev | 💲 paid | ❌ (analyst-tier) |

### Markets / finance / signals (already wired)
`alpha_vantage`, `yfinance`, `nasdaq_data_link` (markets), `dune` (onchain),
`kalshi` (prediction-market signals — quarantined, never feed a TAM),
`reddit` / `twitter` / `stack_exchange` / `github` (community signals).

---

## Proposed next steps (pick a direction)

1. **A — expand the resolver eval set**: port the 77 diligence queries into
   `golden.yaml` shape (+ negative cases that *should* be `unsizable`, like
   SynthioLabs/pharma-commercialization — to test the honest-miss path).
2. **B — wire a high-value global connector**: **ILOSTAT** (global labour →
   persona pools) or **IMF** (macro denominators) are the best first adds; both
   are free APIs and fit the existing 6-layer connector pattern.
3. **C — curate a small ground-truth TAM benchmark**: 10–20 markets with a
   defensible TAM + method, sourced bottoms-up (NOT scraped from analysts), as a
   regression target for the evaluator.

> Open question for the owner: is this branch primarily an **eval/training set**
> (A, lives in `evals/`) or a **data-supply expansion** (B, new connectors +
> primitives)? The catalog above serves both; the build differs.
