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
import { useEffect, useMemo, useState } from "react";

import { ResolveView } from "@/components/ResolveView";
import { BuildStudioView } from "@/components/build/BuildStudioView";
import { GraphComposer } from "@/components/build/GraphComposer";
import { MarketSpecStep } from "@/components/build/MarketSpecStep";
import { ErrorState } from "@/components/ui/ErrorState";
import {
  buildQuery,
  conceptQuery,
  conceptsQuery,
  needsRecompute,
  recomputeQuery,
} from "@/lib/queries";
import { type MarketScope, type TAMOutput, emptyMarketScope } from "@/lib/schemas";
import { type BuildState, decodeState, encodeState, isScopeEmpty } from "@/lib/state-hash";

type BuildMode = "spec" | "studio" | "graph";

const MODES: { key: BuildMode; label: string }[] = [
  { key: "spec", label: "Pin the market" },
  { key: "studio", label: "Watch it build" },
  { key: "graph", label: "Compose a graph" },
];

export function BuildView() {
  const router = useRouter();
  const params = useSearchParams();
  const query = params.get("q") ?? "";
  const rawMode = params.get("mode");
  const mode: BuildMode = rawMode === "graph" ? "graph" : rawMode === "studio" ? "studio" : "spec";

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
        // spec + studio share the MarketSpecStep gate; only the post-Size
        // destination differs (studio renders the reveal in place; spec redirects
        // to the workhorse). SpecMode owns that branch via `studio`.
        <SpecMode query={query} studio={mode === "studio"} />
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

// The ?q= spec flow. It owns its own evaluated content region (no nested <main>;
// the parent provides it). When `studio` is set, sizing renders the Build Studio
// reveal in place (the resolved TAM is held in component state) instead of
// redirecting to the workhorse — the gate is identical, only the destination
// differs. The steered tree still mints /build/<hash>?...&mode=studio from inside
// the studio, so a reload/share reproduces it.
function SpecMode({ query, studio = false }: { query: string; studio?: boolean }) {
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
  // In studio mode the resolved TAM + state are held here so the reveal renders in
  // place after Size (spec mode leaves this null and redirects instead).
  const [studioResult, setStudioResult] = useState<{ tam: TAMOutput; state: BuildState } | null>(
    null,
  );

  // Pin the market, then size. A pinned (non-empty) scope must go through
  // /build/recompute; an empty scope can read the registry default via GET
  // /build/{slug}. Studio mode holds the result in place; spec mode redirects to
  // the canonical /build/<hash>?s= (priming the cache BuildHashView reuses).
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
    // Canonicalize via the encode→decode round-trip so the held/primed state is
    // byte-identical to what BuildHashView reconstructs from ?s=.
    const state = decodeState(encodeState(draft));
    try {
      // Read the registry default when the scope is empty; recompute only when a
      // market is pinned — same contract as BuildHashView.
      const tam = needsRecompute(state)
        ? await queryClient.fetchQuery(recomputeQuery(state))
        : await queryClient.fetchQuery(buildQuery(matchedSlug));
      if (studio) {
        setStudioResult({ tam, state });
        setSizing(false);
      } else {
        router.replace(`/build/${tam.state_hash}?s=${encodeState(state)}`, {
          scroll: false,
        });
      }
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

  // Studio mode, post-Size: render the reveal in place with the resolved TAM.
  if (studio && studioResult) {
    return <BuildStudioView tam={studioResult.tam} state={studioResult.state} />;
  }

  // No concept matched — fall back to dynamic streaming resolution. The switcher
  // stays on top so the user can retarget instead of being stuck on whatever the
  // last query resolved to.
  if (!matchedSlug) {
    return (
      <div className="flex flex-1 flex-col">
        <MarketSwitcher current={query} studio={studio} />
        <ResolveView query={query} />
      </div>
    );
  }

  const conceptName = concept.data?.name ?? matchedSlug.replace(/-/g, " ");
  const initialScope = concept.data?.scope ?? emptyMarketScope();

  return (
    <div className="flex flex-1 flex-col">
      <MarketSwitcher current={conceptName} studio={studio} />
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
    </div>
  );
}

// A free-text market picker pinned above the spec form. Bare /build defaults to
// the first concept alphabetically (an empty query matches every concept name),
// which left no way to size a DIFFERENT market without going back to the home
// search. Typing here routes to /build?q=<market>: a curated market loads its
// declared scope to pin; anything else resolves live from sourced data.
function MarketSwitcher({ current, studio }: { current: string; studio: boolean }) {
  const router = useRouter();
  const [value, setValue] = useState(current);
  // Keep the input in sync when the resolved market changes without a remount
  // (same-page route to /build?q=…): useState's initializer only runs on mount.
  useEffect(() => setValue(current), [current]);

  const go = (e: React.FormEvent) => {
    e.preventDefault();
    const q = value.trim();
    if (!q) return;
    router.push(`/build?q=${encodeURIComponent(q)}${studio ? "&mode=studio" : ""}`);
  };

  return (
    <form onSubmit={go} className="mx-auto w-full max-w-[var(--content-max)] px-8 pt-6">
      <label
        htmlFor="market-switcher"
        className="text-[10px] uppercase tracking-[0.14em] text-[var(--fg-3)]"
      >
        Size a different market
      </label>
      <div className="mt-2 flex gap-2">
        <input
          id="market-switcher"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="e.g. AI coding assistants for enterprise developers US"
          className="h-10 flex-1 rounded-[var(--r-2)] border border-[var(--border-2)] bg-[var(--bg-1)] px-3 text-[14px] text-[var(--fg-1)] outline-none placeholder:text-[var(--fg-3)] focus:border-[var(--accent)]"
        />
        <button
          type="submit"
          className="h-10 shrink-0 rounded-[var(--r-2)] bg-[var(--accent)] px-4 text-[13px] font-medium text-[var(--accent-fg-on)] transition-colors hover:bg-[var(--accent-hover)]"
        >
          Size →
        </button>
      </div>
      <p className="mt-1.5 text-[11px] text-[var(--fg-3)]">
        A curated market loads its scope to pin; anything else resolves live from sourced data (with
        a "synthesized — verify before citing" banner).
      </p>
    </form>
  );
}
