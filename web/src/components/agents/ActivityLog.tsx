"use client";

import { useQuery } from "@tanstack/react-query";

import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { myAuditQuery } from "@/lib/queries-personal";
import type { AuditEvent } from "@/lib/schemas";

/**
 * Activity log surfacing agent calls (audit_events) — the bidirectional sync
 * between the user's personal bank and the shared Strata bank. Every resolve,
 * recompute, and portfolio mutation appears here, timestamped and attributed.
 *
 * Design: tabular, editorial, mono-timestamp, honest empty/error states.
 */
export function ActivityLog() {
  const q = useQuery(myAuditQuery);

  return (
    <section className="flex flex-col gap-3">
      <h2 className="display text-[20px] text-[var(--fg-1)]">Activity log</h2>
      <p className="max-w-[680px] text-[14px] text-[var(--fg-3)]">
        Every agent call — CLI resolve, recompute, portfolio sync — is logged here. This is your
        bidirectional audit trail with the shared bank.
      </p>

      <div className="mt-4">
        {q.isPending ? (
          <LogSkeleton />
        ) : q.error ? (
          <ErrorState error={q.error} onRetry={() => q.refetch()} />
        ) : !q.data || q.data.length === 0 ? (
          <EmptyState
            title="No agent activity yet"
            description="Calls via the CLI/MCP appear here — resolve markets, recompute TAMs, sync your portfolio."
          />
        ) : (
          <LogTable events={q.data} />
        )}
      </div>
    </section>
  );
}

function LogSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: 6 }, (_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: fixed-length placeholder
        <Skeleton key={i} className="h-[44px]" />
      ))}
    </div>
  );
}

function LogTable({ events }: { events: AuditEvent[] }) {
  // Sort descending (most recent first) — the backend returns them in some order;
  // on the client we ensure newest at top.
  const sorted = [...events].sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime());

  return (
    <ul
      aria-label="Agent activity log"
      className="overflow-hidden rounded-[var(--r-3)] border border-[var(--border-2)]"
    >
      {sorted.map((event) => (
        <LogRow key={event.id} event={event} />
      ))}
    </ul>
  );
}

function LogRow({ event }: { event: AuditEvent }) {
  const actionLabel = humanizeAction(event.action);
  const targetLabel = event.target ? humanizeTarget(event.action, event.target) : "—";
  const actor = event.actor ? truncateActor(event.actor) : "anon";

  // Format timestamp: ISO to readable, tabular mono.
  const ts = new Date(event.ts);
  const formattedTs = ts.toLocaleString("en-US", {
    month: "2-digit",
    day: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });

  return (
    <li className="flex min-h-[44px] items-center border-b border-[var(--border-1)] bg-[var(--bg-1)] px-4 py-2.5 last:border-b-0 hover:bg-[var(--bg-2)]">
      {/* Timestamp (mono, tabular, tertiary) */}
      <span className="w-[180px] flex-shrink-0 font-mono text-[11px] text-[var(--fg-3)] tabular-nums">
        {formattedTs}
      </span>

      {/* Action (semantic badge — warn for write, neutral for read) */}
      <div className="flex w-[100px] flex-shrink-0 items-center">
        <span
          className={`rounded-[var(--r-round)] px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-[0.06em] ${actionBadgeClass(event.action)}`}
        >
          {actionLabel}
        </span>
      </div>

      {/* Target (the slug/hash/concept being acted on; mono for hashes) */}
      <div className="flex-1 min-w-0 px-3">
        <span
          className={`truncate text-[13px] ${targetIsHash(event.target) ? "font-mono text-[var(--fg-3)]" : "text-[var(--fg-1)]"}`}
        >
          {targetLabel}
        </span>
      </div>

      {/* Actor (tertiary, right-aligned) */}
      <span className="w-[120px] flex-shrink-0 text-right font-mono text-[11px] text-[var(--fg-3)]">
        {actor}
      </span>
    </li>
  );
}

/* ──────────────────────────────────────────────────────────────────────────── */
/* Helpers                                                                      */
/* ──────────────────────────────────────────────────────────────────────────── */

function humanizeAction(action: string): string {
  const map: Record<string, string> = {
    resolve: "Resolve",
    recompute: "Recompute",
    import_portfolio: "Import",
    size_company: "Size",
    promote: "Promote",
    contribute: "Contribute",
  };
  return map[action] || action;
}

function humanizeTarget(_action: string, target: string): string {
  // Targets are slugs (concept-name, prim-name) or hashes (state-hash, tam-hash).
  // A hash is 64 hex chars; a slug is kebab-case. We trust the target as-is
  // and just truncate hashes for display.
  if (targetIsHash(target)) {
    return `${target.slice(0, 12)}…`;
  }
  return target;
}

function targetIsHash(target: string | null): boolean {
  if (!target) return false;
  // SHA256 is 64 hex chars; state hashes from /build also follow that pattern.
  return /^[a-f0-9]{64}$/i.test(target);
}

function truncateActor(actor: string): string {
  // Clerk user IDs are long; truncate to first 12 chars + ellipsis.
  if (actor.length > 12) {
    return `${actor.slice(0, 12)}…`;
  }
  return actor;
}

function actionBadgeClass(action: string): string {
  // Write actions (mutate the bank): warning semantic. Read actions: neutral.
  const writeActions = ["import_portfolio", "size_company", "promote", "contribute"];
  if (writeActions.includes(action)) {
    return "bg-[var(--warn-soft)] text-[var(--warning-ink)]";
  }
  // Read actions (resolve, recompute, etc.): neutral accent-tint
  return "bg-[var(--accent-soft)] text-[var(--accent-active)]";
}
