/**
 * TanStack Query bindings for the resolver + router endpoints.
 *
 * The CLI ``strata goal`` is server-side; the frontend's equivalent is
 * the existing ``POST /resolve`` SSE stream. These exports give React
 * components a typed handle to that stream plus a placeholder query for
 * the future ``GET /capabilities`` endpoint.
 */

import { type UseMutationOptions, useMutation } from "@tanstack/react-query";

import { type SSEEnvelope, streamResolve } from "./resolver-client";
import {
  type CapabilitySpec,
  type PipelineEvent,
  type ResolverResult,
  capabilitySpecSchema,
} from "./resolver-schemas";

export type RunResolveArgs = {
  query: string;
  onEnvelope?: (env: SSEEnvelope) => void;
  signal?: AbortSignal;
};

export type RunResolveResult = {
  events: SSEEnvelope[];
  finalResult: ResolverResult | null;
  raw: SSEEnvelope[];
};

/**
 * Drive a single /resolve invocation to completion. The generator is
 * drained inside the mutationFn so React Query gets a clean settled
 * promise (no streaming via the hook itself — callers wanting an
 * incremental view should consume ``streamResolve`` directly inside an
 * effect, which is what ResolveView already does).
 *
 * ``onEnvelope`` is called for each frame as it arrives, useful for
 * partial UI updates during the request.
 */
export function useResolveMutation(
  options: Omit<UseMutationOptions<RunResolveResult, Error, RunResolveArgs>, "mutationFn"> = {},
) {
  return useMutation<RunResolveResult, Error, RunResolveArgs>({
    mutationKey: ["resolve"],
    mutationFn: async ({ query, onEnvelope, signal }) => {
      const raw: SSEEnvelope[] = [];
      let finalResult: ResolverResult | null = null;

      for await (const envelope of streamResolve({ query }, { signal })) {
        raw.push(envelope);
        onEnvelope?.(envelope);
        if (envelope.event === "result" && envelope.data && typeof envelope.data === "object") {
          // The /resolve route's payload is a superset of the resolver/CLI
          // ResolverResult; map the relevant fields.
          const data = envelope.data as Record<string, unknown>;
          finalResult = {
            status: "ok",
            via: "fallback",
            tam_value: typeof data.tam_value === "number" ? data.tam_value : null,
            formatted_tam: typeof data.formatted_tam === "string" ? data.formatted_tam : null,
            concept_name: typeof data.concept_name === "string" ? data.concept_name : null,
            definition: typeof data.definition === "string" ? data.definition : null,
            lens: typeof data.lens === "string" ? data.lens : null,
            framework_name: typeof data.framework_name === "string" ? data.framework_name : null,
            independence_score:
              typeof data.independence_score === "number" ? data.independence_score : 0,
            primitives_used: Array.isArray(data.primitives_used)
              ? (data.primitives_used as RunResolveResult["finalResult"] extends infer R
                  ? R extends { primitives_used: infer P }
                    ? P
                    : never
                  : never)
              : [],
            wrote_primitives: [],
            events: [],
            banner: null,
            error: null,
          };
        }
      }

      return { events: raw, finalResult, raw };
    },
    ...options,
  });
}

// ─────────────────────────────────────────────────────────────────────
// Capability manifest fetcher — endpoint not yet exposed on the API,
// but the schema is kept here so a UI can be built ahead of the route.
// ─────────────────────────────────────────────────────────────────────

export async function fetchCapabilities(baseUrl: string): Promise<CapabilitySpec[]> {
  const res = await fetch(`${baseUrl}/capabilities`);
  if (!res.ok) throw new Error(`GET /capabilities failed: ${res.status}`);
  const data: unknown = await res.json();
  return capabilitySpecSchema.array().parse(data);
}

// Re-export commonly used types so callers can `import { ResolverResult, PipelineEvent }
// from "@/lib/resolver-queries"` without crossing modules.
export type { PipelineEvent, ResolverResult, SSEEnvelope };
