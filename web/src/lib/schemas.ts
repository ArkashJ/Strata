import { z } from "zod";

export const sourceTierSchema = z.enum([
  "first_party",
  "regulator",
  "aggregator",
  "analyst",
  "analyst-paraphrase",
  "community",
  "onchain",
  "prediction_market",
  "community-modeled",
]);
export type SourceTier = z.infer<typeof sourceTierSchema>;

export const methodFamilySchema = z.enum([
  "top_down_spend",
  "bottoms_up_seats",
  "comparable_revenue",
  "analog_penetration",
  "value_chain",
  // Phase 2 families the backend's formula engine emits (models/framework.py
  // MethodFamily). Missing here, a valid TAM response failed tamOutputSchema.parse
  // and surfaced as "Could not size this market".
  "adoption_curve",
  "weighted_blend",
]);
export type MethodFamily = z.infer<typeof methodFamilySchema>;

export const analysisLensSchema = z.enum([
  "cost_efficiency",
  "revenue_generation",
  "latent_demand",
  "platform_throughput",
  "bundle_consolidation",
  "productivity_uplift",
]);
export type AnalysisLens = z.infer<typeof analysisLensSchema>;

export const inputRoleSchema = z.enum([
  "base_value",
  "growth_index",
  "regime_modifier",
  "conditional_adjustment",
]);
export type InputRole = z.infer<typeof inputRoleSchema>;

export const unitSchema = z.object({
  kind: z.string(),
  dimension: z.string(),
  denominator: z.string().nullable().optional(),
  currency: z.string().nullable().optional(),
  basis: z.string().nullable().optional(),
});
export type Unit = z.infer<typeof unitSchema>;

export const inputUsedSchema = z.object({
  role_name: z.string(),
  role: inputRoleSchema,
  primitive_slug: z.string(),
  snapshot_sha256: z.string(),
  // enrichment from evaluator
  value: z.number().nullable().optional(),
  name: z.string().nullable().optional(),
  unit: unitSchema.nullable().optional(),
  source_tier: z.string().nullable().optional(),
  // Number-level provenance: the atomic's source URL so the displayed number
  // itself can link to the source behind it. Null for composites (no single
  // source) and absent on pre-enrichment payloads.
  source_url: z.string().nullable().optional(),
});
export type InputUsed = z.infer<typeof inputUsedSchema>;

export const scenarioBannerSchema = z.object({
  kind: z.string(),
  message: z.string(),
});

export const scenarioSchema = z.object({
  definition: z.string(),
  lens: analysisLensSchema,
  framework: z.string(),
  framework_variant: z.string().nullable().optional(),
  value: z.number(),
  unit: unitSchema,
  inputs_used: z.array(inputUsedSchema),
  assumptions: z.record(z.string()),
  banners: z.array(scenarioBannerSchema),
});
export type Scenario = z.infer<typeof scenarioSchema>;

export const tamTargetSchema = z.object({
  concept: z.string(),
  concept_name: z.string().nullable().optional(), // enrichment from evaluator
  geo: z.string().nullable().optional(),
  time: z.string().nullable().optional(),
  expansion_stage: z.string(),
});

// Bottoms-up vs tops-down agreement (MV2). Present only when ≥2 independent
// method families sized the concept; null otherwise (the UI must not fake a
// second method). Mirrors the backend Convergence model field-for-field.
export const convergenceSchema = z.object({
  low_family: methodFamilySchema,
  high_family: methodFamilySchema,
  low_value: z.number(),
  high_value: z.number(),
  ratio: z.number(),
  unit: unitSchema,
});
export type Convergence = z.infer<typeof convergenceSchema>;

// Market scope (sub-project 1). A scope tag is code-anchored (NAICS/SOC) or
// free-text; the guard compares a concept's declared scope against each
// primitive's true scope. Mirrors backend strata.models.scope field-for-field.
export const codedTagSchema = z.object({
  system: z.string(),
  code: z.string(),
  label: z.string(),
});
export type CodedTag = z.infer<typeof codedTagSchema>;

export const firmSizeBandSchema = z.object({
  min_emp: z.number().nullable().optional(),
  max_emp: z.number().nullable().optional(),
  label: z.string(),
});
export type FirmSizeBand = z.infer<typeof firmSizeBandSchema>;

