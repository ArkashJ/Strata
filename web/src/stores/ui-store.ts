// Client-only UI state. Server data lives in TanStack Query, not here.
//
// Add slices by creating sibling files (e.g. `pyramid-store.ts`) — keep this
// store narrow and ephemeral. Persisted slices should opt in to `persist`
// middleware explicitly per-slice.
import { create } from "zustand";
import { persist } from "zustand/middleware";

export type RightRailTab = "frameworks" | "scenarios" | "lineage";

export type RecentKind = "concept" | "primitive" | "framework";

// A jump-back-to entry for the command palette's RECENT group. We store the
// route + label rather than the full record so the list survives a reload
// without re-fetching, and so a stale slug still renders (it just 404s on open).
export interface RecentEntity {
  kind: RecentKind;
  slug: string;
  label: string;
}

const RECENT_LIMIT = 6;

interface UiState {
  // Right rail (build/tam views) — unchanged from the foundation.
  rightRailOpen: boolean;
  rightRailTab: RightRailTab;
  toggleRightRail: () => void;
  setRightRailTab: (tab: RightRailTab) => void;

  // App-shell chrome.
  sidebarCollapsed: boolean;
  drawerOpen: boolean;
  commandPaletteOpen: boolean;
  toggleSidebar: () => void;
  setDrawerOpen: (open: boolean) => void;
  openPalette: () => void;
  closePalette: () => void;
  togglePalette: () => void;

  // Persisted jump-list for the palette's RECENT group.
  recentEntities: RecentEntity[];
  pushRecent: (entity: RecentEntity) => void;
}

// Only `recentEntities` survives reloads — everything else is per-session chrome
// state and should reset on a fresh load.
export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      rightRailOpen: true,
      rightRailTab: "frameworks",
      toggleRightRail: () => set((s) => ({ rightRailOpen: !s.rightRailOpen })),
      setRightRailTab: (tab) => set({ rightRailTab: tab }),

      sidebarCollapsed: false,
      drawerOpen: false,
      commandPaletteOpen: false,
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setDrawerOpen: (open) => set({ drawerOpen: open }),
      openPalette: () => set({ commandPaletteOpen: true }),
      closePalette: () => set({ commandPaletteOpen: false }),
      togglePalette: () => set((s) => ({ commandPaletteOpen: !s.commandPaletteOpen })),

      recentEntities: [],
      pushRecent: (entity) =>
        set((s) => ({
          recentEntities: [
            entity,
            ...s.recentEntities.filter((e) => !(e.kind === entity.kind && e.slug === entity.slug)),
          ].slice(0, RECENT_LIMIT),
        })),
    }),
    {
      name: "strata-ui",
      partialize: (s) => ({ recentEntities: s.recentEntities }),
    },
  ),
);
