"use client";

// TAMs tab under /explore. Adapted from /browse/page.tsx.
// Public registry of buildable TAMs seeded by concepts. Lens-filter chips
// above the grid let the user narrow to a specific analysis family.
// The /explore layout.tsx owns the <main> wrapper and section title.
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { TamRegistryCard } from "@/app/browse/TamRegistryCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { lensLabel } from "@/lib/format";
import { conceptsQuery } from "@/lib/queries";

// The six analysis lenses (Q39). null = no lens filter (the default "All").
const LENSES = [
  "cost_efficiency",
  "revenue_generation",
  "latent_demand",
  "platform_throughput",
  "bundle_consolidation",
  "productivity_uplift",
] as const;

export default function ExploreTamsPage() {
  const concepts = useQuery(conceptsQuery);
  const [filter, setFilter] = useState("");
  const [lens, setLens] = useState<string | null>(null);

  const matches = useMemo(() => {
    const rows = concepts.data ?? [];
    const q = filter.trim().toLowerCase();
    return rows.filter((c) => {
      if (lens && c.primary_lens !== lens) return false;
      if (!q) return true;
      return (
        c.name.toLowerCase().includes(q) ||
        c.slug.includes(q) ||
        c.definition.toLowerCase().includes(q)
      );
    });
    // TODO(api): filter by an `is_promoted` flag once the registry exposes it —
    // this tab should show only promoted TAMs, separate from the auto-mint hash.
  }, [concepts.data, filter, lens]);

  // Only surface lens chips for lenses that actually appear in the data.
  const presentLenses = useMemo(() => {
    const seen = new Set((concepts.data ?? []).map((c) => c.primary_lens));
    return LENSES.filter((l) => seen.has(l));
  }, [concepts.data]);

  return (
    <>
      <div className="flex items-center justify-between gap-6 border-b border-[var(--border-1)] px-8 py-3">
        <span suppressHydrationWarning className="text-[13px] tabular-nums text-[var(--fg-3)]">
          {concepts.data ? `${matches.length} TAM${matches.length === 1 ? "" : "s"}` : ""}
        </span>
        <input
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter TAMs…"
          aria-label="Filter TAMs"
          className="w-[260px] max-w-[40vw] rounded-[var(--r-2)] border border-[var(--border-2)] bg-[var(--bg-1)] px-3 py-1.5 text-[13px] text-[var(--fg-1)] placeholder:text-[var(--fg-3)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)]"
        />
      </div>

      <div className="mx-auto w-full max-w-[1280px] flex-1 px-8 py-8">
        {presentLenses.length > 0 ? (
          <div className="mb-6 flex flex-wrap items-center gap-2">
            <LensChip label="All" active={lens === null} onClick={() => setLens(null)} />
            {presentLenses.map((l) => (
              <LensChip
                key={l}
                label={lensLabel(l)}
                active={lens === l}
                onClick={() => setLens(l)}
              />
            ))}
          </div>
        ) : null}

        {concepts.isPending ? (
          <CardGridSkeleton />
        ) : concepts.error ? (
          <ErrorState error={concepts.error} onRetry={() => concepts.refetch()} />
        ) : matches.length === 0 ? (
          <EmptyState
            title="No TAMs match"
            description={
              filter || lens
                ? "Nothing matches the current filters."
                : "No promoted TAMs in the registry yet."
            }
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {matches.map((c) => (
              <TamRegistryCard key={c.slug} concept={c} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function LensChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-[var(--r-round)] px-3 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors ${
        active
          ? "bg-[var(--accent-tint)] text-[var(--accent-active)]"
          : "bg-[var(--bg-2)] text-[var(--fg-3)] hover:text-[var(--fg-1)]"
      }`}
    >
      {label}
    </button>
  );
}

function CardGridSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 9 }, (_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: fixed-length placeholder, index is stable
        <Skeleton key={i} className="h-[148px]" />
      ))}
    </div>
  );
}
