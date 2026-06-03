// Shared e2e helpers — the single place the suite's backend policy lives.

import type { APIRequestContext } from "@playwright/test";

// Always the LOCAL e2e backend, overridable via E2E_API_URL. NEVER
// NEXT_PUBLIC_API_URL: the playwright config loads web/.env.local into the TEST
// process, where that var points at the PRODUCTION backend — building a TAM
// there yields a hash the local app can never resolve (its /tam SSR fetch hits
// the local backend → 404).
export const API = process.env.E2E_API_URL ?? "http://localhost:8000";

// Build a seeded concept and return its deterministic state hash. Specs derive
// artifact hashes at runtime this way: state hashes are content-derived and
// stable per backend, but any data/evaluator change re-mints them — a
// hardcoded hash silently strands a spec, and never resolves on a cold backend.
export async function buildHash(
  request: APIRequestContext,
  concept = "doc-gen-pc-insurance",
): Promise<string> {
  const res = await request.get(`${API}/build/${concept}`);
  if (!res.ok()) throw new Error(`buildHash: GET /build/${concept} → ${res.status()}`);
  return (await res.json()).state_hash as string;
}