// All array fields are always present in the JSON (the backend serializes every
// MarketScope field, empty tuples included), so they are required here — no
// `.default([])`, which would split the zod input/output types and clash with
// the TAMOutput type used across queries.
export const marketScopeSchema = z.object({
  vertical: z.array(codedTagSchema),
  persona: z.array(codedTagSchema),
  segment: firmSizeBandSchema.nullable().optional(),
  geo_supply: z.array(z.string()),
  geo_demand: z.array(z.string()),
  product: z.array(z.string()),
  include: z.array(z.string()),
  exclude: z.array(z.string()),
});
export type MarketScope = z.infer<typeof marketScopeSchema>;

// A fully-formed empty MarketScope (empty arrays, not undefined) — the single
// source of truth for the default-scope shape so adding a backend field is a
// one-line change here, not a hunt across the form + view + tests.
export function emptyMarketScope(): MarketScope {
  return {
    vertical: [],
    persona: [],
    segment: null,
    geo_supply: [],
    geo_demand: [],
    product: [],
    include: [],
    exclude: [],
  };
}

export const scopeWarningSchema = z.object({
  dimension: z.string(),
  // narrower | broader | partial | disjoint
  relationship: z.string(),
  message: z.string(),
});
export type ScopeWarning = z.infer<typeof scopeWarningSchema>;

export const inputScopeSchema = z.object({
  primitive_slug: z.string(),
  role_name: z.string(),
  // The primitive's actual scope — the displayed tag binds to this truth.
  displayed: marketScopeSchema,
  warnings: z.array(scopeWarningSchema),
});
export type InputScope = z.infer<typeof inputScopeSchema>;

export const scopeReportSchema = z.object({
  declared: marketScopeSchema,
  inputs: z.array(inputScopeSchema),
  ok: z.boolean(),
});
export type ScopeReport = z.infer<typeof scopeReportSchema>;

export const tamOutputSchema = z.object({
  kind: z.literal("tam_output"),
  state_hash: z.string(),
  schema_version: z.number(),
  created_by: z.string(),
  created_at: z.string(),
  target: tamTargetSchema,
  scenarios: z.array(scenarioSchema).min(1),
  method_families_used: z.array(methodFamilySchema),
  convergence: convergenceSchema.nullable().optional(),
  independence_score: z.number().min(0).max(1),
  uses_synthetic_primitives: z.boolean(),
  uses_modeled_composites: z.boolean(),
  scope: scopeReportSchema.nullable().optional(),
});
export type TAMOutput = z.infer<typeof tamOutputSchema>;

// ── Recompute (POST /build/recompute) ─────────────────────────────────────────
// The edit→recompute contract. `framework_assumptions` re-points an input to a
// different SOURCED primitive (schema-pure, no banner). `primitive_overrides`
// injects a transient what-if scalar — never persisted as a primitive (Q20); the
// backend flags every scenario it touches with a `user_override` banner and sets
// uses_synthetic_primitives. Mirrors the backend RecomputeRequest field-for-field.
export const primitiveOverrideSchema = z.object({
  value: z.number(),
  unit: unitSchema,
});
export type PrimitiveOverrideWire = z.infer<typeof primitiveOverrideSchema>;

export const recomputeRequestSchema = z.object({
  concept_slug: z.string(),
  framework_assumptions: z.record(z.record(z.string())).optional(),
  primitive_overrides: z.record(primitiveOverrideSchema).optional(),
  // The user-pinned market (sub-project 1.5). When non-empty it overrides the
  // concept's declared scope as the side the guard checks against, and folds into
  // the backend state hash. Omitted/empty → unchanged behaviour.
  scope: marketScopeSchema.optional(),
});
export type RecomputeRequest = z.infer<typeof recomputeRequestSchema>;

export const conceptSummarySchema = z.object({
  slug: z.string(),
  name: z.string(),
  definition: z.string(),
  primary_lens: z.string(),
  measurement_count: z.number(),
});
export type ConceptSummary = z.infer<typeof conceptSummarySchema>;

export const primitiveSummarySchema = z.object({
  slug: z.string(),
  name: z.string(),
  kind: z.string(),
  concept_slug: z.string(),
  value: z.number().nullable(),
  unit_label: z.string(),
});
export type PrimitiveSummary = z.infer<typeof primitiveSummarySchema>;

