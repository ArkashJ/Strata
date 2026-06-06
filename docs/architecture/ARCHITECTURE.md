# Strata — Architecture (Mermaid reference)

Living architecture map, recovered from a full-codebase synthesis (every claim traced to
`file:line` in the backend/frontend). Diagrams are grouped: **system → data → flows →
subsystems → frontend**. Render in any Mermaid-aware viewer (GitHub, VS Code, Obsidian).

> Sibling docs: [`charts-and-dashboards.md`](charts-and-dashboards.md) (PR 3 chart system),
> the v1.0 program in [`../plans/2026-06-06-v1-program.md`](../plans/2026-06-06-v1-program.md),
> and the question bank in [`../questions/README.md`](../questions/README.md).

---

## 1. System context

```mermaid
flowchart LR
  subgraph FE["Frontend · Next.js 16 (Vercel)"]
    direction TB
    Pages["routes /build /tam /bank /explore /connectors ..."]
    Clerk_fe["Clerk (frontend-only auth)"]
  end
  subgraph BE["Backend · FastAPI (Railway)"]
    direction TB
    Routes["/c /p /f /build /resolve /tam /audit /connectors ..."]
    Eval["Evaluator + AST formula engine"]
    Reg["Registry (in-mem; from YAML dev / from DB prod)"]
    MCP["MCP server: stdio + /mcp HTTP"]
  end
  PG[("Postgres + Alembic\n(migrations 001-007)")]
  CX["~23 typed connectors\n(13 producing committed primitives)"]
  EXT_A["Anthropic SDK\n(resolver parse/route)"]
  EXT_E["Exa\n(fenced fallback)"]
  EXT_C["Clerk (JWKS)"]

  FE -->|HTTP / SSE| Routes
  Clerk_fe -. "session (today: not verified server-side)" .-> EXT_C
  Routes --> Eval --> Reg
  Reg <--> PG
  Routes --> CX
  Routes -->|"parse/route only"| EXT_A
  Routes -->|"fallback (double-fenced, off by default)"| EXT_E
  MCP --> Reg
```

Note the **Clerk gap**: today Clerk authenticates only the frontend; the backend trusts
`X-API-Key` → `Principal(org_id)`. The v1.0 program adds server-side Clerk-JWT verification.

---

## 2. Five-layer data model

```mermaid
erDiagram
  CONCEPT ||--o{ ATOMIC_PRIMITIVE : "measured-by"
  ATOMIC_PRIMITIVE ||--o{ COMPOSITE_PRIMITIVE : "bundled-into (same-unit set ops)"
  FRAMEWORK ||--o{ FRAMEWORK_VARIANT : "has"
  FRAMEWORK_VARIANT }o--o{ ATOMIC_PRIMITIVE : "binds role->slug"
  FRAMEWORK ||--o{ SCENARIO : "emits"
  SCENARIO }o--|| TAM_OUTPUT : "aggregated-into"
  SCENARIO ||--o{ INPUT_USED : "records"
  ATOMIC_PRIMITIVE ||--|| SOURCE : "cites"
  CONCEPT {
    string slug
    enum analysis_lens "primary (+secondary)"
    json scope "declared MarketScope"
    list measurements "competing primitives"
    json modifiers "opex/margin/regulatory/risk"
  }
  ATOMIC_PRIMITIVE {
    float value
    json unit "kind,dimension,currency,basis"
    json scope "ACTUAL scope (snap-to-truth)"
    string visibility "public|private"
    string org_id "tenant"
    enum provenance_class "DERIVED from source.tier"
    string snapshot_sha256 "Q5 content pin"
  }
  COMPOSITE_PRIMITIVE {
    enum set_operation "union|intersection|filter|restrict_by_tag"
    list inputs "same-unit atomics"
  }
  FRAMEWORK {
    enum lens "single"
    enum method_family
    string formula "closed AST, validated at load"
  }
  TAM_OUTPUT {
    string state_hash "permalink"
    json convergence "triangulation"
    float independence_score
    json scope_report "declared vs actual"
    bool uses_synthetic_primitives
  }
  INPUT_USED {
    string primitive_slug
    string snapshot_sha256
    string source_url
    string source_tier
  }
```

---

## 3. Ingest pipeline

```mermaid
flowchart TD
  MAN["data/ingest-manifest.yaml\n(connector, method, arg_sets)"] --> RUN["strata ingest run"]
  RUN --> ELIG{"eligible?\n(keyless OR key present)"}
  ELIG -->|no key| SKIP["skip (honest)"]
  ELIG -->|yes| DISP["connectors._dispatch.call_and_convert"]
  DISP --> WRITE["writer.upsert_primitive\n(refuses MODELED; real-host assert; dedup hash)"]
  WRITE --> AUTO["~/.strata/auto-primitives/*.yaml"]
  AUTO --> PROM["strata promote --from-ingest\n(stage → validate batch → rollback offenders)"]
  PROM -->|MODELED fence| REJECT["refuse modeled/soft-data"]
  PROM --> COMMIT["data/primitives/*.yaml (committed)"]
  COMMIT --> SEED["strata db seed"]
  SEED --> PG[("Postgres")]
```

