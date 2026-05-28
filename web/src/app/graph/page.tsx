"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useCallback, useMemo, useState } from "react";

import { type Axis, PyramidGraph, type Selection } from "@/components/PyramidGraph";
import { lensLabel } from "@/lib/format";
import { conceptsQuery, frameworksQuery } from "@/lib/queries";
import type { ConceptSummary, FrameworkSummary } from "@/lib/schemas";

const EMPTY_SELECTION: Selection = {
  qualitative: null,
  quantitative: null,
  industry: null,
};

/**
 * Geo / time live as filter chips above the graph, never as pyramid axes
 * (product-surface lock U1 / Q12). They narrow which Industry (concept) leaves
 * stay lit. Concept summaries don't carry structured geo at v0.2, so chips
 * match against tokens in the concept name — a best-effort filter, not a claim
 * of structured geo data.
 */
const GEO_CHIPS = [
  { id: "all", label: "All geos", tokens: [] as string[] },
  { id: "us", label: "US", tokens: ["us", "united states", "u.s."] },
  { id: "eu", label: "EU / Europe", tokens: ["eu", "europe", "european"] },
  { id: "global", label: "Global", tokens: ["global", "worldwide", "world"] },
];

const TIME_CHIPS = [
  { id: "all", label: "All years" },
  { id: "2026", label: "2026" },
  { id: "2027", label: "2027" },
];

export default function GraphPage() {
  const concepts = useQuery(conceptsQuery);
  const frameworks = useQuery(frameworksQuery);

  const [selection, setSelection] = useState<Selection>(EMPTY_SELECTION);
  const [geo, setGeo] = useState("all");
  const [time, setTime] = useState("all");

  const toggleSelect = useCallback((axis: Axis, value: string) => {
    setSelection((prev) => ({
      ...prev,
      [axis]: prev[axis] === value ? null : value,
    }));
  }, []);

  const clearAll = useCallback(() => {
    setSelection(EMPTY_SELECTION);
    setGeo("all");
    setTime("all");
  }, []);

  const conceptList = useMemo(() => concepts.data ?? [], [concepts.data]);
  const frameworkList = useMemo(() => frameworks.data ?? [], [frameworks.data]);

  // Geo chip narrows the set of allowed Industry (concept) leaves.
  const industryAllow = useMemo<Set<string> | null>(() => {
    const chip = GEO_CHIPS.find((g) => g.id === geo);
    if (!chip || chip.tokens.length === 0) return null;
    const allow = new Set<string>();
    for (const c of conceptList) {
      const hay = `${c.name} ${c.slug}`.toLowerCase();
      if (chip.tokens.some((t) => hay.includes(t))) allow.add(c.slug);
    }
    return allow;
  }, [geo, conceptList]);

  const compatibleFrameworks = useMemo(
    () => frameworkList.filter((f) => frameworkMatches(f, selection)),
    [frameworkList, selection],
  );

  const isLoading = concepts.isLoading || frameworks.isLoading;
  const hasError = concepts.error || frameworks.error;
  const activeCount =
    (selection.qualitative ? 1 : 0) +
    (selection.quantitative ? 1 : 0) +
    (selection.industry ? 1 : 0);

  return (
    <main className="flex-1 flex flex-col">
      <header className="w-full px-8 py-5 flex items-center justify-between border-b border-[var(--border-1)]">
        <Link
          href="/"
          className="display text-[20px] text-[var(--fg-1)] hover:text-[var(--accent)] transition-colors"
        >
          ← Strata
        </Link>
        <div className="text-[12px] text-[var(--fg-3)]">Pyramid graph · read-only</div>
      </header>

      <div className="flex-1 px-8 py-6 max-w-[1280px] mx-auto w-full flex flex-col min-h-0">
        <div className="mb-4">
          <div className="text-[11px] tracking-[0.04em] uppercase text-[var(--fg-3)]">
            Explore the market space
          </div>
          <h1 className="display text-[32px] mt-1 text-[var(--fg-1)]">
            Qualitative · Quantitative · Industry
          </h1>
          <p className="text-[13px] text-[var(--fg-2)] mt-2 max-w-[640px]">
            Click any leaf to narrow on that axis. Incompatible siblings grey out, and the right
            rail shows the frameworks that survive every active constraint.
          </p>
        </div>

        {/* Geo / time filter chips — above the graph, never an axis. */}
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3 mb-4">
          <ChipRow
            label="Geo"
            chips={GEO_CHIPS.map((c) => ({ id: c.id, label: c.label }))}
            active={geo}
            onSelect={setGeo}
          />
          <ChipRow label="Time" chips={TIME_CHIPS} active={time} onSelect={setTime} />
          {(activeCount > 0 || geo !== "all" || time !== "all") && (
            <button
              type="button"
              onClick={clearAll}
              className="text-[12px] text-[var(--accent)] hover:underline ml-auto"
            >
              Clear all ({activeCount} on graph)
            </button>
          )}
        </div>

        {isLoading ? (
          <div className="flex-1 flex items-center justify-center text-[13px] text-[var(--fg-3)] min-h-[420px]">
            Loading registry…
          </div>
        ) : hasError ? (
          <div className="flex-1 flex items-center justify-center text-[13px] text-[var(--danger)] min-h-[420px]">
            Could not reach the registry. Is the backend running?
          </div>
        ) : (
          <div className="flex-1 flex flex-col md:flex-row gap-6 min-h-0">
            <section className="flex-1 min-w-0 min-h-[520px] flex">
              <PyramidGraph
                concepts={conceptList}
                frameworks={frameworkList}
                selection={selection}
                industryAllow={industryAllow}
                onSelect={toggleSelect}
              />
            </section>

            <aside className="w-full md:w-[320px] md:shrink-0 flex flex-col gap-3">
              <ActiveConstraints
                selection={selection}
                concepts={conceptList}
                onClear={(axis) => toggleSelect(axis, selection[axis] ?? "")}
              />
              <CompatibleFrameworks
                frameworks={compatibleFrameworks}
                total={frameworkList.length}
              />
            </aside>
          </div>
        )}
      </div>
    </main>
  );
}

