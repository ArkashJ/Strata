"use client";

import { useQueries } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";

import { type GeoChip, PyramidFilters, type TimeChip } from "@/components/PyramidFilters";
import { PyramidGraph } from "@/components/PyramidGraph";
import { lensLabel } from "@/lib/format";
import {
  PILLAR_LABEL,
  type Pillar,
  type PyramidNode,
  type Selection,
  buildPyramid,
  compatibleFrameworks,
  narrow,
} from "@/lib/pyramid";
import { conceptsQuery, frameworksQuery, primitivesQuery } from "@/lib/queries";

export function GraphView() {
  const [selection, setSelection] = useState<Selection>({});
  const [geo, setGeo] = useState<GeoChip>("US");
  const [time, setTime] = useState<TimeChip>("2026");

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

  const onSelect = (node: PyramidNode) => setSelection((s) => narrow(s, node));

  return (
    <main className="flex-1 flex flex-col">
      <div className="flex-1 px-8 py-6 max-w-[1400px] mx-auto w-full flex flex-col gap-5">
        <div className="flex flex-col gap-3">
          <h1 className="display text-[28px] text-[var(--fg-1)]">Explore the pyramid</h1>
          <p className="text-[13px] text-[var(--fg-2)] max-w-[640px]">
            Three axes — Qualitative, Quantitative, Industry. Click a node to narrow the view;
            incompatible siblings grey out and the compatible-frameworks panel updates.
          </p>
          <PyramidFilters geo={geo} time={time} onGeo={setGeo} onTime={setTime} />
        </div>

        {error ? (
          <ErrorPanel message={String((error as Error).message ?? error)} />
        ) : loading ? (
          <div className="h-[600px] flex items-center justify-center rounded-[var(--r-4)] border border-[var(--card-border)] text-[13px] text-[var(--fg-3)]">
            Loading registry…
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-5 items-start">
            <PyramidGraph pyramid={pyramid} selection={selection} onSelect={onSelect} />
            <SidePanel
              selection={selection}
              geo={geo}
              time={time}
              frameworks={compatible}
              totalFrameworks={pyramid.frameworks.length}
              onClear={() => setSelection({})}
            />
          </div>
        )}
      </div>
    </main>
  );
}

function SidePanel({
  selection,
  geo,
  time,
  frameworks,
  totalFrameworks,
  onClear,
}: {
  selection: Selection;
  geo: GeoChip;
  time: TimeChip;
  frameworks: ReturnType<typeof compatibleFrameworks>;
  totalFrameworks: number;
  onClear: () => void;
}) {
  const active = (Object.keys(selection) as Pillar[]).filter((p) => selection[p] !== undefined);
  return (
    <aside className="canvas-card p-5 flex flex-col gap-5" style={{ borderRadius: "var(--r-4)" }}>
      <section>
        <div className="flex items-center justify-between">
          <h2 className="text-[13px] font-medium text-[var(--fg-1)]">Selection</h2>
          {active.length > 0 && (
            <button
              type="button"
              onClick={onClear}
              className="text-[11px] text-[var(--accent)] hover:underline"
            >
              Clear
            </button>
          )}
        </div>
        <div className="text-[11px] text-[var(--fg-3)] mt-1">
          {geo} · {time}
        </div>
        {active.length === 0 ? (
          <p className="text-[12px] text-[var(--fg-3)] mt-2">
            No constraints — all {totalFrameworks} frameworks shown.
          </p>
        ) : (
          <ul className="mt-2 flex flex-col gap-1.5">
            {active.map((p) => (
              <li key={p} className="flex items-center gap-2 text-[12px]">
                <span className="text-[10px] uppercase tracking-[0.06em] text-[var(--fg-3)] w-[78px]">
                  {PILLAR_LABEL[p]}
                </span>
                <span className="role-chip role-chip--accent">{lensLabel(selection[p] ?? "")}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

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

function ErrorPanel({ message }: { message: string }) {
  return (
    <div className="h-[600px] flex flex-col items-center justify-center gap-2 rounded-[var(--r-4)] border border-[var(--card-border)] text-center px-6">
      <div className="text-[13px] font-medium text-[var(--fg-1)]">Could not load the registry</div>
      <div className="text-[12px] text-[var(--fg-3)] max-w-[420px]">{message}</div>
      <div className="text-[11px] text-[var(--fg-3)]">
        Is the backend running at the configured API URL?
      </div>
    </div>
  );
}
