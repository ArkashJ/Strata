# Strata — YC Technical Cheatsheet

> One-sitting brain-dump of the whole technical stack, written so you can answer
> any "how does it actually work" question on the spot. Every claim is traced to
> a real file. Read top-to-bottom once, then keep the ASCII flows handy.

---

## 0. The one-paragraph pitch (say this first)

Strata is the **verification layer for AI-generated market claims.** Every TAM is
not a scalar with an error bar — it's a **scenario tree** built by multiplying
**atomic sourced numbers** ("primitives") through **parameterized recipes**
("frameworks / lenses"). Every number carries a `source_url` + a content-hash
pin (`snapshot_sha256`), so the *provenance is the product*. Agents reach it over
**MCP** (`verify_market_claim`), which is the contributor flywheel humans won't be.
The moat is the **frameworks (the real IP)** + the **trust fence** that refuses to
let an LLM's hallucination become a citable number.

---

## 1. The five-layer data model (the spine)

Everything downstream is this stack. Memorize the arrows.

```
Concept                 curated identity object, narrow market scope
  │ measured-by         (e.g. "AI sales-ops tooling, US, mid-market")
  ▼
Atomic Primitive        ONE source · ONE number · reproducible
  │ bundled-into        value + unit + source + sha256 pin
  ▼
Composite Primitive     same-unit SET OPS only (union/filter) — no math across units
  │ consumed-by
  ▼
Framework (a "lens")    unit-CROSSING arithmetic · NO scalar defaults
  │ emits               every input is a primitive slug
  ▼
TAM Output              scenario tree · permanent /tam/<hash> · hash-pinned
```

**The hard line everyone asks about:** composites do *same-unit set operations*
(union two people-counts). Frameworks do *all unit-crossing math* (people ×
$/person = $). Blurring this is forbidden — it's what keeps units honest.
`models/primitive.py:157` (composite) vs `models/framework.py:76` (framework).

---

## 2. What makes the primitives + lenses unique

Three things competitors (IBISWorld / Statista / a GPT wrapper) structurally can't copy:

**(a) A primitive is atomic and reproducible.** One source, one number, one
content hash. Not "a report says ~$5B" — it's `value=5.2e9`, `unit={currency,
flow, USD}`, `source={url, tier, snapshot_sha256}`, `as_of=2025-Q3`.
`models/primitive.py:74`.

**(b) Frameworks have NO scalar defaults — every input is a citable slug.**
You cannot hardcode "assume 20% adoption." Every input is a pointer to a sourced
primitive. The framework declares a **unit signature** per input and the
validator *statically rejects bad wiring at construction time*
(`framework.py:101` parses the formula and rejects undeclared identifiers).
`framework.py:56` (`FrameworkInput.unit_signature`).

**(c) Six structurally-distinct lenses (the math shapes), not one regression.**
Each lens is a different *shape* of arithmetic — `models/_common.py:23`:

| Lens (enum) | Math shape | Example targets |
|---|---|---|
| `cost_efficiency` | persona × cost | Harvey, Glean |
| `revenue_generation` | segment × spend | Brex, Rippling |
| `latent_demand` | population × adoption × WTP | Uber-style |
| `platform_throughput` | volume × take_rate | Stripe, Visa |
| `bundle_consolidation` | total_spend × consolidation | Notion, Linear |
| `productivity_uplift` | personas × value_split | Copilot, Cursor |

The formula is a real string evaluated through a **closed AST interpreter**
(`evaluator/formula/`) with bounded builtins: `min`, `max`, `clamp(x,lo,hi)`,
`logistic(x,mid,steep)`, `curve(x,k)=1−e^(−kx)` (saturating adoption).
`evaluator/formula/interp.py:42`. So a framework can express an S-curve adoption
without anyone injecting a magic number.

---

## 3. How a TAM tree is built (the evaluator)

This is the question "how do you make trees." Entry point `size_concept()` in
`evaluator/engine.py:98`.

```
size_concept(concept_slug, overrides?)
        │
        ▼
1. look up Concept in Registry              engine.py:98
        │
        ▼
2. _iter_scenario_builds()                  engine.py:196
   pick EVERY framework whose:
     • variant.scope == concept.slug
     • fw.lens ∈ {concept.primary_lens, secondary_lens}
     • fw.applicable_to allows it
   → one BUILD per matching framework
        │
        ▼  (for each build)
