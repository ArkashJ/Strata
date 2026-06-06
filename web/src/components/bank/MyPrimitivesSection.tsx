"use client";

/**
 * MyPrimitivesSection — the personal primitive table.
 *
 * Data: myPrimitivesQuery → `GET /me/primitives`, the caller's PRIVATE,
 * tenant-isolated primitive store (server-backed via the Clerk→Principal bridge).
 * The query is resilient: signed out (401) or empty resolves to [], so we render
 * the honest "sync via CLI/MCP" empty state. We never fabricate rows.
 */

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Skeleton } from "@/components/ui/Skeleton";
import { myPrimitivesQuery } from "@/lib/queries-personal";
import type { UserPrimitive } from "@/lib/schemas";

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

function PrimitivesTable({ rows }: { rows: UserPrimitive[] }) {
  return (
    <div className="canvas-card overflow-hidden border border-[var(--border-1)]">
      <table className="w-full border-collapse text-[13px]" aria-label="My primitives">
        <thead>
          <tr className="border-b border-[var(--border-1)]">
            <Th>Name</Th>
            <Th>Slug</Th>
            <Th right>Value</Th>
            <Th>Source</Th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border-1)]">
          {rows.map((row) => (
            <PrimitiveRow key={row.id} row={row} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PrimitiveRow({ row }: { row: UserPrimitive }) {
  const { name, value, unit, source } = row.payload;
  const valueDisplay = value !== undefined ? formatValue(value, unit?.currency ?? null) : null;
  const tier = source?.tier ?? null;

  return (
    <tr className="group transition-colors hover:bg-[var(--bg-2)]">
      {/* Name */}
      <td className="px-4 py-2.5">
        <span className="font-medium text-[var(--fg-1)]">{name ?? row.slug}</span>
      </td>

      {/* Slug — the stable id of the private primitive */}
      <td className="px-4 py-2.5">
        <span className="font-mono text-[11px] text-[var(--fg-3)]">{row.slug}</span>
      </td>

      {/* Value — mono, right-aligned */}
      <td className="px-4 py-2.5 text-right">
        {valueDisplay !== null ? (
          <span className="tam-num text-[13px] text-[var(--fg-1)]">{valueDisplay}</span>
        ) : (
          <span className="tam-num text-[13px] text-[var(--fg-3)]">—</span>
        )}
      </td>

      {/* Source tier chip */}
      <td className="px-4 py-2.5">
        {tier ? <TierChip tier={tier} /> : <span className="text-[var(--fg-4)]">—</span>}
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

// Source-tier chips reuse the load-bearing tier color tokens (DESIGN.md). An
// unknown tier falls back to the neutral surface — never an invented color.
const TIER_STYLES: Record<string, string> = {
  first_party: "bg-[var(--bg-2)] text-[var(--tier-first-party,var(--fg-2))]",
  regulator: "bg-[var(--tier-regulator-tint,rgba(63,166,107,0.1))] text-[var(--tier-regulator)]",
  aggregator: "bg-[var(--bg-2)] text-[var(--tier-aggregator,var(--fg-2))]",
  analyst: "bg-[var(--bg-2)] text-[var(--tier-analyst,var(--fg-2))]",
  community: "bg-[var(--bg-2)] text-[var(--tier-community,var(--fg-3))]",
};

function TierChip({ tier }: { tier: string }) {
  const cls = TIER_STYLES[tier] ?? "bg-[var(--bg-2)] text-[var(--fg-3)]";
  return (
    <span
      className={`inline-flex items-center rounded-[var(--r-1)] px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${cls}`}
    >
      {tier.replace(/_/g, " ")}
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

const countFmt = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 1,
});

// A private primitive can carry money OR a plain count (headcount, units). Use a
// currency format only when the unit declares a currency; otherwise a compact
// count, so a "12.3M employees" row isn't mislabeled as dollars.
function formatValue(value: number, currency: string | null): string {
  if (currency) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(value);
  }
  return countFmt.format(value);
}
