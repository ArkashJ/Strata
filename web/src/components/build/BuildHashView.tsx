"use client";

// Client half of /build/[hash]. The hash segment is the auto-mint address; the
// real state rides in ?s= (the backend does NOT persist computed TAMs, so the
// hash alone can't recover the concept — /tam/{hash} 404s). We decode ?s= to a
// BuildState, re-run the concept evaluation for its TAM, then hand both to the
// workhorse view.
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { BuildWorkspace } from "@/components/build/BuildWorkspace";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { NotFoundState } from "@/components/ui/NotFoundState";
import { Skeleton } from "@/components/ui/Skeleton";
import { ApiError } from "@/lib/api-client";
import { buildQuery } from "@/lib/queries";
import { type BuildState, decodeState } from "@/lib/state-hash";

// Decode ?s= defensively — a hand-edited or truncated param must not throw past
// the error boundary, it should land on the recovery surface below.
function safeDecode(encoded: string | null): BuildState | null {
	if (!encoded) return null;
	try {
		const state = decodeState(encoded);
		if (
			typeof state.target_concept_slug !== "string" ||
			!state.target_concept_slug
		) {
			return null;
		}
		return state;
	} catch {
		return null;
	}
}

export function BuildHashView({ hash, s }: { hash: string; s: string | null }) {
	const state = safeDecode(s);
	// Disabled when state is null so we never fire a /build/ request with an empty
	// slug (which would 422 and look like a server fault rather than a missing ?s=).
	const build = useQuery(buildQuery(state?.target_concept_slug ?? ""));

	// No ?s= (or a corrupt one): the hash can't be resolved to a concept. This is
	// the backend-persistence gap, surfaced honestly rather than as a fake load.
	if (!state) {
		return (
			<Centered>
				<NotFoundState
					label="build state"
					slug={hash.slice(0, 8)}
					action={
						<Link href="/">
							<Button variant="ghost" sm>
								Start a new query
							</Button>
						</Link>
					}
				/>
			</Centered>
		);
	}

	if (build.isPending) return <LoadingShell />;

	if (build.error instanceof ApiError && build.error.status === 404) {
		return (
			<Centered>
				<NotFoundState
					label="concept"
					slug={state.target_concept_slug}
					action={
						<Link href="/">
							<Button variant="ghost" sm>
								Start a new query
							</Button>
						</Link>
					}
				/>
			</Centered>
		);
	}

	if (build.error || !build.data) {
		return (
			<Centered>
				<ErrorState
					title="Could not size this concept"
					error={build.error}
					onRetry={() => build.refetch()}
				/>
			</Centered>
		);
	}

	return <BuildWorkspace tam={build.data} state={state} />;
}

function Centered({ children }: { children: React.ReactNode }) {
	return (
		<main className="mx-auto flex w-full max-w-[var(--content-max)] flex-1 flex-col items-center justify-center px-8 py-16">
			{children}
		</main>
	);
}

function LoadingShell() {
	return (
		<main className="mx-auto flex w-full max-w-[var(--content-max)] flex-1 flex-col gap-6 px-8 py-8">
			<Skeleton className="h-4 w-48" />
			<Skeleton className="h-12 w-2/3" />
			<Skeleton className="h-5 w-64" />
			<div className="flex flex-col gap-6 lg:flex-row">
				<div className="flex flex-1 flex-col gap-6">
					<Skeleton className="h-[140px] w-full" />
					<Skeleton className="h-[520px] w-full" />
				</div>
				<Skeleton className="h-[420px] w-full lg:w-[var(--right-rail-w)]" />
			</div>
		</main>
	);
}
