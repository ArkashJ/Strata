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

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.status} — ${error.message}`;
  }
  if (error instanceof Error) {
    return error.message;
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
