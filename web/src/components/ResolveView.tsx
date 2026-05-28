/**
 * ResolveView — the dynamic-TAM streaming surface (PR8 rewrite).
 *
 * When the build view can't match a query to a registry concept it falls here.
 * We drive `POST /resolve` through the `streamResolve` async generator and fold
 * the frozen §9.1 wire events into a chain-of-thought row list:
 *
 *   parsing → searching → framework_selected → evaluating → result → done|error
 *
 * Legacy `step` envelopes (type: parsing | primitive_found | framework_selected
 * | evaluating) enrich the active row rather than spawning their own — they
 * carry the per-primitive detail the frozen events summarise. The `result`
 * payload is validated with `resolverResultSchema` before it touches the UI; a
 * parse failure is surfaced as an error, not silently swallowed. On any failure
 * (or a result with no primitives) we offer the nearest registry concepts so a
 * dead-end query still routes the user somewhere defensible.
 */

"use client";

import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { IndependenceDonut } from "@/components/ui/IndependenceDonut";
import { TierBadge } from "@/components/ui/TierBadge";
import { formatCompact, formatUSD, lensLabel } from "@/lib/format";
import { rankByQuery } from "@/lib/fuzzy";
import { conceptsQuery } from "@/lib/queries";
import { type SSEEnvelope, streamResolve } from "@/lib/resolver-client";
import {
	type PipelineEvent,
	type PrimitiveUsed,
	type ResolverResult,
	resolverResultSchema,
} from "@/lib/resolver-schemas";
import type { SourceTier } from "@/lib/schemas";
import { PipelineTrace } from "./PipelineTrace";

// ── Chain-of-thought model ────────────────────────────────────────────────
// One row per frozen pipeline phase. `detail` lines hang the legacy `step`
// envelopes (per-primitive hits, formula) under the phase that owns them.

type Phase = "parsing" | "searching" | "framework_selected" | "evaluating";

interface PrimitiveHit {
	role: string;
	name: string;
	value: number | null;
	source_url: string | null;
	source_tier: string | null;
}

interface ThoughtRow {
	phase: Phase;
	label: string;
	hits: PrimitiveHit[];
	framework: string | null;
}

type Status = "streaming" | "done" | "error";

export interface State {
	rows: ThoughtRow[];
	result: ResolverResult | null;
	error: string | null;
	status: Status;
}

const PHASE_LABELS: Record<Phase, string> = {
	parsing: "Parsing the query",
	searching: "Searching for primitives",
	framework_selected: "Selecting a framework",
	evaluating: "Evaluating scenarios",
};

export const initialState: State = {
	rows: [],
	result: null,
	error: null,
	status: "streaming",
};

export type Action =
	| { kind: "reset" }
	| { kind: "envelope"; envelope: SSEEnvelope }
	| { kind: "error"; message: string };

// Append or fetch the row for a phase so repeated step-enrichments land in one
// place. Phases arrive in order, so the matching row is always the last one.
function rowFor(
	rows: ThoughtRow[],
	phase: Phase,
): { rows: ThoughtRow[]; row: ThoughtRow } {
	const existing = rows.find((r) => r.phase === phase);
	if (existing) return { rows, row: existing };
	const row: ThoughtRow = {
		phase,
		label: PHASE_LABELS[phase],
		hits: [],
		framework: null,
	};
	return { rows: [...rows, row], row };
}

function asRecord(data: unknown): Record<string, unknown> {
	return data && typeof data === "object"
		? (data as Record<string, unknown>)
		: {};
}

