"use client";

// Graph composer — the "compose your own TAM" mode of the build workshop
// (formerly the standalone /build/graph route, folded in per the restructure plan
// §2). Start from a market concept, re-bind any framework input to another sourced
// primitive from the bank (unit-compatible only), and the TAM recomputes live via
// POST /build/recompute. The minted state_hash is the shareable artifact — a
// different wiring IS a different build. No fabricated numbers: every binding is an
// existing, hash-pinned primitive.
//
// The recompute contract is identical to the rest of /build: re-bindings are
// carried as framework_assumptions (role_name → primitive_slug) on the BuildState,
// which needsRecompute() picks up so the result is sized server-side, never locally.

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useId, useMemo, useState } from "react";

import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Skeleton } from "@/components/ui/Skeleton";
import { formatCompact } from "@/lib/format";
import { buildQuery, conceptsQuery, primitivesQuery, recomputeQuery } from "@/lib/queries";
import type { BuildState } from "@/lib/state-hash";

type Assumptions = Record<string, Record<string, string>>;

const CURRENCY = { dimension: "currency" as const };

export function GraphComposer() {
  const concepts = useQuery(conceptsQuery);
  const primitives = useQuery(primitivesQuery);
  const [concept, setConcept] = useState("");
  const [assumptions, setAssumptions] = useState<Assumptions>({});
  const marketSelectId = useId();

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
  const hasRewiring = Object.keys(assumptions).length > 0;

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
    return lo === hi
      ? formatCompact(lo, CURRENCY)
      : `${formatCompact(lo, CURRENCY)} – ${formatCompact(hi, CURRENCY)}`;
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

  // The composer needs both lists before it can offer a market or a unit-matched
  // swap; surface their loading / error states honestly rather than rendering an
  // empty <select>.
  const setupError = concepts.error ?? primitives.error;
  if (setupError) {
    return (
      <Shell>
        <ErrorState
          title="Could not load the data bank"
          error={setupError}
          onRetry={() => {
            void concepts.refetch();
            void primitives.refetch();
          }}
        />
      </Shell>
    );
  }
  if (concepts.isPending || primitives.isPending) {
    return (
      <Shell>
        <Skeleton className="h-10 w-[480px] max-w-full" />
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <Skeleton className="h-[320px] w-full" />
          <Skeleton className="h-[200px] w-full" />
        </div>
      </Shell>
    );
  }

  const conceptOptions = concepts.data ?? [];
  // base is the live TAM source while no rewiring is in play; reflect its state.
  const buildError = concept && !hasRewiring ? base.error : null;
  const recomputeError = concept && hasRewiring ? recomputed.error : null;

  return (
    <Shell>
      <label htmlFor={marketSelectId} className="flex flex-col gap-1">
        <span className="text-[12px] uppercase tracking-[0.06em] text-[var(--fg-3)]">Market</span>
        <select
          id={marketSelectId}
          className="max-w-[480px] rounded-[var(--r-1)] border border-[var(--border-2)] bg-[var(--bg-1)] px-3 py-2 text-[14px] text-[var(--fg-1)] outline-none focus:border-[var(--accent)]"
          value={concept}
          onChange={(e) => {
            setConcept(e.target.value);
            setAssumptions({});
          }}
        >
          <option value="">Select a market…</option>
          {conceptOptions.map((c) => (
            <option key={c.slug} value={c.slug}>
              {c.name}
            </option>
          ))}
        </select>
      </label>

      {!concept ? (
        <EmptyState
          title="Pick a market to start"
          description="Then re-wire its framework inputs to other sourced primitives below."
        />
      ) : buildError || recomputeError ? (
        <ErrorState
          title={recomputeError ? "Could not recompute with your wiring" : "Could not size this market"}
          error={recomputeError ?? buildError}
          onRetry={() => (recomputeError ? recomputed.refetch() : base.refetch())}
        />
      ) : !tam && (base.isPending || recomputed.isPending) ? (
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <Skeleton className="h-[320px] w-full" />
          <Skeleton className="h-[200px] w-full" />
        </div>
      ) : (tam?.scenarios?.length ?? 0) === 0 ? (
        <EmptyState
          title="No methods size this market yet"
          description="This concept has no framework results to re-wire. Pick another market."
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <section className="flex flex-col gap-4">
            {(tam?.scenarios ?? []).map((s) => (
              <div
                key={`${s.framework}-${s.framework_variant}`}
                className="rounded-[var(--r-3)] border border-[var(--border-1)] bg-[var(--bg-1)] p-4"
              >
                <div className="flex items-center justify-between gap-2">
                  <code className="text-[13px] text-[var(--fg-1)]">{s.framework}</code>
                  <span className="tabular-nums text-[13px] text-[var(--fg-2)]">
                    {formatCompact(s.value, CURRENCY)}
                  </span>
                </div>
                <div className="mt-3 flex flex-col gap-3">
                  {s.inputs_used.map((inp) => {
                    const unit = unitOf.get(inp.primitive_slug) ?? "";
                    const options = byUnit.get(unit) ?? [];
                    const current = assumptions[s.framework]?.[inp.role_name] ?? inp.primitive_slug;
                    const swapped = current !== inp.primitive_slug;
                    return (
                      <label key={inp.role_name} className="flex flex-col gap-1">
                        <span className="text-[11px] uppercase tracking-[0.05em] text-[var(--fg-3)]">
                          {inp.role_name}
                          {swapped ? (
                            <span className="ml-1.5 normal-case tracking-normal text-[var(--accent)]">
                              · re-wired
                            </span>
                          ) : null}
                        </span>
                        <select
                          aria-label={`${inp.role_name} input for ${s.framework}`}
                          className="rounded-[var(--r-1)] border border-[var(--border-2)] bg-[var(--bg-0)] px-2.5 py-1.5 text-[12.5px] text-[var(--fg-1)] outline-none focus:border-[var(--accent)]"
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

          <aside className="flex h-fit flex-col gap-3 rounded-[var(--r-3)] border border-[var(--border-1)] bg-[var(--bg-1)] p-5">
            <span className="text-[12px] uppercase tracking-[0.06em] text-[var(--fg-3)]">
              Resulting TAM
            </span>
            <div className="display text-[28px] text-[var(--fg-1)]" aria-live="polite">
              {recomputed.isFetching ? (
                <Skeleton className="h-8 w-32" />
              ) : (
                (headline ?? "—")
              )}
            </div>
            <div className="text-[12px] text-[var(--fg-3)]">
              {(tam?.scenarios?.length ?? 0)} method
              {(tam?.scenarios?.length ?? 0) === 1 ? "" : "s"} ·{" "}
              {hasRewiring ? "custom wiring" : "concept defaults"}
            </div>
            {tam?.state_hash ? (
              <div className="mt-2 flex flex-col gap-2">
                <Link
                  href={`/tam/${tam.state_hash}`}
                  className="rounded-[var(--r-2)] bg-[var(--accent)] px-3 py-2 text-center text-[13px] font-medium text-[var(--accent-fg-on)] transition-colors hover:bg-[var(--accent-hover)]"
                >
                  Open &amp; share this TAM
                </Link>
                <Link
                  href={`/build/${tam.state_hash}`}
                  className="text-center font-mono text-[11px] text-[var(--accent)] hover:underline"
                >
                  edit in the workshop
                </Link>
              </div>
            ) : null}
          </aside>
        </div>
      )}
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col gap-6">{children}</div>;
}
