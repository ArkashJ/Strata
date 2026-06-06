# Strata Platform Evolution — Design Spec

> From internal TAM tool → paid product → community-curated data protocol.
> Approach C: Progressive Decentralization.

---

## Context

### What exists today (v0.2)

Working end-to-end pipeline: type any market → Claude parses query into lens +
primitives → Exa deep-searches → evaluator multiplies → SSE streams chain of
thought → ReactFlow graph renders.

**Pages:** Landing (`/`), Build (`/build?q=`), Data (`/data`)

**Backend:** 110 tests, 0 pyright errors, ruff clean. Models for all 6 record
types, evaluator, validator stubs, API routes for healthz/concepts/primitives/
frameworks/build/resolve.

**Data:** 6 concepts across 5 of 6 lenses (L1–L2, L4–L6; L3 latent_demand has no concept yet), 14 atomic primitives,
5 frameworks, 0 composites, 0 stored TAM outputs.

**Dynamic resolve:** POST `/resolve` → Claude (Sonnet) parses → Exa finds
primitives → evaluates → SSE stream. Tested with novel queries.

**Known architectural debt:** The `/resolve` endpoint reimplements framework
selection and TAM computation inline (hardcoded `FRAMEWORK_TEMPLATES` dict,
toy multiply loop) rather than calling `evaluator/engine.py`. This shadow
evaluator bypasses schema validation, snapshot pinning, independence scoring,
and the full framework variant system. Sprint 1A addresses this by hardening
`/resolve` and reconnecting it to the real evaluator for matched concepts.

### What this spec designs

Five gaps between current state and the full platform vision:

1. **Interactive wiring + sliders** — edit assumptions, see TAM update live
2. **Ingest pipeline (CLI + UI)** — the execute.md architecture, built
3. **API + auth for paid access** — sell to other VCs
4. **Contribution schema** — chain-portable fields on every record
5. **Upstream data connectors** — FRED, BLS, Census, etc.

### Strategic sequence

```
Phase 1 (now → v0.3): Internal tool for you + friend
  - Interactive wiring + sliders
  - Ingest CLI (direct-API path: BLS/FRED/EDGAR)
  - Contribution-ready schema (fields added, no chain yet)

Phase 2 (v0.4): Paid product for VCs
  - API keys + metering + subscription tiers
  - Ingest UI (draft review, approve/reject)
  - Multi-framework triangulation in dynamic queries
  - Export (PDF/markdown with citations)

Phase 3 (v0.5): Community contribution layer
  - Contributor profiles + attribution tracking
  - PR-based primitive submission + validator pipeline
  - Web form for annotations
  - Usage-based royalty accrual (Postgres, not chain)
  - Public leaderboard / reputation scores

Phase 4 (v1.0+): Optional chain anchor
  - Anchor contribution hashes to Base/Solana (batch)
  - Move royalty claims on-chain (trustless payouts)
  - Published TAMs get on-chain immutability proofs
```

---

## Gap 1: Interactive Wiring + Sliders

### Problem

The build view is read-only. Users see the graph but can't tweak assumptions
or swap primitives. A TAM is computed once from static YAML; there's no
"what if addressable share is 60% instead of 40%?" workflow.

### Design

**Three additions to `/build/<state-hash>`:**

#### 1a. Editable sliders on primitive values

Each primitive card in the ReactFlow graph gains a slider beneath the value.
Range defaults to ±50% of the base value (configurable). Dragging the slider
updates the framework output and TAM target in real-time.

```
┌─────────────────────────────────────┐
│  % of seats addressable by doc-gen  │
│  0.40                               │
│  0.20 ◄━━━━━━━●━━━━━━━━► 0.60      │
│  base value                         │
└─────────────────────────────────────┘
```

**Implementation:**
- Add `rangeMin` / `rangeMax` fields to `InputUsed` (default: value × 0.5,
  value × 1.5, clamped to [0, ∞) for ratios, [0, 1] for percentages)
- Slider state lives in the build page's React state (zustand store or
  useState — TBD based on complexity)
- On slider change: recalculate framework output client-side using the
  multiplicative formula (same math as `evaluator/engine.py`)
- Debounce 100ms to avoid jank
- **Note:** `rangeMin`/`rangeMax` belong in React state (zustand), NOT in
  the Pydantic `InputUsed` model. Stored records must be reproducible from
  source data alone — slider bounds are ephemeral view-layer config.

#### 1b. Primitive swap

