"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { ListHeader } from "@/components/ui/ListHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { lensLabel, tierLabel } from "@/lib/format";
import { frameworksQuery } from "@/lib/queries";

export default function FrameworksListPage() {
  const frameworks = useQuery(frameworksQuery);
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
    <main className="flex-1 flex flex-col">
      <ListHeader
        title="Frameworks"
        count={frameworks.data?.length}
        filter={filter}
        onFilter={setFilter}
        placeholder="Filter by name, family, lens…"
      />

      <div className="flex-1 px-8 py-8 max-w-[1080px] mx-auto w-full">
        {frameworks.isPending ? (
          <CardGridSkeleton />
        ) : frameworks.error ? (
          <ErrorState error={frameworks.error} onRetry={() => frameworks.refetch()} />
        ) : matches.length === 0 ? (
          <EmptyState
            title="No frameworks match"
            description={filter ? `Nothing matches “${filter}”.` : "No frameworks defined."}
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
    </main>
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
