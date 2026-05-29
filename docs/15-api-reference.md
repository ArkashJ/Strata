# Strata API Reference

**Version:** 0.3.0  
**Base URL:** `http://localhost:8000` (dev) | Railway production URL per deploy config  
**Interactive docs:** `/docs` (Swagger) · `/redoc` (ReDoc) · `/openapi.json` (raw spec)

---

## How this doc is generated

This reference mirrors the live `/openapi.json` schema emitted by FastAPI.
To regenerate the TypeScript web client after any route or schema change:

```
bun run gen:api
```

That command fetches `/openapi.json` from the running backend and writes typed
fetch wrappers into `web/src/lib/api/generated/`.

---

## Request flow

```
Client
  │
  │  GET /c /p /f /build/* /tam/*      POST /resolve (SSE stream)
  ▼                                     ▼
FastAPI routers (api/routes/)
  │                                     │
  │  registry look-up / evaluator       │  resolver pipeline (4 steps)
  ▼                                     ▼
┌─ Registry ──────────────────┐   ┌─ pre. resolve_slug (Claude) ─────────┐
│  concepts · primitives      │   │  1. concept hit → evaluator          │
│  frameworks · tam_outputs   │   │  2. primitive hit → evaluator        │
└──────────────┬──────────────┘   │  3. connector live → writer.upsert   │
               │                  │  4. fallback → Claude parse + Exa    │
               ▼                  └─────────────────────────────────────┘
          Evaluator                        │ SSE events
          (scenario tree)                  ▼
                                    Client (EventSource)
```

---

## Endpoints

### GET /healthz

Liveness probe. Returns 200 when the server is up; used by Railway deploy health checks.

**Response 200**

```json
{ "status": "ok" }
```

---

### GET /c

List every concept in the registry.

**Response 200** — array of `ConceptSummary`

| Field | Type | Description |
|---|---|---|
| `slug` | string | Kebab-case identifier, e.g. `ai-code-review` |
| `name` | string | Human-readable market name |
| `primary_lens` | string | One of the six TAM lenses |
| `measurement_count` | integer | Number of primitives measuring this concept |

**Example**

```json
[
  {
    "slug": "ai-code-review",
    "name": "AI-assisted code review tooling",
    "primary_lens": "cost_efficiency",
    "measurement_count": 4
  }
]
```

---

### GET /c/{slug}

Full concept detail: lens, modifiers, measurements, and competing concepts.

**Path param:** `slug` — concept slug (pattern `^[a-z0-9][a-z0-9-]*$`)

**Response 200** — `Concept`

Key fields:

| Field | Type | Description |
|---|---|---|
| `slug` | string | Concept identifier |
| `name` | string | Display name |
| `analysis_lens.primary` | string | Primary TAM lens |
| `analysis_lens.secondary` | string \| null | Optional secondary lens |
| `measurements` | array | Primitive slugs measuring this concept |
| `competing_concepts` | array | Alternative market definitions |

**Response 404** — concept not found

---

### GET /p

List all atomic and composite primitives in the data bank.

**Response 200** — array of `PrimitiveSummary`

| Field | Type | Description |
|---|---|---|
| `slug` | string | Primitive identifier |
| `kind` | `atomic` \| `composite` | Record type |
| `name` | string | Sourced data point name |
| `value` | number | Raw numeric value |
| `unit` | object | Structured unit (see unit schema below) |
| `concept_slug` | string | Parent concept |

Currently returns 307+ primitives sourced from BLS, FRED, Census, EDGAR, and World Bank.

---

### GET /p/{slug}

Full primitive detail including source citation and SHA256 snapshot pin.

**Path param:** `slug` — primitive slug

**Response 200** — `AtomicPrimitive` or `CompositePrimitive`

Key fields on `AtomicPrimitive`:

| Field | Type | Description |
|---|---|---|
| `slug` | string | Identifier |
| `value` | number | Raw numeric value (currency stored nominal) |
| `unit` | `Unit` | Structured unit (kind/dimension/denominator/currency/basis) |
| `as_of` | date | Date the source figure was current |
| `geo` | `Geo` | ISO 3166 geography |
| `source.snapshot_sha256` | string | Content-hash of the source snapshot |
| `source.url` | string | Source URL |

`CompositePrimitive` omits `source` and adds `inputs` (array of atomic slugs) and `set_operation` (`union` \| `intersect` \| `subtract`).

**Response 404** — primitive not found

---

### GET /f

List all frameworks in the registry.

**Response 200** — array of `FrameworkSummary`

