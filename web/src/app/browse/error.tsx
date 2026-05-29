"use client";

import Link from "next/link";

import { Button } from "@/components/ui/Button";
import { RouteError } from "@/components/ui/RouteError";

export default function BrowseError({
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
      label="Registry"
      notFoundAction={
        <Link href="/">
          <Button variant="ghost" sm>
            Back to search
          </Button>
        </Link>
      }
    />
  );
}