export function reducer(state: State, action: Action): State {
	switch (action.kind) {
		case "reset":
			return initialState;
		case "error":
			return { ...state, error: action.message, status: "error" };
		case "envelope": {
			const { event, data } = action.envelope;
			const payload = asRecord(data);

			switch (event) {
				case "parsing":
				case "searching":
				case "evaluating": {
					const { rows } = rowFor(state.rows, event);
					return { ...state, rows };
				}
				case "framework_selected": {
					const next = rowFor(state.rows, "framework_selected");
					const framework =
						typeof payload.framework === "string" ? payload.framework : null;
					const rows = next.rows.map((r) =>
						r === next.row ? { ...r, framework } : r,
					);
					return { ...state, rows };
				}
				// Legacy step envelopes enrich the owning phase row.
				case "step": {
					const type = typeof payload.type === "string" ? payload.type : "";
					if (type === "primitive_found") {
						const next = rowFor(state.rows, "searching");
						const hit: PrimitiveHit = {
							role: String(payload.role ?? ""),
							name: String(payload.name ?? payload.role ?? "Primitive"),
							value: typeof payload.value === "number" ? payload.value : null,
							source_url:
								typeof payload.source_url === "string"
									? payload.source_url
									: null,
							source_tier:
								typeof payload.source_tier === "string"
									? payload.source_tier
									: null,
						};
						const rows = next.rows.map((r) =>
							r === next.row ? { ...r, hits: [...r.hits, hit] } : r,
						);
						return { ...state, rows };
					}
					if (type === "framework_selected") {
						const next = rowFor(state.rows, "framework_selected");
						const framework =
							typeof payload.name === "string"
								? payload.name
								: next.row.framework;
						const rows = next.rows.map((r) =>
							r === next.row ? { ...r, framework } : r,
						);
						return { ...state, rows };
					}
					// parsing / evaluating step envelopes only confirm a phase exists.
					if (type === "parsing")
						return { ...state, rows: rowFor(state.rows, "parsing").rows };
					if (type === "evaluating")
						return { ...state, rows: rowFor(state.rows, "evaluating").rows };
					return state;
				}
				case "result": {
					// The /resolve route's `result` payload is a superset of the CLI
					// ResolverResult but omits the `status`/`via` discriminators (it's
					// always a successful, fallback-tier synthesis). Inject those defaults
					// before validating, mirroring useResolveMutation.
					const parsed = resolverResultSchema.safeParse({
						status: "ok",
						via: "fallback",
						...payload,
					});
					if (!parsed.success) {
						return {
							...state,
							error: "Resolver returned an unreadable result.",
							status: "error",
						};
					}
					return { ...state, result: parsed.data };
				}
				case "error": {
					const message =
						typeof payload.message === "string"
							? payload.message
							: "Resolution failed.";
					return { ...state, error: message, status: "error" };
				}
				case "done":
					return state.status === "error"
						? state
						: { ...state, status: "done" };
				default:
					return state;
			}
		}
	}
}

export function ResolveView({
	query,
	onBack,
}: {
	query: string;
	onBack?: () => void;
}) {
	const [state, dispatch] = useReducer(reducer, initialState);
	const [attempt, setAttempt] = useState(0);
	const scrollRef = useRef<HTMLDivElement>(null);

	// `attempt` is an intentional re-run key: Retry bumps it to re-fire the
	// stream without changing the query. Not read in the body — kept as a dep.
	// biome-ignore lint/correctness/useExhaustiveDependencies: attempt is a re-run trigger
	useEffect(() => {
		dispatch({ kind: "reset" });
		const controller = new AbortController();

		(async () => {
			try {
				for await (const envelope of streamResolve(
					{ query },
					{ signal: controller.signal },
				)) {
					dispatch({ kind: "envelope", envelope });
				}
				// Generator returns on `done`; if it ends without one, settle anyway.
				dispatch({ kind: "envelope", envelope: { event: "done", data: null } });
			} catch (e) {
				if (controller.signal.aborted) return;
				dispatch({
					kind: "error",
					message: e instanceof Error ? e.message : "Stream failed.",
				});
			}
		})();

		return () => controller.abort();
	}, [query, attempt]);

	// Auto-scroll as rows/result arrive.
	// biome-ignore lint/correctness/useExhaustiveDependencies: scroll on every stream change
	useEffect(() => {
		scrollRef.current?.scrollIntoView({ behavior: "smooth" });
	}, [state.rows, state.result, state.error]);

	const retry = useCallback(() => setAttempt((n) => n + 1), []);

	const { rows, result, error, status } = state;
	// A result with no primitives is a dead end — treat it like a soft failure so
	// the nearest-concept fallback still fires.
	const emptyResult = result !== null && result.primitives_used.length === 0;
	const showFallback = status === "error" || emptyResult;

	return (
		<main className="flex-1 flex flex-col">
			<header className="w-full px-8 py-5 flex items-center justify-between border-b border-[var(--border-1)]">
				<button
					type="button"
					aria-label="Back to search"
					onClick={() => (onBack ? onBack() : window.history.back())}
					className="display text-[20px] text-[var(--fg-1)] hover:text-[var(--accent)] transition-colors"
				>
					← Strata
				</button>
				<div className="font-mono text-[12px] text-[var(--fg-3)]">
					{status === "streaming"
						? "resolving…"
						: status === "error"
							? "failed"
							: "resolved"}
				</div>
			</header>

			<div className="flex-1 flex flex-col px-8 py-8 max-w-[800px] mx-auto w-full gap-4">
				<div className="text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
					Dynamic TAM resolution
				</div>
				<h1 className="display text-[32px] leading-[1.1] text-[var(--fg-1)]">
					&ldquo;{query}&rdquo;
				</h1>

				<ol className="mt-6 flex flex-col gap-3">
					{rows.map((row) => (
						<ThoughtRowItem
							key={row.phase}
							row={row}
							streaming={status === "streaming"}
						/>
					))}
				</ol>

				{status === "streaming" ? (
					<div className="flex items-center gap-2 text-[13px] text-[var(--fg-3)]">
						<span className="animate-pulse text-[var(--accent)]">●</span>{" "}
						Thinking…
					</div>
				) : null}

				{result && !emptyResult ? <ResultCard result={result} /> : null}

				{result && result.events.length > 0 ? (
					<TraceDisclosure events={result.events} />
				) : null}

				{error ? (
					<div
						role="alert"
						className="rounded-[var(--r-3)] bg-[var(--danger-tint,rgba(229,72,77,0.1))] px-4 py-3 text-[13px] text-[var(--danger)]"
					>
						{error}
					</div>
				) : null}

				{status !== "streaming" ? (
					<div className="mt-1 flex items-center gap-3">
						<button
							type="button"
							onClick={retry}
							className="rounded-[var(--r-2)] border border-[var(--border-2)] px-3 py-1.5 text-[13px] text-[var(--fg-1)] hover:bg-[var(--bg-2)] transition-colors"
						>
							Retry resolution
						</button>
					</div>
				) : null}

				{showFallback ? <NearestConceptFallback query={query} /> : null}

				<div ref={scrollRef} />
			</div>
		</main>
	);
}

