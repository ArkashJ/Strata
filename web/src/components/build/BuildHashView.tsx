"use client";

// Client half of /build/[hash]. The hash segment is the auto-mint address; the
// real state rides in ?s= (the backend does NOT persist computed TAMs, so the
// hash alone can't recover the concept — /tam/{hash} 404s). We decode ?s= to a
// BuildState, re-run the concept evaluation for its TAM, then hand both to the
// workhorse view.
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect } from "react";

import { BuildWorkspace } from "@/components/build/BuildWorkspace";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { NotFoundState } from "@/components/ui/NotFoundState";
import { Skeleton } from "@/components/ui/Skeleton";
import { ApiError } from "@/lib/api-client";
import { recordBuildVisit } from "@/lib/build-history";
import { buildQuery, needsRecompute, recomputeQuery } from "@/lib/queries";
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

// A neutral state for the recompute hook when ?s= is missing/corrupt — keeps the
// hook order stable while staying disabled (empty slug + no overrides).
const EMPTY_STATE: BuildState = {
	target_concept_slug: "",
	frameworks_selected: [],
	framework_assumptions: {},
	primitive_pins: {},
	primitive_overrides: {},
};

export function BuildHashView({ hash, s }: { hash: string; s: string | null }) {
	const state = safeDecode(s);
	const slug = state?.target_concept_slug ?? "";
	// When the user has diverged — a what-if scalar, a primitive swap, or a pinned
	// market — the TAM must be recomputed server-side; otherwise the registry
	// default GET suffices. Both hooks always run (stable order); enabled flags
	// pick exactly one.
	const recomputing = state ? needsRecompute(state) : false;
	const build = useQuery({
		...buildQuery(slug),
		enabled: !!slug && !recomputing,
	});
	const recompute = useQuery(recomputeQuery(state ?? EMPTY_STATE));
	const active = recomputing ? recompute : build;

	// Remember this build so it surfaces under "Your builds" on /dashboard. The
	// backend doesn't persist TAMs, so we keep the hash + encoded state locally;
	// recording on successful resolve (not on mount) avoids saving dead links.
	const resolvedName = active.data?.target.concept_name ?? slug;
	useEffect(() => {
		if (!state || !active.data || !s) return;
		recordBuildVisit({
			hash,
			encoded: s,
			label: resolvedName,
			conceptSlug: slug,
		});
		// `state` is intentionally excluded — it's a fresh object each render
		// (safeDecode(s)); `s` already captures the only meaningful change.
	}, [hash, s, slug, resolvedName, active.data]);

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

	if (active.isPending) return <LoadingShell />;

	if (active.error instanceof ApiError && active.error.status === 404) {
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

	if (active.error || !active.data) {
		return (
			<Centered>
				<ErrorState
					title={recomputing ? "Could not recompute with your overrides" : "Could not size this concept"}
					error={active.error}
					onRetry={() => active.refetch()}
				/>
			</Centered>
		);
	}

	return <BuildWorkspace tam={active.data} state={state} recomputing={active.isFetching} />;
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
