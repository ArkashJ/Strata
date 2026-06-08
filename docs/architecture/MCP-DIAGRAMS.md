# Strata MCP — architecture diagrams

Detailed Mermaid diagrams of the Strata MCP server: the surface agents drive to
generate and verify sourced market research. Companion to
[`DIAGRAMS.md`](DIAGRAMS.md) (whole-system) — this file zooms into the **MCP**.

As of 2026-06-08 the live surface is **26 tools** over two transports. Verified
live: `https://strata-api-production-9740.up.railway.app/mcp/`.

---

## 1. The 26-tool surface, by tier

```mermaid
graph TD
    subgraph CALLER["AI tool of choice (Claude, IDE agent, ChatGPT)"]
        AG["Agent / analyst"]
    end

    AG -->|stdio or HTTPS /mcp| SRV{{"strata.mcp server<br/>call_tool dispatch"}}

    SRV --> READ["READ · sourced data (11)"]
    SRV --> REPORT["REPORT · async DB (2)"]
    SRV --> LIVE["LIVE · network-gated (1)"]
    SRV --> PORT["PORTFOLIO write (3)"]
    SRV --> BANK["PRIVATE BANK write (2)"]
    SRV --> FB["FEEDBACK loop (3)"]
    SRV --> ADMIN["ADMIN cross-org (2)"]
    SRV --> GAP["SOURCING-GAP (2)"]

    READ --- R1["whoami · search_concepts · get_primitive<br/>list_primitives · list_frameworks · list_connectors<br/>size_tam · resolve_market · build_tam<br/>verify_market_claim · get_report"]
    REPORT --- R2["get_report_for_tam · export_report<br/>(branded HTML + WeasyPrint PDF)"]
    LIVE --- R3["get_connector_data<br/>[STRATA_MCP_LIVE_CONNECTORS=1]"]
    PORT --- R4["import_portfolio · size_company · list_portfolio<br/>[STRATA_PORTFOLIO_ENABLED]"]
    BANK --- R5["save_primitive · list_my_primitives<br/>(org-private, RLS)"]
    FB --- R6["submit_feedback · list_feedback · apply_feedback<br/>(org-scoped, RLS)"]
    ADMIN --- R7["admin_list_feedback · admin_promote_correction<br/>[STRATA_ADMIN_ORGS — audited GUC]"]
    GAP --- R8["report_sourcing_gap · list_sourcing_gaps<br/>(demand-ranked backlog)"]

    classDef write fill:#5B5BD6,color:#fff;
    classDef read fill:#eef;
    class PORT,BANK,FB,ADMIN,GAP write;
    class READ,REPORT,LIVE read;
```

**Invariant:** every numeric payload carries its citation (`source_url`,
`source_tier`, `snapshot_sha256`, `integrity`). No tool ever returns a fabricated
number — a miss is flagged `unsourced=true`, never synthesized (Q20).

---

## 2. Transport + auth + tenant isolation

```mermaid
flowchart TD
    start(["MCP request"]) --> trans{transport?}

    trans -->|"stdio (local-trust)"| stdio["no auth middleware<br/>org = 'default'<br/>(write tools refuse: no tenant)"]
    trans -->|"HTTPS /mcp"| mw["McpAuthMiddleware"]

    mw --> hdr{credential?}
    hdr -->|"Authorization: Bearer strata_sk_…"| key["API-key store<br/>→ Principal{org_id}"]
    hdr -->|"Authorization: Bearer <JWT>"| clerk["verify vs Clerk JWKS<br/>→ Principal{org_id=clerk_org|clerk_user}"]
    hdr -->|"Bearer <opaque>"| oauth["OAuth access-token cache<br/>(expiry + RFC8707 audience)<br/>→ Principal{org_id}"]
    hdr -->|"X-API-Key"| key
    hdr -->|none| anon{"require_auth?"}
    anon -->|yes| r401["401"]
    anon -->|no| pub["anonymous Principal(org=public)"]

    key --> rl["rate-limit (token bucket)<br/>→ 429 + Retry-After"]
    clerk --> rl
    oauth --> rl
    rl --> ctx["set current_principal ContextVar<br/>(MCP SDK can't thread ASGI scope)"]
    ctx --> disp["call_tool(reg, name, args)"]
    disp --> scope["org_session_scope(org_id)<br/>SET app.org_id (txn-local)"]
    scope --> rls[("Postgres RLS<br/>org_id = current_setting('app.org_id')<br/>fails CLOSED when unset")]
    disp --> meter["meter usage on 2xx"]
```