function ThoughtRowItem({
	row,
	streaming,
}: {
	row: ThoughtRow;
	streaming: boolean;
}) {
	return (
		<li className="flex flex-col gap-2">
			<div className="flex items-center gap-2 text-[13px] text-[var(--fg-2)]">
				<span className="text-[var(--accent)]">→</span>
				<span className="text-[var(--fg-1)]">{row.label}</span>
				{row.framework ? (
					<span className="role-chip uppercase tracking-[0.04em]">
						{lensLabel(row.framework)}
					</span>
				) : null}
			</div>
			{row.hits.length > 0 ? (
				<ul className="ml-5 flex flex-col gap-1.5">
					{row.hits.map((hit) => (
						<li
							key={`${hit.role}-${hit.name}`}
							className="canvas-card flex items-center justify-between px-3 py-2"
							style={{ borderRadius: "var(--r-2)" }}
						>
							<div className="flex min-w-0 flex-col gap-0.5">
								<span className="truncate text-[12px] text-[var(--fg-1)]">
									{hit.name}
								</span>
								{hit.source_tier ? (
									<TierBadge tier={coerceTier(hit.source_tier)} />
								) : null}
							</div>
							<div className="flex shrink-0 items-center gap-3">
								<span className="tam-num text-[13px] text-[var(--fg-1)] tabular-nums">
									{hit.value !== null ? formatCompact(hit.value) : "—"}
								</span>
								{hit.source_url ? (
									<a
										href={hit.source_url}
										target="_blank"
										rel="noopener noreferrer"
										className="text-[10px] text-[var(--accent)] hover:underline"
									>
										source ↗
									</a>
								) : null}
							</div>
						</li>
					))}
				</ul>
			) : streaming && row.phase === "searching" ? (
				<span className="ml-5 text-[11px] text-[var(--fg-3)]">
					looking up sources…
				</span>
			) : null}
		</li>
	);
}

