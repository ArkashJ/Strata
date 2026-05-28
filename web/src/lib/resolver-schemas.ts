/**
 * Zod schemas mirroring the backend's `strata.resolver` + `strata.router`
 * Pydantic models, so the frontend can validate parsed SSE events / pipeline
 * results coming back from `POST /resolve` and (future) /goal endpoints.
 *
 * Kept in lockstep with:
 *   backend/src/strata/resolver/events.py
 *   backend/src/strata/resolver/slug.py
 *   backend/src/strata/router.py
 *   backend/src/strata/connectors/_capability.py
 */

import { z } from "zod";

import { sourceTierSchema, unitSchema } from "./schemas";

// ─────────────────────────────────────────────────────────────────────
// Slug resolution (resolver/slug.py)
// ─────────────────────────────────────────────────────────────────────

export const resolverIntentSchema = z.enum(["concept", "primitive", "novel"]);
export type ResolverIntent = z.infer<typeof resolverIntentSchema>;

export const resolvedQuerySchema = z.object({
  intent: resolverIntentSchema,
  concept_slug: z.string().nullable().optional(),
  primitive_slugs: z.array(z.string()).default([]),
  framework_hint: z.string().nullable().optional(),
  confidence: z.number().min(0).max(1).default(0),
});
export type ResolvedQuery = z.infer<typeof resolvedQuerySchema>;

// ─────────────────────────────────────────────────────────────────────
// Pipeline events (resolver/events.py — frozen wire set §9.1 + CLI extras)
// ─────────────────────────────────────────────────────────────────────

export const pipelineEventKindSchema = z.enum([
  // §9.1 frozen wire events
  "parsing",
  "searching",
  "framework_selected",
  "evaluating",
  "result",
  "error",
  // CLI-internal events (also useful in the frontend stream view)
  "slug_resolved",
  "concept_hit",
  "primitive_hit",
  "router_decision",
  "connector_call",
  "wrote_primitive",
  "budget_exceeded",
]);
export type PipelineEventKind = z.infer<typeof pipelineEventKindSchema>;

export const pipelineStepSchema = z.enum(["pre", "1", "2", "3", "4"]);
export type PipelineStep = z.infer<typeof pipelineStepSchema>;

export const pipelineStatusSchema = z.enum(["ok", "partial", "failed"]);
export type PipelineStatus = z.infer<typeof pipelineStatusSchema>;

export const pipelineEventSchema = z.object({
  kind: pipelineEventKindSchema,
  step: pipelineStepSchema,
  payload: z.record(z.unknown()).default({}),
  message: z.string().nullable().optional(),
});
export type PipelineEvent = z.infer<typeof pipelineEventSchema>;

// ─────────────────────────────────────────────────────────────────────
// ResolverResult (resolver/events.py)
// ─────────────────────────────────────────────────────────────────────

export const resolverViaSchema = z.enum(["concept", "primitive", "connector", "fallback", "none"]);
export type ResolverVia = z.infer<typeof resolverViaSchema>;

export const primitiveUsedSchema = z.object({
  slug: z.string().nullable().optional(),
  role: z.string().nullable().optional(),
  name: z.string().nullable().optional(),
  value: z.number(),
  unit: z
    .union([unitSchema, z.record(z.unknown())])
    .nullable()
    .optional(),
  source_url: z.string().nullable().optional(),
  source_tier: z.string().nullable().optional(),
});
export type PrimitiveUsed = z.infer<typeof primitiveUsedSchema>;

export const resolverResultSchema = z.object({
  status: pipelineStatusSchema,
  via: resolverViaSchema,
  tam_value: z.number().nullable().optional(),
  formatted_tam: z.string().nullable().optional(),
  concept_name: z.string().nullable().optional(),
  definition: z.string().nullable().optional(),
  lens: z.string().nullable().optional(),
  framework_name: z.string().nullable().optional(),
  independence_score: z.number().min(0).max(1).default(0),
  primitives_used: z.array(primitiveUsedSchema).default([]),
  wrote_primitives: z.array(z.string()).default([]),
  events: z.array(pipelineEventSchema).default([]),
  banner: z.string().nullable().optional(),
  error: z.string().nullable().optional(),
});
export type ResolverResult = z.infer<typeof resolverResultSchema>;

// ─────────────────────────────────────────────────────────────────────
// Router (router.py)
// ─────────────────────────────────────────────────────────────────────

export const routingDecisionSchema = z.object({
  connector: z.string(),
  method: z.string(),
  args: z.record(z.union([z.string(), z.number(), z.boolean()])).default({}),
  confidence: z.number().min(0).max(1),
  rationale: z.string(),
});
export type RoutingDecision = z.infer<typeof routingDecisionSchema>;

// ─────────────────────────────────────────────────────────────────────
// Capability manifest (connectors/_capability.py)
// ─────────────────────────────────────────────────────────────────────

export const capabilityArgTypeSchema = z.enum(["str", "int", "float", "bool", "date"]);
export type CapabilityArgType = z.infer<typeof capabilityArgTypeSchema>;

export const capabilityArgSchema = z.object({
  name: z.string(),
  type: capabilityArgTypeSchema,
  description: z.string(),
  example: z.string().nullable().optional(),
  required: z.boolean().default(true),
});
export type CapabilityArg = z.infer<typeof capabilityArgSchema>;

export const capabilitySpecSchema = z.object({
  connector: z.string(),
  method: z.string(),
  description: z.string().min(8),
  returns: z.string().min(4),
  args: z.array(capabilityArgSchema).default([]),
  source_tier: sourceTierSchema,
  is_fragile: z.boolean().default(false),
  requires_paid_tier: z.boolean().default(false),
});
export type CapabilitySpec = z.infer<typeof capabilitySpecSchema>;

// ─────────────────────────────────────────────────────────────────────
// SSE event names (frozen wire-level set per §9.1)
// ─────────────────────────────────────────────────────────────────────

export const FROZEN_SSE_EVENTS = [
  "parsing",
  "searching",
  "framework_selected",
  "evaluating",
  "result",
  "error",
] as const satisfies readonly PipelineEventKind[];

export const LEGACY_SSE_EVENTS = ["step", "done"] as const;
