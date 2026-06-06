/**
 * Explore shell — the shared Strata bank. A heading plus a tab bar across the
 * registry surfaces (concepts · primitives · frameworks · signals · pyramid ·
 * TAMs). This file owns only the chrome; each tab's contents is moved in by the
 * surface that owns it under /explore/<tab>.
 */

import type { ReactNode } from "react";

import { ExploreTabs } from "./ExploreTabs";

export default function ExploreLayout({ children }: { children: ReactNode }) {
  return (
    <main className="flex flex-1 flex-col">
      <header className="px-8 pt-7 pb-0 border-b border-[var(--border-1)]">
        <h1 className="display text-[26px] leading-tight text-[var(--fg-1)] text-balance">
          Explore the Strata bank
        </h1>
        <p className="mt-1.5 max-w-[68ch] text-[14px] text-[var(--fg-2)]">
          The shared, sourced registry: every concept, primitive, framework, and signal that
          frameworks compose into a TAM.
        </p>
        <ExploreTabs />
      </header>
      {children}
    </main>
  );
}
