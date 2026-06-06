# The TAM/market question bank (PR 4)

## "Did you see the questions?" — status

There is **no "118 YC questions" file anywhere in this repo or its git history** (searched
exhaustively: `y.?combinator`, `118 question`, `question bank`, `interview question` → zero
hits). The "118" is not committed. The only adjacent assets are:
- the **six analysis lenses** (`backend/src/strata/models/_common.py:23-76`) + their
  `REQUIRED_PRIMITIVE_ROLES` — the *shape* of an answer;
- the internal **Q1–Q40 schema taxonomy** (design decisions, in the recovered `docs/07`);
- a YC *interview* Q&A (git history only) — pitch questions, not market-analysis questions.

So the bank is **greenfield**, authored here as fully-curated YAML. This doc is the source
spec; the records land under `data/questions/` in PR 4.

## Principle (load-bearing)

Every question's answer must resolve to **sourced bank data** — a sourced primitive, a
concept measurement, or a pure synthesis of sourced scenarios — or it honestly says
**"no data in bank"**. Never an LLM-projected number (Q20). Junk questions ("should we move
to SF?", "who should we hire?") are **excluded by design**: if a question can't bind to a
registry object, it's not in the bank. The fence is structural — the answer schema can only
reference registry objects, and a validator rejects any question resolving to a quarantined
signal.

## Answer strategies

| strategy | resolves from | yields |
|---|---|---|
| `primitive_role` | the concept's framework variant binding for a role | a sourced primitive (value+unit+source+snapshot) |
| `concept_measurement` | the concept's competing `measurements` | a **spread** when ≥2 disagree ("page, not a footnote") |
| `tam_field` | a field of the computed `TAMOutput` | triangulated synthesis (labeled, reproducible at `/tam/<hash>`) |
| `qualitative` | a concept modifier / annotation | sourced narrative (regulation, risk) |
| → else | — | honest **gap** + `resource_target` hint |

## Categories (~150 total: ~90 cross-cutting + ~60 lens-specific)

### market_size
1. What is the triangulated TAM, and what's the range across methods?
2. How large is the addressable population/persona base the product serves?
3. What share of that base is realistically reachable (in-scope vs total)?
4. What's the per-unit economic value (spend/seat, ACV, take) the market turns on?
5. How does the bottoms-up build compare to the top-down build, and by how much?
6. What fraction of TAM is already captured by incumbents vs greenfield?

### growth_rate
7. What growth trajectory does the bank's adoption data imply over 3–5 years?
8. What is the current adoption/penetration level vs the addressable ceiling?
9. Which input is growing fastest, and is its source recent enough to trust?
10. Is the market expanding the pie or reallocating existing spend?

### segmentation
11. How does TAM split by firm-size band (SMB / mid-market / enterprise)?
12. Which segment carries the most defensible (most-sourced) number?
13. What share of the segment is capturable given the sourced capture rate?
14. Which sub-markets are explicitly in vs out of scope (and why)?

### geography
15. How does TAM split across the in-scope geographies?
16. Is the number supply-side, demand-side, or both (geo_supply vs geo_demand)?
17. Which geos lack sourced data and are therefore excluded?

### competition_share
18. Who are the incumbents this displaces, and what share assumption is sourced?
19. What market-share assumption does the throughput/revenue model use, and is it cited?
20. How fragmented is the market (is a share assumption even meaningful)?
21. What's the value split between platform and participants (take rate / vendor split)?

### regulation
22. What regulatory change could unlock or constrain this market, and when?
23. Is any part of the TAM gated behind a regulated transition (subsidy, mandate)?

### adoption
24. What replacement/displacement rate vs incumbents does the data support?
25. What willingness-to-pay is sourced, and from whom?
26. What's the realistic adoption curve shape (S-curve params), if sourced?

### unit_economics
27. What is the sourced spend-per-target / cost-per-persona?
28. What take-rate or value-split does the model apply, and is it cited?
29. How sensitive is TAM to the per-unit price assumption (±20%)?

### risks
30. Which inputs are MODELED (not sourced), and how wide is their range?
31. What is the spread between the low and high method, and why do they disagree?
32. Which single assumption most moves the answer (sensitivity leader)?
33. Are any inputs stale (past their freshness SLA)?

### methodology
34. How many independent method families agree (independence score)?
35. Is the estimate triangulated or single-method?
36. Which inputs are first-party/regulator vs aggregator vs analyst-paraphrase?

> The ~60 lens-specific questions are mechanical expansions of #2–#5, #13, #21, #24–#29 keyed
> to each lens's `REQUIRED_PRIMITIVE_ROLES` (e.g. cost_efficiency → persona_pool /
> addressable_share / replacement_rate / cost_per_persona). Authored after the assembler
> proves end-to-end on 3 concepts.

## Worked record

```yaml
kind: analysis_question
question_id: Q-MS-002
prompt: "How large is the addressable population/persona base this product serves?"
category: market_size
lenses: [cost_efficiency]
applies_when: { lens_in: [cost_efficiency], requires_role: [persona_pool] }
answer: { strategy: primitive_role, roles: [persona_pool], aggregation: value }
narrative_template: "The addressable base is {value} ({source_name}, {source_tier}, {as_of}). Snapshot {snapshot}."
gap_text: "No sourced persona-pool primitive bound — needs a BLS/Census headcount ingest."
```
