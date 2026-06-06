"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";

import {
  type GeoChip,
  PyramidFilters,
  type StageChip,
  type TimeChip,
} from "@/components/PyramidFilters";
import { PyramidGraph } from "@/components/PyramidGraph";
import { IndependenceDonut } from "@/components/ui/IndependenceDonut";
import { TierBadge } from "@/components/ui/TierBadge";
import { formatCompact, lensLabel } from "@/lib/format";
import {
  PILLAR_LABEL,
  type Pillar,
  type PyramidNode,
  type Selection,
  buildPyramid,
  compatibleFrameworks,
  narrow,
} from "@/lib/pyramid";
import {
  buildQuery,
  conceptsQuery,
  frameworksQuery,
  primitiveQuery,
  primitivesQuery,
} from "@/lib/queries";
import type { PrimitiveSummary, SourceTier } from "@/lib/schemas";
import { isDegenerate, tamRange } from "@/lib/tam";

// `embedded` drops this view's own <main> + page heading so it can sit inside a
// surface that already provides them (the /explore Pyramid tab) without nesting
// landmarks or duplicating the "Explore the…" headline.
export function GraphView({ embedded = false }: { embedded?: boolean } = {}) {
  const [selection, setSelection] = useState<Selection>({});
  const [geo, setGeo] = useState<GeoChip>("US");
  const [time, setTime] = useState<TimeChip>("2026");
  const [stage, setStage] = useState<StageChip>("wedge");

  const [concepts, frameworks, primitives] = useQueries({
    queries: [conceptsQuery, frameworksQuery, primitivesQuery],
  });

  const loading = concepts.isPending || frameworks.isPending || primitives.isPending;
  const error = concepts.error ?? frameworks.error ?? primitives.error;

  const pyramid = useMemo(
    () => buildPyramid(concepts.data ?? [], frameworks.data ?? [], primitives.data ?? []),
    [concepts.data, frameworks.data, primitives.data],
  );

  const compatible = useMemo(() => compatibleFrameworks(pyramid, selection), [pyramid, selection]);

  // The RESULTING TAM card resolves only when exactly one industry concept is
  // selected — a single concept maps to one /build TAM.
  const industrySel = selection.industry ?? [];
  const soleConcept = industrySel.length === 1 ? industrySel[0] : null;

  const onSelect = (node: PyramidNode, additive: boolean) =>
    setSelection((s) => narrow(s, node, { additive }));

  const Root = embedded ? "div" : "main";

  return (
    <Root className="flex-1 flex flex-col">
      <div className="flex-1 px-8 py-6 max-w-[1400px] mx-auto w-full flex flex-col gap-5">
        <div className="flex flex-col gap-3">
          {embedded ? null : (
            <>
              <h1 className="display text-[28px] text-[var(--fg-1)]">Explore the pyramid</h1>
              <p className="text-[13px] text-[var(--fg-2)] max-w-[640px]">
                Three axes — Qualitative, Quantitative, Industry. Click a node to narrow the view;
                shift-click to OR within a pillar. Incompatible siblings grey out and the right rail
                updates.
              </p>
            </>
          )}
          <PyramidFilters
            geo={geo}
            time={time}
            stage={stage}
            onGeo={setGeo}
            onTime={setTime}
            onStage={setStage}
          />
        </div>

        {error ? (
          <ErrorPanel message={String((error as Error).message ?? error)} />
        ) : loading ? (
          <div className="h-[640px] flex items-center justify-center rounded-[var(--r-4)] border border-[var(--card-border)] text-[13px] text-[var(--fg-3)]">
            Loading registry…
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-5 items-start">
            <PyramidGraph pyramid={pyramid} selection={selection} onSelect={onSelect} />
            <SidePanel
              selection={selection}
              geo={geo}
              time={time}
              stage={stage}
              soleConcept={soleConcept}
              soleConceptName={
                soleConcept
                  ? (pyramid.concepts.find((c) => c.slug === soleConcept)?.name ?? soleConcept)
                  : null
              }
              conceptPrimitives={
                soleConcept
                  ? (primitives.data ?? []).filter((p) => p.concept_slug === soleConcept)
                  : []
              }
              frameworks={compatible}
              totalFrameworks={pyramid.frameworks.length}
              onClear={() => setSelection({})}
            />
          </div>
        )}
      </div>
    </Root>
  );
}