| Field | Type | Description |
|---|---|---|
| `slug` | string | Framework identifier |
| `name` | string | Display name |
| `lens` | string | TAM lens this framework implements |
| `method_family` | string | Calculation family (top_down / bottom_up / etc.) |
| `applicable_to` | array | Concept slugs this framework can size |

---

### GET /f/{slug}

Full framework detail: inputs, output unit, variants, and applicable concepts.

**Path param:** `slug` — framework slug

**Response 200** — `Framework`

Key fields:

| Field | Type | Description |
|---|---|---|
| `inputs` | array | Input definitions (name, role, expected unit) |
| `output_unit` | `Unit` | Unit emitted by this framework's calculation |
| `variants` | array | `FrameworkVariant` objects binding input names to primitive slugs |
| `method_family` | string | Scoring category for independence calculation |

**Response 404** — framework not found

---

### GET /build/{concept_slug}

Evaluate a concept through all applicable framework variants and return a TAM scenario tree.

**Path param:** `concept_slug` — concept slug

**Response 200** — `TAMOutput`

| Field | Type | Description |
|---|---|---|
| `state_hash` | string | SHA256 of the canonical scenario payload — stable URL key |
| `target.concept_slug` | string | Concept that was sized |
| `target.concept_name` | string | Display name |
| `scenarios` | array | One `Scenario` per satisfiable framework variant |
| `scenarios[].value` | number | TAM value in output unit |
| `scenarios[].lens` | string | TAM lens applied |
| `scenarios[].framework` | string | Framework slug used |
| `scenarios[].inputs_used` | array | Primitive values consumed |
| `scenarios[].banners` | array | Data-quality flags (analyst-paraphrase, synthetic, …) |
| `independence_score` | number | 0–1; fraction of distinct method families across scenarios |
| `method_families_used` | array | Method families present |

**Response 422** — concept has no applicable framework variants

**Example**

```json
{
  "state_hash": "a3f8c2...",
  "target": { "concept_slug": "ai-code-review", "concept_name": "AI-assisted code review tooling" },
  "scenarios": [
    {
      "value": 18600000000,
      "lens": "cost_efficiency",
      "framework": "cost-efficiency-v1",
      "inputs_used": [
        { "role_name": "persona_count", "value": 4650000, "primitive_slug": "us-software-devs-bls-2023" },
        { "role_name": "annual_cost_per_persona", "value": 4000, "primitive_slug": "copilot-seat-cost-2023" }
      ],
      "banners": []
    }
  ],
  "independence_score": 0.0,
  "method_families_used": ["bottom_up"]
}
```

---

### GET /build/{concept_slug}/trajectory

Return a TAM-over-time series. Each point is a snapshot of the TAM evaluated using
only primitives whose `as_of` date is on or before that snapshot date.

```
Primitive as_of dates (sorted):  [2021-01-01, 2022-01-01, 2023-01-01]
                                        │            │            │
                                   re-evaluate  re-evaluate  re-evaluate
                                   (subset)     (subset)     (all)
                                        │            │            │
                                        ▼            ▼            ▼
                                   point[0]    point[1]    point[2]
                                   (low/mid/   (low/mid/   (low/mid/
                                    high)       high)       high)
```

Frameworks whose required inputs are not all present at a given cutoff are skipped for that point.
Points where no framework is satisfiable are omitted entirely.

**Path param:** `concept_slug` — concept slug

**Response 200** — `TAMTrajectory`

| Field | Type | Description |
|---|---|---|
| `concept_slug` | string | Concept identifier |
| `concept_name` | string | Display name |
| `unit` | `Unit` | Output unit (from first applicable framework) |
| `points` | array | Chronological `TrajectoryPoint` objects |
| `points[].as_of` | date | Cutoff date for this snapshot |
| `points[].value` | number | Midpoint (average across satisfiable scenarios) |
| `points[].low` | number | Min across scenarios |
| `points[].high` | number | Max across scenarios |
| `points[].scenarios_n` | integer | Number of satisfiable scenarios at this date |
| `points[].method_families` | array | Method families contributing |

**Response 422** — concept not found

---

### GET /tam/{state_hash}

Retrieve a frozen, content-addressed TAM output by its state hash.

The hash is deterministic: identical scenario payloads (same concept, same framework
variants, same primitive values and snapshot hashes) produce the same hash. This
gives permanent, shareable `/tam/<hash>` URLs.

**Path param:** `state_hash` — SHA256 hex string from a prior `/build/` response

**Response 200** — `TAMOutput` (same shape as `/build/{concept_slug}`)

