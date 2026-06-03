"use client";

// Legacy /build?q=<query> entry. Every link into the build surface still arrives
// here with a free-text query; this view routes it onward:
//   • query matches a registry concept → PIN THE MARKET first (sub-project 1.5).
//     We render MarketSpecStep prefilled from the concept's declared scope; the
//     Size button is the gate. On Size we recompute with the pinned market and
//     redirect to the canonical /build/<state_hash>?s=<encoded BuildState> (U6).
//     The hash is the backend's evaluated-payload sha256 (it folds the pinned
//     scope in, so a different market is a different URL); ?s= carries the state
//     so the workhorse page can re-run the evaluation (the backend does NOT
//     persist TAMs, so the hash alone can't recover it — the cache primed by
//     fetchQuery below makes the redirect render instantly).
//   • query matches nothing → stream a dynamic resolution (ResolveView).
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { MarketSpecStep } from "@/components/build/MarketSpecStep";
import { ResolveView } from "@/components/ResolveView";
import { ErrorState } from "@/components/ui/ErrorState";
import { conceptQuery, conceptsQuery, recomputeQuery } from "@/lib/queries";
import { emptyMarketScope, type MarketScope } from "@/lib/schemas";
import { type BuildState, decodeState, encodeState, isScopeEmpty } from "@/lib/state-hash";

export function BuildView() {
	const router = useRouter();
	const queryClient = useQueryClient();
	const params = useSearchParams();
	const query = params.get("q") ?? "";

	const concepts = useQuery(conceptsQuery);
	const q = query.toLowerCase().trim();
	const matchedSlug = useMemo(
		() =>
			concepts.data?.find(
				(c) =>
					c.slug === q ||
					c.name.toLowerCase().includes(q) ||
					(q.length > 0 && q.includes(c.name.toLowerCase())),
			)?.slug ?? "",
		[concepts.data, q],
	);

	// Prefill the market-spec chips from the matched concept's declared scope.
	const concept = useQuery(conceptQuery(matchedSlug));

	const [sizing, setSizing] = useState(false);
	const [error, setError] = useState<string | null>(null);

	// Pin the market, then size: recompute with the chosen scope (priming the
	// cache under the key BuildHashView will reuse) and redirect to its hash.
	const onSize = async (scope: MarketScope) => {
		setSizing(true);
		setError(null);
		const draft: BuildState = {
			target_concept_slug: matchedSlug,
			// The user's pinned geo wins over the concept's default — they may have
			// edited it in the form before sizing.
			geo: scope.geo_demand[0] ?? concept.data?.scope?.geo_demand?.[0] ?? null,
			time: null,
			expansion_stage: null,
			frameworks_selected: [],
			framework_assumptions: {},
			primitive_pins: {},
			primitive_overrides: {},
			scope: isScopeEmpty(scope) ? null : scope,
		};
		// Prime the cache under the *canonical* state (sorted scope), which is exactly
		// what BuildHashView reconstructs from ?s= — so its useQuery hits this entry
		// instead of firing a second recompute. The encoded URL is identical either
		// way (encodeState is canonical), so the redirect address is unchanged.
		const state = decodeState(encodeState(draft));
		try {
			const tam = await queryClient.fetchQuery(recomputeQuery(state));
			router.replace(`/build/${tam.state_hash}?s=${encodeState(state)}`, {
				scroll: false,
			});
		} catch (e) {
			setError(e instanceof Error ? e.message : "Could not size this market.");
			setSizing(false);
		}
	};

	if (concepts.isLoading || (matchedSlug && concept.isLoading)) {
		return (
			<main className="flex-1 flex items-center justify-center text-[13px] text-[var(--fg-3)]">
				Loading…
			</main>
		);
	}

	// No concept matched — fall back to dynamic streaming resolution.
	if (!matchedSlug) {
		return <ResolveView query={query} />;
	}

	const conceptName = concept.data?.name ?? matchedSlug.replace(/-/g, " ");
	const initialScope = concept.data?.scope ?? emptyMarketScope();

	return (
		<>
			{error ? (
				<div className="mx-auto w-full max-w-[var(--content-max)] px-8 pt-6">
					<ErrorState
						title="Could not size this market"
						error={error}
						onRetry={() => setError(null)}
					/>
				</div>
			) : null}
			<MarketSpecStep
				conceptName={conceptName}
				initialScope={initialScope}
				onSize={onSize}
				sizing={sizing}
			/>
		</>
	);
}
