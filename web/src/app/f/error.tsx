"use client";

import Link from "next/link";

import { Button } from "@/components/ui/Button";
import { RouteError } from "@/components/ui/RouteError";

export default function FrameworkError({
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
      label="Framework"
      notFoundAction={
        <Link href="/f">
          <Button variant="ghost" sm>
            Browse frameworks
          </Button>
        </Link>
      }
    />
  );
}
