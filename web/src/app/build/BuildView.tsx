"use client";

// Legacy /build?q=<query> entry. Every link into the build surface still arrives
// here with a free-text query; this view's only job is to *route* it onward:
//   • query matches a registry concept → size it, then redirect to the canonical
//     auto-mint URL /build/<state_hash>?s=<encoded BuildState> (U6). The hash is
//     the backend's evaluated-payload sha256 — the artifact address — and ?s=
//     carries the concept so the workhorse page can re-run the evaluation (the
//     backend does NOT persist TAMs, so the hash alone can't recover it).
//   • query matches nothing → stream a dynamic resolution (ResolveView).
// router.replace, not push: the ?q= URL is a transient entry point, not a state
// the user should land back on with the Back button.
import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef } from "react";

import { ResolveView } from "@/components/ResolveView";
import { buildQuery, conceptsQuery } from "@/lib/queries";
import { type BuildState, encodeState } from "@/lib/state-hash";

export function BuildView() {
	const router = useRouter();
	const params = useSearchParams();
	const query = params.get("q") ?? "";

	const concepts = useQuery(conceptsQuery);
	const q = query.toLowerCase().trim();
	const matchedSlug =
		concepts.data?.find(
			(c) =>
				c.slug === q ||
				c.name.toLowerCase().includes(q) ||
				(q.length > 0 && q.includes(c.name.toLowerCase())),
		)?.slug ?? "";

	const build = useQuery(buildQuery(matchedSlug));

	// Redirect exactly once per resolved concept. A ref guards against re-firing
	// when the query cache settles or the component re-renders mid-navigation.
	const redirected = useRef(false);
	useEffect(() => {
		if (redirected.current || !build.data) return;
		redirected.current = true;
		const tam = build.data;
		const state: BuildState = {
			target_concept_slug: matchedSlug,
			geo: tam.target.geo ?? null,
			time: tam.target.time ?? null,
			expansion_stage: tam.target.expansion_stage ?? null,
			// Empty selection = "all frameworks", the unmodified default. Diverging
			// from this is the first meaningful change the workhorse page mints on.
			frameworks_selected: [],
			framework_assumptions: {},
			primitive_pins: {},
			primitive_overrides: {},
		};
		router.replace(`/build/${tam.state_hash}?s=${encodeState(state)}`, {
			scroll: false,
		});
	}, [build.data, matchedSlug, router]);

	if (concepts.isLoading || (matchedSlug && build.isLoading) || build.data) {
		return (
			<main className="flex-1 flex items-center justify-center text-[13px] text-[var(--fg-3)]">
				Sizing…
			</main>
		);
	}

	// No concept matched (or the match failed to size) — fall back to dynamic
	// streaming resolution.
	return <ResolveView query={query} />;
}