3. _build_scenario()                        engine.py:315
   for each framework input slug:
     _resolve_input() → primitive value     engine.py:235
     bind into env[input_name] = value
   _eval_formula(parse(fw.formula), env)    engine.py:295
     └─ walks the AST: a*b, +, min, logistic, curve…
   → one Scenario {value, unit, inputs_used[], banners}
        │
        ▼
4. mint_state_hash(payload)                 engine.py:173  → /tam/<hash>
        │
        ▼
5. _convergence()  (only if ≥2 method families)   engine.py:476
   _independence()                                engine.py:510
   build_scope_report()  (derived, NOT in hash)   engine.py:192
        │
        ▼
   TAMOutput { scenarios[], convergence, independence_score, scope }
```

**The data structure** (`models/tam_output.py`):

```
TAMOutput                                   tam_output.py:137
├─ state_hash         (the /tam/<hash> permalink)
├─ target             (what market this sizes)
├─ scenarios[]        ◄── THE TREE (min 1, never a scalar)
│   └─ Scenario                             tam_output.py:95
│       ├─ lens, framework, framework_variant
│       ├─ value, unit
│       ├─ inputs_used[]                     tam_output.py:62
│       │   └─ InputUsed { primitive_slug, snapshot_sha256(pin),
│       │                  value, source_tier, source_url }
│       └─ banners[]   (MODELED / USER_OVERRIDE / dark_estimate…)
├─ convergence        (null unless ≥2 independent families agree)
├─ independence_score
└─ scope: ScopeReport (derived — see §6)
```

**Convergence** is the killer demo: when ≥2 *independent method families* (a
bottoms-up seat count AND a top-down spend number) size the same concept, the
evaluator emits a `convergence` object — "lower $X · higher $Y · spread N×". That
agreement (or disagreement) is the trust signal. It's `null` for single-method
concepts and *refuses to compare across units*. `engine.py:476`.

**What-if / Strata Live** — `EvalOverrides` (`engine.py:71`) threads two knobs:
- `primitive_overrides` — a transient what-if scalar+unit (NEVER persisted as a
  primitive — that's the Q20 rule). Sets `uses_synthetic=True`, emits a
  `USER_OVERRIDE` banner. `engine.py:353`.
- `framework_assumptions` — re-point a named input to a *different existing*
  sourced primitive slug. `engine.py:329`.
- Guard: an override slug that no framework input actually binds is *rejected*
  (`engine.py:115`) so the API can never claim a recompute changed something it
  didn't. Overrides fold into the hash → distinct what-if = distinct URL.

---

## 4. Hashing — how `/build/<hash>` and `/tam/<hash>` are minted

Question: "how is hashing working." It's tiny and deliberate — `hashing.py` (28 lines).

```
mint_state_hash(payload):                   hashing.py:25
   canonical = json.dumps(payload,
                 sort_keys=True,            ← key order can't change the hash
                 separators=(",",":"),
                 default=str)               hashing.py:14
   return sha256_hex(canonical)
```

**The whole trick is canonicalization:** sort keys + tight separators *before*
sha256, so two equivalent states collide to the same URL, and any one-field change
mints a new URL. Built in `engine.py:130`.

```
┌─ INCLUDED in the hash (state identity) ─────────────┐
│  • concept slug                                      │
│  • per scenario: framework slug, variant.scope,      │
│    value, inputs:[{name, primitive, snapshot_sha256}]│
│  • overrides (what-if value+unit, re-pointed inputs) │
│  • declared_scope (the user-pinned MarketScope)      │
└──────────────────────────────────────────────────────┘
┌─ EXCLUDED (derived / display-only) ─────────────────┐
│  • source_url, source_tier  (display enrichment)     │
│  • ScopeReport              (derived from scope)      │
│  • created_at, created_by, banners, convergence      │
└──────────────────────────────────────────────────────┘
```

Why it matters: the hash is the *math identity* of the answer. Cosmetic stuff
(who looked at it, what the source URL renders as) must NOT change the hash, or
forking/caching breaks. Pin lives *inside* the hash (`snapshot_sha256` per input)
so a TAM is only equal to another TAM if it used byte-identical sourced inputs.

---

## 5. Citations, snapshots & verification (the trust fence)

Question: "how is hashing and verification working / citations." Two different
hashes — don't conflate them:

- **`snapshot_sha256`** = content hash of the *source document* at ingest time
  (proves the number hasn't drifted from its source).
- **`state_hash`** = hash of the *whole TAM computation* (proves the answer is
  reproducible). §4.

```
INGEST                          QUERY-TIME VERIFY                AGENT-TIME
source doc bytes                strata verify-integrity          every API/MCP
   │ sha256                        │                             payload carries:
   ▼                               ▼                             source_url
