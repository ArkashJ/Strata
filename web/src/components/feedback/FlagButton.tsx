"use client";

/**
 * FlagButton — the inline assumption-flagging affordance (Phase F).
 *
 * Drop it next to any flaggable target (a TAM input, a primitive, a query) so a
 * user can flag a bad assumption / wrong number / missing data without leaving
 * the page. It POSTs to `/feedback` (org-scoped server-side) via `submitFeedback`
 * and, on success, invalidates the `feedback` query so the /feedback triage page
 * reflects the new row.
 *
 * A flag is commentary on the tool, never an input to the math (E1) — submitting
 * a `suggested_value` records a proposal, it does not change any sourced number.
 *
 * Reusable + props-driven: the caller supplies the target (type + id), an
 * optional default kind, and an optional query string; the component owns the
 * disclosure + form. Brand tokens only.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";

import { Button } from "@/components/ui/Button";
import { type SubmitFeedbackInput, submitFeedback } from "@/lib/queries";
import type { FeedbackKind, FeedbackTargetType } from "@/lib/schemas";

const KIND_LABELS: Record<FeedbackKind, string> = {
  bad_assumption: "Bad assumption",
  failed_query: "Failed query",
  primitive_correction: "Wrong number",
  missing_data: "Missing data",
  general: "General",
};

export interface FlagButtonProps {
  targetType: FeedbackTargetType;
  targetId?: string | null;
  /** Pre-select the kind most relevant to the surface (e.g. bad_assumption on a TAM input). */
  defaultKind?: FeedbackKind;
  /** The query that produced this surface, if any — captured for the backlog. */
  queryText?: string | null;
  /** Compact icon-only trigger for dense rows; otherwise a labelled ghost button. */
  compact?: boolean;
  className?: string;
}

export function FlagButton({
  targetType,
  targetId,
  defaultKind = "bad_assumption",
  queryText,
  compact = false,
  className = "",
}: FlagButtonProps) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<FeedbackKind>(defaultKind);
  const [body, setBody] = useState("");
  const formId = useId();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (input: SubmitFeedbackInput) => submitFeedback(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["feedback"] });
      setBody("");
      setOpen(false);
    },
  });

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    mutation.mutate({
      kind,
      target_type: targetType,
      target_id: targetId ?? null,
      query_text: queryText ?? null,
      body: body.trim(),
    });
  }

  return (
    <div className={`relative inline-block ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="true"
        title="Flag this"
        className={
          compact
            ? "inline-flex h-6 w-6 items-center justify-center rounded-[var(--r-1)] text-[var(--fg-4)] transition-colors hover:bg-[var(--bg-2)] hover:text-[var(--fg-2)]"
            : "inline-flex items-center gap-1.5 rounded-[var(--r-2)] border border-[var(--border-2)] px-2.5 py-1 text-[11px] font-medium text-[var(--fg-3)] transition-colors hover:bg-[var(--bg-2)] hover:text-[var(--fg-1)]"
        }
      >
        <FlagIcon />
        {!compact && <span>Flag</span>}
      </button>

      {open && (
        <div
          aria-label="Flag this"
          className="canvas-card absolute right-0 z-20 mt-2 w-[300px] border border-[var(--border-1)] p-3 shadow-lg"
        >
          <form onSubmit={onSubmit} className="flex flex-col gap-2.5">
            <label
              htmlFor={`${formId}-kind`}
              className="text-[10px] font-medium uppercase tracking-[0.08em] text-[var(--fg-4)]"
            >
              What's wrong?
            </label>
            <select
              id={`${formId}-kind`}
              value={kind}
              onChange={(e) => setKind(e.target.value as FeedbackKind)}
              className="rounded-[var(--r-2)] border border-[var(--border-2)] bg-[var(--bg-1)] px-2 py-1.5 text-[12px] text-[var(--fg-1)]"
            >
              {(Object.keys(KIND_LABELS) as FeedbackKind[]).map((k) => (
                <option key={k} value={k}>
                  {KIND_LABELS[k]}
                </option>
              ))}
            </select>

            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              required
              rows={3}
              placeholder="Describe the problem (e.g. the adoption rate looks aggressive)…"
              className="resize-none rounded-[var(--r-2)] border border-[var(--border-2)] bg-[var(--bg-1)] px-2 py-1.5 text-[12px] text-[var(--fg-1)] placeholder:text-[var(--fg-4)]"
            />

            {mutation.isError && (
              <p className="text-[11px] text-[var(--danger,#d1453b)]">
                Could not submit — you may need to sign in.
              </p>
            )}

            <div className="flex items-center justify-end gap-2">
              <Button variant="ghost" sm onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" sm disabled={mutation.isPending || !body.trim()}>
                {mutation.isPending ? "Sending…" : "Submit flag"}
              </Button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

function FlagIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" />
      <line x1="4" y1="22" x2="4" y2="15" />
    </svg>
  );
}
