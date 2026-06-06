"use client";

// Primitives tab under /explore. Adapted from /p/page.tsx.
// The /explore layout.tsx owns the <main> wrapper and section title.
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { primitivesQuery } from "@/lib/queries";
import { useHasMounted } from "@/lib/use-has-mounted";

const PAGE_SIZE = 50;

export default function ExplorePrimitivesPage() {
  const primitives = useQuery(primitivesQuery);
  const mounted = useHasMounted();
  const [filter, setFilter] = useState("");
  const [visible, setVisible] = useState(PAGE_SIZE);

  const matches = useMemo(() => {
    const rows = primitives.data ?? [];
    const q = filter.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.slug.includes(q) ||
        p.concept_slug.includes(q) ||
        p.kind.includes(q),
    );
  }, [primitives.data, filter]);

  const shown = matches.slice(0, visible);

  return (
    <>
      <div className="flex items-center justify-between gap-6 border-b border-[var(--border-1)] px-8 py-3">
        <span suppressHydrationWarning className="text-[13px] tabular-nums text-[var(--fg-3)]">
          {primitives.data ? `${matches.length} primitive${matches.length === 1 ? "" : "s"}` : ""}
        </span>
        <input
          type="search"
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value);
            setVisible(PAGE_SIZE);
          }}
          placeholder="Filter by name, concept, kind…"
          aria-label="Filter primitives"
          className="w-[260px] max-w-[40vw] rounded-[var(--r-2)] border border-[var(--border-2)] bg-[var(--bg-1)] px-3 py-1.5 text-[13px] text-[var(--fg-1)] placeholder:text-[var(--fg-3)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)]"
        />
      </div>

      <div className="flex-1 px-8 py-8 max-w-[1080px] mx-auto w-full">
        {!mounted || primitives.isPending ? (
          <TableSkeleton />
        ) : primitives.error ? (
          <ErrorState error={primitives.error} onRetry={() => primitives.refetch()} />
        ) : matches.length === 0 ? (
          <EmptyState
            title="No primitives match"
            description={filter ? `Nothing matches "${filter}".` : "The data bank is empty."}
          />
        ) : (
          <>
            <div className="overflow-x-auto canvas-card" style={{ borderRadius: "var(--r-3)" }}>
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
                    <th className="px-4 py-3 font-medium">Name</th>
                    <th className="px-4 py-3 font-medium">Concept</th>
                    <th className="px-4 py-3 font-medium text-right">Value</th>
                    <th className="px-4 py-3 font-medium">Unit</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((p) => (
                    <tr
                      key={p.slug}
                      className="border-t border-[var(--border-1)] hover:bg-[var(--bg-2)] transition-colors"
                    >
                      <td className="px-4 py-2.5">
                        <Link
                          href={`/p/${p.slug}`}
                          className="text-[var(--fg-1)] hover:text-[var(--accent)] transition-colors"
                        >
                          {p.name}
                        </Link>
                      </td>
                      <td className="px-4 py-2.5">
                        <Link
                          href={`/c/${p.concept_slug}`}
                          className="font-mono text-[12px] text-[var(--fg-3)] hover:text-[var(--accent)] transition-colors"
                        >
                          {p.concept_slug}
                        </Link>
                      </td>
                      <td className="px-4 py-2.5 text-right font-mono tabular-nums text-[var(--fg-1)]">
                        {p.value === null ? "—" : compact(p.value)}
                      </td>
                      <td className="px-4 py-2.5 text-[var(--fg-3)]">{p.unit_label}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-6 flex items-center justify-center gap-4 text-[13px] text-[var(--fg-3)]">
              <span className="tabular-nums">
                Showing {shown.length} of {matches.length}
              </span>
              {visible < matches.length ? (
                <Button variant="ghost" sm onClick={() => setVisible((v) => v + PAGE_SIZE)}>
                  Load more
                </Button>
              ) : null}
            </div>
          </>
        )}
      </div>
    </>
  );
}

function compact(value: number): string {
  if (!Number.isFinite(value)) return "—";
  return Intl.NumberFormat("en", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

function TableSkeleton() {
  return (
    <div className="flex flex-col gap-1">
      {Array.from({ length: 12 }, (_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: fixed-length placeholder, index is stable
        <Skeleton key={i} className="h-11 w-full" />
      ))}
    </div>
  );
}