function SidePanel({
  selection,
  geo,
  time,
  stage,
  soleConcept,
  soleConceptName,
  conceptPrimitives,
  frameworks,
  totalFrameworks,
  onClear,
}: {
  selection: Selection;
  geo: GeoChip;
  time: TimeChip;
  stage: StageChip;
  soleConcept: string | null;
  soleConceptName: string | null;
  conceptPrimitives: PrimitiveSummary[];
  frameworks: ReturnType<typeof compatibleFrameworks>;
  totalFrameworks: number;
  onClear: () => void;
}) {
  const activePillars = (Object.keys(selection) as Pillar[]).filter(
    (p) => (selection[p] ?? []).length > 0,
  );
  return (
    <aside className="canvas-card p-5 flex flex-col gap-5" style={{ borderRadius: "var(--r-4)" }}>
      <section>
        <div className="flex items-center justify-between">
          <h2 className="text-[13px] font-medium text-[var(--fg-1)]">Selection</h2>
          {activePillars.length > 0 && (
            <button
              type="button"
              onClick={onClear}
              className="text-[11px] text-[var(--accent)] hover:underline"
            >
              Clear
            </button>
          )}
        </div>
        <div className="text-[11px] text-[var(--fg-3)] mt-1 uppercase tracking-[0.04em]">
          {geo} · {time} · {stage}
        </div>
        {activePillars.length === 0 ? (
          <p className="text-[12px] text-[var(--fg-3)] mt-2">
            No constraints — all {totalFrameworks} frameworks shown.
          </p>
        ) : (
          <ul className="mt-2 flex flex-col gap-1.5">
            {activePillars.map((p) => (
              <li key={p} className="flex items-start gap-2 text-[12px]">
                <span className="text-[10px] uppercase tracking-[0.06em] text-[var(--fg-3)] w-[78px] shrink-0 pt-0.5">
                  {PILLAR_LABEL[p]}
                </span>
                <span className="flex flex-wrap gap-1">
                  {(selection[p] ?? []).map((key) => (
                    <span key={key} className="role-chip role-chip--accent">
                      {lensLabel(key)}
                    </span>
                  ))}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {soleConcept && <ResultingTam slug={soleConcept} name={soleConceptName ?? soleConcept} />}

      {soleConcept && <SourcesPanel primitives={conceptPrimitives} />}

      <section>
        <h2 className="text-[13px] font-medium text-[var(--fg-1)]">
          Compatible frameworks{" "}
          <span className="text-[var(--fg-3)] tabular-nums">
            ({frameworks.length}/{totalFrameworks})
          </span>
        </h2>
        {frameworks.length === 0 ? (
          <p className="text-[12px] text-[var(--fg-3)] mt-2">
            No framework satisfies this combination of constraints.
          </p>
        ) : (
          <ul className="mt-2 flex flex-col gap-2">
            {frameworks.map((f) => (
              <li key={f.slug}>
                <Link
                  href={`/f/${f.slug}`}
                  className="block rounded-[var(--r-2)] border border-[var(--card-border)] px-3 py-2 hover:bg-[var(--bg-2)] transition-colors"
                >
                  <div className="text-[12px] font-medium text-[var(--fg-1)]">{f.name}</div>
                  <div className="flex items-center gap-1.5 mt-1">
                    <span className="role-chip uppercase tracking-[0.04em]">
                      {lensLabel(f.lens)}
                    </span>
                    <span className="role-chip">{lensLabel(f.method_family)}</span>
                    <span className="text-[10px] text-[var(--fg-3)] tabular-nums">
                      {f.input_count} inputs
                    </span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </aside>
  );
}

// RESULTING TAM — the headline number for a single selected industry concept.
// Resolves the concept's /build TAM, shows midpoint + range + the independence
// donut, and links into the full /build workhorse.
function ResultingTam({ slug, name }: { slug: string; name: string }) {
  const build = useQuery(buildQuery(slug));

  return (
    <section className="border-t border-[var(--border-1)] pt-4">
      <h2 className="text-[10px] uppercase tracking-[0.08em] text-[var(--fg-3)]">Resulting TAM</h2>
      {build.isPending ? (
        <p className="text-[12px] text-[var(--fg-3)] mt-2">Sizing {name}…</p>
      ) : build.error || !build.data ? (
        <p className="text-[12px] text-[var(--fg-3)] mt-2">
          No precomputed TAM for this concept yet.
        </p>
      ) : (
        (() => {
          const tam = build.data;
          const range = tamRange(tam);
          const unit = tam.scenarios[0]?.unit;
          const degenerate = isDegenerate(tam);
          return (
            <div className="mt-2 flex items-center gap-4">
              <div className="flex-1">
                <div className="tam-num text-[24px] text-[var(--fg-1)]">
                  {formatCompact(range.mid, unit)}
                </div>
                {degenerate ? (
                  <div className="text-[11px] text-[var(--fg-3)] mt-0.5">
                    single-method estimate
                  </div>
                ) : (
                  <div className="text-[11px] text-[var(--fg-2)] mt-0.5 tabular-nums">
                    {formatCompact(range.low, unit)} – {formatCompact(range.high, unit)}
                  </div>
                )}
                <Link
                  href={`/build?q=${encodeURIComponent(slug)}`}
                  className="inline-block mt-2 text-[12px] font-medium text-[var(--accent)] hover:underline"
                >
                  Open this TAM →
                </Link>
              </div>
              <IndependenceDonut score={tam.independence_score} size={72} strokeWidth={7} />
            </div>
          );
        })()
      )}
    </section>
  );
}

// SOURCES — the selected concept's primitives, each stamped with its source
// tier. Tier lives only on the primitive detail record, so we fetch detail for
// just this concept's (small) primitive set.
function SourcesPanel({ primitives }: { primitives: PrimitiveSummary[] }) {
  const details = useQueries({
    queries: primitives.map((p) => primitiveQuery(p.slug)),
  });

  return (
    <section className="border-t border-[var(--border-1)] pt-4">
      <h2 className="text-[10px] uppercase tracking-[0.08em] text-[var(--fg-3)]">
        Sources{" "}
        <span className="tabular-nums normal-case tracking-normal">({primitives.length})</span>
      </h2>
      {primitives.length === 0 ? (
        <p className="text-[12px] text-[var(--fg-3)] mt-2">No primitives for this concept.</p>
      ) : (
        <ul className="mt-2 flex flex-col gap-2">
          {primitives.map((p, i) => {
            const detail = details[i]?.data;
            // Composite primitives are set-ops over others — they carry no source.
            const tier: SourceTier | null =
              detail && detail.kind === "atomic_primitive" ? detail.source.tier : null;
            return (
              <li key={p.slug} className="flex items-center justify-between gap-2">
                <Link
                  href={`/p/${p.slug}`}
                  className="text-[12px] text-[var(--fg-1)] hover:text-[var(--accent)] truncate"
                  title={p.name}
                >
                  {p.name}
                </Link>
                {tier ? (
                  <TierBadge tier={tier} className="shrink-0" />
                ) : (
                  <span className="role-chip shrink-0">{p.kind}</span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function ErrorPanel({ message }: { message: string }) {
  return (
    <div className="h-[640px] flex flex-col items-center justify-center gap-2 rounded-[var(--r-4)] border border-[var(--card-border)] text-center px-6">
      <div className="text-[13px] font-medium text-[var(--fg-1)]">Could not load the registry</div>
      <div className="text-[12px] text-[var(--fg-3)] max-w-[420px]">{message}</div>
      <div className="text-[11px] text-[var(--fg-3)]">
        Is the backend running at the configured API URL?
      </div>
    </div>
  );
}
