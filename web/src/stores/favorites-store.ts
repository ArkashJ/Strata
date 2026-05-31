// Favorited TAM builds, persisted locally. We store the whole BuildHistoryEntry
// (not just the hash) so a favorite renders — and re-opens — without needing the
// build to still be in the visit history. Keyed by hash; toggling is idempotent.
import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { BuildHistoryEntry } from "@/lib/build-history";

interface FavoritesState {
  items: Record<string, BuildHistoryEntry>;
  toggle: (entry: BuildHistoryEntry) => void;
}

export const useFavoritesStore = create<FavoritesState>()(
  persist(
    (set) => ({
      items: {},
      toggle: (entry) =>
        set((s) => {
          const next = { ...s.items };
          if (next[entry.hash]) {
            delete next[entry.hash];
          } else {
            next[entry.hash] = entry;
          }
          return { items: next };
        }),
    }),
    { name: "strata-favorites" },
  ),
);