data/snapshots/<sha256>        verify_snapshot_store()          source_tier
(filename IS the hash)            walk dir, re-sha256 each       snapshot_sha256
   │                              file, compare to its name
   ▼                               │
primitive.source.snapshot_sha256   ▼
                               IntegrityReport{verified, failures}
                               exit 1 on any mismatch
```

`integrity.py:48` (store walk; `path.stem` is the expected hash), CLI at
`cli.py:463`.

**The four guards that stop an LLM from poisoning the bank** (this is the part YC
will poke at — "how do you stop hallucinated numbers"):

```
LLM proposes a number on the /resolve fallback path
        │
        ▼
① Host allowlist     resolver/citations.py:94
   is_real_host()? host ∈ gov/edu TLD ∪ curated connector hosts
   else → FabricatedHostError. "strata.internal" placeholder rejected.
        │
        ▼
② Tier from host     resolver/citations.py:106
   tier_for_host() — tier is DERIVED from the host class,
   NEVER taken from the LLM. kalshi→prediction_market,
   gov→regulator, worldbank→aggregator, else→community.
        │
        ▼
③ Unit guard         resolver/units.py:28
   assert_multipliable(): EXACTLY ONE currency factor.
   0 → "not a TAM"; >1 → "money double-counted" (money²).
        │
        ▼
④ Verifier / critic  resolver/verify.py:38
   plausibility (positive, finite, < 1e13) → stamps a
   "dark_estimate" banner. ONLY on the synthesized path;
   registry-sourced numbers are already pinned & trusted.
```

The point: a fabricated number cannot acquire a real tier, cannot cross units,
and if synthesized at all wears a loud `dark_estimate` / `MODELED` banner
downstream. **The worst-case outcome — an LLM hallucination becoming a citable
primitive — is structurally blocked.** No LLM-projected primitives, ever (Q20).

---

## 6. The two other guards (scope + verbatim)

These are what make "which market does this number actually describe" checkable.

**Verbatim guard** (`sizing/guard.py` — the Q20 wall, pure/deterministic, no LLM).
When sourcing a number from analyst prose, two gates in series:

```
analyst sentence: "...the US market reached $4.2 billion in 2024..."
        │
        ▼
Gate 1 — magnitude + role locality        guard.py:173
   the claimed magnitude ($4.2B) must appear as a numeric
   surface form whose SAME CLAUSE mentions the role keyword.
   tolerance ±0.5%.
        │
        ▼
Gate 2 — corroboration
   magnitude must reappear in ≥1 other role-matched sentence
   OR a second independent source.
        │
        ▼
verdict:  verbatim_corroborated → public-eligible
          verbatim_single       → org-private only
          semantic_mismatch/absent → REJECT
```

**Scope guard** (`scope/guard.py`, also pure). A `MarketScope` (vertical→NAICS,
persona→SOC, segment→firm-size band, geo→ISO) sits on both the Concept (declared)
and each primitive (true). The guard classifies declared-vs-actual per dimension:

```
exact / narrower / broader / partial / disjoint / unknown
        │
        ▼
ScopeReport attached to every TAM (derived, NOT in hash)
"displayed scope is ALWAYS the primitive's truth" (snap-to-truth)
```

This is what explains the $2.0B-vs-$31.2B spread on the demo: the bottoms-up
input is wholesale-only (SOC 41-4012, NARROWER), the top-down inputs are
mid-market-only. The disagreement *gets a page*, not a footnote. `scope/guard.py:293`.

---

## 7. Backend API surface (FastAPI)

App factory `api/app.py:199`. The routes you'll be asked to name:

```
READ THE LIBRARY
  GET  /c, /c/{slug}              concepts (the "disagreement view")
  GET  /p, /p/{slug}             atomic + composite primitives
  GET  /f, /f/{slug}             frameworks
  GET  /signals, /signals/{slug} quarantined prediction-market signals (read-only)
  GET  /report/{concept_slug}    question-driven sourced report

