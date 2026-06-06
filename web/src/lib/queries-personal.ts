/**
 * Personal-tier (My Bank) react-query options (PR 1 / U9). Kept separate from
 * lib/queries.ts so the leaf agents building the personal surfaces don't collide
 * on the shared registry queries.
 *
 * These hit the real server-backed `/me/*` workspace: the backend resolves the
 * caller from the Clerk Bearer token (injected by api-client) into a tenant-
 * isolated Principal. Every query is RESILIENT — a 401 (signed out) or any error
 * resolves to an empty list rather than throwing, so the Bank surfaces render an
 * honest empty/loading state instead of erroring. Auth-gated UI (sign-in prompt)
 * lives in the section components, not here.
 */

import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";

import { api } from "./api-client";
import {
  type AuditEvent,
  type TAMOutput,
  type UserPrimitive,
  auditEventSchema,
  tamOutputSchema,
  userPrimitiveSchema,
} from "./schemas";

// Parse what we can; anything malformed (or a 401/5xx) degrades to [] rather than
// rejecting, so the personal surfaces never throw on a stale backend or signed-out
// session.
async function safeList<T>(path: string, schema: z.ZodType<T[]>): Promise<T[]> {
  try {
    const data = await api(path);
    const parsed = schema.safeParse(data);
    return parsed.success ? parsed.data : [];
  } catch {
    return [];
  }
}

// The caller's PRIVATE primitive store (GET /me/primitives). Empty list when
// signed out (the endpoint 401s and safeList swallows it) or when the user has
// synced nothing yet — the section renders its honest "sync via CLI/MCP" state.
export const myPrimitivesQuery = queryOptions({
  queryKey: ["personal", "my-primitives"],
  queryFn: (): Promise<UserPrimitive[]> => safeList("/me/primitives", z.array(userPrimitiveSchema)),
  staleTime: 60_000,
});

// The caller's saved research (GET /me/tams) — TAMs they explicitly saved,
// cross-device. Empty when signed out or nothing saved.
export const savedTamsQuery = queryOptions({
  queryKey: ["personal", "saved-tams"],
  queryFn: (): Promise<TAMOutput[]> => safeList("/me/tams", z.array(tamOutputSchema)),
  staleTime: 30_000,
});

// The caller's activity history (GET /me/audit) — only the caller's own events,
// RLS-scoped server-side. Resilient: [] when signed out or on error.
export const myAuditQuery = queryOptions({
  queryKey: ["personal", "my-audit"],
  queryFn: (): Promise<AuditEvent[]> => safeList("/me/audit", z.array(auditEventSchema)),
  staleTime: 30_000,
});