The `current_principal` **ContextVar** is the key trick: the MCP SDK doesn't pass
the ASGI scope into tool callbacks, so the middleware stashes the authenticated
`Principal` in a ContextVar that write/portfolio/feedback tools read.

---

## 3. Request lifecycle of one sourced TAM (`size_tam`)

```mermaid
sequenceDiagram
    participant A as Agent
    participant M as MCP server
    participant R as Registry (YAML dev / PG prod, 30s TTL)
    participant E as Evaluator (AST formula engine)
    participant C as Cache + tam_outputs (PG)

    A->>M: tools/call size_tam {concept_slug}
    M->>R: load concept + its frameworks + primitives
    R-->>M: Concept, Framework[], AtomicPrimitive[]
    M->>E: size_concept(reg, slug)
    Note over E: multiply unit-checked inputs per framework variant<br/>→ scenario tree; convergence if ≥2 independent families
    E-->>M: TAMOutput {scenarios[], method_families, convergence,<br/>independence_score, scope, state_hash}
    M->>C: remember_tam (FIFO cache) + persist
    M-->>A: {matched:true, scenarios[], charts, permalink,<br/>every input cited (url+tier+sha256+integrity)}
    Note over A,M: resource_links → strata://primitive/<slug>,<br/>strata://tam/<hash>; next_actions → get_report_for_tam, build_tam
```

A **miss** (`resolve_market` with no curated concept) takes the honest branch
instead — see diagram 5.

---

## 4. The feedback flywheel (org loop → admin promote to shared bank)

```mermaid
flowchart TD
    bad["Agent/analyst spots a wrong number or bad assumption"] --> sub["submit_feedback<br/>(kind, target, body, suggested_value?)"]
    sub --> fe[("feedback_events<br/>org-scoped RLS<br/>migration 014/015")]

    fe --> lst["list_feedback<br/>(own org, status filter)"]
    lst --> dec{applicable kind?<br/>primitive_correction / missing_data}
    dec -->|yes| app["apply_feedback"]
    dec -->|"no (commentary, E1)"| triage["stays a triage note<br/>never mutates math"]

    app --> fence1{"shared/private fence<br/>modeled/analyst tier?"}
    fence1 -->|refused Q20| rej["ModeledFenceError"]
    fence1 -->|sourced| up[("user_primitives<br/>org-private, RLS<br/>migration 009")]
    up --> link["flag → RESOLVED<br/>+ resolved_primitive_id"]

    link --> nextagent["next agent: list_my_primitives<br/>sees the fix"]

    %% admin cross-org governance
    fe -. "STRATA_ADMIN_ORGS only" .-> alf["admin_list_feedback<br/>(EVERY org, attributed)"]
    alf --> pick["owner picks a high-value correction"]
    pick --> apc["admin_promote_correction<br/>(admin_session_scope: app.is_admin GUC)"]
    apc --> fence2{"validate_and_fence_shared_primitive<br/>modeled/analyst?"}
    fence2 -->|refused Q20| rej
    fence2 -->|sourced| yaml["returns committable<br/>data/primitives/&lt;slug&gt;.yaml<br/>(prod-safe: no server disk write)"]
    yaml --> cli["strata admin promote &lt;id&gt; --org X<br/>writes + commits in a checkout"]
    cli --> shared[("SHARED bank<br/>data/primitives/*.yaml<br/>→ strata db seed → every org")]

    classDef danger fill:#fee,stroke:#c00;
    class rej danger;
```

**E1 holds throughout:** a flag is commentary; applying one *creates* a new
(private, then optionally promoted) number — it never silently rewrites a sourced
one. **Q20 holds at both doors:** modeled/analyst tier is refused into the private
*and* the shared bank.

---

## 5. The sourcing-gap loop (novel query → ranked demand → connector → sourced)

