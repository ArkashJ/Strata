"use client";

// BuildStudioView — the "watch it build" surface (?mode=studio · DIAGRAMS flow 31).
//
// The same finished TAM the workhorse renders, played back apex → frameworks →
// role leaves so a viewer SEES the market size assemble from sourced primitives.
// The reveal is a cursor over the pure step list (deriveBuildSteps); the staged
// build and the finished tree are the SAME artifact at cursor=0 vs cursor=last,
// so nothing new is persisted — the steered tree round-trips through BuildState
// (?s=) + /build/<hash> exactly like the workhorse.
//
// #107 — never theater. Three hard guarantees:
//   1. prefers-reduced-motion → NO timer is ever created; the full tree shows on
//      the first frame, the headline reads the final value instantly. The single
//      crossfade is gated off. (useReducedMotion drives this.)
//   2. once the user is steering (a what-if / swap / pinned scope is in play) the
//      staged reveal is skipped too — edits must be honest and instant, so the
//      whole tree shows and the recompute resumes at the edited node.
//   3. an aria-live region speaks every reveal + the running market size, so AT
//      users perceive the build without seeing the animation.
//
//        recompute payload (one fetch) ──▶ deriveBuildSteps ──▶ cursor over steps
//          ▲ steer (what-if/swap)                                   │
//          └──────────────── mint(next BuildState) ◀────────────────┘ (replays)

import { useReducedMotion } from "motion/react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";

import { BuildStudioGraph } from "@/components/build/BuildStudioGraph";
import { LensPicker, suggestPrimaryLens } from "@/components/build/LensPicker";
import { OverridePanel } from "@/components/build/OverridePanel";
import { StudioStepRail } from "@/components/build/StudioStepRail";
import { CountUp, Pulse } from "@/components/ui/motion";
import { type BuildStep, deriveBuildSteps, stepIndexForRole } from "@/lib/build-studio";
import { formatCompact } from "@/lib/format";
import { needsRecompute } from "@/lib/queries";
import type { AnalysisLens, InputUsed, TAMOutput, Unit } from "@/lib/schemas";
import { type BuildState, encodeState, hashState } from "@/lib/state-hash";

const REVEAL_MS = 420;

// ── reducer ───────────────────────────────────────────────────────────────────

interface StudioState {
  steps: BuildStep[];
  cursor: number;
  // True once any steer has happened — flips the reveal to instant (no theater).
  hasEdited: boolean;
  editing: { input: InputUsed; frameworkSlug: string } | null;
}

type StudioAction =
  // Recompute landed (or first mount): rebuild the step list. `resumeAt` is the
  // cursor to start from — steps.length when instant, 1 (apex only) when staged.
  | { type: "SET_STEPS"; steps: BuildStep[]; resumeAt: number; edited: boolean }
  | { type: "REVEAL_NEXT" }
  | { type: "REVEAL_ALL" }
  | { type: "EDIT_OPEN"; input: InputUsed; frameworkSlug: string }
  | { type: "EDIT_CLOSE" };

function reducer(state: StudioState, action: StudioAction): StudioState {
  switch (action.type) {
    case "SET_STEPS":
      return {
        ...state,
        steps: action.steps,
        cursor: Math.min(action.resumeAt, action.steps.length),
        hasEdited: state.hasEdited || action.edited,
      };
    case "REVEAL_NEXT":
      return state.cursor >= state.steps.length ? state : { ...state, cursor: state.cursor + 1 };
    case "REVEAL_ALL":
      return { ...state, cursor: state.steps.length };
    case "EDIT_OPEN":
      return { ...state, editing: { input: action.input, frameworkSlug: action.frameworkSlug } };
    case "EDIT_CLOSE":
      return { ...state, editing: null };
  }
}

// ── view ────────────────────────────────────────────────────────────────────

export interface BuildStudioViewProps {
  // The resolved TAM for the pinned market (from the recompute cache primed by
  // BuildView.SpecMode, or the registry default). Never persisted server-side.
  tam: TAMOutput;
  // The reconstructed BuildState (target concept + pinned scope + any overrides).
  state: BuildState;
  // True while a steer-recompute is in flight (drives the headline affordance +
  // the aria-live "recomputing" announcement).
  recomputing?: boolean;
}

