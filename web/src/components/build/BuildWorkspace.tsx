"use client";

import { useQuery } from "@tanstack/react-query";
// The /build workhorse view (U1, U2, U6 · design 18-build). A live TAM rendered
// over a re-runnable concept evaluation, with a U2-ordered accordion rail and
// auto-mint URL state.
//
// Two hash spaces meet here, deliberately:
//   • the backend's TAMOutput.state_hash — sha256 of the *evaluated* payload,
//     used as the canonical artifact address when the state is unmodified;
//   • this view's hashState(BuildState) — sha256 of the *user's* build state,
//     used the moment the user diverges from the backend default (deselects a
//     framework, etc.), because the backend can't recompute those variants yet.
// Either way the URL is /build/<hash> and the full BuildState rides in ?s= so a
// reload / back / share round-trips losslessly (the backend does NOT persist
// computed TAMs — /tam/{hash} 404s — so ?s= is the only recovery path).
//
// Meaningful change (U6) → mint. Pan/zoom/hover/accordion → never mint (they
// live in component or ui-store state, off the URL).
import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import { CompositionChart, ScenarioComparisonChart } from "@/components/charts";
import { LineageGraph } from "@/components/LineageGraph";
import { OverridePanel } from "@/components/build/OverridePanel";
import { AccordionSection } from "@/components/rail/AccordionSection";
import {
	ProvenanceBanner,
	modeledInputNotes,
	provenanceNotes,
} from "@/components/rail/ProvenanceBanner";
import { ScenarioGraph } from "@/components/ScenarioGraph";
import { MethodDirections } from "@/components/tam/MethodDirections";
import { ScopeRailSummary, ScopeStrip, ScopeWarnings } from "@/components/tam/ScopeCheck";
import { TamTrajectoryChart } from "@/components/tam/TamTrajectoryChart";
import { Button } from "@/components/ui/Button";
import { IndependenceDonut } from "@/components/ui/IndependenceDonut";
import { Skeleton } from "@/components/ui/Skeleton";
import { Pulse } from "@/components/ui/motion";
import { formatCompact, lensLabel, tierLabel } from "@/lib/format";
import { trajectoryQuery } from "@/lib/queries";
import type { InputUsed, Scenario, ScopeReport, TAMOutput, Unit } from "@/lib/schemas";
import { type BuildState, encodeState, hashState, isScopeEmpty } from "@/lib/state-hash";
import { isDegenerate, midScenario, tamRange, tamToMarkdown } from "@/lib/tam";

// Every framework slug present in the backend evaluation — the universe the user
// can select from. Selecting a subset is the v0.3 "meaningful change" we support.
function allFrameworkSlugs(tam: TAMOutput): string[] {
	return [...new Set(tam.scenarios.map((s) => s.framework))];
}

// Narrow the full TAM to just the selected frameworks. A derived TAM, not a
// fetch — the backend gave us every scenario; selection is a client-side lens.
// We never drop below one scenario (an empty selection would break the schema's
// `.min(1)` and produce a meaningless TAM), so a fully-cleared selection falls
// back to the full set.
//
// The wire doesn't tag each scenario with its method family, so we can't
// recompute the exact family count for a narrowed set. Rather than fabricate
// one, we scale the backend's independence score by the fraction of scenarios
// kept — a conservative proxy that only ever *lowers* the score as the user
// prunes (never overstates triangulation), and collapses to 0 at one scenario
// (where the headline goes degenerate and the donut greys out anyway).
function applySelection(tam: TAMOutput, selected: string[]): TAMOutput {
	const keep = new Set(selected);
	const scenarios = tam.scenarios.filter((s) => keep.has(s.framework));
	if (scenarios.length === 0 || scenarios.length === tam.scenarios.length) {
		return scenarios.length === 0 ? tam : { ...tam, scenarios };
	}
	const fraction = scenarios.length / tam.scenarios.length;
	return {
		...tam,
		scenarios,
		independence_score:
			scenarios.length > 1 ? tam.independence_score * fraction : 0,
	};
}

export interface BuildWorkspaceProps {
	// The backend evaluation for `state.target_concept_slug` — the registry default
	// or, when overrides are active, the recomputed TAM. Never persisted server-side.
	tam: TAMOutput;
	// The reconstructed user state (from ?s= or a fresh concept default).
	state: BuildState;
	// True while a recompute is in flight (overrides changed) — drives the
	// headline/graph "recomputing…" affordance.
	recomputing?: boolean;
}

