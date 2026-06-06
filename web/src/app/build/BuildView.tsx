"use client";

// The single build workshop. Two modes share one surface, switched by ?mode=:
//
//   • "spec" (default) — the legacy /build?q=<query> entry. Every link into the
//     build surface arrives here with a free-text query; this view routes it:
//       - query matches a registry concept → PIN THE MARKET first (sub-project
//         1.5). MarketSpecStep, prefilled from the concept's declared scope; the
//         Size button is the gate. On Size we recompute with the pinned market and
//         redirect to the canonical /build/<state_hash>?s=<encoded BuildState> (U6).
//         The hash is the backend's evaluated-payload sha256 (it folds the pinned
//         scope in, so a different market is a different URL); ?s= carries the
//         state so the workhorse page can re-run the evaluation (the backend does
//         NOT persist TAMs, so the hash alone can't recover it — the cache primed
//         by fetchQuery below makes the redirect render instantly).
//       - query matches nothing → stream a dynamic resolution (ResolveView).
//   • "graph" — the composer (formerly the standalone /build/graph route, folded
//     in per the restructure plan §2). Re-bind framework inputs to other sourced
//     primitives; the TAM recomputes live. Same recompute contract as spec mode.
//
// Both modes are one coherent workshop: a tablist switches ?mode= without losing
// the in-flight ?q=, and each mode keeps its own evaluated <main>.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { GraphComposer } from "@/components/build/GraphComposer";
import { MarketSpecStep } from "@/components/build/MarketSpecStep";
import { ResolveView } from "@/components/ResolveView";
import { ErrorState } from "@/components/ui/ErrorState";
import { conceptQuery, conceptsQuery, recomputeQuery } from "@/lib/queries";
import { emptyMarketScope, type MarketScope } from "@/lib/schemas";
import { type BuildState, decodeState, encodeState, isScopeEmpty } from "@/lib/state-hash";

type BuildMode = "spec" | "graph";

const MODES: { key: BuildMode; label: string }[] = [
  { key: "spec", label: "Pin the market" },
  { key: "graph", label: "Compose a graph" },
];

export function BuildView() {
  const router = useRouter();
  const params = useSearchParams();
  const query = params.get("q") ?? "";
  const mode: BuildMode = params.get("mode") === "graph" ? "graph" : "spec";

  // Switching mode preserves the in-flight query so a user who typed a market in
  // spec mode and flips to the composer doesn't lose their place.
  const switchMode = (next: BuildMode) => {
    const sp = new URLSearchParams(params.toString());
    if (next === "spec") sp.delete("mode");
    else sp.set("mode", next);
    const qs = sp.toString();
    router.replace(qs ? `/build?${qs}` : "/build", { scroll: false });
  };

  // Outer wrapper is a plain region, not <main>: each mode supplies its own
  // single <main> (MarketSpecStep / ResolveView / the graph composer wrapper),
  // so we never nest landmark roles.
  return (
    <div className="flex flex-1 flex-col">
      <ModeTabs mode={mode} onSwitch={switchMode} />
      {mode === "graph" ? (
        <main className="mx-auto w-full max-w-[var(--content-max)] px-8 py-8">
          <GraphComposer />
        </main>
      ) : (
        <SpecMode query={query} />
      )}
    </div>
  );
}

function ModeTabs({ mode, onSwitch }: { mode: BuildMode; onSwitch: (m: BuildMode) => void }) {
  // Switching mode is a route change (?mode=), so these are navigation controls,
  // not an ARIA tabs widget: a real tablist would promise arrow-key panel cycling
  // we don't implement. Buttons in a labelled <nav> with aria-current keep the
  // contract honest and accessible.
  return (
    <div className="border-b border-[var(--border-2)]">
      <nav
        aria-label="Build mode"
        className="mx-auto flex w-full max-w-[var(--content-max)] gap-1 px-8 pt-4"
      >
        {MODES.map((m) => {
          const active = m.key === mode;
          return (
            <button
              key={m.key}
              type="button"
              aria-current={active ? "page" : undefined}
              onClick={() => onSwitch(m.key)}
              className="relative -mb-px border-b-2 px-3 py-2 text-[13px] font-medium transition-colors hover:text-[var(--fg-1)]"
              style={{
                borderColor: active ? "var(--accent)" : "transparent",
                color: active ? "var(--fg-1)" : "var(--fg-3)",
              }}
            >
              {m.label}
            </button>
          );
        })}
      </nav>
    </div>
  );
}

// The legacy ?q= spec flow, unchanged except for living under the tablist. It owns
// its own evaluated content region (no nested <main>; the parent provides it).
function SpecMode({ query }: { query: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();

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
      <div className="flex flex-1 items-center justify-center text-[13px] text-[var(--fg-3)]">
        Loading…
      </div>
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