Click a primitive card → opens a drawer showing other primitives attached to
the same concept with compatible units. Select one → it replaces the current
primitive in the wiring. TAM recalculates.

If no compatible primitive exists, offer "Search for one" which triggers the
ingest discovery flow (Gap 2).

#### 1c. Scenario snapshot

After adjusting sliders, user clicks "Save scenario" → current slider
positions are captured as a named scenario (bear/base/bull or custom name).
Multiple scenarios appear as rows in the scenario comparison chart on `/data`.

State is canonicalized (sorted keys) and sha256-hashed → mints a new
`/build/<state-hash>` URL. Browser history works as undo.

### Files to create/modify

```
web/src/components/PrimitiveSlider.tsx    — new slider component
web/src/components/PrimitiveSwapDrawer.tsx — new swap drawer
web/src/lib/evaluator.ts                  — client-side multiplicative calc
web/src/app/build/BuildView.tsx           — integrate sliders + swap
web/src/lib/schemas.ts                    — add rangeMin/rangeMax to InputUsed
backend/src/strata/models/tam_output.py   — NO CHANGE (slider range is view state, not data)
```

---

## Gap 2: Ingest Pipeline (CLI + UI)

### Problem

The `execute.md` pipeline architecture is fully designed but not built.
Currently all primitives are hand-written YAML. The resolve endpoint does
ad-hoc discovery via Claude + Exa, but there's no persistent ingest workflow
(discover → fetch → snapshot → extract → validate → gate → publish).

### Design

#### 2a. CLI surface (`strata ingest`)

Per `execute.md`, four commands:

```bash
strata ingest pull <source-slug>
  # One-shot: fetch → snapshot → extract → validate → tier-gate
  # If auto-publishable (regulator + validators pass): writes to data/primitives/
  # Else: writes draft to data/.drafts/ for review

strata ingest discover <concept-slug>
  # End-to-end: Exa search → candidate URLs → fetch best → extract → validate
  # Produces draft primitive(s) for review

strata ingest refresh [--tier regulator]
  # Run all due refreshes based on source-class cadence
  # Uses Perplexity Sonar as cheap "did it move?" probe (v0.4)

strata ingest status
  # Show pending drafts, last refresh times, scheduled scouts
```

#### 2b. Module layout

```
backend/src/strata/ingest/
  __init__.py
  cli.py              — Typer commands wired to main CLI
  discover.py          — Exa search → candidate URLs
  fetch/
    __init__.py
    api_client.py      — generic httpx + retry
    bls.py             — BLS API (OES, QCEW)
    fred.py            — FRED API (fredapi)
    edgar.py           — SEC EDGAR (XBRL + full-text)
    census.py          — Census Bureau API
    web.py             — Firecrawl/Jina fallback for HTML/PDF
  snapshot.py          — sha256 + blob store (filesystem)
  extract/
    __init__.py
    structural.py      — JSON/XBRL → primitive (no LLM)
    parallel.py        — Parallel Task API (v0.3)
  validate.py          — Q25 layered gate
  tier_gate.py         — auto-publish decision
  drafts.py            — draft CRUD (data/.drafts/)
```

#### 2c. Direct-API connectors (v0.2 scope)

Three connectors, free APIs only:

| Connector | What it pulls | Output primitive shape |
|---|---|---|
| `bls.py` | OES employment + wages by SOC code | `{value, unit: "persons" or "$/yr", source.tier: "regulator"}` |
| `fred.py` | Any FRED series by ID (GDP, CPI, rates) | `{value, unit: from series metadata, source.tier: "regulator"}` |
| `edgar.py` | Company financials from 10-K/10-Q XBRL | `{value, unit: "$/yr", source.tier: "first_party"}` |

Each connector:
1. Fetches raw response → stores snapshot (pretty-printed JSON, sha256)
2. Extracts value + metadata into draft primitive YAML
3. Runs validator chain
4. Tier-gate: regulator + all pass → auto-publish; else → draft

#### 2d. Ingest UI (`/ingest` page, Phase 2)

```
/ingest
├── Drafts awaiting review (approve / edit / reject)
├── Recent ingests (auto-published + manually approved)
├── Discovery launcher (concept slug → Exa search → results)
└── Refresh schedule (next due, last run, source tier filter)
```

Draft review shows: extracted value, source URL, snapshot hash, tier,
confidence score, validator results (pass/fail per check). One-click
approve writes to `data/primitives/` and git-commits.

