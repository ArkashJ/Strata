"use client";

/**
 * ActivitySection — the personal activity log under My Bank.
 *
 * Uses myAuditQuery from lib/queries-personal — the server-backed, RLS-scoped
 * `GET /me/audit` that returns ONLY the caller's own events. It is resilient:
 * a 401 (signed out) or any error resolves to [] rather than throwing, so the
 * Bank page renders an honest empty state instead of erroring out.
 */

import { useQuery } from "@tanstack/react-query";

import { Skeleton } from "@/components/ui/Skeleton";
import { myAuditQuery } from "@/lib/queries-personal";
import type { AuditEvent } from "@/lib/schemas";

// ── Section ───────────────────────────────────────────────────────────────────

export function ActivitySection() {
  const { data, isPending } = useQuery(myAuditQuery);

  return (
    <section aria-labelledby="bank-activity-heading">
      <h2
        id="bank-activity-heading"
        className="mb-3 text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--fg-4)]"
      >
        Activity
      </h2>

      {isPending ? (
        <ActivitySkeleton />
      ) : data && data.length > 0 ? (
        <ul className="canvas-card divide-y divide-[var(--border-1)] overflow-hidden border border-[var(--border-1)]">
          {data.map((ev) => (
            <ActivityRow key={ev.id} ev={ev} />
          ))}
        </ul>
      ) : (
        <div className="canvas-card border border-[var(--border-1)] p-5">
          <p className="text-[13px] text-[var(--fg-3)]">No activity yet.</p>
          <p className="mt-1 text-[12px] text-[var(--fg-3)]">
            Resolve or build a market to see your activity log here.
          </p>
        </div>
      )}
    </section>
  );
}

// ── Row ───────────────────────────────────────────────────────────────────────

function ActivityRow({ ev }: { ev: AuditEvent }) {
  return (
    <li className="flex items-center gap-2 px-3 py-2.5 text-[12px]">
      <span className="shrink-0 font-mono text-[var(--fg-2)]">{ev.actor ?? "anon"}</span>
      <span className="shrink-0 rounded-[var(--r-1)] bg-[var(--bg-2)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--fg-1)]">
        {ev.action}
      </span>
      {ev.target && <span className="min-w-0 flex-1 truncate text-[var(--fg-3)]">{ev.target}</span>}
      <span className="ml-auto shrink-0 font-mono text-[11px] text-[var(--fg-4)]">
        {relativeTime(ev.ts)}
      </span>
    </li>
  );
}

// ── Loading state ─────────────────────────────────────────────────────────────

function ActivitySkeleton() {
  return (
    <div className="canvas-card overflow-hidden border border-[var(--border-1)]">
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          className="flex items-center gap-3 border-b border-[var(--border-1)] px-3 py-2.5 last:border-0"
        >
          <Skeleton className="h-3.5 w-20" />
          <Skeleton className="h-5 w-16 rounded-[var(--r-1)]" />
          <Skeleton className="h-3.5 flex-1" />
          <Skeleton className="ml-auto h-3.5 w-12" />
        </div>
      ))}
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
const DIVISIONS: { amount: number; unit: Intl.RelativeTimeFormatUnit }[] = [
  { amount: 60, unit: "second" },
  { amount: 60, unit: "minute" },
  { amount: 24, unit: "hour" },
  { amount: 7, unit: "day" },
  { amount: 4.34524, unit: "week" },
  { amount: 12, unit: "month" },
  { amount: Number.POSITIVE_INFINITY, unit: "year" },
];

function relativeTime(input: number | string): string {
  const normalized =
    typeof input === "string" && !/[Z+]|-\d\d:\d\d$/.test(input) ? `${input}Z` : input;
  const ms = typeof normalized === "number" ? normalized : Date.parse(normalized);
  if (!Number.isFinite(ms)) return "";
  let duration = (ms - Date.now()) / 1000;
  for (const div of DIVISIONS) {
    if (Math.abs(duration) < div.amount) {
      return rtf.format(Math.round(duration), div.unit);
    }
    duration /= div.amount;
  }
  return "";
}