SIZE & FREEZE
  GET  /build/{concept_slug}            size → TAMOutput
  POST /build/recompute                 EvalOverrides / scope override (what-if)
  GET  /build/{slug}/trajectory         TAM-over-time
  GET  /build/{slug}/sensitivity        tornado (|impact|-sorted)
  POST /build/{slug}/promote            freeze a TAM
  GET  /tam/{state_hash}                fetch frozen artifact by hash
  GET  /browse                          promoted TAMs

DYNAMIC RESOLUTION
  POST /resolve   (SSE)          NL query → Claude parse → Exa search → tree, STREAMED

SUBSTRATE / COMPANY
  GET  /audit                    resolve/recompute events
  GET  /usage, /metrics          per-org metering + Prometheus metrics
  GET  /connectors               connector catalog × live bank (host-attributed counts)
  GET  /portfolio                cached offline portfolio sizing
  GET  /lineage/{concept_slug}   concept lineage

CONTRIBUTION (validator-gated)
  POST /contribute               regulator/first-party auto-accept org-private; rest queue
  GET/POST /integrations/{provider}/...   inbound SaaS OAuth → org-private primitives
  GET/POST/PATCH/DELETE /me/...  per-user primitives, saved TAMs, audit

AGENTS
  /mcp                           MCP server (ASGI mount, auth-gated)
```

Observability middleware (`app.py:162`) stamps request-id + structured timing +
per-org metering on every call.

---

## 8. MCP — the agent surface (the thesis)

`mcp/tools.py` — 12 tools, every numeric payload cited via `_cite()`
(`tools.py:40`); modeled numbers emit `source_url=None` (never a fabricated host).

```
                 ┌──────────────── AGENT (Claude, Cursor, …) ──────────────┐
                 │  "verify this market claim" / "size my portfolio"        │
                 └───────────────────────────┬─────────────────────────────┘
                                              │ MCP (stdio local / HTTP /mcp auth)
  READ (sourced)            WHAT-IF                 LIVE              WRITE (gated)
  search_concepts          build_tam (override-     get_connector_   import_portfolio
  get_primitive             aware, never persisted)  data [LIVE]      size_company
  list_frameworks          size_tam (hash-pinned    (STRATA_MCP_     list_portfolio
  list_primitives           scenario tree)           LIVE_CONNECTORS) (STRATA_PORTFOLIO
  list_connectors          resolve_market                             _ENABLED)
                            (registry-first,
                             NO LLM synthesis —
                             matched:true/false)
```

`resolve_market` is the honesty showpiece: it's **registry-first and LLM-free** —
it either matches a sourced TAM (`matched:true`) or admits `matched:false`. It will
not invent. `tools.py:166`.

---

## 9. Source tiers (the honesty ladder)

`models/source.py:24` — 9 tiers, ordered by trust. Tier is **derived from the host
class**, never asserted by the writer/LLM:

```
first_party ─ regulator ─ aggregator ─ analyst ─ analyst-paraphrase ─
community ─ onchain ─ prediction_market ─ community-modeled
   trusted ─────────────────────────────────────────► graded/fenced
```

- **Quarantined (never reach the evaluator):** `prediction_market`, `community`
  — `NON_SIZING_TIERS`, enforced on BOTH the DB and YAML load paths
  (`source.py:52`). The 202 Kalshi signals live in `data/signals/`, surfaced
  read-only at `/signals`, fenced by a "never feeds a TAM" banner.
- **Modeled (sizing-eligible but loudly fenced):** `community-modeled`,
  `analyst-paraphrase`, `analyst` → `_MODELED_TIERS` → `ProvenanceClass.MODELED`
  → a loud `MODELED` banner downstream (`primitive.py:34`, `engine.py:395`). The
  YAML *can't* mislabel a modeled number as sourced — `provenance_class` is
  *derived* from the tier, not declared (`primitive.py:126`).
- `analyst-paraphrase` is a special source type: ≤280-char paraphrase + mandatory
  publisher/reviewer (`source.py:91`).

**The strategic insight (from the adversarial review):** the *most valuable*
numbers — capture rate, ACV, adoption — are all `community-modeled`, i.e. the
*least* trustworthy under a binary fence. The roadmap move is to make the MODELED
fence **graded, not binary** — own the "defensible-assumption layer."

---

## 10. Connectors (the data bank intake)

23 typed ingest connectors; 13 currently produce committed primitives. Each
follows a **6-layer pattern** (`connectors/CLAUDE.md`):

```
① Enums (API constants)
② TypedDicts (raw API response shapes)
③ frozen dataclasses (validated internal models)
④ one unified *Response return type
⑤ disk cache  ~/.strata/cache/{connector}/
⑥ context-manager Client (one method per endpoint)
   + *_to_primitive_yaml() / *_to_source_yaml() converters
