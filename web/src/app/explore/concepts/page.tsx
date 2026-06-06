"use client";

// Concepts tab under /explore. Adapted from /c/page.tsx.
// The /explore layout.tsx owns the <main> wrapper and the section title;
// this page starts with the filter bar then renders the grid.
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { lensLabel } from "@/lib/format";
import { conceptsQuery } from "@/lib/queries";
import { useHasMounted } from "@/lib/use-has-mounted";

export default function ExploreConceptsPage() {
  const concepts = useQuery(conceptsQuery);
  const mounted = useHasMounted();
  const [filter, setFilter] = useState("");

  const matches = useMemo(() => {
    const rows = concepts.data ?? [];
    const q = filter.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.slug.includes(q) ||
        c.definition.toLowerCase().includes(q),
    );
  }, [concepts.data, filter]);

  return (
    <>
      <div className="flex items-center justify-between gap-6 border-b border-[var(--border-1)] px-8 py-3">
        <span suppressHydrationWarning className="text-[13px] tabular-nums text-[var(--fg-3)]">
          {concepts.data ? `${matches.length} concept${matches.length === 1 ? "" : "s"}` : ""}
        </span>
        <input
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter concepts…"
          aria-label="Filter concepts"
          className="w-[260px] max-w-[40vw] rounded-[var(--r-2)] border border-[var(--border-2)] bg-[var(--bg-1)] px-3 py-1.5 text-[13px] text-[var(--fg-1)] placeholder:text-[var(--fg-3)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)]"
        />
      </div>

      <div className="flex-1 px-8 py-8 max-w-[1280px] mx-auto w-full">
        {!mounted || concepts.isPending ? (
          <CardGridSkeleton />
        ) : concepts.error ? (
          <ErrorState error={concepts.error} onRetry={() => concepts.refetch()} />
        ) : matches.length === 0 ? (
          <EmptyState
            title="No concepts match"
            description={filter ? `Nothing matches "${filter}".` : "The registry is empty."}
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {matches.map((c) => (
              <Link
                key={c.slug}
                href={`/c/${c.slug}`}
                className="canvas-card flex flex-col gap-2 p-5 group"
                style={{ borderRadius: "var(--r-3)" }}
              >
                <div className="flex items-start justify-between gap-3">
                  <h2 className="text-[15px] font-medium text-[var(--fg-1)] leading-snug group-hover:text-[var(--accent)] transition-colors">
                    {c.name}
                  </h2>
                </div>
                <p className="text-[13px] text-[var(--fg-3)] leading-relaxed line-clamp-3">
                  {c.definition}
                </p>
                <div className="mt-auto flex items-center gap-2 pt-2 text-[11px] text-[var(--fg-3)]">
                  <span className="role-chip role-chip--accent uppercase tracking-[0.04em]">
                    {lensLabel(c.primary_lens)}
                  </span>
                  <span className="text-[var(--fg-4)]">·</span>
                  <span className="tabular-nums">
                    {c.measurement_count} measurement
                    {c.measurement_count === 1 ? "" : "s"}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function CardGridSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: 9 }, (_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: fixed-length placeholder, index is stable
        <Skeleton key={i} className="h-[148px]" />
      ))}
    </div>
  );
}