export function BuildWorkspace({
	tam: baseTam,
	state,
	recomputing = false,
}: BuildWorkspaceProps) {
	const router = useRouter();
	const universe = useMemo(() => allFrameworkSlugs(baseTam), [baseTam]);

	// The input whose override panel is open (null = closed). Click a base-value
	// graph node to open it.
	const [editing, setEditing] = useState<{
		input: InputUsed;
		frameworkSlug: string;
	} | null>(null);

	// Accent any node the user has touched: a what-if scalar (keyed by the original
	// primitive slug) or a swap (whose target slug becomes the node's primitive
	// after recompute, so highlighting the target matches the post-recompute graph).
	const overriddenSlugs = useMemo(() => {
		const slugs = new Set(Object.keys(state.primitive_overrides ?? {}));
		for (const roles of Object.values(state.framework_assumptions ?? {})) {
			for (const targetSlug of Object.values(roles)) slugs.add(targetSlug);
		}
		return slugs;
	}, [state.primitive_overrides, state.framework_assumptions]);

	const conceptSlug = state.target_concept_slug;

	// Default to every framework when the state carries no explicit selection
	// (a fresh concept open). An explicit selection means the user has diverged.
	// Memoized so the derived TAM (and the graph it feeds) only recompute when the
	// selection actually changes, not on every render.
	const selected = useMemo(
		() =>
			state.frameworks_selected.length > 0
				? state.frameworks_selected.filter((f) => universe.includes(f))
				: universe,
		[state.frameworks_selected, universe],
	);

	const tam = useMemo(
		() => applySelection(baseTam, selected),
		[baseTam, selected],
	);

	// A meaningful change (U6): recompute the build-state hash and replace the URL
	// in place (no history spam for in-flight tweaks — replace, not push, mirrors
	// the auto-mint "current state is the URL" model). The full state rides in ?s=
	// because the backend can't recompute it from the hash alone.
	const mint = useCallback(
		async (next: BuildState) => {
			const hash = await hashState(next);
			router.replace(`/build/${hash}?s=${encodeState(next)}`, {
				scroll: false,
			});
		},
		[router],
	);

	const toggleFramework = useCallback(
		(slug: string) => {
			const current = new Set(selected);
			if (current.has(slug)) {
				// Refuse to clear the last framework — an empty TAM is meaningless.
				if (current.size <= 1) return;
				current.delete(slug);
			} else {
				current.add(slug);
			}
			void mint({ ...state, frameworks_selected: [...current] });
		},
		[selected, state, mint],
	);

	const onEditPrimitive = useCallback(
		(input: InputUsed, frameworkSlug: string) => setEditing({ input, frameworkSlug }),
		[],
	);

	// Apply a transient what-if scalar: stash it under the primitive slug and
	// re-mint. BuildHashView sees the override and routes to /build/recompute.
	const applyWhatIf = useCallback(
		(input: InputUsed, value: number, unit: Unit) => {
			void mint({
				...state,
				primitive_overrides: {
					...state.primitive_overrides,
					[input.primitive_slug]: { value, unit },
				},
			});
			setEditing(null);
		},
		[state, mint],
	);

	// Re-point an input to a different sourced primitive (schema-pure swap).
	const applySwap = useCallback(
		(input: InputUsed, frameworkSlug: string, primitiveSlug: string) => {
			const fa = state.framework_assumptions ?? {};
			void mint({
				...state,
				framework_assumptions: {
					...fa,
					[frameworkSlug]: { ...(fa[frameworkSlug] ?? {}), [input.role_name]: primitiveSlug },
				},
			});
			setEditing(null);
		},
		[state, mint],
	);

	// Drop both override kinds for one input, returning it to the sourced value.
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
			setEditing(null);
		},
		[state, mint],
	);

	// Surface the pinned/declared market (sub-project 1.5): the chip strip + scope
	// check only when a market is actually declared — an unscoped concept stays
	// clean rather than showing an empty "all good" section.
	const report = tam.scope ?? null;
	const scoped = !!report && !isScopeEmpty(report.declared);

	const degenerate = isDegenerate(tam);
	const range = tamRange(tam);
	const mid = midScenario(tam);
	const industry =
		tam.target.concept_name ?? tam.target.concept.replace(/-/g, " ");
	const geo = state.geo ?? tam.target.geo ?? "Global";
	const time = state.time ?? tam.target.time ?? "latest";

	return (
		<main className="mx-auto flex w-full max-w-[var(--content-max)] flex-1 flex-col px-8 py-8">
			<Header industry={industry} geo={geo} time={time} hash8={hashFromUrl()} />

			{scoped && report ? (
				<div className="mt-4">
					<ScopeStrip scope={report.declared} />
				</div>
			) : null}

			<div className="mt-6 flex flex-col gap-6 lg:flex-row">
				<section className="flex min-w-0 flex-1 flex-col gap-6">
					<HeadlineCard
						tam={tam}
						degenerate={degenerate}
						range={range}
						mid={mid}
						recomputing={recomputing}
					/>
					{/* Which canonical sizing directions back this number — and which are
					    missing (sub-project 2 honesty: name the absent direction, never
					    fabricate it). */}
					<MethodDirections families={tam.method_families_used} />
					<div className="relative">
						{recomputing ? (
							<div className="pointer-events-none absolute right-3 top-3 z-10 rounded-[var(--r-1)] bg-[var(--bg-0)]/90 px-2 py-1 text-[11px] text-[var(--accent)]">
								recomputing…
							</div>
						) : null}
						<ScenarioGraph
							tam={tam}
							onEditPrimitive={onEditPrimitive}
							overriddenSlugs={overriddenSlugs}
						/>
					</div>
					<ChartsSection tam={tam} mid={mid} />
					{scoped && report ? <ScopeWarnings report={report} /> : null}
					<TrajectorySection slug={tam.target.concept} />
				</section>

				<Rail
					tam={tam}
					baseTam={baseTam}
					universe={universe}
					selected={selected}
					report={scoped ? report : null}
					onToggleFramework={toggleFramework}
					degenerate={degenerate}
				/>
			</div>

			{editing ? (
				<OverridePanel
					input={editing.input}
					frameworkSlug={editing.frameworkSlug}
					conceptSlug={conceptSlug}
					currentOverride={state.primitive_overrides?.[editing.input.primitive_slug]?.value}
					currentSwap={state.framework_assumptions?.[editing.frameworkSlug]?.[editing.input.role_name]}
					onApplyWhatIf={(value, unit) => applyWhatIf(editing.input, value, unit)}
					onApplySwap={(slug) => applySwap(editing.input, editing.frameworkSlug, slug)}
					onClear={() => clearOverride(editing.input, editing.frameworkSlug)}
					onClose={() => setEditing(null)}
				/>
			) : null}
		</main>
	);
}

