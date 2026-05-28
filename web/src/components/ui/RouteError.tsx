/**
 * RouteError — the body shared by every route-level error.tsx boundary. A
 * thrown ApiError with status 404 becomes a NotFoundState (unknown slug);
 * anything else is a generic ErrorState with a reset() retry. The query views
 * already handle errors inline, so this boundary mostly catches render crashes
 * and any error that escapes the query layer.
 */

"use client";

import type { ReactNode } from "react";

import { ApiError } from "@/lib/api-client";
import { ErrorState } from "./ErrorState";
import { NotFoundState } from "./NotFoundState";

export interface RouteErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
  label: string;
  notFoundAction?: ReactNode;
}

export function RouteError({ error, reset, label, notFoundAction }: RouteErrorProps) {
  if (error instanceof ApiError && error.status === 404) {
    return (
      <main className="flex-1">
        <NotFoundState label={label} action={notFoundAction} />
      </main>
    );
  }
  return (
    <main className="flex-1">
      <ErrorState error={error} onRetry={reset} />
    </main>
  );
}
