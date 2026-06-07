/**
 * Error-state — a query threw (network, 5xx, schema-validation failure).
 * Shows a danger-tinted title, the error message, and an optional Retry.
 * Pass the caught `error`; we surface its message without leaking a stack.
 */

"use client";

import { ApiError } from "@/lib/api-client";
import { Button } from "./Button";

export interface ErrorStateProps {
  title?: string;
  error?: unknown;
  onRetry?: () => void;
}

// FastAPI returns a human-readable reason in `detail` (a string, or a list of
// {msg} for validation errors). Surface it instead of the bare status line.
function apiDetail(body: unknown): string | null {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      const msgs = d.map((e) => (e && typeof e === "object" && "msg" in e ? String((e as { msg: unknown }).msg) : null)).filter(Boolean);
      if (msgs.length) return msgs.join("; ");
    }
  }
  return null;
}

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = apiDetail(error.body);
    return detail ? `${detail} (${error.status})` : `${error.status} — ${error.message}`;
  }
  // A Zod schema-validation throw carries an enormous JSON message; collapse it
  // to a concise, honest note rather than dumping the issue list at the user.
  if (error instanceof Error && error.name === "ZodError") {
    return "The result came back in an unexpected shape and couldn't be displayed. This is a known data/schema mismatch, not a problem with your query.";
  }
  if (error instanceof Error) {
    return error.message;
  }
  // A plain string (some callers set error state to e.message directly).
  if (typeof error === "string" && error.trim()) {
    return error;
  }
  return "An unexpected error occurred.";
}

export function ErrorState({ title = "Something went wrong", error, onRetry }: ErrorStateProps) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center"
    >
      <p className="font-medium text-[var(--danger)] text-sm">{title}</p>
      <p className="max-w-sm text-[var(--fg-3)] text-sm">{messageFor(error)}</p>
      {onRetry ? (
        <Button variant="ghost" sm onClick={onRetry} className="mt-2">
          Retry
        </Button>
      ) : null}
    </div>
  );
}
