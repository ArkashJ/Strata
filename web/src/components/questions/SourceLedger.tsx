"use client";

// The competing-measurements ledger — every distinct sourced primitive behind
// the answered figures, listed ONCE as an analyst table instead of being
// reprinted on every card. This is the provenance the whole report rests on:
// source, tier (colour = tier, the load-bearing contract), as-of date, and an
// HONEST pin status (a demo sentinel reads "not pinned (demo)", never a fake
// green check). Tier hue is the only colour; nothing here implies a value.
//
// App-specific by design: depends on the app design tokens.

import Link from "next/link";

import { tierColor } from "@/lib/chart-colors";
import { formatSnapshot, isPlaceholderSnapshot, tierLabel } from "@/lib/format";
import type { LedgerRow } from "@/lib/report-metrics";

export function SourceLedger({
  rows,
  className,
}: {
  rows: readonly LedgerRow[];
  className?: string;
}) {
  if (rows.length === 0) return null;

  return (
    <div className={className}>
      <div className="overflow-hidden rounded-[var(--r-3)] border border-[var(--border-1)]">
        {/* Header */}
        <div className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-x-4 border-b border-[var(--border-1)] bg-[var(--bg-2)] px-4 py-2 font-mono text-[10px] uppercase tracking-[0.08em] text-[var(--fg-3)]">
          <span>Source primitive</span>
          <span>Tier</span>
          <span className="text-right">As of</span>
          <span className="text-right">Pin</span>
        </div>
        {rows.map((r, i) => {
          const placeholder = isPlaceholderSnapshot(r.snapshot_sha256);
          const slug = (
            <span className="truncate font-mono text-[12px] text-[var(--fg-1)]">
              {r.primitive_slug}
            </span>
          );
          return (
            <div
              key={r.primitive_slug}
              className={`grid grid-cols-[1fr_auto_auto_auto] items-center gap-x-4 px-4 py-2.5 ${
                i > 0 ? "border-t border-[var(--border-1)]" : ""
              }`}
            >
              {r.source_url ? (
                <Link
                  href={r.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="min-w-0 truncate decoration-dotted underline-offset-2 hover:underline"
                >
                  {slug}
                </Link>
              ) : (
                <span className="min-w-0">{slug}</span>
              )}

              {r.source_tier ? (
                <span
                  className="justify-self-start whitespace-nowrap rounded-full px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide"
                  style={{
                    color: tierColor(r.source_tier),
                    backgroundColor: `color-mix(in srgb, ${tierColor(r.source_tier)} 14%, transparent)`,
                  }}
                >
                  {tierLabel(r.source_tier)}
                </span>
              ) : (
                <span className="justify-self-start font-mono text-[10px] uppercase tracking-wide text-[var(--fg-4)]">
                  Composite
                </span>
              )}

              <span className="text-right font-mono text-[11px] tabular-nums text-[var(--fg-3)]">
                {r.as_of ?? "—"}
              </span>

              <span
                className={`text-right font-mono text-[11px] ${
                  placeholder ? "text-[var(--warning)]" : "text-[var(--fg-3)]"
                }`}
              >
                {formatSnapshot(r.snapshot_sha256)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
