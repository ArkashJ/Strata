"use client";

// SourceAppendixTable — the "every figure named + dated + tiered + pinned"
// appendix that makes a report defensible in IC. One row per sourced input:
// the figure (linked to its source via SourcedNumber), the tier badge, the
// snapshot pin (rendered honestly — "not pinned (demo)" for the placeholder
// sentinel, never a fake green check), and the source link.
//
// Tier badges wear the tier ramp (provenance). Composite inputs (no single
// source) read as "composite", not a fabricated tier.

import { SourcedNumber } from "@/components/ui/SourcedNumber";
import { TierBadge } from "@/components/ui/TierBadge";
import { formatSnapshot } from "@/lib/format";
import type { InputUsed, SourceTier } from "@/lib/schemas";

export interface AppendixRow extends InputUsed {
  // as_of date string for the "dated" column, when the evaluator supplied it.
  as_of?: string | null;
}

export function SourceAppendixTable({
  rows,
  headline = "Sources & methodology appendix",
  className,
}: {
  rows: AppendixRow[];
  headline?: string;
  className?: string;
}) {
  if (rows.length === 0) {
    return (
      <div className={`text-[13px] text-[var(--fg-3)] ${className ?? ""}`}>
        No sourced inputs to list.
      </div>
    );
  }

  return (
    <section className={className}>
      <h2 className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--fg-2)]">
        {headline}
      </h2>
      <div className="mt-3 overflow-hidden rounded-[var(--r-3)] border border-[var(--border-1)]">
        <table className="w-full text-left text-[12px]">
          <thead>
            <tr className="border-b border-[var(--border-1)] text-[10px] uppercase tracking-wide text-[var(--fg-3)]">
              <th className="px-3 py-2 font-medium">Figure</th>
              <th className="px-3 py-2 font-medium">Value</th>
              <th className="px-3 py-2 font-medium">Tier</th>
              <th className="px-3 py-2 font-medium">As of</th>
              <th className="px-3 py-2 font-medium">Snapshot</th>
              <th className="px-3 py-2 font-medium">Source</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((iu) => {
              const year = iu.as_of ? new Date(iu.as_of).getFullYear() : null;
              return (
                <tr
                  key={iu.primitive_slug}
                  className="border-b border-[var(--border-1)] align-top last:border-0"
                >
                  <td className="px-3 py-2 text-[var(--fg-1)]">{iu.name ?? iu.primitive_slug}</td>
                  <td className="px-3 py-2 text-[var(--fg-2)]">
                    <SourcedNumber input={iu} />
                  </td>
                  <td className="px-3 py-2">
                    {iu.source_tier ? (
                      <TierBadge tier={iu.source_tier as SourceTier} />
                    ) : (
                      <span className="text-[var(--fg-3)]">composite</span>
                    )}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-[var(--fg-3)]">
                    {year && !Number.isNaN(year) ? year : "—"}
                  </td>
                  <td className="px-3 py-2 font-mono text-[10px] text-[var(--fg-3)]">
                    {formatSnapshot(iu.snapshot_sha256)}
                  </td>
                  <td className="px-3 py-2">
                    {iu.source_url ? (
                      <a
                        href={iu.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[var(--accent)] underline decoration-dotted underline-offset-2"
                      >
                        link
                      </a>
                    ) : (
                      <span className="text-[var(--fg-4)]">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
