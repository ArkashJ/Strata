import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";

import { api } from "./api-client";
import {
  type ConceptSummary,
  type FrameworkSummary,
  type PrimitiveSummary,
  type TAMOutput,
  type TamTrajectory,
  conceptDetailSchema,
  conceptSummarySchema,
  frameworkDetailSchema,
  frameworkSummarySchema,
  primitiveDetailSchema,
  primitiveSummarySchema,
  tamOutputSchema,
  tamTrajectorySchema,
} from "./schemas";

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
