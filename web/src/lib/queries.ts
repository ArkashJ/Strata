import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";

import type { SensitivityResponse } from "@/components/charts/TornadoChart";
import { api } from "./api-client";
import {
  type AuditEvent,
  type ConceptSummary,
  type Connector,
  type FrameworkSummary,
  type PrimitiveSummary,
  type RecomputeRequest,
  type SignalSummary,
  type TAMOutput,
  type TamTrajectory,
  auditEventSchema,
  conceptDetailSchema,
  conceptSummarySchema,
  connectorSchema,
  frameworkDetailSchema,
  frameworkSummarySchema,
  primitiveDetailSchema,
  primitiveSummarySchema,
  signalSummarySchema,
  tamOutputSchema,
  tamTrajectorySchema,
} from "./schemas";
import type { BuildState } from "./state-hash";

function validated<T>(schema: z.ZodType<T>, data: unknown): T {
  return schema.parse(data);
}

export const conceptsQuery = queryOptions({
  queryKey: ["concepts"],
  queryFn: async (): Promise<ConceptSummary[]> => {
    const data = await api("/c");
    return validated(z.array(conceptSummarySchema), data);
  },
});

export const conceptQuery = (slug: string) =>
  queryOptions({
    queryKey: ["concept", slug],
    queryFn: async () => validated(conceptDetailSchema, await api(`/c/${slug}`)),
    enabled: !!slug,
  });

export const primitivesQuery = queryOptions({
  queryKey: ["primitives"],
  queryFn: async (): Promise<PrimitiveSummary[]> => {
    const data = await api("/p");
    return validated(z.array(primitiveSummarySchema), data);
  },
});

export const primitiveQuery = (slug: string) =>
  queryOptions({
    queryKey: ["primitive", slug],
    queryFn: async () => validated(primitiveDetailSchema, await api(`/p/${slug}`)),
    enabled: !!slug,
  });

export const connectorsQuery = queryOptions({
  queryKey: ["connectors"],
  queryFn: async (): Promise<Connector[]> => {
    const data = await api("/connectors");
    return validated(z.array(connectorSchema), data);
  },
});

export const signalsQuery = queryOptions({
  queryKey: ["signals"],
  queryFn: async (): Promise<SignalSummary[]> => {
    const data = await api("/signals");
    return validated(z.array(signalSummarySchema), data);
  },
});

export const frameworksQuery = queryOptions({
  queryKey: ["frameworks"],
  queryFn: async (): Promise<FrameworkSummary[]> => {
    const data = await api("/f");
    return validated(z.array(frameworkSummarySchema), data);
  },
});

export const frameworkQuery = (slug: string) =>
  queryOptions({
    queryKey: ["framework", slug],
    queryFn: async () => validated(frameworkDetailSchema, await api(`/f/${slug}`)),
    enabled: !!slug,
  });

export const buildQuery = (conceptSlug: string) =>
  queryOptions({
    queryKey: ["build", conceptSlug],
    queryFn: async (): Promise<TAMOutput> => {
      const data = await api(`/build/${conceptSlug}`);
      return validated(tamOutputSchema, data);
    },
    enabled: !!conceptSlug,
    staleTime: 5 * 60_000,
  });

// True when the user has diverged from the registry defaults — i.e. a what-if
// scalar or a primitive swap is in play, so the TAM must be recomputed server-side
// rather than read from GET /build/{slug}.
export function hasOverrides(state: BuildState): boolean {
  const fa = state.framework_assumptions ?? {};
  const po = state.primitive_overrides ?? {};
  return Object.values(fa).some((m) => Object.keys(m).length > 0) || Object.keys(po).length > 0;
}

function toRecomputeRequest(state: BuildState): RecomputeRequest {
  return {
    concept_slug: state.target_concept_slug,
    framework_assumptions: state.framework_assumptions,
    primitive_overrides: state.primitive_overrides,
  };
}

// POST the overrides; the backend re-evaluates and mints a fresh state_hash. The
// query key includes the canonical override payload so distinct what-ifs cache
// independently and an unchanged override re-uses the result.
export const recomputeQuery = (state: BuildState) => {
  const req = toRecomputeRequest(state);
  return queryOptions({
    queryKey: ["recompute", req],
    queryFn: async (): Promise<TAMOutput> => {
      const data = await api("/build/recompute", {
        method: "POST",
        body: JSON.stringify(req),
      });
      return validated(tamOutputSchema, data);
    },
    enabled: !!state.target_concept_slug && hasOverrides(state),
    staleTime: 5 * 60_000,
  });
};

export const trajectoryQuery = (conceptSlug: string) =>
  queryOptions({
    queryKey: ["trajectory", conceptSlug],
    queryFn: async (): Promise<TamTrajectory> => {
      const data = await api(`/build/${conceptSlug}/trajectory`);
      return validated(tamTrajectorySchema, data);
    },
    enabled: !!conceptSlug,
    staleTime: 5 * 60_000,
  });

// Per-input ±pct TAM swing for the sensitivity tornado (Wave 2 / AC2.3).
// Validated like every other query so a malformed response degrades to the
// SensitivitySection error guard instead of crashing TornadoChart at render.
const sensitivityResponseSchema = z.object({
  concept_slug: z.string(),
  base: z.number(),
  pct: z.number(),
  inputs: z.array(
    z.object({
      primitive_slug: z.string(),
      name: z.string(),
      base: z.number(),
      low: z.number(),
      high: z.number(),
      impact: z.number(),
    }),
  ),
}) satisfies z.ZodType<SensitivityResponse>;

export const sensitivityQuery = (conceptSlug: string, pct = 0.2) =>
  queryOptions({
    queryKey: ["sensitivity", conceptSlug, pct],
    queryFn: async (): Promise<SensitivityResponse> =>
      validated(
        sensitivityResponseSchema,
        await api(`/build/${conceptSlug}/sensitivity?pct=${pct}`),
      ),
    enabled: !!conceptSlug,
    staleTime: 5 * 60_000,
  });

export const tamQuery = (stateHash: string) =>
  queryOptions({
    queryKey: ["tam", stateHash],
    queryFn: async (): Promise<TAMOutput> => {
      const data = await api(`/tam/${stateHash}`);
      return validated(tamOutputSchema, data);
    },
    enabled: !!stateHash,
    staleTime: Number.POSITIVE_INFINITY,
  });

// Paginated audit feed (newest-first) for the dashboard. The backend already
// orders by ts desc, so we render rows in the order returned.
export const auditQuery = (limit = 50, offset = 0) =>
  queryOptions({
    queryKey: ["audit", limit, offset],
    queryFn: async (): Promise<AuditEvent[]> => {
      const data = await api(`/audit?limit=${limit}&offset=${offset}`);
      return validated(z.array(auditEventSchema), data);
    },
    staleTime: 30_000,
  });
