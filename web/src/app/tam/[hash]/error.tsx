"use client";

// Route error boundary. A 404 from /tam/{hash} means the hash was never minted
// (no such frozen artifact) — show the dedicated not-found surface. Anything
// else (network, 5xx, schema mismatch) is a genuine error with a Retry.
import Link from "next/link";

import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { NotFoundState } from "@/components/ui/NotFoundState";
import { ApiError } from "@/lib/api-client";

export default function TamError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const isNotFound = error instanceof ApiError && error.status === 404;

  return (
    <main className="mx-auto flex w-full max-w-[var(--content-max)] flex-1 flex-col items-center justify-center px-8 py-16">
      {isNotFound ? (
        <NotFoundState
          label="TAM"
          action={
            <Link href="/browse">
              <Button variant="ghost" sm>
                Browse TAMs
              </Button>
            </Link>
          }
        />
      ) : (
        <ErrorState title="Could not load this TAM" error={error} onRetry={reset} />
      )}
    </main>
  );
}