// ── Prediction-market signals (GET /signals · T1) ─────────────────────────────
// The `prediction_market` primitives quarantined to data/signals/ (Q20). They
// never feed a TAM — a separate, honestly-labelled surface of live Kalshi event
// probabilities + contract volumes, each with a source URL + SHA256 snapshot pin.
// Mirrors the backend SignalSummary field-for-field.
export const signalSummarySchema = z.object({
  slug: z.string(),
  name: z.string(),
  concept_slug: z.string(),
  value: z.number(),
  unit_dimension: z.string(),
  as_of: z.string(),
  source_url: z.string(),
  // Locked to the literal: a signal is by definition prediction-market tier, so
  // the page never silently renders a non-signal row if the backend regresses.
  source_tier: z.literal("prediction_market"),
  snapshot_sha256: z.string(),
  uncertainty_low: z.number().nullable().optional(),
  uncertainty_high: z.number().nullable().optional(),
  uncertainty_basis: z.string().nullable().optional(),
});
export type SignalSummary = z.infer<typeof signalSummarySchema>;

// Ingest connectors (GET /connectors · connector-explorer). The typed clients
// that manufacture sourced primitives (connector → primitive → framework → TAM).
// `primitives_in_bank` is a LIVE count of what this connector has produced in the
// current data bank; 0 means capability-only (honest — not yet ingested).
export const connectorCapabilitySchema = z.object({
  method: z.string(),
  description: z.string(),
  returns: z.string(),
});
export const connectorSchema = z.object({
  connector: z.string(),
  source_tier: z.string(),
  method_count: z.number(),
  capabilities: z.array(connectorCapabilitySchema),
  primitives_in_bank: z.number(),
  sample_primitive_slug: z.string().nullable(),
  sample_source_url: z.string().nullable(),
});
export type Connector = z.infer<typeof connectorSchema>;

// Portfolio (P1) — read-only cached demo subset.
export const portfolioCompanySchema = z.object({
  name: z.string(),
  domain: z.string(),
  vertical: z.string().nullable(),
  status: z.string(),
  market_concept_slug: z.string().nullable(),
  tam_value: z.number().nullable(),
  reason: z.string().nullable(),
  state_hash: z.string().nullable(),
  has_analyst_input: z.boolean(),
});
export const portfolioResponseSchema = z.object({
  org_id: z.string(),
  enabled: z.boolean(),
  counts: z.record(z.string(), z.number()),
  companies: z.array(portfolioCompanySchema),
});
export type PortfolioCompany = z.infer<typeof portfolioCompanySchema>;
export type PortfolioResponse = z.infer<typeof portfolioResponseSchema>;

export const frameworkSummarySchema = z.object({
  slug: z.string(),
  name: z.string(),
  method_family: z.string(),
  lens: z.string(),
  input_count: z.number(),
});
export type FrameworkSummary = z.infer<typeof frameworkSummarySchema>;

// ── Detail-page record schemas (GET /c/{slug}, /p/{slug}, /f/{slug}) ──────────
// These mirror the backend Pydantic models exactly; verified against the live
// /openapi.json component shapes. Keep field-for-field — the detail pages render
// every sourced number and the validator statically rejects bad wiring upstream.

export const geoSchema = z.object({
  level: z.string(),
  codes: z.array(z.string()),
  aggregate: z.string().nullable().optional(),
  aggregation_rule: z.string().nullable().optional(),
  allocator_primitive: z.string().nullable().optional(),
});
export type Geo = z.infer<typeof geoSchema>;

export const geoPerspectiveSchema = z.enum(["supply", "demand", "mixed", "unknown"]);
export type GeoPerspective = z.infer<typeof geoPerspectiveSchema>;

export const uncertaintySchema = z.object({
  range: z.tuple([z.number(), z.number()]),
  basis: z.string(),
});
export type Uncertainty = z.infer<typeof uncertaintySchema>;

export const setOperationSchema = z.enum(["union", "intersection", "filter", "restrict_by_tag"]);
export type SetOperation = z.infer<typeof setOperationSchema>;

// Source is a discriminated union on `tier` in the backend, but every variant
// shares the same base shape and `analyst-paraphrase` adds three optional fields.
// A permissive superset keeps the detail card resilient to either variant.
export const sourceSchema = z.object({
  slug: z.string(),
  url: z.string(),
  accessed: z.string(),
  snapshot_sha256: z.string(),
  tier: sourceTierSchema,
  original_publisher: z.string().nullable().optional(),
  paraphrase_reviewer: z.string().nullable().optional(),
  paraphrase_text: z.string().nullable().optional(),
});
export type Source = z.infer<typeof sourceSchema>;

