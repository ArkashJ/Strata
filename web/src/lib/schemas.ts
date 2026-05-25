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
