"use client";

import Link from "next/link";

import { Button } from "@/components/ui/Button";
import { RouteError } from "@/components/ui/RouteError";

export default function ConceptError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <RouteError
      error={error}
      reset={reset}
      label="Concept"
      notFoundAction={
        <Link href="/c">
          <Button variant="ghost" sm>
            Browse concepts
          </Button>
        </Link>
      }
    />
  );
}