// Method-comparison + composition charts (Track B). The composition view is
// driven by the midpoint scenario — the one the headline reports.
function ChartsSection({ tam, mid }: { tam: TAMOutput; mid: Scenario }) {
	return (
		<div className="flex flex-col gap-6">
			<div>
				<h2 className="display text-[20px] text-[var(--fg-1)]">Method comparison</h2>
				<p className="mt-1 text-[13px] text-[var(--fg-3)]">
					Each independent method's estimate, side by side.
				</p>
				<div className="canvas-card mt-3 p-6">
					<ScenarioComparisonChart tam={tam} />
				</div>
			</div>
			<div>
				<h2 className="display text-[20px] text-[var(--fg-1)]">How this scenario is built</h2>
				<p className="mt-1 text-[13px] text-[var(--fg-3)]">
					The sourced inputs that multiply into the headline midpoint.
				</p>
				<div className="canvas-card mt-3 p-6">
					<CompositionChart scenario={mid} />
				</div>
			</div>
		</div>
	);
}

// TAM-over-time, below the canvas. Supplementary: a failed/empty fetch renders
// nothing so the workhorse view is unaffected (the trajectory is a read, not
// part of the live evaluation the user is steering).
function TrajectorySection({ slug }: { slug: string }) {
	const traj = useQuery(trajectoryQuery(slug));

	if (traj.isPending) {
		return (
			<div>
				<h2 className="display text-[20px] text-[var(--fg-1)]">
					TAM over time
				</h2>
				<Skeleton className="mt-3 h-[200px] w-full" />
			</div>
		);
	}
	if (traj.error || !traj.data) return null;

	return (
		<div>
			<h2 className="display text-[20px] text-[var(--fg-1)]">TAM over time</h2>
			<p className="mt-1 text-[13px] text-[var(--fg-3)]">
				Current TAM vs the path it travelled, re-evaluated at each dated source
				snapshot.
			</p>
			<div className="canvas-card mt-3 p-6">
				<TamTrajectoryChart trajectory={traj.data} />
			</div>
		</div>
	);
}

