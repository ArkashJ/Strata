# Corrected TAM Methodology for 77-Query Test Set

**Date:** 2026-05-26
**Author:** Arkash Jain (with Claude)
**Status:** Approved, ready for implementation
**Scope:** Replace `backend/scripts/tam_77_estimates.py` output with rigorous per-company estimates that fix 12 identified methodology errors

---

## Why This Spec Exists

The first run of `tam_77_estimates.py` produced 77 TAM estimates across 24 portfolio companies. A subsequent audit identified 12 systematic methodology errors. This spec defines the corrected methodology and serves as the implementation blueprint for the re-estimation.

### The Twelve Errors Found

**Geographic errors** (one-size-fits-all GDP scaling applied to geographically-constrained markets):
1. **Yotta** — India-only DC capacity ($1.8B) was labeled "NA" and GDP-scaled globally to $6.0B. Yotta cannot operate outside India (physical DCs + RBI data localization).
2. **Minerva** — AI accounting *firm* requires US CPA licenses. Scaled to $42.9B global; correct ceiling is US-only.
3. **Accrual** — US federal/state tax software for US CPA firms. Scaled to $5.2B global; correct is US-only.
4. **Kaizen Labs** — US state/local GovTech. Domestic-only by procurement scope.
5. **Kyber** — P&C insurance regulation is state-level US. EU/Asia P&C is a separate market.
6. **Effective AI** — Insurance actuarial work is jurisdiction-bound.
7. **SignalLabs** — US payer/provider system unique; HIPAA-bound.
8. **Zero RFI** — Construction is local; international construction services is a separate buyer set.

**Sizing errors** (TAM ceiling reported as addressable market):
9. **Endeavor $75B** — Total mfg back-office labor pool. Realistic SAM: $5-15B.
10. **Zero RFI $72B** — Total construction services. Owner's-rep AI slice: $5-10B.
11. **Minerva $43B** — Total SMB accounting services. AI-native firm capture: $5-15B.

**Layer/stack error** (infra layers labeled "nascent" instead of sized to application stack):
12. **MetaVoice $2.5B (voice AI infra) — UNDERSIZED.** Voice infra is the picks-and-shovels layer for an $80B+ application market (contact center automation, voice agents, audiobooks, media localization, accessibility, game voice). Correct TAM is 4-5x my original estimate.

### The Three Root Causes

**A. Premature aggregation.** I computed a US number first, then GDP-scaled globally. Broke Yotta (India-only) and Kaizen (US-only). **Fix:** compute each geography independently from local primitives, then sum.

**B. TAM ceiling vs. captured-market confusion.** Reported "total labor pool" as TAM. **Fix:** every TAM formula needs TWO multipliers — addressability (what % of this work AI can do) × capture (what % of AI-eligible work this company wins).

**C. "Nascent revenue" treated as "small TAM" for infra layers.** Voice infra has small revenue today but enables an $80B+ application market. **Fix:** infra TAM = sum of application markets × infra share, not extrapolation from current ARR.

---

## Decisions (from brainstorming)

| Decision | Choice |
|----------|--------|
| Output scope | Full audit + corrected table (all 24 companies re-estimated) |
| TAM model | Single TAM per company with explicit "addressability %" multiplier shown |
| Methodology | **Hybrid per-company** — pick the strongest sizing method per company based on data availability |
| **Classification** | **Claude API classifies each company** (geo profile + sizing method + addressability + capture %) using the existing `/resolve` pattern. The script provides connector primitives; Claude does the reasoning. **This is the whole point of Strata — not hand-coded profiles.** |

---

## Architecture

### 1. Geographic Profile Tags (per company)

Every company gets exactly one geographic profile that determines how TAM is computed:

| Profile | Companies | Treatment |
|---------|-----------|-----------|
| `us_only_regulated` | Kyber, SignalLabs, Effective AI, Minerva, Accrual, Kaizen Labs, Zero RFI | TAM = US only. International = "not addressable today" (regulatory/licensing/jurisdictional barriers) |
| `india_only` | Yotta | TAM = India only. Physical DCs + RBI/DPDP localization |
| `global_saas` | Gather, Echelon, Skyramp, Numeral, Contrario AI, PlayerZero, Wraithwatch, Moda, Melius, ST Labs | TAM = global. Geographic split = tech-spend ratios (NA 40 / EU 25 / APAC 30 / RoW 5) applied to the global product TAM |
| `infra_layer` | Supermemory, MetaVoice, Miravoice, Sieve | TAM = sum of global application markets enabled × infra layer share |
| `multi_jurisdiction_regulated` | Piramidal | Split by regulatory regime: FDA (US, hardest) + CE-EU (EU) + CDSCO (India, faster) + ANVISA (Brazil/LATAM) + selected APAC. Lower-regulation geographies = larger SAM at lower entry cost. **AI must reason about where regulation costs vs. addressable demand make economic sense, not just default to FDA-first.** |
| `global_industrial` | Endeavor | Global mfg back-office, heavily discounted for AI-addressability AND capture |

### 2. Sizing Method Per Company

Six formulas, applied based on data availability and company type:

| Method | Formula | Source Requirements |
|--------|---------|--------------------|
| `bottoms_up_seat` | `firms × seats_per_firm × dollar_per_seat × addressability` | Census NAICS + BLS occupation + ACV from comp |
| `labor_displacement` | `occupation_count × salary × addressability × capture_pct` | BLS + industry analog for capture % |
| `capacity_based` | `capacity_units × revenue_per_unit` | EIA / CBRE / industry capacity reports |
| `services_revenue` | `services_market_size × take_rate` | Census services + comparable take-rate |
| `infra_stack` | `sum(application_markets_enabled) × infra_layer_share_pct` | EDGAR comps + industry app market sizes |
| `share_shift` | `incumbent_revenue × share_shift_pct` | EDGAR incumbent + addressability |

### 3. Voice Infra Worked Example (the methodology fix)

**Old:** $2.5B global (labeled "nascent market," based on hardcoded `voice_app_devs = 200_000`)

**New (infra-stack method):**

| Application Market | Size | Source |
|-------------------|------|--------|
| Contact center automation | $20B | Genesys/NICE/Five9 revenue (EDGAR) + industry reports |
| AI customer service agents (Decagon, Sierra, Ada, Decagon serving Grubhub/Notion/etc.) | $15B+ | Rapidly growing — modernization of $80B contact center labor pool |
| Voice agents for QSR / food delivery / order-taking (Giga ML, Bland AI serving Wendy's, McDonald's, Grubhub) | $5B+ | Restaurant industry phone-order automation; growing fast |
| Voice agents for outbound sales / scheduling / booking | $8B | Outbound calling automation; healthcare scheduling; salon/services booking |
| Audiobooks | $5B | Audible parent + industry reports |
| Media localization / dubbing | $50B | Global media localization industry |
| Accessibility (screen readers, voice UI) | $2B | Assistive tech market |
| Game/character voice | $3B | Game audio production market |
| **Total addressable application stack** | **$108B+** | |
| Voice infra layer share | **12-15%** | Analog: cloud infra ≈ 12% of total cloud spend (AWS/Azure/GCP infra revenue ÷ total cloud spend); higher share for newer layers |
| **Voice Infra TAM (global)** | **$13-16B** | |
| US share (40% tech split) | **$5-6B** | |

**Why 5-6x my original:** I treated current voice-API revenue ($1-2B today) as the TAM. The infra-stack model correctly sizes TAM as a fraction of what the infra *enables*. The application stack is bigger than I first sized — companies like Decagon (AI customer service for Grubhub, Notion), Giga ML (voice agents for QSR), Sierra, Bland, Ada are building the voice-agent application layer that pays voice infra. As they scale, infra TAM scales with them.

**Application-company-aware sizing**: For any infra layer (voice, code, memory, multimodal), the script should enumerate the *named application companies* that depend on this infra and use their funding/revenue as additional signal for application-market size.

### 4. Source Attribution Schema

Every TAM line in the output must specify:

```yaml
company: <name>
query_id_range: <e.g., "1-4">
geographic_profile: <one of 6 tags>
sizing_method: <one of 6 methods>
underlying_market:
  value: <number, in $B>
  source: <connector method name OR named industry report with year>
  primitives:
    - <specific primitive used, e.g., "Census NAICS 5241 establishments: 7,500">
addressability:
  pct: <number, 0-100>
  justification: <one sentence with source>
capture_rate:  # optional, only for labor_displacement
  pct: <number, 0-100>
  justification: <one sentence>
tam:
  us: <number, in $B>
  international: <number, in $B>  # 0 if us_only_regulated
  total: <number, in $B>
confidence_tier: <S1 | S2 | S3>
sources_cited: <list of source codes from legend>
warnings: <optional list of caveats>
```

### 5. Confidence Tiers (unchanged from prior spec)

- **S1** — Both market denominator AND addressability multiplier are government-sourced (connector APIs)
- **S2** — Gov-sourced denominator, industry/analyst multiplier
- **S3** — Both analyst-sourced (must be flagged for verification, used only when no gov data exists)

### 6. Output Table Structure

Primary table columns:

```
| Qry | Company | Geo Profile | Sizing Method | Underlying Market | Addressability | US TAM | Intl TAM | Total TAM | Tier | Sources |
```

Plus a per-company section showing the full math chain.

---

## Claude-Driven Classification Architecture

The script must NOT hardcode geographic profiles, addressability %, or sizing methods. Instead, it follows the existing `/resolve` pattern:

```
For each of 24 companies:
  1. Pull company description + website + 77-query angles
  2. Pull connector primitives (BLS occupation counts, Census firms, EDGAR comps, etc.)
  3. Pull industry context via Exa search (named comparable companies, recent funding, application markets)
  4. Call Claude (claude-opus-4-7) with structured tool-use to classify:
     - geographic_profile (one of 6 tags)
     - sizing_method (one of 6 methods)
     - addressability_pct + justification
     - capture_rate_pct + justification (if labor_displacement)
     - infra_layer_share_pct + analog (if infra_stack)
     - lower_regulation_geographies (for multi_jurisdiction_regulated only)
     - named_application_companies (for infra layers — e.g., Decagon, Giga, Sierra for voice)
  5. Compute TAM = market × addressability_pct (× capture_pct if labor)
  6. Stream chain-of-thought via SSE (matches /resolve pattern)
  7. Output: full source attribution + Claude's reasoning trace
```

This matches Strata's existing architecture (`POST /resolve` → Claude parse → Exa search → evaluate → SSE stream) and gives every estimate a defensible reasoning chain that future-Arkash (or another VC) can audit.

### Why This Matters

The whole product thesis is: VCs don't want analyst guesses, they want defensible primitives + a transparent reasoning chain. If I (Claude in this brainstorm session) hand-code Piramidal as "FDA-only," I've made the same mistake as Statista — assertion without reasoning chain. The corrected script must show its work for every classification decision.

## Implementation Plan (high-level — full plan via writing-plans)

1. **Replace `scripts/tam_77_estimates.py`** with new architecture that:
   - Loads geographic profile + sizing method per company from a config dict
   - Implements 6 sizing-method functions (one each, with named primitives)
   - Outputs JSON + markdown with full source attribution per company
2. **Create `docs/tam-77-corrected.md`** with the new table
3. **Update PR #44 comment** with corrected table + audit document
4. **Update `CHANGELOG.md`** noting the methodology correction
5. **Update test `test_tam_query_coverage.py`** if any assertions break

---

## Acceptance Criteria

- [ ] All 24 companies re-estimated using assigned geographic profile + sizing method
- [ ] Voice infra (MetaVoice) shows $8-12B global with infra-stack derivation
- [ ] Yotta shows India-only TAM (~$3-5B), zero international
- [ ] All US-only companies show $0 international TAM
- [ ] Endeavor / Zero RFI / Minerva show realistic SAM, not labor-pool ceilings
- [ ] Every estimate cites: market denominator source + addressability justification + confidence tier
- [ ] Q29 (Yotta GPU forecast) still REFUSED per Q20 policy
- [ ] PR #44 comment updated, CHANGELOG updated, audit doc committed

---

## Out of Scope

- Live connector API endpoint fixes (FDIC redirect, CMS 404, EIA facets, Census method names) — separate PR
- Adding new connectors beyond the 9 already shipped
- Computing TAMs for companies not in the 77-query test set
- Productionizing the script as an API endpoint (this is a one-shot research script)