---

## 4. Resolve flow (`POST /resolve`, SSE)

```mermaid
sequenceDiagram
  participant C as Client
  participant R as routes/resolve.py
  participant P as resolver/pipeline.run()
  participant Cl as Claude
  participant Ex as Exa
  C->>R: POST /resolve {query}
  R->>R: enforce_rate_limit(org_id)
  R-->>C: SSE parsing
  R->>P: run() in thread
  P->>P: registry-first match_concept (LLM-free)
  alt concept hit (conf>=0.5)
    P->>P: Step1 size_concept → scenario tree
    P->>P: Step2 compose registry primitives
  else miss
    P->>P: Step3 connector live (HTTP: allow_live=False → SKIP)
    P->>Ex: Step4 Exa fallback (only if STRATA_ALLOW_EXA_FALLBACK=1)
    Ex-->>P: candidates (ephemeral, never persisted)
  end
  P-->>C: SSE searching→framework_selected→evaluating→result→done
```

---

## 5. Build / recompute + state-hash

```mermaid
flowchart LR
  B["GET /build/{slug}"] --> SC["size_concept"]
  RC["POST /build/recompute\n{framework_assumptions, primitive_overrides, scope}"] --> UV["validate override units\n(422 on mismatch)"]
  UV --> EO["EvalOverrides\nwhat-if = banner + ephemeral\nassumption = re-point, schema-pure"]
  EO --> SC
  SC --> H["state_hash (overrides fold in;\nequivalent states collide)"]
  H --> PS["persist_tam + remember_tam (FIFO)"]
  PS --> TAM["/tam/<hash> (cache → DB fallback)"]
```

---

## 6. Evaluator + AST formula engine

```mermaid
flowchart TD
  SZ["size_concept(reg, slug, overrides?)"] --> IT["_iter_scenario_builds\n(one per framework whose variant.scope==slug\nAND lens ∈ {primary, secondary})"]
  IT --> RI["_resolve_input per role\natomic: value+hash · composite: union fsum"]
  RI --> ENV["env: {name → float}"]
  ENV --> FP["parse(fw.formula) → AST"]
  FP --> EVAL["eval_node (closed: + - * , min|max|clamp|logistic|curve, consts 0/1)"]
  EVAL --> SCN["Scenario {value, unit, inputs_used, banners}"]
  SCN --> AGG["aggregate → convergence (≥2 families) + independence"]
  AGG --> OUT["TAMOutput {state_hash, scenarios, scope_report}"]
```

---

## 7. Six lenses → frameworks → required roles

```mermaid
flowchart LR
  L1[cost_efficiency] --> R1["persona_pool · addressable_share · replacement_rate · cost_per_persona"]
  L2[revenue_generation] --> R2["target_segment_count · spend_per_target · capture_rate"]
  L3["latent_demand ⚠ 0 frameworks, 0 concepts"] --> R3["addressable_population · adoption_rate_curve · willingness_to_pay"]
  L4[platform_throughput] --> R4["gmv_or_volume · take_rate · market_share_assumption"]
  L5[bundle_consolidation] --> R5["tools_displaced · spend_per_tool · consolidation_rate · pricing_discount"]
  L6[productivity_uplift] --> R6["persona_count · productivity_gain_pct · value_split_to_vendor"]
  R1 --> F["frameworks\n(5 today → 25+ at v1.0)\nvalidator: concept.lens ∋ framework.lens"]
  R2 --> F
  R3 --> F
  R4 --> F
  R5 --> F
  R6 --> F
```

---

## 8. Auth + multi-tenancy (current + the Clerk bridge)

```mermaid
flowchart TD
  Req[request] --> HJ{"Authorization: Bearer JWT?\n(NEW)"}
  HJ -->|yes + Clerk configured| V["verify vs Clerk JWKS\n(cached, kid-refresh)"]
  V -->|valid| P1["Principal{org_id=clerk_org:* | clerk_user:*, user_id=sub}"]
  V -->|invalid| E1[401]
  HJ -->|no| HK{X-API-Key?}
  HK -->|yes| P2["Principal{org_id from key store}"]
  HK -->|no| RA{require_auth?}
  RA -->|yes| E1
  RA -->|no| P3["anonymous Principal(org_id=public)\nkeyless prod preserved"]
  P1 --> S["set app.org_id → RLS policies (mig 003/006/008/009)"]
  P2 --> S
```

---

## 9. Soft-data fence (the trust contract)

