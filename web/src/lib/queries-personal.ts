/**
 * Personal-tier (My Bank / Agents) react-query options. Kept in a separate file
 * from lib/queries.ts so the leaf agents building those surfaces don't collide
 * on the shared registry queries.
 *
 * Both are RESILIENT: a missing/erroring endpoint resolves to an empty list, not
 * a thrown query — the personal surfaces are scaffolding and must render even
 * before their backend lands. Swap to a strict throwing query once the real
 * endpoints exist.
 */

import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";

import { api } from "./api-client";
import {
  type AuditEvent,
  type PortfolioCompany,
  auditEventSchema,
  portfolioResponseSchema,
} from "./schemas";

// Parse what we can; anything malformed degrades to [] rather than rejecting.
async function safeList<T>(path: string, schema: z.ZodType<T[]>): Promise<T[]> {
  try {
    const data = await api(path);
    const parsed = schema.safeParse(data);
    return parsed.success ? parsed.data : [];
  } catch {
    return [];
  }
}

// TODO(bank-agent): no dedicated "my primitives" endpoint yet — until the CLI/MCP
// sync surface lands, the closest personal data is the org's portfolio companies.
// Returns [] gracefully when /portfolio is absent or the org has none.
export const myPrimitivesQuery = queryOptions({
  queryKey: ["personal", "my-primitives"],
  queryFn: async (): Promise<PortfolioCompany[]> => {
    try {
      const data = await api("/portfolio");
      const parsed = portfolioResponseSchema.safeParse(data);
      return parsed.success ? parsed.data.companies : [];
    } catch {
      return [];
    }
  },
  staleTime: 60_000,
});

// Activity log for the Agents/Bank surfaces (resolve + recompute events). The
// strict variant lives in lib/queries.ts; this one never throws so the personal
// scaffolding renders empty instead of erroring.
export const auditQuery = (limit = 50, offset = 0) =>
  queryOptions({
    queryKey: ["personal", "audit", limit, offset],
    queryFn: (): Promise<AuditEvent[]> =>
      safeList(`/audit?limit=${limit}&offset=${offset}`, z.array(auditEventSchema)),
    staleTime: 30_000,
  });