### Files to create/modify

```
backend/src/strata/ingest/         — entire new module (see layout above)
backend/src/strata/cli.py          — wire `strata ingest` subcommand
backend/pyproject.toml             — add httpx (runtime), fredapi, pypdf
data/.drafts/                      — new directory for draft primitives
web/src/app/ingest/page.tsx        — new ingest UI page (Phase 2)
web/src/components/DraftReview.tsx  — draft approval component (Phase 2)
```

---

## Gap 3: API + Auth for Paid Access

### Problem

Currently the API is open, no auth, no rate limiting. Phase 2 requires
selling access to other VCs. Note: the Postgres connection layer already
exists (`backend/src/strata/db/` with SQLAlchemy 2.0 async engine and
session factory) — Sprint 4 adds tables and routes, not infrastructure.

### Design

#### 3a. API key system

Simple API key auth — no OAuth, no JWTs for v0.4.

```
POST /auth/keys          — create API key (admin only)
DELETE /auth/keys/{id}   — revoke key
GET /auth/keys           — list active keys

All other endpoints require header:
  Authorization: Bearer sk_strata_<random>
```

Keys stored in Postgres (lands at v0.3 anyway per roadmap). Table:

```sql
CREATE TABLE api_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key_hash TEXT NOT NULL UNIQUE,    -- bcrypt hash of the key
  name TEXT NOT NULL,               -- "Arkash's key", "Sequoia demo"
  tier TEXT NOT NULL DEFAULT 'free', -- free | pro | enterprise
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at TIMESTAMPTZ,
  is_active BOOLEAN NOT NULL DEFAULT true
);
```

#### 3b. Rate limiting

Per-tier limits enforced via middleware:

| Tier | Requests/min | /resolve calls/day | Stored TAMs |
|---|---|---|---|
| `free` | 30 | 5 | 10 |
| `pro` | 120 | 50 | unlimited |
| `enterprise` | 600 | 200 | unlimited |

Use `slowapi` (built on `limits`) for FastAPI rate limiting. Redis
backend at scale; in-memory for MVP.

#### 3c. Metered endpoints

Track per-key usage in Postgres:

```sql
CREATE TABLE api_usage (
  id BIGSERIAL PRIMARY KEY,
  api_key_id UUID REFERENCES api_keys(id),
  endpoint TEXT NOT NULL,
  method TEXT NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
  response_ms INT
);
```

Dashboard at `/admin/usage` (internal only) shows per-key consumption.

### Files to create/modify

```
backend/src/strata/api/auth.py         — key verification middleware
backend/src/strata/api/routes/auth.py  — key CRUD endpoints
backend/src/strata/api/rate_limit.py   — slowapi configuration
backend/src/strata/db/models/          — api_keys + api_usage tables
backend/pyproject.toml                 — add slowapi, passlib[bcrypt]
```

---

## Gap 4: Contribution Schema (Chain-Portable)

### Problem

Every record needs fields that track who contributed it, when, and how it's
been used — so that when/if chain anchoring happens (Phase 4), it's a data
migration, not a redesign.

### Design

#### 4a. Contribution metadata on every record

Add to `_common.py` base model:

```python
class ContributionMeta(BaseModel):
    contributor_id: str | None = None      # who created this
    created_at: datetime                    # when
    content_hash: str                       # sha256 of canonical form
    validation_status: Literal[
        "draft", "validated", "published", "rejected", "expired"
    ] = "draft"
    usage_count: int = 0                    # how many TAMs reference this
    royalty_accrued: Decimal = Decimal("0") # future: revenue share
```

Every AtomicPrimitive, CompositePrimitive, Framework, Concept, Annotation,
and TAMOutput carries a `contribution: ContributionMeta` field.

#### 4b. YAML extension

Existing primitive YAML gains an optional `contribution` block:

```yaml
slug: bls-pc-claims-adjusters-headcount
value: 322500
# ... existing fields ...
contribution:
  contributor_id: "arkash"
  created_at: "2026-05-21T00:00:00Z"
  content_hash: "a3f8c2..."
  validation_status: published
  usage_count: 3
```

For seed data (created by you), `contributor_id` is your handle.
`content_hash` is computed on save/commit.

#### 4c. Chain-portability guarantee

The `ContributionMeta` fields map directly to what a smart contract needs:

