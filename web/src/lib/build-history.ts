// Local, SSR-safe record of the /build artifacts a user has visited. The backend
// does NOT persist computed TAMs (/tam/{hash} 404s), so the only way to surface
// "your saved builds" on the dashboard is to remember the hash + encoded state we
// minted on each visit. This is a thin localStorage wrapper — no zustand needed,
// since the dashboard reads it once on mount and the recorder writes fire-and-forget.

const STORAGE_KEY = "strata-build-history";
const LIMIT = 40;

export interface BuildHistoryEntry {
  // state hash (path segment of /build/<hash>)
  hash: string;
  // base64url-encoded BuildState carried in ?s= — required to re-open the build,
  // because the hash alone can't recover the (un-persisted) TAM.
  encoded: string;
  // human label: the resolved concept name, falling back to the slug.
  label: string;
  // target concept slug, for a compact secondary line.
  conceptSlug: string;
  // epoch ms of the most recent visit.
  visitedAt: number;
}

function hasStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export function readBuildHistory(): BuildHistoryEntry[] {
  if (!hasStorage()) return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    // Defensive: keep only well-shaped rows so a corrupted/old entry can't crash
    // the dashboard render.
    return parsed.filter(
      (e): e is BuildHistoryEntry =>
        typeof e === "object" &&
        e !== null &&
        typeof (e as BuildHistoryEntry).hash === "string" &&
        typeof (e as BuildHistoryEntry).encoded === "string" &&
        typeof (e as BuildHistoryEntry).visitedAt === "number",
    );
  } catch {
    return [];
  }
}

// Record (or refresh) one visited build. De-dupes on hash, moves the entry to the
// front, and caps the list. No-op on the server.
export function recordBuildVisit(entry: Omit<BuildHistoryEntry, "visitedAt">): void {
  if (!hasStorage()) return;
  if (!entry.hash || !entry.encoded) return;
  try {
    const existing = readBuildHistory().filter((e) => e.hash !== entry.hash);
    const next: BuildHistoryEntry[] = [{ ...entry, visitedAt: Date.now() }, ...existing].slice(
      0,
      LIMIT,
    );
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Quota / serialization failure — history is best-effort, never block a build.
  }
}
