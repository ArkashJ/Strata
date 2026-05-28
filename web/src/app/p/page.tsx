"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { ListHeader } from "@/components/ui/ListHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { primitivesQuery } from "@/lib/queries";

const PAGE_SIZE = 50;

export default function PrimitivesListPage() {
  const primitives = useQuery(primitivesQuery);
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
    <main className="flex-1 flex flex-col">
      <ListHeader
        title="Primitives"
        count={primitives.data?.length}
        filter={filter}
        onFilter={(v) => {
          setFilter(v);
          setVisible(PAGE_SIZE);
        }}
        placeholder="Filter by name, concept, kind…"
      />

      <div className="flex-1 px-8 py-8 max-w-[1080px] mx-auto w-full">
        {primitives.isPending ? (
          <TableSkeleton />
        ) : primitives.error ? (
          <ErrorState error={primitives.error} onRetry={() => primitives.refetch()} />
        ) : matches.length === 0 ? (
          <EmptyState
            title="No primitives match"
            description={filter ? `Nothing matches “${filter}”.` : "The data bank is empty."}
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
    </main>
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