function ResultCard({ result }: { result: ResolverResult }) {
	const headline =
		result.formatted_tam ??
		(result.tam_value != null ? formatUSD(result.tam_value) : "—");

	return (
		<div
			className="canvas-card mt-4 px-6 py-5"
			style={{ borderRadius: "var(--r-3)" }}
		>
			<div className="flex items-start justify-between gap-6">
				<div className="min-w-0">
					<div className="text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
						Result
					</div>
					<div className="mt-1 text-[18px] font-medium text-[var(--fg-1)]">
						{result.concept_name ?? "Resolved estimate"}
					</div>
					<div className="tam-num mt-2 text-[48px] text-[var(--fg-1)]">
						{headline}
					</div>
					<div className="mt-2 text-[13px] text-[var(--fg-2)]">
						{result.framework_name ?? ""}
						{result.lens ? ` · ${lensLabel(result.lens)}` : ""}
					</div>
				</div>
				<IndependenceDonut score={result.independence_score} size={84} />
			</div>

			{result.primitives_used.length > 0 ? (
				<div className="mt-5 flex flex-col gap-2 border-t border-[var(--border-1)] pt-4">
					<div className="text-[10px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
						Primitives used
					</div>
					{result.primitives_used.map((p, idx) => (
						<PrimitiveRow
							key={`${p.slug ?? p.role ?? "p"}-${idx}`}
							primitive={p}
						/>
					))}
				</div>
			) : null}

			{result.banner ? (
				<div
					role="note"
					className="mt-4 rounded-[var(--r-2)] bg-[var(--tier-analyst-tint)] px-3 py-2 text-[12px] text-[var(--fg-2)]"
				>
					<span className="font-medium text-[var(--tier-analyst)]">
						Provenance
					</span>{" "}
					{result.banner}
				</div>
			) : null}
		</div>
	);
}

function PrimitiveRow({ primitive }: { primitive: PrimitiveUsed }) {
	const label =
		primitive.name ?? primitive.slug ?? primitive.role ?? "Primitive";
	return (
		<div className="flex items-center justify-between gap-3 text-[13px]">
			<div className="flex min-w-0 items-center gap-2">
				<span className="truncate text-[var(--fg-2)]">{label}</span>
				{primitive.source_tier ? (
					<TierBadge tier={coerceTier(primitive.source_tier)} />
				) : null}
			</div>
			{primitive.source_url ? (
				<a
					href={primitive.source_url}
					target="_blank"
					rel="noopener noreferrer"
					className="shrink-0 tabular-nums text-[var(--accent)] hover:underline"
				>
					{formatCompact(primitive.value)} ↗
				</a>
			) : (
				<span className="shrink-0 tabular-nums text-[var(--fg-1)]">
					{formatCompact(primitive.value)}
				</span>
			)}
		</div>
	);
}

function TraceDisclosure({ events }: { events: PipelineEvent[] }) {
	const [open, setOpen] = useState(false);
	return (
		<details
			className="mt-2 rounded-[var(--r-3)] border border-[var(--border-1)] px-4 py-3"
			open={open}
			onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}
		>
			<summary className="cursor-pointer text-[12px] text-[var(--fg-3)] hover:text-[var(--fg-1)]">
				Pipeline trace · {events.length} event{events.length === 1 ? "" : "s"}
			</summary>
			<div className="mt-3">
				<PipelineTrace events={events} />
			</div>
		</details>
	);
}

function NearestConceptFallback({ query }: { query: string }) {
	const concepts = useQuery(conceptsQuery);
	if (concepts.isPending || !concepts.data) return null;

	const ranked = rankByQuery(
		concepts.data,
		query,
		(c) => `${c.name} ${c.slug}`,
	).slice(0, 3);
	if (ranked.length === 0) return null;

	return (
		<div
			className="mt-4 flex flex-col gap-2 canvas-card px-5 py-4"
			style={{ borderRadius: "var(--r-3)" }}
		>
			<div className="text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
				Closest concepts in the registry
			</div>
			<p className="text-[12px] text-[var(--fg-3)]">
				We couldn&rsquo;t resolve this query live. These curated concepts are
				the nearest match — open one to build a TAM on sourced primitives.
			</p>
			<ul className="mt-1 flex flex-col gap-1">
				{ranked.map(({ item }) => (
					<li key={item.slug}>
						<a
							href={`/build?q=${encodeURIComponent(item.slug)}`}
							className="flex items-center justify-between gap-2 rounded-[var(--r-2)] px-2 py-1.5 text-[13px] text-[var(--fg-1)] hover:bg-[var(--bg-2)] hover:text-[var(--accent)] transition-colors"
						>
							<span className="truncate">{item.name}</span>
							<span className="text-[var(--fg-4)]">→</span>
						</a>
					</li>
				))}
			</ul>
		</div>
	);
}

// The wire `source_tier` is a free string; TierBadge wants a known SourceTier.
// Fold unknown tiers onto "community" so the badge never crashes on bad data.
const KNOWN_TIERS: ReadonlySet<string> = new Set<SourceTier>([
	"first_party",
	"regulator",
	"aggregator",
	"analyst",
	"analyst-paraphrase",
	"community",
	"onchain",
	"prediction_market",
	"community-modeled",
]);

function coerceTier(tier: string): SourceTier {
	return (KNOWN_TIERS.has(tier) ? tier : "community") as SourceTier;
}
