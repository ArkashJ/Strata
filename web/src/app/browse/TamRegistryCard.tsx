"use client";

// A registry entry on /browse. Until the backend serves promoted TAMs with
// their state hashes, each card represents a buildable TAM seeded by a concept
// and links into the build workhorse (matching ConceptCard / the home grid).
// Swap the href to /tam/{state_hash} once the promoted-TAM list endpoint lands.
import { useRouter } from "next/navigation";

import { lensLabel } from "@/lib/format";
import type { ConceptSummary } from "@/lib/schemas";

export function TamRegistryCard({ concept }: { concept: ConceptSummary }) {
  const router = useRouter();

  return (
    <button
      type="button"
      onClick={() => router.push(`/build?q=${encodeURIComponent(concept.name)}`)}
      className="canvas-card group flex w-full cursor-pointer flex-col gap-2 p-5 text-left transition-transform duration-[var(--t-fast)] hover:translate-y-[-1px] active:translate-y-0"
      style={{ borderRadius: "var(--r-3)" }}
    >
      <h2 className="text-[15px] font-medium leading-snug text-[var(--fg-1)] transition-colors group-hover:text-[var(--accent)]">
        {concept.name}
      </h2>
      <p className="line-clamp-3 text-[13px] leading-relaxed text-[var(--fg-3)]">
        {concept.definition}
      </p>
      <div className="mt-auto flex items-center gap-2 pt-2 text-[11px] text-[var(--fg-3)]">
        <span className="role-chip role-chip--accent uppercase tracking-[0.04em]">
          {lensLabel(concept.primary_lens)}
        </span>
        <span className="text-[var(--fg-4)]">·</span>
        <span className="tabular-nums">
          {concept.measurement_count} primitive
          {concept.measurement_count === 1 ? "" : "s"}
        </span>
        <span className="ml-auto text-[var(--accent)] opacity-0 transition-opacity group-hover:opacity-100">
          Build →
        </span>
      </div>
    </button>
  );
}