```mermaid
flowchart LR
    q["First-time query"] --> rm["resolve_market"]
    rm --> hit{curated concept match?}
    hit -->|yes| sized["sourced scenario tree<br/>(diagram 3)"]
    hit -->|no| miss["matched:false<br/>unsourced:true<br/>independence_score:0<br/>next_action → report_sourcing_gap"]

    miss --> rep["report_sourcing_gap<br/>(agent-native: the agent reports the miss)"]
    rep --> dedup{"dedup_key<br/>(org_id, normalized query / resource_target)"}
    dedup -->|new| ins[("sourcing_gaps INSERT<br/>migration 017, closed RLS")]
    dedup -->|seen| bump["ON CONFLICT → hit_count++<br/>incoming resource_target wins"]
    ins --> rank
    bump --> rank["list_sourcing_gaps<br/>most-demanded first"]

    rank -->|"scope=all (admin)"| backlog["platform-wide demand-ranked backlog<br/>= which connector to build next"]
    backlog --> build["build the connector for the top gap<br/>(ingest run → promote --from-ingest)"]
    build --> prim[("committed data/primitives/*.yaml")]
    prim --> close["strata gaps resolve &lt;id&gt;<br/>→ status=sourced + link primitive"]
    close --> requery["next query for that vertical<br/>resolves SOURCED, not unsourced"]

    classDef honest fill:#fff3cd,stroke:#b80;
    class miss honest;
```

**A gap is a demand signal, never a number (E1)** — it never feeds the evaluator.
It is the supply-side twin of feedback: *feedback says a number is wrong; a gap
says there is no number here yet.*

---

## 6. Admin cross-org bypass — additive, never fail-open

```mermaid
flowchart TD
    call["admin_* tool call"] --> gate{"auth.is_admin(principal)?<br/>org ∈ STRATA_ADMIN_ORGS<br/>(anon/public refused)"}
    gate -->|no| forbid["error: forbidden<br/>(never another org's data)"]
    gate -->|yes| ascope["admin_session_scope(org)<br/>SET app.org_id = own<br/>SET app.is_admin = 'on'  (txn-local)"]

    ascope --> pol{{"Postgres permissive policies (OR'd)"}}
    pol --> tenant["tenant_isolation<br/>org_id = app.org_id  (UNCHANGED)"]
    pol --> adminp["admin_read / admin_update<br/>app.is_admin = 'on'  (migration 016/017)"]

    tenant --> result
    adminp --> result["admin SELECT → every org's rows<br/>admin UPDATE → resolve cross-org<br/>WITH CHECK OR'd → passes"]

    note["GUC unset (normal request) ⇒ admin policy false<br/>⇒ behaves EXACTLY as before ⇒ a tenant sees only its own rows<br/>(verified empirically: 2nd tenant reads 0 rows)"]
    adminp -.-> note

    classDef safe fill:#e6ffe6,stroke:#0a0;
    class note safe;
```