```

```
manifest (concept-linked arg_sets)
        │  data/ingest-manifest.yaml
        ▼
strata ingest run ──► live API ──► disk cache ──► YAML converter
        │
        ▼
strata promote --from-ingest [--validate-only]
   stage batch → validate once → roll back only attributed offenders
        │
        ▼
data/primitives/*.yaml  (hash-pinned, validated, committed)
        │
        ▼
strata db seed ──► Postgres (production primary store)
```

Connectors: bls, fred, census, edgar, worldbank, kalshi, oecd, eurostat,
comtrade, fdic, cms, eia, usda_nass, faa, openfda, alpha_vantage,
nasdaq_data_link, yfinance, reddit, github, stack_exchange, twitter. Each is
typed → disk-cached → sha256-pinned → DB. Capability manifests
(`connectors/_capability.py`) are serialized into an Anthropic system block so the
router can pick the right connector for a query (`router.py`).

**Inbound SaaS connectors** (`connectors/saas/`) are different — OAuth into a
customer's HubSpot etc. → Fernet-encrypted org-scoped tokens → **org-private
first-party primitives** (isolated cross-tenant; disconnect purges). 4-method
contract: `authorize_url / exchange_code / fetch / to_private_primitives`
(`saas/base.py:19`).

---

## 11. Storage & deploy (one breath)

```
Production (Railway):  Postgres = primary. YAML baked into Docker image as seed.
                       `strata db seed` once after deploy. RLS on app.org_id
                       (cross-tenant read = 0 rows). Prod resolver = paid
                       Anthropic SDK (STRATA_LLM_BACKEND=anthropic).
Local dev:             YAML on disk → in-memory Registry (no DB needed) OR
                       seed local Postgres.
CI / tests:            YAML loader directly, no Postgres. 798 backend tests,
                       pyright strict + ruff + biome clean.
```

---

## 12. The 8 answers, compressed (rapid-fire YC version)

1. **What's unique about your primitives/lenses?** One atomic sourced number per
   primitive (hash-pinned); frameworks have *zero scalar defaults* (every input is
   a citable slug, statically unit-checked); 6 structurally-distinct lens shapes,
   not one regression.
2. **How do you make trees?** `size_concept` picks every framework matching the
   concept's lens+scope, resolves each input slug to a sourced value, walks a
   closed-AST formula, and emits a *scenario tree* — never a scalar. ≥2
   independent families → a convergence banner.
3. **Hashing?** Canonicalize the math payload (sort keys, tight separators) → one
   sha256. Equivalent states collide; one-field change = new `/tam/<hash>`.
   Display fields and derived reports are excluded by design.
4. **Verification?** Two hashes: `snapshot_sha256` pins the source bytes
   (`verify-integrity` re-hashes the store), `state_hash` pins the computation.
   Plus four LLM guards: host allowlist, host-derived tier, unit guard, plausibility
   critic.
5. **Citations?** Every primitive carries `source_url + tier + snapshot_sha256`;
   tier is derived from the host class, never the LLM; fabricated hosts rejected;
   modeled numbers cite their open model-definition file, not a fake host.
6. **Backend APIs?** Read (`/c /p /f /signals /report`), size+freeze
   (`/build /recompute /tam /browse /sensitivity`), dynamic (`/resolve` SSE),
   substrate (`/audit /usage /metrics /connectors /portfolio`), contribute
   (`/contribute /integrations /me`), agents (`/mcp`).
7. **Agents?** 12 MCP tools; `resolve_market` is registry-first and LLM-free
   (matched:true/false, never invents) — agents are the contributor flywheel.
8. **Trust fence?** Quarantined tiers never reach the evaluator; modeled tiers
   are derived (YAML can't lie) and wear loud banners; no LLM-projected primitives
   ever. The honesty fence is the product.

---

*Grounding: evaluator `evaluator/engine.py`, hashing `hashing.py`, integrity
`integrity.py`, guards `resolver/{citations,units,verify}.py` +
`sizing/guard.py` + `scope/guard.py`, models `models/{primitive,framework,unit,
tam_output,source}.py`, APIs `api/routes/`, MCP `mcp/tools.py`, connectors
`connectors/`.*
