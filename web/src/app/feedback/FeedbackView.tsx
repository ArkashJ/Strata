"use client";

/**
 * FeedbackView — the assumption-flagging triage queue (Phase F).
 *
 * Lists the org's flags (open / triaged / resolved / wontfix) and lets a
 * maintainer resolve one. Data is `feedbackQuery` → `GET /feedback`, RLS-scoped
 * server-side and resilient (a 401 / malformed response renders an honest empty
 * state, never throws). A flag is commentary on the tool, never an input to the
 * math (E1) — resolving it records a decision, it does not touch any number.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { feedbackQuery, updateFeedback } from "@/lib/queries";
import type { FeedbackEvent, FeedbackStatus } from "@/lib/schemas";

const STATUS_TABS: { label: string; value: FeedbackStatus | undefined }[] = [
  { label: "All", value: undefined },
  { label: "Open", value: "open" },
  { label: "Triaged", value: "triaged" },
  { label: "Resolved", value: "resolved" },
  { label: "Won't fix", value: "wontfix" },
];

const KIND_LABELS: Record<string, string> = {
  bad_assumption: "Bad assumption",
  failed_query: "Failed query",
  primitive_correction: "Wrong number",
  missing_data: "Missing data",
  general: "General",
};

export function FeedbackView() {
  const [status, setStatus] = useState<FeedbackStatus | undefined>(undefined);
  const { data, isPending, isError } = useQuery(feedbackQuery(status));

  return (
    <main className="mx-auto flex w-full max-w-[var(--content-max,1100px)] flex-1 flex-col gap-8 px-8 py-8">
      <header className="border-b border-[var(--border-1)] pb-6">
        <h1 className="display text-[28px] text-[var(--fg-1)]">Feedback</h1>
        <p className="mt-1.5 max-w-[62ch] text-[13px] leading-relaxed text-[var(--fg-3)]">
          Flags raised on assumptions, failed queries, wrong numbers, and missing data — by you,
          your team, or an MCP-connected agent. Constant feedback, stored, so the tool improves.
          Flags are commentary; they never change a sourced number.
        </p>
      </header>

      {/* ── Status filter ──────────────────────────────────────────────────── */}
      <nav className="flex flex-wrap gap-1.5" aria-label="Filter by status">
        {STATUS_TABS.map((tab) => {
          const active = tab.value === status;
          return (
            <button
              key={tab.label}
              type="button"
              onClick={() => setStatus(tab.value)}
              aria-pressed={active}
              className={`rounded-[var(--r-2)] px-3 py-1 text-[12px] font-medium transition-colors ${
                active
                  ? "bg-[var(--accent)] text-[var(--accent-fg-on)]"
                  : "border border-[var(--border-2)] text-[var(--fg-3)] hover:bg-[var(--bg-2)] hover:text-[var(--fg-1)]"
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </nav>

      {isPending ? (
        <ListSkeleton />
      ) : isError ? (
        <ErrorCard />
      ) : data && data.length > 0 ? (
        <ul className="flex flex-col gap-3">
          {data.map((row) => (
            <FeedbackRow key={row.id} row={row} />
          ))}
        </ul>
      ) : (
        <EmptyState />
      )}
    </main>
  );
}

// ── Row ─────────────────────────────────────────────────────────────────────

function FeedbackRow({ row }: { row: FeedbackEvent }) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (next: FeedbackStatus) => updateFeedback(row.id, { status: next }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["feedback"] }),
  });

  const created = new Date(row.created_at);

  return (
    <li className="canvas-card border border-[var(--border-1)] p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <KindChip kind={row.kind} />
            <span className="font-mono text-[11px] text-[var(--fg-4)]">
              {row.target_type}
              {row.target_id ? `:${row.target_id}` : ""}
            </span>
            <StatusChip status={row.status} />
          </div>
          <p className="mt-2 text-[13px] leading-relaxed text-[var(--fg-1)]">{row.body}</p>
          {row.query_text && (
            <p className="mt-1.5 text-[12px] italic text-[var(--fg-3)]">“{row.query_text}”</p>
          )}
          {row.resolution && (
            <p className="mt-1.5 text-[12px] text-[var(--fg-3)]">
              <span className="font-medium text-[var(--fg-2)]">Resolution:</span> {row.resolution}
            </p>
          )}
          <p className="mt-2 text-[11px] text-[var(--fg-4)]">{created.toLocaleString()}</p>
        </div>

        {/* Resolve action — only when not already terminal. */}
        {row.status !== "resolved" && row.status !== "wontfix" && (
          <Button
            variant="ghost"
            sm
            disabled={mutation.isPending}
            onClick={() => mutation.mutate("resolved")}
          >
            {mutation.isPending ? "…" : "Resolve"}
          </Button>
        )}
      </div>
    </li>
  );
}

// ── Chips ─────────────────────────────────────────────────────────────────────

function KindChip({ kind }: { kind: string }) {
  return (
    <span className="inline-flex items-center rounded-[var(--r-1)] bg-[var(--bg-2)] px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--fg-2)]">
      {KIND_LABELS[kind] ?? kind}
    </span>
  );
}

const STATUS_STYLES: Record<FeedbackStatus, string> = {
  open: "bg-[var(--bg-2)] text-[var(--fg-2)]",
  triaged: "bg-[var(--bg-2)] text-[var(--accent)]",
  resolved: "bg-[var(--tier-regulator-tint,rgba(63,166,107,0.1))] text-[var(--tier-regulator)]",
  wontfix: "bg-[var(--bg-2)] text-[var(--fg-4)]",
};

function StatusChip({ status }: { status: FeedbackStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-[var(--r-1)] px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${STATUS_STYLES[status]}`}
    >
      {status}
    </span>
  );
}

// ── Empty / loading / error ────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="canvas-card border border-[var(--border-1)] px-5 py-6">
      <p className="text-[13px] font-medium text-[var(--fg-1)]">No feedback yet</p>
      <p className="mt-1.5 max-w-[52ch] text-[12px] leading-relaxed text-[var(--fg-3)]">
        Flag a bad assumption from any TAM input or report, or submit a flag via the MCP (
        <span className="font-mono text-[11px]">submit_feedback</span>). Failed queries are captured
        automatically. Sign in to see your org's flags.
      </p>
    </div>
  );
}

function ListSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      {[0, 1, 2].map((i) => (
        <div key={i} className="canvas-card border border-[var(--border-1)] p-4">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="mt-2 h-4 w-full" />
          <Skeleton className="mt-1.5 h-3 w-24" />
        </div>
      ))}
    </div>
  );
}

function ErrorCard() {
  return (
    <div className="canvas-card border border-[var(--border-1)] p-5">
      <p className="text-[13px] text-[var(--fg-3)]">Could not load feedback.</p>
    </div>
  );
}