This fixes the fail-*open* worry (#99): the cross-tenant read is an **explicit,
opt-in, audited GUC** OR'd alongside the closed policy — not a column-nullability
accident.

---

## 7. Five-layer data model as it surfaces through the MCP

```mermaid
graph TD
    C["Concept<br/>(curated identity, competing measurements)"] -->|measured-by| AP["Atomic Primitive<br/>(one source · one number · sha256-pinned)"]
    AP -->|bundled-into| CP["Composite Primitive<br/>(same-unit set ops)"]
    CP -->|consumed-by| FW["Framework<br/>(unit-crossing arithmetic · no scalar defaults)"]
    AP -->|consumed-by| FW
    FW -->|emits| TAM["TAM Output<br/>(scenario tree · convergence · permalink)"]

    AP -. "get_primitive / list_primitives" .-> mcpR["MCP read"]
    C -. "search_concepts / get_report" .-> mcpR
    FW -. "list_frameworks" .-> mcpR
    TAM -. "size_tam / build_tam / resolve_market<br/>verify_market_claim / export_report" .-> mcpR

    classDef layer fill:#f7f7ff,stroke:#5B5BD6;
    class C,AP,CP,FW,TAM layer;
```

Source tiers (trust order): `first_party · regulator · aggregator · analyst ·
analyst-paraphrase · community · onchain · prediction_market · community-modeled`.
The last three never feed a TAM (quarantined); the MCP exposes their tier so a
caller always knows how trustworthy a number is.

---

## 8. MCP trace capture: recording tool calls for replay and golden tests

```mermaid
flowchart TD
    call["MCP tools/call"] -->|every call| dispatch["_call_tool dispatch<br/>(server.py:106)"]
    
    dispatch -->|audit path| audit["_audit_call<br/>(hashed args)"]
    audit --> done["tool returns"]
    
    dispatch -->|trace path| trace["_trace_call (fire-and-forget)<br/>gated: STRATA_TRACE_CAPTURE"]
    trace --> record["record_trace_safe<br/>(args, result_summary + sha256, status, ms)"]
    record --> tool_traces[("tool_traces RLS<br/>session_id · seq · tool<br/>args · result_summary · result_sha256<br/>status · duration_ms")]
    tool_traces --> session_upsert["upsert trace_sessions<br/>(call_count++, last_seen_at)"]
    session_upsert --> prune["prune sessions > N per org<br/>(STRATA_TRACE_MAX_SESSIONS)"]
    
    done --> end1["✓ call completes"]
    prune --> end2["(fire-and-forget)"]
    
    agent["agent"] -->|optional| reasoning["record_session_reasoning<br/>(MCP tool)"]
    reasoning --> record_reason["record_reasoning<br/>(session_id, reasoning, outcome)"]
    record_reason --> trace_sessions[("trace_sessions RLS<br/>session_id (pk) · org_id<br/>call_count · reasoning<br/>outcome · created_at")]
    
    list_show["strata traces<br/>list|show|export|replay"]
    list_show -->|list/show| readers["list_sessions / get_session_calls<br/>(RLS-scoped, org or admin)"]
    readers --> display["ordered calls: seq · tool · status · ms<br/>+ reasoning block"]
    
    list_show -->|export| export["→ golden fixture<br/>backend/tests/fixtures/traces/<session>.json"]
    list_show -->|replay| replay["replay.py: registry-first, offline<br/>re-run call_tool per captured call<br/>sha256 diff: canonicalized result"]
    replay --> report["ReplayReport per call:<br/>{match: bool, captured_hash, fresh_hash}"]
    report -->|divergence?| status["exit non-zero (regression signal)"]
    report -->|all match| green["exit 0 (golden test)"]
    
    classDef capture fill:#e6f3ff,stroke:#5B5BD6;
    classDef rls fill:#fff,stroke:#0a0;
    classDef cli fill:#f7f7ff,stroke:#333;
    class trace,record,tool_traces,session_upsert capture;
    class tool_traces,trace_sessions rls;
    class list_show,replay,export cli;
```

**Two-tier capture (automatic + opt-in):** every MCP call is automatically recorded
(name, args, structural result summary + sha256, status, duration, org, session, seq)
fire-and-forget into RLS-scoped `tool_traces` + `trace_sessions` tables, gated off by
default (`STRATA_TRACE_CAPTURE`). The agent can opt-in to a second tier by calling
`record_session_reasoning` with its reasoning and a coarse outcome tag (ok / unsourced /
unverifiable / error / flagged), stitching WHY into the session. The replay side exports
a captured session to a golden fixture or replays it offline against current code,
sha256-diffing results to surface silent regressions — the instrument that makes
connector roadmapping evidence-driven.

---

## Tool index (quick reference)

| Tier | Tools | Gate |
|---|---|---|
| Read (sourced) | whoami, search_concepts, get_primitive, list_primitives, list_frameworks, list_connectors, size_tam, resolve_market, build_tam, verify_market_claim, get_report | — |
| Report (async) | get_report_for_tam, export_report | — |
| Live | get_connector_data | `STRATA_MCP_LIVE_CONNECTORS` |
| Portfolio (write) | import_portfolio, size_company, list_portfolio | `STRATA_PORTFOLIO_ENABLED` |
| Private bank (write) | save_primitive, list_my_primitives | auth (org) |
| Feedback (write) | submit_feedback, list_feedback, apply_feedback | auth (org) |
| Admin (cross-org) | admin_list_feedback, admin_promote_correction | `STRATA_ADMIN_ORGS` |
| Sourcing-gap | report_sourcing_gap, list_sourcing_gaps | auth (org); `scope=all` admin |
| Trace (capture) | record_session_reasoning | auth (org); `STRATA_TRACE_CAPTURE` |
