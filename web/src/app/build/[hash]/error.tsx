"use client";

// Route error boundary for /build/[hash]. A 404 means the concept the ?s= state
// points at doesn't exist; anything else (network, 5xx, schema mismatch) is a
// genuine error with a Retry. The "no ?s=" recovery case is handled inside the
// view (it's not an error — just an unresolvable hash), so it never reaches here.
import Link from "next/link";

import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { NotFoundState } from "@/components/ui/NotFoundState";
import { ApiError } from "@/lib/api-client";

export default function BuildHashError({
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
					label="concept"
					action={
						<Link href="/">
							<Button variant="ghost" sm>
								Start a new query
							</Button>
						</Link>
					}
				/>
			) : (
				<ErrorState
					title="Could not load this build"
					error={error}
					onRetry={reset}
				/>
			)}
		</main>
	);
}
