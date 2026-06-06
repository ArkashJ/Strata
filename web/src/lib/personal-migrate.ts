// One-time localStorage → server migration for the personal workspace (PR 1 / U9).
//
// Before PR 1 the only "saved research" surface was per-browser localStorage:
//   - strata-build-history  (recent builds, lib/build-history.ts)
//   - strata-favorites      (pinned builds, stores/favorites-store.ts)
// PR 1 makes saved TAMs real and server-backed (`POST /me/tams/save`). On the
// FIRST authenticated load we push those local entries to the server so a user's
// pre-existing favorites/history follow them across devices, then mark the
// migration done so it never runs again (idempotent, even across reloads).
//
// This is best-effort: a failed save is swallowed (the local copy still renders),
// and the done-flag is only set after the batch completes so a mid-flight failure
// retries next load. We migrate FAVORITES (the user's explicit intent to keep a
// build); recent-build history stays local (it is browser-scoped breadcrumbs, not
// research the user asked to keep).

import { api } from "./api-client";
import type { BuildHistoryEntry } from "./build-history";

const DONE_KEY = "strata-personal-migrated-v1";
const FAVORITES_KEY = "strata-favorites";

function hasStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

// Read the favorites the zustand `persist` middleware wrote under `strata-favorites`.
// Shape: { state: { items: Record<hash, BuildHistoryEntry> }, version: number }.
function readLocalFavorites(): BuildHistoryEntry[] {
  if (!hasStorage()) return [];
  try {
    const raw = window.localStorage.getItem(FAVORITES_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    const items =
      typeof parsed === "object" && parsed !== null
        ? (parsed as { state?: { items?: unknown } }).state?.items
        : undefined;
    if (typeof items !== "object" || items === null) return [];
    return Object.values(items as Record<string, BuildHistoryEntry>).filter(
      (e): e is BuildHistoryEntry =>
        typeof e === "object" && e !== null && typeof (e as BuildHistoryEntry).hash === "string",
    );
  } catch {
    return [];
  }
}

// Migrate local favorites to the server exactly once. Safe to call on every
// authenticated mount: it no-ops after the first successful run.
export async function migratePersonalDataOnce(): Promise<void> {
  if (!hasStorage()) return;
  try {
    if (window.localStorage.getItem(DONE_KEY)) return;
  } catch {
    return;
  }

  const favorites = readLocalFavorites();
  // Even with nothing to migrate we set the flag so we stop checking.
  await Promise.allSettled(
    favorites.map((fav) =>
      api("/me/tams/save", {
        method: "POST",
        body: JSON.stringify({ state_hash: fav.hash, title: fav.label }),
      }),
    ),
  );

  try {
    window.localStorage.setItem(DONE_KEY, String(Date.now()));
  } catch {
    // Quota failure — the migration ran; we just couldn't record the flag, so it
    // may run again. The server save is an idempotent upsert, so that is harmless.
  }
}
