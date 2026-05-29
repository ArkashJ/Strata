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
import { LineageGraph } from "@/components/LineageGraph";
import { AccordionSection } from "@/components/rail/AccordionSection";
import {
	ProvenanceBanner,
	provenanceNotes,
} from "@/components/rail/ProvenanceBanner";
import { ScenarioGraph } from "@/components/ScenarioGraph";
import { TamTrajectoryChart } from "@/components/tam/TamTrajectoryChart";
import { Button } from "@/components/ui/Button";
import { IndependenceDonut } from "@/components/ui/IndependenceDonut";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatCompact, lensLabel, tierLabel } from "@/lib/format";
import { trajectoryQuery } from "@/lib/queries";
import type { Scenario, TAMOutput } from "@/lib/schemas";
import { type BuildState, encodeState, hashState } from "@/lib/state-hash";
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
	// The backend evaluation for `state.target_concept_slug`. Re-fetched on each
	// mount; never persisted server-side.
	tam: TAMOutput;
	// The reconstructed user state (from ?s= or a fresh concept default).
	state: BuildState;
}

export function BuildWorkspace({ tam: baseTam, state }: BuildWorkspaceProps) {
	const router = useRouter();
	const universe = useMemo(() => allFrameworkSlugs(baseTam), [baseTam]);

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

			<div className="mt-6 flex flex-col gap-6 lg:flex-row">
				<section className="flex min-w-0 flex-1 flex-col gap-6">
					<HeadlineCard
						tam={tam}
						degenerate={degenerate}
						range={range}
						mid={mid}
					/>
					<ScenarioGraph tam={tam} />
					<TrajectorySection slug={tam.target.concept} />
				</section>

				<Rail
					tam={tam}
					baseTam={baseTam}
					universe={universe}
					selected={selected}
					onToggleFramework={toggleFramework}
					degenerate={degenerate}
				/>
			</div>
		</main>
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
}: {
	tam: TAMOutput;
	degenerate: boolean;
	range: ReturnType<typeof tamRange>;
	mid: Scenario;
}) {
	const leafCount = tam.scenarios.length;
	const spread = range.low > 0 ? range.high / range.low : null;

	return (
		<div className="canvas-card flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
			<div className="min-w-0">
				<div className="text-[11px] uppercase tracking-[0.06em] text-[var(--fg-3)]">
					{degenerate ? "Single-method estimate" : "Triangulated midpoint"}
				</div>
				<div className="tam-num mt-1 text-[44px] leading-[1] text-[var(--fg-1)]">
					{formatCompact(range.mid, mid.unit)}
				</div>
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
	onToggleFramework,
	degenerate,
}: {
	tam: TAMOutput;
	baseTam: TAMOutput;
	universe: string[];
	selected: string[];
	onToggleFramework: (slug: string) => void;
	degenerate: boolean;
}) {
	const [lineageOpen, setLineageOpen] = useState(false);
	const selectedSet = new Set(selected);
	const banners = provenanceNotes(tam);

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
									className="canvas-card flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
									style={{ borderRadius: "var(--r-2)", opacity: on ? 1 : 0.45 }}
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
									<span className="text-[12px] text-[var(--fg-3)]">
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

			{/* BANNERS — only when the data layer flagged something (U2). */}
			{banners.length > 0 ? (
				<AccordionSection
					title="Banners"
					badge={`${banners.length}`}
					defaultOpen
				>
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
