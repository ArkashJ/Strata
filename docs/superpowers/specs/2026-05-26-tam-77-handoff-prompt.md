# Handoff Prompt — TAM-77 Corrected Estimation

Paste this into a fresh Claude Code session at `/Users/arkashjain/Desktop/work/VC_stuff` to continue this work.

---

## Context

You are continuing work on Strata, an open-source community-curated market-sizing engine for VCs (see `CLAUDE.md`). A previous session built 9 new data connectors (OECD, Eurostat, UN Comtrade, FDIC, CMS, EIA, USDA NASS, FAA, openFDA) on top of the existing 6 (BLS, FRED, Census, EDGAR, World Bank, Kalshi) — all merged into PR #44 (draft) on branch `ArkashJ/additional_apis`. Tests: 304 passing, pyright strict clean, ruff clean.

The previous session also produced a first TAM estimation script (`backend/scripts/tam_77_estimates.py`) for the 77-query VC test set covering 24 portfolio companies. That first run produced numbers but **had 12 methodology errors** documented in `docs/superpowers/specs/2026-05-26-tam-77-corrected-methodology.md`.

## Your Job

**Rebuild `backend/scripts/tam_77_estimates.py` using the methodology in the spec** at `docs/superpowers/specs/2026-05-26-tam-77-corrected-methodology.md`.

## Key Requirements (from spec)

1. **Use Claude API for classification, not hardcoded profiles.** Match the existing `/resolve` pattern in `backend/src/strata/api/routes/resolve.py`. The script must call `anthropic` SDK with tool-use to classify each company's:
   - Geographic profile (one of: `us_only_regulated`, `india_only`, `global_saas`, `infra_layer`, `multi_jurisdiction_regulated`, `global_industrial`)
   - Sizing method (one of: `bottoms_up_seat`, `labor_displacement`, `capacity_based`, `services_revenue`, `infra_stack`, `share_shift`)
   - Addressability % + justification
   - Capture rate % + justification (for labor_displacement only)
   - Infra layer share % + analog (for infra_stack only)
   - Lower-regulation geographies (for multi_jurisdiction_regulated only — e.g., Piramidal can target India CDSCO, Brazil ANVISA in addition to FDA)
   - Named application companies depending on this infra (for infra_stack — e.g., voice infra is paid by Decagon, Giga, Sierra, Ada, Bland AI)

2. **Pull connector primitives before calling Claude.** For each company:
   - Identify relevant connectors from the query angles
   - Pull real primitives (BLS occupation counts, Census firms by NAICS, EDGAR incumbent revenues, World Bank country GDP)
   - Pass these primitives to Claude as structured context

3. **Use Exa search** (already integrated, see `backend/src/strata/exa_client.py`) to fetch:
   - Application companies in each infra layer's ecosystem (Decagon, Giga, Sierra for voice; named comparables for memory, multimodal)
   - Recent funding rounds for sizing context
   - Industry market sizes when no government data exists

4. **Output requirements:**
   - JSON file: `backend/tam_77_results_v2.json` with full Claude reasoning trace per company
   - Markdown: `docs/tam-77-corrected.md` with the new table (replaces `docs/tam-77-results.md`)
   - Updated PR comment on #44
   - Updated CHANGELOG.md entry under [Unreleased]

5. **Acceptance criteria** (from spec):
   - [ ] Voice infra (MetaVoice) lands at $8-16B global (not $2.5B), via infra-stack with Decagon/Giga/Sierra/Bland in the application stack
   - [ ] Yotta TAM is India-only (~$3-5B), zero international
   - [ ] All US-only-regulated companies (Kyber, SignalLabs, Effective AI, Minerva, Accrual, Kaizen Labs, Zero RFI) show $0 international TAM
   - [ ] Endeavor / Zero RFI / Minerva show realistic SAM, not total-labor-pool ceilings
   - [ ] Piramidal estimates include lower-regulation geographies (India CDSCO, Brazil ANVISA, EU CE) with appropriate per-geo discounts
   - [ ] Every estimate cites: market denominator source + addressability justification + confidence tier (S1/S2/S3)
   - [ ] Q29 (Yotta GPU forecast over 5 years) is REFUSED per Q20 no-forecasting policy
   - [ ] All 304 existing tests still pass

