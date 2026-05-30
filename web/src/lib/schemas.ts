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

export const tamOutputSchema = z.object({
  kind: z.literal("tam_output"),
  state_hash: z.string(),
  schema_version: z.number(),
  created_by: z.string(),
  created_at: z.string(),
  target: tamTargetSchema,
  scenarios: z.array(scenarioSchema).min(1),
  method_families_used: z.array(methodFamilySchema),
  independence_score: z.number().min(0).max(1),
  uses_synthetic_primitives: z.boolean(),
  uses_modeled_composites: z.boolean(),
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