| Field | On-chain equivalent |
|---|---|
| `contributor_id` | Wallet address (added at Phase 4) |
| `content_hash` | Primitive hash (anchor point) |
| `created_at` | Block timestamp |
| `validation_status` | Contract state enum |
| `usage_count` | Counter incremented on TAM creation |
| `royalty_accrued` | Token balance |

Phase 4 migration: batch-write all `ContributionMeta` records to a smart
contract. No schema change needed.

### Files to create/modify

```
backend/src/strata/models/_common.py      — add ContributionMeta
backend/src/strata/models/primitive.py    — add contribution field
backend/src/strata/models/framework.py    — add contribution field
backend/src/strata/models/concept.py      — add contribution field
backend/src/strata/models/tam_output.py   — add contribution field
backend/src/strata/models/annotation.py   — add contribution field
backend/src/strata/hashing.py             — extend for canonical content hash
data/**/*.yaml                            — add contribution blocks to seeds
```

---

## Gap 5: Upstream Data Connectors

### Problem

The 50+ API catalog at `docs/11-api-catalog.md` is researched but none are
wired. The ingest pipeline (Gap 2) provides the framework; this gap covers
the specific connectors beyond the initial three (BLS/FRED/EDGAR).

### Design

#### 5a. Connector rollout sequence

Per `execute.md` and the API catalog:

| Phase | Connectors | Why this order |
|---|---|---|
| v0.2 | BLS, FRED, EDGAR | Free, highest-leverage, prove the pipeline |
| v0.3 | + Census, Exa (discovery), Parallel (extraction) | Census for business counts; Exa+Parallel for long-tail discovery |
| v0.4 | + Perplexity Sonar (refresh), World Bank, OECD | Sonar as cheap refresh probe; international aggregates |
| v0.5 | + Polymarket, Kalshi, DeFi Llama, Dune, The Graph | Onchain + prediction market tiers |
| v1.0 | + Yutori Scouting (monitoring), Yutori Browsing (awkward sources) | Scheduled monitoring; login-walled sources |

#### 5b. Connector interface

Every connector implements:

```python
class ConnectorResult(BaseModel):
    value: float
    unit: Unit
    as_of: date
    source_url: str
    source_tier: SourceTier
    snapshot_blob: bytes
    snapshot_hash: str
    metadata: dict[str, Any]  # connector-specific extras

class Connector(Protocol):
    async def fetch(self, query: str, **kwargs) -> list[ConnectorResult]: ...
    @property
    def tier(self) -> SourceTier: ...
    @property
    def name(self) -> str: ...
```

#### 5c. Connector registry

```python
CONNECTORS: dict[str, Connector] = {
    "bls": BLSConnector(),
    "fred": FREDConnector(),
    "edgar": EDGARConnector(),
    "census": CensusConnector(),
    # ... added per rollout sequence
}
```

CLI uses it: `strata ingest pull --source bls --query "SOC 13-1031"`

#### 5d. Cost model at scale

Per `execute.md` cost analysis, at 500 primitives refreshed weekly:

| Line item | Monthly cost |
|---|---|
| Direct APIs (BLS/FRED/EDGAR/Census) | $0 |
| Parallel Task (discovery + extraction) | $1 |
| Exa search | $0.50 |
| Perplexity Sonar (refresh probes) | $2 |
| Yutori Scouts | $70 |
| **Total** | **~$75/mo** |

Scales sub-linearly: most refreshes are cheap Sonar probes; only deltas
trigger expensive Parallel runs.

### Files to create/modify

```
backend/src/strata/ingest/fetch/bls.py      — BLS connector
backend/src/strata/ingest/fetch/fred.py     — FRED connector
backend/src/strata/ingest/fetch/edgar.py    — EDGAR connector
backend/src/strata/ingest/fetch/census.py   — Census connector (v0.3)
backend/src/strata/ingest/fetch/registry.py — connector registry
backend/src/strata/ingest/discover.py       — Exa integration (v0.3)
backend/src/strata/ingest/extract/parallel.py — Parallel API (v0.3)
backend/src/strata/ingest/refresh/perplexity.py — Sonar probe (v0.4)
backend/src/strata/ingest/refresh/scout.py  — Yutori Scout (v0.5)
docs/11-api-catalog.md                      — reference (already exists)
```

---

## Competitive Positioning

### Landscape summary (May 2026 research)

No existing tool combines open-source + sourced primitives + parameterized
frameworks + scenario trees + community curation for TAM. The gaps:

| Category | Players | What they lack |
|---|---|---|
| Black-box incumbents | IBISWorld, Statista, Gartner, Mordor | No visible methodology, no primitives, no frameworks |
| Closest functional | Scalepath (B2B TAM SaaS) | B2B-only, proprietary, ML black box, no community |
| Closest philosophical | VantaInsights (federal-data sizing) | Proprietary, US-only, no composable frameworks |
| AI calculators | FounderPal, IdeaProof, CharliA | LLM-hallucinated numbers, non-reproducible |
| Estimation tools | Squiggle Hub, Guesstimate | No structured data layer, no TAM-specific, no citations |
| AI research agents | Perplexity Deep Research | Ad-hoc, non-deterministic, no versioning, no community |

### Strata's moat

1. **Primitives are sourced and pinned.** Every number traces to a sha256'd
   snapshot of the original source. No other TAM tool does this.
2. **Frameworks are code, not prose.** The multiplicative formula is explicit,
   auditable, forkable. Change one input, see exactly what moves.
3. **Progressive decentralization.** Contribution schema is chain-portable
   from day one. When community + revenue justify it, anchoring is a data
   migration, not a redesign.
4. **Multi-vendor ingest.** Exa for discovery, Parallel for extraction,
   Perplexity for refresh probes, Yutori for monitoring, direct APIs for
   government data. Each tool in its best slot, not one tool for everything.

---

## Non-goals

- **No blockchain at v0.2–v0.4.** Chain-portable schema yes; chain infra no.
- **No LLM-projected primitives** (Q20). The resolve endpoint uses Claude
  to *parse queries* and *select frameworks*, never to *generate numbers*.
- **No MCP server.** CLI + REST API are the surfaces. AI agents query the
  API like any other consumer.
- **No open-source release** at launch. Closed product, paid access.
  Open-source consideration deferred to post-v1.0.
- **No pyramid graph** in this spec. That's a separate v0.3 design per
  `docs/08-product-surface-brainstorm.md` U1.

---

## Build sequence (implementation order)

```
Sprint 1A: Resolve endpoint hardening + ingest skeleton
  - Fix /resolve: async clients, error handling, no internal leaks
  - Create ingest/ module skeleton with Connector protocol
  - Add `strata ingest pull` CLI command (skeleton)
  - Wire BLS connector (first real data pull)

Sprint 1B: FRED connector + contribution schema
  - Wire FRED connector
  - Introduce shared StrataRecord base, add ContributionMeta
  - Update all YAML fixtures with contribution blocks
  - Clean pyright warnings before adding complexity

Sprint 2: Interactive wiring
  - PrimitiveSlider component
  - Client-side evaluator (multiplicative calc in TypeScript)
  - Slider state management in build view
  - State hashing → URL minting on save

Sprint 3: EDGAR connector + ingest UI
  - EDGAR XBRL connector
  - Draft management (data/.drafts/)
  - /ingest page with draft review queue
  - `strata ingest discover` CLI command

Sprint 4: API auth + metering
  - Initialize Alembic, create initial migration from existing db/ module
  - API key system (Postgres)
  - Rate limiting middleware (slowapi)
  - Usage tracking
  - Subscription tier enforcement

Sprint 5: Exa + Parallel integration
  - Exa discovery in ingest pipeline
  - Parallel Task API for structured extraction
  - End-to-end: concept → discover → extract → validate → publish

Sprint 6: Refresh + monitoring
  - Perplexity Sonar refresh probes
  - Source-class cadence scheduler
  - Yutori Scouting for URL monitoring
```

---

## Verification

### Sprint 1 smoke test

```bash
strata ingest pull --source bls --query "SOC 13-1031"
# → Fetches claims adjusters headcount from BLS OES
# → Stores snapshot (JSON, sha256)
# → Extracts: {value: 322500, unit: persons, tier: regulator}
# → Validators pass → auto-publishes to data/primitives/
# → contribution.contributor_id = "cli"
# → contribution.content_hash = sha256(canonical YAML)
```

### Sprint 2 smoke test

Open `/build?q=insurance` → drag slider on "% of seats addressable" from
0.40 to 0.60 → TAM updates from $47M to $70M in real-time → click "Save
scenario" → new `/build/<hash>` URL minted.

### Sprint 4 smoke test

```bash
curl -H "Authorization: Bearer sk_strata_test123" \
  http://localhost:8000/build/doc-gen-pc-insurance
# → 200 OK with TAM output

curl http://localhost:8000/build/doc-gen-pc-insurance
# → 401 Unauthorized
```