## Important Files to Read First

1. **`docs/superpowers/specs/2026-05-26-tam-77-corrected-methodology.md`** — the design spec with all decisions
2. **`backend/scripts/tam_77_estimates.py`** — current script with hardcoded values (the thing being replaced)
3. **`backend/src/strata/api/routes/resolve.py`** — existing /resolve endpoint to match patterns
4. **`backend/src/strata/exa_client.py`** — Exa search wrapper
5. **`docs/04-user-journey.md`** — the 77-query spec with all company descriptions
6. **`backend/src/strata/connectors/CLAUDE.md`** — all 15 connectors documented

## The 12 Errors Being Fixed

(See spec for full audit, but in brief:)

**Geographic errors (8):**
- Yotta: India-only, was scaled globally to $6B → should be ~$3-5B India
- Minerva: US CPA firm services, was $43B global → US-only
- Accrual: US tax software, was $5.2B global → US-only
- Kaizen Labs, Kyber, Effective AI, SignalLabs, Zero RFI: all US-regulated, treated as global

**Sizing errors (3):**
- Endeavor $75B: total mfg back-office, not AI-addressable → ~$5-15B
- Zero RFI $72B: total construction services → ~$5-10B
- Minerva $43B: total SMB accounting → ~$5-15B

**Layer error (1):**
- MetaVoice $2.5B (voice infra): was sized as nascent ARR; should be sized as infra share of application stack (contact center + voice agents + audiobooks + localization + accessibility) = $13-16B global, $5-6B US

## Suggested Implementation Order

1. **Read all listed files** (1-6 above) before writing any code
2. **Sketch the Claude tool-use schema** for classification — what JSON does Claude return per company?
3. **Build the per-company pipeline**:
   - `gather_primitives(company) -> dict[connector → values]`
   - `gather_industry_context(company) -> dict[exa search results]`
   - `classify_with_claude(company, primitives, context) -> Classification`
   - `compute_tam(classification, primitives) -> TAMEstimate`
   - Loop over 24 companies
4. **Stream the chain-of-thought** to stderr (or log) so Arkash can watch the reasoning
5. **Write outputs** (JSON + markdown + PR comment + CHANGELOG)
6. **Verify acceptance criteria** end-to-end

## Environment

- API keys are in `.env` at repo root:
  - `ANTHROPIC_API_KEY`
  - `EXA_API_KEY`
  - `STRATA_BLS_API_KEY`, `STRATA_FRED_API_KEY`, `STRATA_CENSUS_API_KEY`
  - `STRATA_EIA_API_KEY`, `STRATA_USDA_NASS_API_KEY`, `STRATA_OPENFDA_API_KEY`
- Some connectors (FDIC, CMS, EIA, Census) have known endpoint bugs documented in the previous session — they may need quick fixes (redirect handling, method names, facet format) before they return data live. See the previous PR comment on #44 for specifics.

## Constraints

- Pyright strict, ruff clean (run from `backend/` directory)
- All `uv run` commands from `backend/`
- New code should follow existing patterns (look at `resolve.py` for AI-driven endpoints, `connectors/bls.py` for the 6-layer connector pattern)
- Don't break the 304 existing tests
- Use the Anthropic SDK directly with prompt caching (the existing pattern in `resolve.py`)
- Model: `claude-opus-4-7` (or `claude-sonnet-4-6` if cost matters)

## When You Finish

1. Run `cd backend && uv run pytest` — all tests must pass
2. Run `cd backend && uv run pyright src/strata/` and `uv run ruff check .` — must be clean
3. Commit + push to `ArkashJ/additional_apis`
4. Update PR #44 with new comment summarizing the v2 results
5. Update CHANGELOG.md [Unreleased] section

Branch: `ArkashJ/additional_apis`
PR: https://github.com/ArkashJ/Strata/pull/44
Issues: #35-#43 (close on merge)
