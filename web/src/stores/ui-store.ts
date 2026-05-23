// Client-only UI state. Server data lives in TanStack Query, not here.
//
// Add slices by creating sibling files (e.g. `pyramid-store.ts`) — keep this
// store narrow and ephemeral. Persisted slices should opt in to `persist`
// middleware explicitly per-slice.
import { create } from "zustand";

export type RightRailTab = "frameworks" | "scenarios" | "lineage";

interface UiState {
  rightRailOpen: boolean;
  rightRailTab: RightRailTab;
  toggleRightRail: () => void;
  setRightRailTab: (tab: RightRailTab) => void;
}

export const useUiStore = create<UiState>((set) => ({
  rightRailOpen: true,
  rightRailTab: "frameworks",
  toggleRightRail: () => set((s) => ({ rightRailOpen: !s.rightRailOpen })),
  setRightRailTab: (tab) => set({ rightRailTab: tab }),
}));