**Response 404** — hash not in registry

---

### POST /resolve

Accept a free-form natural language market query and stream the resolver's
chain-of-thought as Server-Sent Events (SSE). The backend runs the 4-step pipeline
in a thread and pushes events as milestones are reached.

**Request body**

```json
{ "query": "what is the TAM for AI-assisted code review?" }
```

**Response** — `text/event-stream`

#### SSE wire format

Each event is:

```
event: <event_type>
data: <JSON payload>

```

#### Event sequence (§9.1 wire contract)

```
Client                              Server (pipeline thread)
  │                                     │
  │   POST /resolve {"query": "..."}    │
  │─────────────────────────────────────►│
  │                                     │
  │   event: parsing                    │
  │◄────────────────────────────────────│  parse intent + primitives needed
  │                                     │
  │   event: searching (x N)            │
  │◄────────────────────────────────────│  Exa search per primitive
  │                                     │
  │   event: framework_selected         │
  │◄────────────────────────────────────│  lens resolved
  │                                     │
  │   event: evaluating                 │
  │◄────────────────────────────────────│  multiplying inputs
  │                                     │
  │   event: result                     │
  │◄────────────────────────────────────│  TAM value + primitives + sources
  │                                     │
  │   event: done                       │
  │◄────────────────────────────────────│  stream closed
  │                                     │
  │   (on any failure)                  │
  │   event: error                      │
  │◄────────────────────────────────────│  then event: done
```

#### Event payloads

**`parsing`**

```json
{ "query": "what is the TAM for AI-assisted code review?", "model": "claude-sonnet-4-6" }
```

**`searching`** — one event per primitive

```json
{ "primitive_name": "persona_count", "role": "persona_count" }
```

**`framework_selected`**

```json
{ "framework": "cost_efficiency", "lens": "cost_efficiency" }
```

**`evaluating`**

```json
{
  "inputs": [
    { "slug": "persona_count", "value": 4650000, "unit": { "kind": "stock", "dimension": "people" } }
  ]
}
```

**`result`**

```json
{
  "tam_usd": 18600000000,
  "scenarios": [{ "label": "point", "value": 18600000000 }],
  "sources": [{ "url": "https://bls.gov/...", "tier": "regulator" }],
  "concept_name": "AI-assisted code review tooling",
  "definition": "...",
  "formatted_tam": "$18.6B",
  "lens": "cost_efficiency",
  "framework_name": "Cost Efficiency",
  "independence_score": 0.0,
  "primitives_used": [...],
  "banner": "synthesized via fallback — not in data bank, do not cite without manual verification"
}
```

**`error`**

```json
{ "message": "Could not find enough market data for this query.", "step": "search" }
```

**`done`**

```json
{}
```

> **Note:** The pipeline runs in step-4 fallback mode for HTTP clients (steps 1–3
> are skipped on the hot request path). The `banner` field in `result` will say
> "synthesized via fallback" for novel queries not yet in the data bank.
> Use `strata promote <slug>` to graduate a synthesized primitive into the
> committed data bank.

---

## Shared schemas

### Unit

```json
{
  "kind": "flow",
  "dimension": "currency",
  "denominator": "year",
  "currency": "USD",
  "basis": "nominal"
}
```

| Field | Allowed values |
|---|---|
| `kind` | `stock` · `flow` · `intensive` · `dimensionless` |
| `dimension` | `currency` · `people` · `organizations` · `percent` · `units` |
| `denominator` | `year` · `month` · `quarter` (only on `flow`) |
| `currency` | ISO 4217 code, e.g. `USD` |
| `basis` | `nominal` · `real` |

### BannerKind

Flags that surface on scenario outputs and in exports as footnotes:

| Value | Meaning |
|---|---|
| `synthetic` | LLM-projected value, not a sourced figure |
| `modeled` | Community-modeled multiplier |
| `subsidy` | Includes a government subsidy component |
| `regulated` | Price or access is regulated |
| `dark-estimate` | Sparse or indirect sourcing |
| `analyst-paraphrase` | Paraphrased from an analyst report; verify against full text |

### Six TAM lenses

| Lens | Math shape | Example |
|---|---|---|
| `cost_efficiency` | persona × cost | Copilot, Glean |
| `revenue_generation` | segment × spend | Brex, Rippling |
| `latent_demand` | population × adoption × WTP | Uber |
| `platform_throughput` | volume × take_rate | Stripe, Visa |
| `bundle_consolidation` | total_spend × consolidation | Notion, Linear |
| `productivity_uplift` | personas × value_split | Cursor |