export const conceptDetailSchema = z.object({
  kind: z.literal("concept"),
  slug: z.string(),
  schema_version: z.number(),
  name: z.string(),
  definition: z.string(),
  analysis_lens: z.object({
    primary: analysisLensSchema,
    secondary: analysisLensSchema.nullable().optional(),
  }),
  modifiers: z.record(z.unknown()).nullable().optional(),
  measurements: z.array(z.string()),
  competing_concepts: z.array(z.string()),
  requires_clearance: z.array(z.string()),
  // The concept's canonical declared market (sub-project 1). The market-spec step
  // prefills its chips from this; defaults empty so unscoped concepts load fine.
  scope: marketScopeSchema.optional(),
});
export type ConceptDetail = z.infer<typeof conceptDetailSchema>;

export const atomicPrimitiveSchema = z.object({
  kind: z.literal("atomic_primitive"),
  slug: z.string(),
  schema_version: z.number(),
  concept_slug: z.string(),
  name: z.string(),
  description: z.string(),
  value: z.number(),
  unit: unitSchema,
  as_of: z.string(),
  expiry: z.string().nullable().optional(),
  geo: geoSchema,
  geo_perspective: geoPerspectiveSchema,
  distribution_shape: z.string(),
  delivery_mode: z.string(),
  uncertainty: uncertaintySchema.nullable().optional(),
  source: sourceSchema,
  derives_from: z.array(z.string()),
});
export type AtomicPrimitive = z.infer<typeof atomicPrimitiveSchema>;

export const compositePrimitiveSchema = z.object({
  kind: z.literal("composite_primitive"),
  slug: z.string(),
  schema_version: z.number(),
  concept_slug: z.string(),
  name: z.string(),
  description: z.string(),
  inputs: z.array(z.string()),
  set_operation: setOperationSchema,
  tag_filter: z.string().nullable().optional(),
  as_of: z.string(),
  unit: unitSchema,
  geo: geoSchema,
  geo_perspective: geoPerspectiveSchema,
});
export type CompositePrimitive = z.infer<typeof compositePrimitiveSchema>;

export const primitiveDetailSchema = z.discriminatedUnion("kind", [
  atomicPrimitiveSchema,
  compositePrimitiveSchema,
]);
export type PrimitiveDetail = z.infer<typeof primitiveDetailSchema>;

export const frameworkInputSchema = z.object({
  name: z.string(),
  role: inputRoleSchema,
  unit_signature: unitSchema,
  required: z.boolean(),
});
export type FrameworkInput = z.infer<typeof frameworkInputSchema>;

export const frameworkVariantSchema = z.object({
  scope: z.string(),
  default_inputs: z.record(z.string()),
});
export type FrameworkVariant = z.infer<typeof frameworkVariantSchema>;

export const horizonClassSchema = z.enum(["snapshot", "short_extrapolation", "long_extrapolation"]);
export type HorizonClass = z.infer<typeof horizonClassSchema>;

export const frameworkDetailSchema = z.object({
  kind: z.literal("framework"),
  slug: z.string(),
  schema_version: z.number(),
  name: z.string(),
  method_family: methodFamilySchema,
  lens: analysisLensSchema,
  inputs: z.array(frameworkInputSchema),
  formula: z.string(),
  output_unit: unitSchema,
  applicable_to: z.array(z.string()),
  not_applicable_to: z.array(z.string()),
  requires_clearance: z.array(z.string()),
  variants: z.array(frameworkVariantSchema),
  expansion_stage_parameter: z.boolean(),
  horizon_class: horizonClassSchema,
});
export type FrameworkDetail = z.infer<typeof frameworkDetailSchema>;

// ── TAM-over-time (GET /build/{slug}/trajectory · PR12) ───────────────────────
// The TAM re-evaluated at each distinct primitive `as_of` date — the headline
// "current vs previous" view. Most concepts share one as_of today, so a single
// point is the common case; the chart must degrade to an honest snapshot, never
// fabricate a curve. Field-for-field against the backend trajectory model.
export const trajectoryPointSchema = z.object({
  as_of: z.string(),
  value: z.number(),
  low: z.number(),
  high: z.number(),
  method_families: z.array(z.string()),
  scenarios_n: z.number(),
});
export type TrajectoryPoint = z.infer<typeof trajectoryPointSchema>;