// The short hash is read from the URL rather than recomputed so the header
// always reflects the *minted* address, even one frame before a pending mint
// resolves. SSR-safe: empty string on the server.
function hashFromUrl(): string {
	if (typeof window === "undefined") return "";
	const seg = window.location.pathname.split("/").filter(Boolean);
	return seg[1]?.slice(0, 8) ?? "";
}

function Header({
	industry,
	geo,
	time,
	hash8,
}: {
	industry: string;
	geo: string;
	time: string;
	hash8: string;
}) {
	return (
		<header className="flex flex-col gap-3">
			<div className="text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
				TAM · {geo} · {time}
			</div>
			<h1 className="display text-[40px] leading-[1.05] text-[var(--fg-1)] capitalize">
				{industry}
			</h1>
			<div className="flex items-center gap-2 font-mono text-[12px] text-[var(--fg-3)]">
				<span>/build/</span>
				<code className="rounded-[var(--r-1)] bg-[var(--bg-2)] px-2 py-0.5 text-[var(--fg-2)]">
					{hash8 || "…"}
				</code>
				<CopyUrlButton />
			</div>
		</header>
	);
}

function HeadlineCard({
	tam,
	degenerate,
	range,
	mid,
	recomputing = false,
}: {
	tam: TAMOutput;
	degenerate: boolean;
	range: ReturnType<typeof tamRange>;
	mid: Scenario;
	recomputing?: boolean;
}) {
	const leafCount = tam.scenarios.length;
	const spread = range.low > 0 ? range.high / range.low : null;
	// Any what-if scalar in the evaluation flips this flag on the recomputed TAM.
	const hasWhatIf = tam.uses_synthetic_primitives;

	return (
		<div className="canvas-card flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
			<div className="min-w-0">
				<div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.06em] text-[var(--fg-3)]">
					{degenerate ? "Single-method estimate" : "Triangulated midpoint"}
					{hasWhatIf ? (
						<span className="rounded-[var(--r-1)] bg-[var(--bg-2)] px-1.5 py-0.5 normal-case tracking-normal text-[var(--accent)]">
							what-if
						</span>
					) : null}
				</div>
				{/* Pulse-ring the headline on every recompute (keyed by the evaluated
				    hash) so an override's effect on the number is visible, not just
				    the rail. Reduced-motion-gated inside Pulse. */}
				<Pulse pulseKey={tam.state_hash} className="tam-num mt-1 inline-block">
					<span
						className="text-[44px] leading-[1] text-[var(--fg-1)] transition-opacity"
						style={{ opacity: recomputing ? 0.5 : 1 }}
					>
						{formatCompact(range.mid, mid.unit)}
					</span>
				</Pulse>
				{/* Screen-reader announcement: the visual recompute is opacity-only, so
				    AT users get no signal the number changed. This polite live region
				    speaks the recompute and the new value. */}
				<span className="sr-only" aria-live="polite">
					{recomputing
						? "Recomputing market size"
						: `Market size ${formatCompact(range.mid, mid.unit)}`}
				</span>
				{degenerate ? (
					// No real spread — present a point estimate, never a fabricated range.
					<div className="mt-2 text-[13px] text-[var(--fg-3)]">
						{leafCount} {leafCount === 1 ? "scenario" : "scenarios"}, one method
						family
					</div>
				) : (
					<div className="mt-2 text-[13px] text-[var(--fg-2)]">
						{formatCompact(range.low, mid.unit)} –{" "}
						{formatCompact(range.high, mid.unit)}
						<span className="mx-1.5 text-[var(--fg-4)]">·</span>
						{leafCount} scenarios
						{spread ? (
							<>
								<span className="mx-1.5 text-[var(--fg-4)]">·</span>~
								{spread.toFixed(1)}× spread
							</>
						) : null}
					</div>
				)}
			</div>

			{/* A degenerate TAM has no real independence — grey the donut and say what
          it would take to earn a score rather than imply triangulation (U2). */}
			<div className="shrink-0">
				{degenerate ? (
					<div className="flex flex-col items-center gap-1 opacity-40">
						<IndependenceDonut score={tam.independence_score} size={104} />
						<span className="max-w-[120px] text-center text-[10px] text-[var(--fg-3)]">
							needs ≥2 method families
						</span>
					</div>
				) : (
					<IndependenceDonut score={tam.independence_score} size={104} />
				)}
			</div>
		</div>
	);
}