function frameworkMatches(f: FrameworkSummary, selection: Selection): boolean {
  if (selection.qualitative && f.lens !== selection.qualitative) return false;
  if (selection.quantitative && f.method_family !== selection.quantitative) return false;
  return true;
}

function ChipRow({
  label,
  chips,
  active,
  onSelect,
}: {
  label: string;
  chips: { id: string; label: string }[];
  active: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)]">{label}</span>
      <div className="flex flex-wrap gap-1.5">
        {chips.map((chip) => (
          <button
            type="button"
            key={chip.id}
            onClick={() => onSelect(chip.id)}
            aria-pressed={active === chip.id}
            className={`px-3 py-1 rounded-[var(--r-round)] text-[12px] font-medium transition-colors ${
              active === chip.id
                ? "bg-[var(--accent)] text-[var(--accent-fg-on)]"
                : "bg-[var(--bg-2)] text-[var(--fg-2)] hover:bg-[var(--bg-3)] hover:text-[var(--fg-1)]"
            }`}
          >
            {chip.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function ActiveConstraints({
  selection,
  concepts,
  onClear,
}: {
  selection: Selection;
  concepts: ConceptSummary[];
  onClear: (axis: Axis) => void;
}) {
  const rows: { axis: Axis; label: string; value: string }[] = [];
  if (selection.qualitative)
    rows.push({
      axis: "qualitative",
      label: "Qualitative",
      value: lensLabel(selection.qualitative),
    });
  if (selection.quantitative)
    rows.push({
      axis: "quantitative",
      label: "Quantitative",
      value: lensLabel(selection.quantitative),
    });
  if (selection.industry) {
    const c = concepts.find((x) => x.slug === selection.industry);
    rows.push({
      axis: "industry",
      label: "Industry",
      value: c?.name ?? selection.industry,
    });
  }

  return (
    <section className="canvas-card px-4 py-3" style={{ borderRadius: "var(--r-3)" }}>
      <div className="text-[13px] font-medium text-[var(--fg-1)] mb-2">Active constraints</div>
      {rows.length === 0 ? (
        <div className="text-[12px] text-[var(--fg-3)]">
          None — the whole space is shown. Click a leaf to narrow.
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {rows.map((r) => (
            <li key={r.axis} className="flex items-center justify-between gap-2 text-[12px]">
              <span className="text-[var(--fg-3)] uppercase tracking-[0.04em] text-[11px]">
                {r.label}
              </span>
              <span className="text-[var(--fg-1)] truncate flex-1 text-right">{r.value}</span>
              <button
                type="button"
                onClick={() => onClear(r.axis)}
                aria-label={`Clear ${r.label} constraint`}
                className="text-[var(--fg-3)] hover:text-[var(--danger)] transition-colors"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function CompatibleFrameworks({
  frameworks,
  total,
}: {
  frameworks: FrameworkSummary[];
  total: number;
}) {
  return (
    <section className="canvas-card px-4 py-3" style={{ borderRadius: "var(--r-3)" }}>
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-[13px] font-medium text-[var(--fg-1)]">Compatible frameworks</span>
        <span className="text-[12px] text-[var(--fg-3)] tabular-nums">
          {frameworks.length}/{total}
        </span>
      </div>
      {frameworks.length === 0 ? (
        <div className="text-[12px] text-[var(--fg-3)]">
          No framework matches the current constraints.
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {frameworks.map((f) => (
            <li
              key={f.slug}
              className="flex flex-col gap-1 rounded-[var(--r-2)] bg-[var(--bg-2)] px-3 py-2"
            >
              <span className="text-[13px] text-[var(--fg-1)] leading-[1.3]">{f.name}</span>
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="role-chip uppercase tracking-[0.04em]">{lensLabel(f.lens)}</span>
                <span className="role-chip uppercase tracking-[0.04em]">
                  {lensLabel(f.method_family)}
                </span>
                <span className="text-[11px] text-[var(--fg-3)] ml-auto tabular-nums">
                  {f.input_count} inputs
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
