"use client";

/**
 * BankView — the full client-rendered My Bank page.
 *
 * Two-tier framing: "My Bank" (this surface — private, org-scoped) vs the
 * shared Strata bank (/explore — public, generic). The intro line makes that
 * duality legible without belaboring it.
 *
 * Sections:
 *   1. My primitives  — private primitive table (CLI/MCP synced)
 *   2. Saved builds   — favorites + recent-build history
 *   3. Activity       — audit feed (soft query, never throws)
 */

import Link from "next/link";

import { ActivitySection } from "@/components/bank/ActivitySection";
import { MyPrimitivesSection } from "@/components/bank/MyPrimitivesSection";
import { SavedBuildsSection } from "@/components/bank/SavedBuildsSection";

export function BankView() {
  return (
    <main className="mx-auto flex w-full max-w-[var(--content-max,1100px)] flex-1 flex-col gap-10 px-8 py-8">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="border-b border-[var(--border-1)] pb-6">
        <h1 className="display text-[28px] text-[var(--fg-1)]">My Bank</h1>
        <p className="mt-1.5 max-w-[62ch] text-[13px] leading-relaxed text-[var(--fg-3)]">
          Your private primitives, builds, and TAMs, synced via the CLI or an MCP-connected agent.
          The shared Strata bank — sourced, public primitives — lives at{" "}
          <Link href="/explore" className="text-[var(--accent)] underline-offset-2 hover:underline">
            /explore
          </Link>
          .
        </p>
      </header>

      {/* ── My primitives ──────────────────────────────────────────────────── */}
      <MyPrimitivesSection />

      {/* ── Saved builds (favorites + history) ────────────────────────────── */}
      <SavedBuildsSection />

      {/* ── Activity log ───────────────────────────────────────────────────── */}
      <ActivitySection />
    </main>
  );
}