```mermaid
stateDiagram-v2
  [*] --> TierCheck
  TierCheck --> Sourced: regulator / aggregator / first_party
  TierCheck --> Modeled: community-modeled / analyst-paraphrase / analyst
  Sourced --> Cite: SourcedNumber links real source_url + snapshot
  Modeled --> Banner: per-scenario MODELED banner ("do not cite as fact")
  Modeled --> NoCite: source_url=None when strata.internal
  Banner --> Promote: strata promote REFUSES modeled
  note right of Modeled
    PR0 trust fix: kill strata.internal URLs,
    replace fake d3d3 snapshots, honest footer claim,
    render MODELED at the number (not only banner)
  end note
```

---

## 10. Two-tier data bank (private ↔ shared via agents)

```mermaid
flowchart LR
  subgraph Priv["My Bank · org-scoped (RLS)"]
    UP["user_primitives (visibility=private)"]
    SB["saved TAMs · boards · audit"]
  end
  subgraph Shared["Strata Bank · /explore"]
    PUB["public sourced primitives + frameworks + concepts"]
  end
  AG["Agents (CLI / MCP)\nevery call logged to audit_events"]
  Priv -->|"push (validator-gated → contribute queue)"| AG
  AG -->|"pull (read public into a build)"| Priv
  AG --> Shared
```

---

## 11. Validator (3-layer) + guards

```mermaid
flowchart TD
  V["validate(data_dir)"] --> ST["structural (Pydantic/loader)"]
  ST -->|clean| SE["semantic"]
  SE -->|clean| CR["cross_record (build Registry first)"]
  CR --> C1["measurement links"]
  CR --> C2["framework variant + unit-signature (Q4)"]
  CR --> C3["formula coherence (parse + infer_unit)"]
  CR --> C4["role coverage (WARN)"]
  CR --> C5["secondary-lens overlap (WARN)"]
  CR --> C6["⊕ NEW: question-answer resolvability (PR4)\nreject answers resolving to reg.signals"]
  subgraph Guards["cross-cutting guards"]
    SG["scope guard (declared vs actual)"]
    VG["verbatim guard"]
    CIT["citation allowlist (no fabricated hosts)"]
    UG["unit guard (no money²)"]
  end
```

---

## 12. Frontend route / IA map

```mermaid
flowchart TD
  subgraph WORK
    H["/"]:::live
    B["/build (+ ?mode=studio NEW PR2)"]:::live
    PF["/portfolio"]:::live
  end
  subgraph MYDATA["MY DATA"]
    BK["/bank (real CRM, PR1)"]:::live
    DSH["/dashboard → boards (PR1/PR3)"]:::new
    AG["/agents"]:::live
  end
  subgraph BANKGRP["STRATA BANK"]
    EX["/explore"]:::live --> EXT["concepts|primitives|frameworks|signals|pyramid|tams"]
  end
  subgraph SRC["SOURCES"]
    CN["/connectors"]:::live
    IN["/integrations"]:::live
  end
  CP["/c/<slug>"]:::live --> CR["/c/<slug>/report (150-Q report, PR4)"]:::new
  TM["/tam/<hash>"]:::live --> TR["/tam/<hash>/report (PDF target, PR3 fix)"]:::live
  classDef new fill:#eef,stroke:#5b5bd6;
  classDef live fill:#fff,stroke:#999;
```

---

## 13. MCP tool surface (12 tools)

```mermaid
flowchart LR
  subgraph READ
    a[search_concepts]; b[get_primitive]; c[list_frameworks]; d[size_tam]
    e[resolve_market\nLLM-free]; f[list_primitives]; g[build_tam\nwhat-if, never persisted]; h[list_connectors]
  end
  subgraph LIVE
    i["get_connector_data\n(STRATA_MCP_LIVE_CONNECTORS=1)"]
  end
  subgraph WRITE
    j["import_portfolio"]; k["size_company"]; l[list_portfolio]
  end
  M["/mcp (McpAuthMiddleware: 401/429/meter)\n+ stdio (local-trust)"] --> READ
  M --> LIVE
  M --> WRITE
```

---

## 14. Migrations timeline

```mermaid
timeline
  title Alembic migrations
  001 : data bank tables (primitives, sources, concepts, frameworks)
  002 : audit_events
  003 : substrate auth + RLS (api_keys, usage_events, tenant_data)
  004 : contributions (review queue)
  005 : tam_outputs (durable permalinks)
  006 : companies (portfolio + RLS)
  007 : scope JSONB on primitives + concepts
  008 : ⊕ org_id on tam_outputs + audit_events (PR1)
  009 : ⊕ user_primitives, boards, board_items (PR1)
```

---

## Design-system anchor

Tokens are committed and load-bearing ("The Sourced Ledger"): paper `--bg-0 #fafafa`, ink
`--fg-1 #0a0a0b`, accent indigo `--accent #5b5bd6`, AA-verified muted `--fg-3 #6b6b73`.
Type: Instrument Serif (display) + Geist (body) + tabular Geist Mono (numbers). Chart vars:
`--chart-1..6` alias accent + tier hues; `--chart-lens-*` carry the cool lens family.
**A colour means one thing** — tier ramp = provenance, cool family = lens. See
[`charts-and-dashboards.md`](charts-and-dashboards.md).