// ── Right rail: accordion in U2 order ─────────────────────────────────────────
// Target (pinned) → Frameworks (open) → Scenarios (open) → Independence
// (collapsed) → Lineage (collapsed) → Banners → Export (pinned).

function Rail({
	tam,
	baseTam,
	universe,
	selected,
	report,
	onToggleFramework,
	degenerate,
}: {
	tam: TAMOutput;
	baseTam: TAMOutput;
	universe: string[];
	selected: string[];
	report: ScopeReport | null;
	onToggleFramework: (slug: string) => void;
	degenerate: boolean;
}) {
	const [lineageOpen, setLineageOpen] = useState(false);
	const selectedSet = new Set(selected);
	// Phase 4: the Banners section must also open for per-scenario MODELED inputs,
	// not only the two rolled-up flags — else a modeled/paraphrased input that sets
	// neither flag would be hidden on /build.
	const bannerCount = provenanceNotes(tam).length + modeledInputNotes(tam).length;

	return (
		<aside className="flex w-full flex-col gap-3 lg:w-[var(--right-rail-w)] lg:shrink-0">
			{/* TARGET — pinned top */}
			<AccordionSection title="Target" pinned>
				<div className="flex flex-col gap-1 text-[13px]">
					<span className="capitalize text-[var(--fg-1)]">
						{tam.target.concept_name ?? tam.target.concept.replace(/-/g, " ")}
					</span>
					<span className="text-[var(--fg-3)]">
						{tam.target.geo ?? "Global"} · {tam.target.time ?? "latest"} ·{" "}
						{tam.target.expansion_stage}
					</span>
				</div>
			</AccordionSection>

			{/* MARKET — the pinned scope's at-a-glance check (sub-project 1.5). */}
			{report ? (
				<AccordionSection title="Market" defaultOpen>
					<ScopeRailSummary report={report} />
				</AccordionSection>
			) : null}

			{/* FRAMEWORKS — open by default. Toggling a row is a meaningful change. */}
			<AccordionSection
				title="Frameworks"
				badge={`${selected.length}/${universe.length}`}
				defaultOpen
			>
				<ul className="flex flex-col gap-1.5">
					{universe.map((slug) => {
						const on = selectedSet.has(slug);
						const scenario = baseTam.scenarios.find(
							(s) => s.framework === slug,
						);
						return (
							<li key={slug}>
								<button
									type="button"
									role="switch"
									aria-checked={on}
									onClick={() => onToggleFramework(slug)}
									className="canvas-card flex w-full items-center justify-between gap-2 px-3 py-2 text-left transition-opacity"
									style={{ borderRadius: "var(--r-2)", opacity: on ? 1 : 0.55 }}
								>
									<span className="flex min-w-0 flex-col gap-0.5">
										<span className="truncate text-[13px] text-[var(--fg-1)]">
											{scenario?.definition ?? slug.replace(/-/g, " ")}
										</span>
										{scenario ? (
											<span className="role-chip self-start uppercase tracking-[0.04em]">
												{lensLabel(scenario.lens)}
											</span>
										) : null}
									</span>
									<span
										className="text-[11px] font-medium uppercase tracking-[0.04em]"
										style={{ color: on ? "var(--accent-active)" : "var(--fg-4)" }}
									>
										{on ? "on" : "off"}
									</span>
								</button>
							</li>
						);
					})}
				</ul>
			</AccordionSection>

			{/* SCENARIOS — open by default. One row per surviving (selected) scenario. */}
			<AccordionSection
				title="Scenarios"
				badge={`${tam.scenarios.length}`}
				defaultOpen
			>
				<ul className="flex flex-col gap-2">
					{tam.scenarios.map((s) => (
						<li
							key={`${s.framework}-${s.framework_variant ?? ""}`}
							className="canvas-card flex items-center justify-between gap-3 px-3 py-2.5"
							style={{ borderRadius: "var(--r-2)" }}
						>
							<div className="flex min-w-0 flex-col gap-1">
								<span className="truncate text-[13px] text-[var(--fg-1)]">
									{s.definition}
								</span>
								<span className="role-chip self-start uppercase tracking-[0.04em]">
									{lensLabel(s.lens)}
								</span>
							</div>
							<span className="tam-num text-[15px] tabular-nums text-[var(--fg-1)]">
								{formatCompact(s.value, s.unit)}
							</span>
						</li>
					))}
				</ul>
			</AccordionSection>

			{/* INDEPENDENCE — collapsed. Greyed when degenerate (no real triangulation). */}
			<AccordionSection
				title="Independence"
				badge={tam.independence_score.toFixed(2)}
			>
				{degenerate ? (
					<p className="text-[13px] text-[var(--fg-3)] opacity-60">
						Single-method estimate — needs ≥2 method families to score
						independence.
					</p>
				) : (
					<p className="text-[13px] leading-[1.5] text-[var(--fg-2)]">
						{tam.method_families_used.map(tierLabel).join(", ") || "—"} ·{" "}
						{tam.scenarios.length} scenarios. Higher is better.
					</p>
				)}
			</AccordionSection>

			{/* LINEAGE — collapsed, opens the modal. */}
			<AccordionSection title="Lineage graph">
				<button
					type="button"
					onClick={() => setLineageOpen(true)}
					className="text-[13px] text-[var(--accent)] hover:underline"
				>
					Open lineage modal →
				</button>
			</AccordionSection>

			{/* BANNERS — when the data layer flagged something: rolled-up flags OR a
			    per-scenario MODELED input (U2). */}
			{bannerCount > 0 ? (
				<AccordionSection title="Banners" badge={`${bannerCount}`} defaultOpen>
					<ProvenanceBanner tam={tam} />
				</AccordionSection>
			) : null}

			{/* EXPORT — pinned bottom (U10). */}
			<AccordionSection title="Export" pinned>
				<div className="flex flex-col gap-2">
					<CopyUrlButton variant="ghost" label="Copy URL" full />
					<DownloadMarkdownButton tam={tam} />
					<Button
						variant="ghost"
						sm
						onClick={() => typeof window !== "undefined" && window.print()}
						className="justify-start"
					>
						Download PDF
					</Button>
				</div>
			</AccordionSection>

			<LineageGraph
				tam={tam}
				open={lineageOpen}
				onClose={() => setLineageOpen(false)}
			/>
		</aside>
	);
}

