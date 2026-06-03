"use client";

// /build/graph — the user-generated graph builder (Phase 4). Start from a market
// concept, re-bind any framework input to another sourced primitive from the bank,
// and the TAM recomputes live via POST /build/recompute. The minted state_hash is
// the shareable artifact — a different wiring IS a different build. No fabricated
// numbers: every binding is an existing, hash-pinned primitive.
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { formatCompact } from "@/lib/format";
import { buildQuery, conceptsQuery, primitivesQuery, recomputeQuery } from "@/lib/queries";
import type { BuildState } from "@/lib/state-hash";

type Assumptions = Record<string, Record<string, string>>;

export default function GraphBuilderPage() {
  const concepts = useQuery(conceptsQuery);
  const primitives = useQuery(primitivesQuery);
  const [concept, setConcept] = useState("");
  const [assumptions, setAssumptions] = useState<Assumptions>({});

  const base = useQuery({ ...buildQuery(concept), enabled: !!concept });

  const state: BuildState = {
    target_concept_slug: concept,
    frameworks_selected: [],
    framework_assumptions: assumptions,
    primitive_pins: {},
    primitive_overrides: {},
  };
  const recomputed = useQuery(recomputeQuery(state));

  // The live TAM is the recomputed one once the user has re-bound an input,
  // otherwise the concept's own sized build.
  const tam = recomputed.data ?? base.data;

  // unit_label → the primitives that share it, so a swap stays unit-compatible.
  const byUnit = useMemo(() => {
    const m = new Map<string, { slug: string; name: string }[]>();
    for (const p of primitives.data ?? []) {
      const list = m.get(p.unit_label) ?? [];
      list.push({ slug: p.slug, name: p.name });
      m.set(p.unit_label, list);
    }
    return m;
  }, [primitives.data]);

  const unitOf = useMemo(() => {
    const m = new Map<string, string>();
    for (const p of primitives.data ?? []) m.set(p.slug, p.unit_label);
    return m;
  }, [primitives.data]);

  const headline = useMemo(() => {
    const vals = (tam?.scenarios ?? []).map((s) => s.value).filter((v) => Number.isFinite(v));
    if (!vals.length) return null;
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    const cur = { dimension: "currency" as const };
    return lo === hi ? formatCompact(lo, cur) : `${formatCompact(lo, cur)} – ${formatCompact(hi, cur)}`;
  }, [tam]);

  function rebind(framework: string, role: string, slug: string) {
    setAssumptions((prev) => {
      const next: Assumptions = { ...prev, [framework]: { ...(prev[framework] ?? {}) } };
      if (slug) next[framework][role] = slug;
      else delete next[framework][role];
      if (Object.keys(next[framework]).length === 0) delete next[framework];
      return next;
    });
  }

  return (
    <main className="mx-auto flex w-full max-w-[var(--content-max,1100px)] flex-1 flex-col gap-6 px-8 py-8">
      <header className="flex flex-col gap-2">
        <h1 className="display text-[32px] leading-[1.05] text-[var(--fg-1)]">Build a graph</h1>
        <p className="max-w-[680px] text-[14px] text-[var(--fg-3)]">
          Compose your own TAM from the data bank: start from a market, then re-bind any framework
          input to a different sourced primitive. The TAM recomputes live and mints a shareable URL —
          every number stays traceable to a snapshot.
        </p>
      </header>

      <label className="flex flex-col gap-1">
        <span className="text-[12px] uppercase tracking-[0.06em] text-[var(--fg-3)]">Market</span>
        <select
          className="max-w-[480px] rounded-[8px] border border-[var(--border-1)] bg-[var(--bg-1)] px-3 py-2 text-[14px] text-[var(--fg-1)]"
          value={concept}
          onChange={(e) => {
            setConcept(e.target.value);
            setAssumptions({});
          }}
        >
          <option value="">Select a market…</option>
          {(concepts.data ?? []).map((c) => (
            <option key={c.slug} value={c.slug}>
              {c.name}
            </option>
          ))}
        </select>
      </label>

      {!concept ? (
        <EmptyState title="Pick a market to start" description="Then re-wire its inputs below." />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <section className="flex flex-col gap-4">
            {(tam?.scenarios ?? []).map((s) => (
              <div
                key={`${s.framework}-${s.framework_variant}`}
                className="rounded-[12px] border border-[var(--border-1)] bg-[var(--bg-1)] p-4"
              >
                <div className="flex items-center justify-between gap-2">
                  <code className="text-[13px] text-[var(--fg-1)]">{s.framework}</code>
                  <span className="tabular-nums text-[13px] text-[var(--fg-2)]">
                    {formatCompact(s.value, { dimension: "currency" })}
                  </span>
                </div>
                <div className="mt-3 flex flex-col gap-3">
                  {s.inputs_used.map((inp) => {
                    const unit = unitOf.get(inp.primitive_slug) ?? "";
                    const options = byUnit.get(unit) ?? [];
                    const current = assumptions[s.framework]?.[inp.role_name] ?? inp.primitive_slug;
                    return (
                      <label key={inp.role_name} className="flex flex-col gap-1">
                        <span className="text-[11px] uppercase tracking-[0.05em] text-[var(--fg-3)]">
                          {inp.role_name}
                        </span>
                        <select
                          className="rounded-[8px] border border-[var(--border-1)] bg-[var(--bg-0)] px-2.5 py-1.5 text-[12.5px] text-[var(--fg-1)]"
                          value={current}
                          onChange={(e) => rebind(s.framework, inp.role_name, e.target.value)}
                        >
                          {/* Always include the current binding even if it has a one-off unit. */}
                          {!options.some((o) => o.slug === inp.primitive_slug) ? (
                            <option value={inp.primitive_slug}>{inp.primitive_slug}</option>
                          ) : null}
                          {options.map((o) => (
                            <option key={o.slug} value={o.slug}>
                              {o.name}
                            </option>
                          ))}
                        </select>
                      </label>
                    );
                  })}
                </div>
              </div>
            ))}
          </section>

          <aside className="flex h-fit flex-col gap-3 rounded-[12px] border border-[var(--border-1)] bg-[var(--bg-1)] p-5">
            <span className="text-[12px] uppercase tracking-[0.06em] text-[var(--fg-3)]">
              Resulting TAM {recomputed.isFetching ? "· recomputing…" : ""}
            </span>
            <div className="display text-[28px] text-[var(--fg-1)]">{headline ?? "—"}</div>
            <div className="text-[12px] text-[var(--fg-3)]">
              {(tam?.scenarios?.length ?? 0)} method
              {(tam?.scenarios?.length ?? 0) === 1 ? "" : "s"} ·{" "}
              {Object.keys(assumptions).length > 0 ? "custom wiring" : "concept defaults"}
            </div>
            {tam?.state_hash ? (
              <div className="mt-2 flex flex-col gap-2">
                <Link
                  href={`/tam/${tam.state_hash}`}
                  className="rounded-[8px] bg-[var(--accent)] px-3 py-2 text-center text-[13px] font-medium text-[var(--bg-0)] hover:opacity-90"
                >
                  Open & share this TAM →
                </Link>
                <Link
                  href={`/build/${tam.state_hash}`}
                  className="text-center font-mono text-[11px] text-[var(--accent)] hover:underline"
                >
                  edit in the workhorse
                </Link>
              </div>
            ) : null}
          </aside>
        </div>
      )}
    </main>
  );
}
