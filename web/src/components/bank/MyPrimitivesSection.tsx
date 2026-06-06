"use client";

/**
 * MyPrimitivesSection — the personal primitive table ("my CRM").
 *
 * Data: myPrimitivesQuery from lib/queries-personal. Today that endpoint
 * returns the org's portfolio companies (visibility=private) as the closest
 * available stand-in for a personal primitive list — per the TODO comment in
 * queries-personal.ts. When a dedicated /my-primitives endpoint lands, only
 * the query needs updating; this component's shape is already correct.
 *
 * Empty state: honest. Sync via CLI/MCP is the advertised path. We never
 * fabricate rows.
 */

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Skeleton } from "@/components/ui/Skeleton";
import { myPrimitivesQuery } from "@/lib/queries-personal";
import type { PortfolioCompany } from "@/lib/schemas";

// ── Section ───────────────────────────────────────────────────────────────────

export function MyPrimitivesSection() {
  const { data, isPending, isError } = useQuery(myPrimitivesQuery);

  return (
    <section aria-labelledby="bank-primitives-heading">
      <div className="mb-3 flex items-baseline justify-between gap-4">
        <h2
          id="bank-primitives-heading"
          className="text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--fg-4)]"
        >
          My primitives
        </h2>
        {data && data.length > 0 && (
          <span className="tam-num text-[11px] text-[var(--fg-3)]">{data.length}</span>
        )}
      </div>

      {isPending ? (
        <PrimitivesSkeleton />
      ) : isError ? (
        <ErrorCard />
      ) : data && data.length > 0 ? (
        <PrimitivesTable rows={data} />
      ) : (
        <EmptySync />
      )}
    </section>
  );
}

// ── Table ─────────────────────────────────────────────────────────────────────

function PrimitivesTable({ rows }: { rows: PortfolioCompany[] }) {
  return (
    <div className="canvas-card overflow-hidden border border-[var(--border-1)]">
      <table className="w-full border-collapse text-[13px]" aria-label="My primitives">
        <thead>
          <tr className="border-b border-[var(--border-1)]">
            <Th>Name</Th>
            <Th>Market</Th>
            <Th right>TAM</Th>
            <Th>Status</Th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border-1)]">
          {rows.map((row) => (
            <PrimitiveRow key={row.domain} row={row} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PrimitiveRow({ row }: { row: PortfolioCompany }) {
  const tamDisplay = row.tam_value !== null ? formatTam(row.tam_value) : null;

  return (
    <tr className="group transition-colors hover:bg-[var(--bg-2)]">
      {/* Name + domain */}
      <td className="px-4 py-2.5">
        <span className="font-medium text-[var(--fg-1)]">{row.name}</span>
        <span className="ml-2 font-mono text-[11px] text-[var(--fg-3)]">{row.domain}</span>
      </td>

      {/* Market concept — link to its build if we have one */}
      <td className="px-4 py-2.5 text-[var(--fg-2)]">
        {row.market_concept_slug ? (
          <Link
            href={`/build/${row.market_concept_slug}`}
            className="text-[var(--accent)] underline-offset-2 hover:underline"
          >
            {row.market_concept_slug}
          </Link>
        ) : (
          <span className="text-[var(--fg-4)]">—</span>
        )}
      </td>

      {/* TAM value — mono, right-aligned */}
      <td className="px-4 py-2.5 text-right">
        {tamDisplay !== null ? (
          row.state_hash ? (
            <Link
              href={`/tam/${row.state_hash}`}
              className="tam-num text-[13px] text-[var(--fg-1)] underline-offset-2 hover:text-[var(--accent)] hover:underline"
            >
              {tamDisplay}
            </Link>
          ) : (
            <span className="tam-num text-[13px] text-[var(--fg-1)]">{tamDisplay}</span>
          )
        ) : (
          <span className="tam-num text-[13px] text-[var(--fg-3)]">—</span>
        )}
      </td>

      {/* Status chip */}
      <td className="px-4 py-2.5">
        <StatusChip status={row.status} />
      </td>
    </tr>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function Th({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return (
    <th
      scope="col"
      className={`px-4 py-2 text-[11px] font-medium uppercase tracking-[0.06em] text-[var(--fg-3)] ${right ? "text-right" : "text-left"}`}
    >
      {children}
    </th>
  );
}

const STATUS_STYLES: Record<string, string> = {
  sized: "bg-[var(--tier-regulator-tint,rgba(63,166,107,0.1))] text-[var(--tier-regulator)]",
  unsizable: "bg-[var(--bg-2)] text-[var(--fg-3)]",
  pending: "bg-[var(--bg-2)] text-[var(--fg-3)]",
};

function StatusChip({ status }: { status: string }) {
  const cls = STATUS_STYLES[status] ?? "bg-[var(--bg-2)] text-[var(--fg-3)]";
  return (
    <span
      className={`inline-flex items-center rounded-[var(--r-1)] px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${cls}`}
    >
      {status}
    </span>
  );
}

// ── Empty / loading / error states ───────────────────────────────────────────

function EmptySync() {
  return (
    <div className="canvas-card border border-[var(--border-1)] px-5 py-6">
      <p className="text-[13px] font-medium text-[var(--fg-1)]">No primitives yet</p>
      <p className="mt-1.5 max-w-[52ch] text-[12px] leading-relaxed text-[var(--fg-3)]">
        Your private data table is empty. Sync primitives, builds, or TAMs from the CLI or an
        MCP-connected agent. The shared Strata bank is available at{" "}
        <Link href="/explore" className="text-[var(--accent)] underline-offset-2 hover:underline">
          /explore
        </Link>
        .
      </p>
      <div className="mt-4">
        <SyncHint />
      </div>
    </div>
  );
}

function SyncHint() {
  return (
    <pre
      aria-label="CLI sync example"
      className="inline-block rounded-[var(--r-2)] border border-[var(--border-1)] bg-[var(--bg-2)] px-3 py-2 font-mono text-[11px] text-[var(--fg-2)]"
    >
      {"strata portfolio import <file.yaml>"}
    </pre>
  );
}

function PrimitivesSkeleton() {
  return (
    <div className="canvas-card overflow-hidden border border-[var(--border-1)]">
      <div className="border-b border-[var(--border-1)] px-4 py-2">
        <Skeleton className="h-4 w-48" />
      </div>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="flex items-center gap-4 border-b border-[var(--border-1)] px-4 py-3 last:border-0"
        >
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="ml-auto h-4 w-16" />
          <Skeleton className="h-5 w-14" />
        </div>
      ))}
    </div>
  );
}

function ErrorCard() {
  return (
    <div className="canvas-card border border-[var(--border-1)] p-5">
      <p className="text-[13px] text-[var(--fg-3)]">Could not load primitives.</p>
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const currencyFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});

function formatTam(value: number): string {
  return currencyFmt.format(value);
}
