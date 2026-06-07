import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";

import type { SensitivityResponse } from "@/components/charts/TornadoChart";
import { api } from "./api-client";
import {
  type AuditEvent,
  type ConceptQuestionReport,
  type ConceptSummary,
  type Connector,
  type FeedbackEvent,
  type FeedbackKind,
  type FeedbackStatus,
  type FeedbackTargetType,
  type FrameworkSummary,
  type PortfolioResponse,
  type PrimitiveSummary,
  type QuestionSummary,
  type RecomputeRequest,
  type SignalSummary,
  type TAMOutput,
  type TamTrajectory,
  auditEventSchema,
  conceptDetailSchema,
  conceptQuestionReportSchema,
  conceptSummarySchema,
  connectorSchema,
  feedbackEventSchema,
  frameworkDetailSchema,
  frameworkSummarySchema,
  portfolioResponseSchema,
  primitiveDetailSchema,
  primitiveSummarySchema,
  questionSummarySchema,
  signalSummarySchema,
  tamOutputSchema,
  tamTrajectorySchema,
} from "./schemas";
import { type BuildState, isScopeEmpty } from "./state-hash";

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

export const portfolioQuery = queryOptions({
  queryKey: ["portfolio"],
  queryFn: async (): Promise<PortfolioResponse> => {
    const data = await api("/portfolio");
    return validated(portfolioResponseSchema, data);
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

// The plain GET /build/{slug} always sizes against the concept's *own* declared
// scope, so a user-pinned market — like a what-if — can only be honoured by the
// recompute path. Recompute whenever the state carries either.
export function needsRecompute(state: BuildState): boolean {
  return hasOverrides(state) || !isScopeEmpty(state.scope);
}

function toRecomputeRequest(state: BuildState): RecomputeRequest {
  return {
    concept_slug: state.target_concept_slug,
    framework_assumptions: state.framework_assumptions,
    primitive_overrides: state.primitive_overrides,
    // Only send a pinned market; an empty scope is omitted so the backend follows
    // its unchanged default-scope path.
    scope: isScopeEmpty(state.scope) ? undefined : (state.scope ?? undefined),
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
    enabled: !!state.target_concept_slug && needsRecompute(state),
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

// Question-driven market report (PR4). The catalog of analysis questions, and
// the assembled report for one concept — both validated through the schemas
// exactly like conceptQuery / tamQuery. Every figure in the report response is
// registry-sourced or TAM-field-synthesised; the UI never fabricates a number.
export const questionsQuery = queryOptions({
  queryKey: ["questions"],
  queryFn: async (): Promise<QuestionSummary[]> => {
    const data = await api("/report");
    return validated(z.array(questionSummarySchema), data);
  },
  staleTime: 5 * 60_000,
});

export const questionReportQuery = (conceptSlug: string) =>
  queryOptions({
    queryKey: ["question-report", conceptSlug],
    queryFn: async (): Promise<ConceptQuestionReport> =>
      validated(conceptQuestionReportSchema, await api(`/report/${conceptSlug}`)),
    enabled: !!conceptSlug,
    staleTime: 5 * 60_000,
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

// ── Feedback / assumption-flagging (Phase F) ────────────────────────────────
// The org's flags (GET /feedback) — newest-first, RLS-scoped server-side. The
// list is RESILIENT: a 401 (signed out) or malformed response degrades to []
// so the triage page renders an honest empty state instead of throwing.
export const feedbackQuery = (status?: FeedbackStatus) =>
  queryOptions({
    queryKey: ["feedback", status ?? "all"],
    queryFn: async (): Promise<FeedbackEvent[]> => {
      try {
        const qs = status ? `?status=${status}` : "";
        const data = await api(`/feedback${qs}`);
        const parsed = z.array(feedbackEventSchema).safeParse(data);
        return parsed.success ? parsed.data : [];
      } catch {
        return [];
      }
    },
    staleTime: 30_000,
  });

// Submit a flag (POST /feedback). The submitter is resolved server-side from the
// Clerk Bearer / API-key principal; visibility is org-scoped. A flag is
// commentary only — it never changes a sourced number (E1).
export interface SubmitFeedbackInput {
  kind: FeedbackKind;
  target_type: FeedbackTargetType;
  body: string;
  target_id?: string | null;
  query_text?: string | null;
  severity?: string | null;
  suggested_value?: Record<string, unknown> | null;
}

export async function submitFeedback(input: SubmitFeedbackInput): Promise<FeedbackEvent> {
  const data = await api("/feedback", { method: "POST", body: JSON.stringify(input) });
  return validated(feedbackEventSchema, data);
}

// Triage / resolve a flag (PATCH /feedback/{id}).
export async function updateFeedback(
  id: number,
  patch: { status?: FeedbackStatus; resolution?: string | null },
): Promise<FeedbackEvent> {
  const data = await api(`/feedback/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
  return validated(feedbackEventSchema, data);
}
