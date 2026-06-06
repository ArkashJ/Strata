"use client";

// Frameworks tab under /explore. Adapted from /f/page.tsx.
// The /explore layout.tsx owns the <main> wrapper and section title.
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { lensLabel, tierLabel } from "@/lib/format";
import { frameworksQuery } from "@/lib/queries";
import { useHasMounted } from "@/lib/use-has-mounted";

export default function ExploreFrameworksPage() {
  const frameworks = useQuery(frameworksQuery);
  const mounted = useHasMounted();
  const [filter, setFilter] = useState("");

  const matches = useMemo(() => {
    const rows = frameworks.data ?? [];
    const q = filter.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(
      (f) =>
        f.name.toLowerCase().includes(q) ||
        f.slug.includes(q) ||
        f.method_family.includes(q) ||
        f.lens.includes(q),
    );
  }, [frameworks.data, filter]);

  return (
    <>
      <div className="flex items-center justify-between gap-6 border-b border-[var(--border-1)] px-8 py-3">
        <span suppressHydrationWarning className="text-[13px] tabular-nums text-[var(--fg-3)]">
          {frameworks.data ? `${matches.length} framework${matches.length === 1 ? "" : "s"}` : ""}
        </span>
        <input
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by name, family, lens…"
          aria-label="Filter frameworks"
          className="w-[260px] max-w-[40vw] rounded-[var(--r-2)] border border-[var(--border-2)] bg-[var(--bg-1)] px-3 py-1.5 text-[13px] text-[var(--fg-1)] placeholder:text-[var(--fg-3)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)]"
        />
      </div>

      <div className="flex-1 px-8 py-8 max-w-[1080px] mx-auto w-full">
        {!mounted || frameworks.isPending ? (
          <CardGridSkeleton />
        ) : frameworks.error ? (
          <ErrorState error={frameworks.error} onRetry={() => frameworks.refetch()} />
        ) : matches.length === 0 ? (
          <EmptyState
            title="No frameworks match"
            description={filter ? `Nothing matches "${filter}".` : "No frameworks defined."}
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {matches.map((f) => (
              <Link
                key={f.slug}
                href={`/f/${f.slug}`}
                className="canvas-card flex flex-col gap-3 p-5 group"
                style={{ borderRadius: "var(--r-3)" }}
              >
                <h2 className="text-[16px] font-medium text-[var(--fg-1)] group-hover:text-[var(--accent)] transition-colors">
                  {f.name}
                </h2>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="role-chip uppercase tracking-[0.04em]">
                    {tierLabel(f.method_family)}
                  </span>
                  <span className="role-chip role-chip--accent uppercase tracking-[0.04em]">
                    {lensLabel(f.lens)}
                  </span>
                </div>
                <span className="text-[12px] text-[var(--fg-3)] tabular-nums">
                  {f.input_count} input{f.input_count === 1 ? "" : "s"}
                </span>
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
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {Array.from({ length: 4 }, (_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: fixed-length placeholder, index is stable
        <Skeleton key={i} className="h-[140px]" />
      ))}
    </div>
  );
}
