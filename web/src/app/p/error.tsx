"use client";

import Link from "next/link";

import { Button } from "@/components/ui/Button";
import { RouteError } from "@/components/ui/RouteError";

export default function PrimitiveError({
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
      label="Primitive"
      notFoundAction={
        <Link href="/p">
          <Button variant="ghost" sm>
            Browse primitives
          </Button>
        </Link>
      }
    />
  );
}