export function BuildStudioView({ tam, state, recomputing = false }: BuildStudioViewProps) {
  const router = useRouter();
  const reduce = useReducedMotion();

  // The lens being revealed. Auto-suggested from the richest available lens, then
  // user-confirmable via the picker (honest gating lives in LensPicker).
  const [lens, setLens] = useState<AnalysisLens>(
    () => suggestPrimaryLens(tam) ?? tam.scenarios[0].lens,
  );

  // The steered state is the source of truth: once the user has a what-if / swap /
  // pinned scope, the reveal is instant (no theater). We also go instant under
  // reduced motion. `entrySteering` is captured per (tam,lens) recompute.
  const steering = needsRecompute(state);

  const steps = useMemo(() => deriveBuildSteps(tam, lens, state), [tam, lens, state]);

  const [studio, dispatch] = useReducer(reducer, undefined, () => ({
    steps,
    // apex shown on the first frame (never a blank canvas); full tree when instant.
    cursor: reduce || steering ? steps.length : Math.min(1, steps.length),
    hasEdited: steering,
    editing: null,
  }));

  // Recompute / lens change landed → rebuild the step list. Resume at the edited
  // role when steering (so a steer never rewinds the reveal before its edit),
  // else replay from the apex (or jump to the end under reduced motion).
  const lastEditedSlug = useRef<string | null>(null);
  useEffect(() => {
    const instant = reduce || studio.hasEdited || steering;
    const resumeAt = instant ? steps.length : Math.min(1, steps.length);
    // When a steer just landed, resume the staged reveal at the edited node rather
    // than the end — but only when NOT instant (instant always shows the whole
    // tree). Under our rules a steer forces instant, so this is the resume hook
    // for any future "staged after edit" mode; today it collapses to steps.length.
    const at =
      lastEditedSlug.current && !instant
        ? stepIndexForRole(steps, lastEditedSlug.current)
        : resumeAt;
    dispatch({ type: "SET_STEPS", steps, resumeAt: at, edited: steering });
    lastEditedSlug.current = null;
  }, [steps, reduce, steering, studio.hasEdited]);

  // The reveal timer: advance the cursor every REVEAL_MS until the tree is whole,
  // then stop. SKIPPED entirely when instant (reduced-motion or steering) — no
  // interval is ever created in that branch (the #107 instant path).
  const instant = reduce || studio.hasEdited || steering;
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    if (instant || paused) return;
    if (studio.cursor >= studio.steps.length) return;
    const id = setInterval(() => dispatch({ type: "REVEAL_NEXT" }), REVEAL_MS);
    return () => clearInterval(id);
  }, [instant, paused, studio.cursor, studio.steps.length]);

  // mint(next): the shared workhorse contract — hash the steered state, replace the
  // URL in place. The /build/[hash] page re-runs the recompute and re-enters here.
  const mint = useCallback(
    async (next: BuildState) => {
      const hash = await hashState(next);
      router.replace(`/build/${hash}?s=${encodeState(next)}&mode=studio`, { scroll: false });
    },
    [router],
  );

  const onEditPrimitive = useCallback(
    (input: InputUsed, frameworkSlug: string) =>
      dispatch({ type: "EDIT_OPEN", input, frameworkSlug }),
    [],
  );

  const applyWhatIf = useCallback(
    (input: InputUsed, value: number, unit: Unit) => {
      lastEditedSlug.current = input.primitive_slug;
      void mint({
        ...state,
        primitive_overrides: {
          ...state.primitive_overrides,
          [input.primitive_slug]: { value, unit },
        },
      });
      dispatch({ type: "EDIT_CLOSE" });
    },
    [state, mint],
  );

  const applySwap = useCallback(
    (input: InputUsed, frameworkSlug: string, primitiveSlug: string) => {
      lastEditedSlug.current = primitiveSlug;
      const fa = state.framework_assumptions ?? {};
      void mint({
        ...state,
        framework_assumptions: {
          ...fa,
          [frameworkSlug]: { ...(fa[frameworkSlug] ?? {}), [input.role_name]: primitiveSlug },
        },
      });
      dispatch({ type: "EDIT_CLOSE" });
    },
    [state, mint],
  );

  const clearOverride = useCallback(
    (input: InputUsed, frameworkSlug: string) => {
      const overrides = { ...(state.primitive_overrides ?? {}) };
      delete overrides[input.primitive_slug];
      const fa = { ...(state.framework_assumptions ?? {}) };
      if (fa[frameworkSlug]) {
        const inner = { ...fa[frameworkSlug] };
        delete inner[input.role_name];
        if (Object.keys(inner).length === 0) delete fa[frameworkSlug];
        else fa[frameworkSlug] = inner;
      }
      void mint({ ...state, primitive_overrides: overrides, framework_assumptions: fa });
      dispatch({ type: "EDIT_CLOSE" });
    },
    [state, mint],
  );

  // Accent any node the user has touched — mirrors BuildWorkspace's derivation so
  // a what-if (keyed by original slug) and a swap (keyed by target slug) both light.
  const overriddenSlugs = useMemo(() => {
    const slugs = new Set(Object.keys(state.primitive_overrides ?? {}));
    for (const roles of Object.values(state.framework_assumptions ?? {})) {
      for (const targetSlug of Object.values(roles)) slugs.add(targetSlug);
    }
    return slugs;
  }, [state.primitive_overrides, state.framework_assumptions]);

  // The set of revealed node ids the graph slices against.
  const revealedIds = useMemo(
    () => new Set(studio.steps.slice(0, studio.cursor).map((s) => s.id)),
    [studio.steps, studio.cursor],
  );
  const frontier = studio.cursor > 0 ? studio.steps[studio.cursor - 1] : null;
  const complete = studio.cursor >= studio.steps.length;

  // The headline number is the frontier step's running value — the partial market
  // size as the chain assembles, the final TAM once complete.
  const headlineValue = frontier?.runningValue ?? studio.steps[0]?.runningValue ?? 0;
  const headlineUnit = frontier?.unit ?? studio.steps[0]?.unit ?? tam.scenarios[0].unit;

  const [shared, setShared] = useState(false);
  const onShare = useCallback(() => {
    if (typeof window === "undefined") return;
    navigator.clipboard
      .writeText(window.location.href)
      .then(() => {
        setShared(true);
        setTimeout(() => setShared(false), 1500);
      })
      .catch(() => {});
  }, []);

  const industry = tam.target.concept_name ?? tam.target.concept.replace(/-/g, " ");

  return (
    <main className="mx-auto flex w-full max-w-[var(--content-max)] flex-1 flex-col px-8 py-8">
      <header className="flex flex-col gap-3">
        <div className="text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
          Build studio · watch it size
        </div>
        <h1 className="display text-[40px] capitalize leading-[1.05] text-[var(--fg-1)]">
          {industry}
        </h1>
        <div className="flex flex-wrap items-center gap-4">
          <LensPicker tam={tam} value={lens} onChange={setLens} />
        </div>
      </header>

      {/* Running headline — CountUp speaks the partial market size as the chain
          assembles. Pulse-rings on each frontier change; both no-op under reduced
          motion, so the value shows final + static instantly. */}
      <div className="mt-6 canvas-card flex flex-col gap-1 p-6">
        <span className="text-[11px] uppercase tracking-[0.06em] text-[var(--fg-3)]">
          {complete ? "Market size" : "Building market size"}
        </span>
        <Pulse pulseKey={frontier?.id ?? "init"} className="tam-num inline-block">
          <CountUp
            value={headlineValue}
            format={(n) => formatCompact(n, headlineUnit)}
            className="text-[44px] leading-[1] text-[var(--fg-1)]"
          />
        </Pulse>
        {/* The only channel AT users have for the staged build: announce each
            reveal + the running value, debounced to the cursor (not per frame). */}
        <span className="sr-only" aria-live="polite">
          {recomputing
            ? "Recomputing market size"
            : frontier
              ? `Added ${frontier.label} — running market size ${formatCompact(headlineValue, headlineUnit)}.`
              : `Market size ${formatCompact(headlineValue, headlineUnit)}.`}
        </span>
      </div>

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <section className="flex min-w-0 flex-1 flex-col gap-6">
          {/* Pause the reveal while the pointer/focus rests inside the graph, so a
              reader isn't rushed past a node they're inspecting. No effect when
              instant (no timer exists). */}
          <div
            onMouseEnter={() => setPaused(true)}
            onMouseLeave={() => setPaused(false)}
            onFocusCapture={() => setPaused(true)}
            onBlurCapture={() => setPaused(false)}
          >
            <BuildStudioGraph
              tam={tam}
              revealedIds={revealedIds}
              frontierId={frontier?.id ?? null}
              onEditPrimitive={onEditPrimitive}
              overriddenSlugs={overriddenSlugs}
            />
          </div>
        </section>

        <StudioStepRail
          steps={studio.steps}
          cursor={studio.cursor}
          complete={complete}
          onRevealAll={() => dispatch({ type: "REVEAL_ALL" })}
          onShare={onShare}
          shared={shared}
        />
      </div>

      {studio.editing ? (
        <OverridePanel
          input={studio.editing.input}
          frameworkSlug={studio.editing.frameworkSlug}
          conceptSlug={state.target_concept_slug}
          currentOverride={state.primitive_overrides?.[studio.editing.input.primitive_slug]?.value}
          currentSwap={
            state.framework_assumptions?.[studio.editing.frameworkSlug]?.[
              studio.editing.input.role_name
            ]
          }
          onApplyWhatIf={(value, unit) =>
            studio.editing && applyWhatIf(studio.editing.input, value, unit)
          }
          onApplySwap={(slug) =>
            studio.editing && applySwap(studio.editing.input, studio.editing.frameworkSlug, slug)
          }
          onClear={() =>
            studio.editing && clearOverride(studio.editing.input, studio.editing.frameworkSlug)
          }
          onClose={() => dispatch({ type: "EDIT_CLOSE" })}
        />
      ) : null}
    </main>
  );
}
