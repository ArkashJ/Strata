"use client";

// Public registry of promoted TAMs (U6 · /browse). The backend has no
// list-promoted-TAMs endpoint and no `is_promoted` flag yet, so the grid is
// driven by the real concepts registry — each concept is the seed of a TAM and
// links into the build workhorse. Client-side search + lens filters; the
// is_promoted cut is a flagged TODO(api) below.
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { ListHeader } from "@/components/ui/ListHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { lensLabel } from "@/lib/format";
import { conceptsQuery } from "@/lib/queries";
import { TamRegistryCard } from "./TamRegistryCard";

// The six analysis lenses (Q39). null = no lens filter (the default "All").
const LENSES = [
  "cost_efficiency",
  "revenue_generation",
  "latent_demand",
  "platform_throughput",
  "bundle_consolidation",
  "productivity_uplift",
] as const;

export default function BrowsePage() {
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
    // /browse should show only promoted TAMs, separate from the auto-mint hash.
  }, [concepts.data, filter, lens]);

  // Only surface lens chips for lenses that actually appear in the data.
  const presentLenses = useMemo(() => {
    const seen = new Set((concepts.data ?? []).map((c) => c.primary_lens));
    return LENSES.filter((l) => seen.has(l));
  }, [concepts.data]);

  return (
    <main className="flex flex-1 flex-col">
      <ListHeader
        title="Browse TAMs"
        count={matches.length}
        filter={filter}
        onFilter={setFilter}
        placeholder="Filter TAMs…"
      />

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
    </main>
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
