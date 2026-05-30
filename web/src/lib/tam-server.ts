// Server-side TAM fetch for SSR + OpenGraph (Wave 0 / AC0.8). The /tam/<hash>
// route is server-rendered so a shared link's initial HTML carries the TAM
// headline (crawlers + previews see it, not an empty #root) and so
// generateMetadata + opengraph-image can read the real value. Returns null on a
// 404 / fetch error so the caller degrades to the client NotFound shell.
import { ApiError, api } from "./api-client";
import type { TAMOutput } from "./schemas";

export async function getTamServer(hash: string): Promise<TAMOutput | null> {
  try {
    return await api<TAMOutput>(`/tam/${hash}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    // Network/backend hiccup during SSR — don't 500 the page; let the client
    // component retry and render its own error/empty state.
    return null;
  }
}