// ── Export bits ───────────────────────────────────────────────────────────────

function DownloadMarkdownButton({ tam }: { tam: TAMOutput }) {
	return (
		<Button
			variant="ghost"
			sm
			onClick={() => downloadMarkdown(tam)}
			className="justify-start"
		>
			Download Markdown
		</Button>
	);
}

function downloadMarkdown(tam: TAMOutput) {
	if (typeof window === "undefined") return;
	const blob = new Blob([tamToMarkdown(tam)], { type: "text/markdown" });
	const url = URL.createObjectURL(blob);
	const a = document.createElement("a");
	a.href = url;
	a.download = `tam-${tam.state_hash.slice(0, 8)}.md`;
	a.click();
	URL.revokeObjectURL(url);
}

function CopyUrlButton({
	variant = "ghost",
	label = "Copy link",
	full = false,
}: {
	variant?: "primary" | "ghost";
	label?: string;
	full?: boolean;
}) {
	const [copied, setCopied] = useState(false);
	return (
		<Button
			variant={variant}
			sm
			className={full ? "justify-start" : ""}
			onClick={() => {
				if (typeof window === "undefined") return;
				navigator.clipboard
					.writeText(window.location.href)
					.then(() => {
						setCopied(true);
						setTimeout(() => setCopied(false), 1500);
					})
					.catch(() => {});
			}}
		>
			{copied ? "Copied!" : label}
		</Button>
	);
}
