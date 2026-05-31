// Simple, zero-config local identity. Strata's real auth path is Clerk (enabled
// when keys are present); this is the lightweight fallback so a keyless deploy
// still has a working "who am I" — the analyst's name + org, persisted locally
// and used as the sidebar identity, audit actor, and build attribution. It is
// NOT a security boundary (no server verification) — it's a single-user demo
// identity, which is exactly what the keyless tool needs out of the box.
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface IdentityState {
  name: string | null;
  org: string | null;
  signIn: (name: string, org: string) => void;
  signOut: () => void;
}

export const useIdentityStore = create<IdentityState>()(
  persist(
    (set) => ({
      name: null,
      org: null,
      signIn: (name, org) => set({ name: name.trim() || null, org: org.trim() || null }),
      signOut: () => set({ name: null, org: null }),
    }),
    { name: "strata-identity" },
  ),
);
