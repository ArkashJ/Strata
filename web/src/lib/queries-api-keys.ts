/**
 * API key management queries (GET /me/api-keys).
 *
 * The list query follows the safeList pattern from queries-personal.ts:
 * a 401 (signed-out) or any error degrades to [] so the panel renders an
 * honest empty/auth-prompt state rather than throwing.
 *
 * The secret is ONLY returned on POST — the list endpoint returns masked keys
 * (prefix only, no secret). Generation and revocation live as mutations in
 * ApiKeysPanel.tsx; they invalidate this query key on success.
 */

import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";

import { api } from "./api-client";

export const apiKeySchema = z.object({
  key_id: z.string(),
  label: z.string(),
  prefix: z.string(),
  created_at: z.string(),
  last_used_at: z.string().nullable(),
});

export type ApiKey = z.infer<typeof apiKeySchema>;

// The full secret is only on the POST 201 response.
export const apiKeyCreatedSchema = apiKeySchema.extend({
  key: z.string(), // strata_sk_live_… — shown once, never returned again
});
export type ApiKeyCreated = z.infer<typeof apiKeyCreatedSchema>;

async function safeListApiKeys(): Promise<ApiKey[]> {
  try {
    const data = await api("/me/api-keys");
    const parsed = z.array(apiKeySchema).safeParse(data);
    return parsed.success ? parsed.data : [];
  } catch {
    return [];
  }
}

export const apiKeysQuery = queryOptions({
  queryKey: ["personal", "api-keys"] as const,
  queryFn: safeListApiKeys,
  staleTime: 30_000,
});