export const tamTrajectorySchema = z.object({
  concept_slug: z.string(),
  concept_name: z.string(),
  unit: unitSchema,
  points: z.array(trajectoryPointSchema),
});
export type TamTrajectory = z.infer<typeof tamTrajectorySchema>;

// ── Audit feed (GET /audit · Strata Live Track C) ─────────────────────────────
// One row per user-visible action (resolve / recompute / promote). Mirrors the
// backend AuditEvent Pydantic model field-for-field: `actor` is the Clerk user
// id or "anon", `target` is the touched slug/hash, `meta` is freeform jsonb.
// `ts` is an ISO-8601 datetime string (FastAPI serializes datetime as such).
export const auditEventSchema = z.object({
  id: z.number(),
  actor: z.string().nullable(),
  action: z.string(),
  target: z.string().nullable(),
  ts: z.string(),
  meta: z.record(z.unknown()).nullable().optional(),
});
export type AuditEvent = z.infer<typeof auditEventSchema>;

// ── User primitives (GET /me/primitives) ──────────────────────────────────────
// A row from the caller's PRIVATE primitive store. `payload` is the full
// AtomicPrimitive the user stored; we parse it loosely (passthrough) so a future
// payload field never rejects the row — the bank table only reads name/value/unit.
export const userPrimitivePayloadSchema = z
  .object({
    name: z.string().optional(),
    value: z.number().optional(),
    unit: z.object({ currency: z.string().nullable().optional() }).passthrough().optional(),
    source: z.object({ tier: z.string().optional() }).passthrough().optional(),
  })
  .passthrough();

export const userPrimitiveSchema = z.object({
  id: z.number(),
  org_id: z.string(),
  created_by: z.string().nullable(),
  slug: z.string(),
  visibility: z.string(),
  payload: userPrimitivePayloadSchema,
  created_at: z.string(),
});
export type UserPrimitive = z.infer<typeof userPrimitiveSchema>;

// --- Question-driven market report (PR4) ----------------------------------
// Mirrors backend strata.models.question field-for-field. Verified against
// /openapi.json (GET /report, GET /report/{concept_slug}). Every numeric answer
// is registry-sourced (provenance) or TAM-field synthesis — never authored.

export const questionCategorySchema = z.enum([
  "market_size",
  "growth_rate",
  "segmentation",
  "geography",
  "competition_share",
  "regulation",
  "adoption",
  "unit_economics",
  "risks",
  "methodology",
]);
export type QuestionCategory = z.infer<typeof questionCategorySchema>;

export const answerStrategySchema = z.enum([
  "primitive_role",
  "concept_measurement",
  "tam_field",
  "qualitative",
]);
export type AnswerStrategy = z.infer<typeof answerStrategySchema>;

// One provenance row behind a resolved answer (InputUsed shape semantics).
// source_url / source_tier are null for composites (a union has no single
// source of its own) — honest, never fabricated.
export const answerProvenanceSchema = z.object({
  primitive_slug: z.string(),
  source_url: z.string().nullable().optional(),
  source_tier: z.string().nullable().optional(),
  snapshot_sha256: z.string(),
  as_of: z.string().nullable().optional(),
});
export type AnswerProvenance = z.infer<typeof answerProvenanceSchema>;

// The assembler's runtime output (the Q20 fence). A numeric `value` is only
// present when backed by `provenance` or a reproducible `synthesis`.
export const resolvedAnswerSchema = z.object({
  question_id: z.string(),
  prompt: z.string(),
  category: questionCategorySchema,
  status: z.enum(["answered", "gap"]),
  value: z.number().nullable().optional(),
  display: z.string().nullable().optional(),
  narrative: z.string(),
  provenance: z.array(answerProvenanceSchema),
  synthesis: z.string().nullable().optional(),
  resource_target: z.string().nullable().optional(),
});
export type ResolvedAnswer = z.infer<typeof resolvedAnswerSchema>;

// The assembled report for one concept: meta + resolved answers.
export const conceptQuestionReportSchema = z.object({
  concept_slug: z.string(),
  concept_name: z.string(),
  answers: z.array(resolvedAnswerSchema),
});
export type ConceptQuestionReport = z.infer<typeof conceptQuestionReportSchema>;

// One row of the question catalog (GET /report).
export const questionSummarySchema = z.object({
  question_id: z.string(),
  prompt: z.string(),
  category: questionCategorySchema,
  lenses: z.array(z.string()),
});
export type QuestionSummary = z.infer<typeof questionSummarySchema>;
