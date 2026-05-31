"use client";

// Prediction-market signals (T1 · /signals). The `prediction_market` primitives
// quarantined to data/signals/ (Q20). They NEVER feed a TAM — this is a separate,
// honestly-labelled surface of live Kalshi event probabilities + contract volumes,
// each carrying a source URL + SHA256 snapshot pin. The loud banner makes the
// quarantine explicit so a reader never mistakes a signal for a sized number.
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { ListHeader } from "@/components/ui/ListHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { signalsQuery } from "@/lib/queries";
import type { SignalSummary } from "@/lib/schemas";

const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });

function formatValue(s: SignalSummary): string {
  if (s.unit_dimension === "percent") return `${(s.value * 100).toFixed(1)}%`;
  return compact.format(s.value);
}

export default function SignalsPage() {
  const signals = useQuery(signalsQuery);
  const [filter, setFilter] = useState("");

  const groups = useMemo(() => {
    const rows = signals.data ?? [];
    const q = filter.trim().toLowerCase();
    const matched = rows.filter(
      (s) =>
        !q || s.name.toLowerCase().includes(q) || s.slug.includes(q) || s.concept_slug.includes(q),
    );
    const byConcept = new Map<string, SignalSummary[]>();
    for (const s of matched) {
      const list = byConcept.get(s.concept_slug) ?? [];
      list.push(s);
      byConcept.set(s.concept_slug, list);
    }
    return [...byConcept.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [signals.data, filter]);

  const total = useMemo(() => groups.reduce((n, [, list]) => n + list.length, 0), [groups]);

  return (
    <main className="flex flex-1 flex-col">
      <ListHeader
        title="Signals"
        count={total}
        filter={filter}
        onFilter={setFilter}
        placeholder="Filter signals…"
      />

      <div className="mx-auto w-full max-w-[1280px] flex-1 px-8 py-8">
        <div className="mb-6 rounded-[var(--r-3)] border border-[var(--border-2)] bg-[var(--bg-2)] px-4 py-3 text-[13px] leading-relaxed text-[var(--fg-2)]">
          <span className="font-medium text-[var(--fg-1)]">Prediction-market signals.</span> Live
          event probabilities and contract volumes from Kalshi. These are{" "}
          <span className="font-medium text-[var(--fg-1)]">never used to size a TAM</span> — they
          are quarantined from every framework (Q20) and shown read-only. Each carries a source link
          and a SHA256 snapshot pin, so you can read a market signal next to a sized number without
          the two ever being mixed.
        </div>

        {signals.isPending ? (
          <div className="flex flex-col gap-3">
            {Array.from({ length: 8 }, (_, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: fixed-length placeholder, index is stable
              <Skeleton key={i} className="h-[56px]" />
            ))}
          </div>
        ) : signals.error ? (
          <ErrorState error={signals.error} onRetry={() => signals.refetch()} />
        ) : total === 0 ? (
          <EmptyState
            title="No signals match"
            description={filter ? "Nothing matches the current filter." : "No signals loaded."}
          />
        ) : (
          <div className="flex flex-col gap-8">
            {groups.map(([concept, list]) => (
              <section key={concept}>
                <h2 className="mb-3 font-mono text-[11px] uppercase tracking-wide text-[var(--fg-3)]">
                  {concept} · {list.length}
                </h2>
                <div className="flex flex-col divide-y divide-[var(--border-1)] rounded-[var(--r-3)] border border-[var(--border-1)]">
                  {list.map((s) => (
                    <SignalRow key={s.slug} signal={s} />
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}

function SignalRow({ signal: s }: { signal: SignalSummary }) {
  return (
    <div className="flex items-center justify-between gap-4 px-4 py-3">
      <div className="min-w-0">
        <div className="truncate text-[13px] text-[var(--fg-1)]">{s.name}</div>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-[var(--fg-3)]">
          <span className="rounded-[var(--r-round)] bg-[var(--bg-3)] px-1.5 py-0.5 font-mono uppercase tracking-wide">
            prediction market
          </span>
          <span className="tabular-nums">as of {s.as_of}</span>
          {s.uncertainty_low != null && s.uncertainty_high != null ? (
            <span className="tabular-nums" title={s.uncertainty_basis ?? undefined}>
              range {s.uncertainty_low}–{s.uncertainty_high}
            </span>
          ) : null}
          <a
            href={s.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-[var(--accent)] hover:underline"
            title={`snapshot ${s.snapshot_sha256.slice(0, 12)}…`}
          >
            source ↗
          </a>
        </div>
      </div>
      <div className="shrink-0 text-right">
        <div className="text-[16px] font-medium tabular-nums text-[var(--fg-1)]">
          {formatValue(s)}
        </div>
        <div className="font-mono text-[10px] uppercase tracking-wide text-[var(--fg-4)]">
          {s.unit_dimension}
        </div>
      </div>
    </div>
  );
}
