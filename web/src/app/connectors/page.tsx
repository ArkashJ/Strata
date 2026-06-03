"use client";

// Connector explorer (/connectors). Answers "how do the connectors come into
// play": each typed connector turns a regulator/aggregator API into hash-pinned
// atomic primitives that frameworks consume to size a TAM. Connectors that have
// actually produced primitives in the bank lead (with a live count + a sample you
// can open); capability-only connectors are listed honestly below as "wired, not
// yet ingested". All read-only — no live API calls.
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { ListHeader } from "@/components/ui/ListHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { tierLabel } from "@/lib/format";
import { connectorsQuery } from "@/lib/queries";
import type { Connector } from "@/lib/schemas";

const TIER_TOKEN: Record<string, string> = {
  regulator: "var(--success)",
  aggregator: "var(--accent)",
  analyst: "var(--warning)",
  "analyst-paraphrase": "var(--warning)",
  prediction_market: "var(--warning)",
  community: "var(--fg-3)",
};

export default function ConnectorsPage() {
  const q = useQuery(connectorsQuery);
  const [filter, setFilter] = useState("");

  const { active, wired, totalPrimitives } = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    const rows = (q.data ?? []).filter(
      (c) =>
        !needle ||
        c.connector.toLowerCase().includes(needle) ||
        c.source_tier.toLowerCase().includes(needle) ||
        c.capabilities.some((cap) => cap.returns.toLowerCase().includes(needle)),
    );
    const active = rows
      .filter((c) => c.primitives_in_bank > 0)
      .sort((a, b) => b.primitives_in_bank - a.primitives_in_bank);
    const wired = rows
      .filter((c) => c.primitives_in_bank === 0)
      .sort((a, b) => a.connector.localeCompare(b.connector));
    const totalPrimitives = active.reduce((n, c) => n + c.primitives_in_bank, 0);
    return { active, wired, totalPrimitives };
  }, [q.data, filter]);

  return (
    <main className="flex flex-1 flex-col">
      <ListHeader
        title="Connectors"
        count={(q.data ?? []).length}
        filter={filter}
        onFilter={setFilter}
        placeholder="Filter by name, tier, or what it returns…"
      />

      <div className="mx-auto w-full max-w-[1100px] flex-1 px-8 py-8">
        {/* The pipeline, stated plainly. */}
        <div className="mb-7 rounded-[var(--r-3)] border border-[var(--border-2)] bg-[var(--bg-2)] px-5 py-4">
          <div className="text-[13px] leading-relaxed text-[var(--fg-2)]">
            <span className="font-medium text-[var(--fg-1)]">How a number gets here.</span> Every
            sourced primitive is manufactured by a typed connector — a regulator or aggregator API,
            disk-cached and SHA-256 snapshot-pinned. Frameworks then multiply those primitives into
            a TAM. The connector is why each number is defensible: its tier comes from the source
            host, never an LLM.
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2 font-mono text-[11px] text-[var(--fg-3)]">
            {["API", "typed client", "snapshot pin", "atomic primitive", "framework", "TAM"].map(
              (step, i) => (
                <span key={step} className="flex items-center gap-2">
                  {i > 0 ? <span className="text-[var(--fg-4)]">→</span> : null}
                  <span className="rounded-[var(--r-round)] bg-[var(--bg-3)] px-2 py-0.5">
                    {step}
                  </span>
                </span>
              ),
            )}
          </div>
        </div>

        {q.isPending ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 9 }, (_, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: fixed-length placeholder
              <Skeleton key={i} className="h-[150px]" />
            ))}
          </div>
        ) : q.error ? (
          <ErrorState error={q.error} onRetry={() => q.refetch()} />
        ) : (q.data ?? []).length === 0 ? (
          <EmptyState title="No connectors" description="The connector catalog is empty." />
        ) : (
          <>
            <SectionLabel>
              Producing data now · {active.length} connectors · {totalPrimitives.toLocaleString()}{" "}
              primitives in the bank
            </SectionLabel>
            <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {active.map((c) => (
                <ConnectorCard key={c.connector} connector={c} />
              ))}
            </div>

            <SectionLabel className="mt-9">
              Wired, not yet ingested · {wired.length} connectors
            </SectionLabel>
            <p className="mt-1 text-[12px] text-[var(--fg-3)]">
              Typed and ready; no primitives in the current bank yet. We never synthesize a sample —
              an empty connector is shown empty.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {wired.map((c) => (
                <span
                  key={c.connector}
                  className="rounded-[var(--r-round)] border border-[var(--border-2)] bg-[var(--bg-1)] px-3 py-1 font-mono text-[11px] text-[var(--fg-3)]"
                  title={`${c.method_count} methods · ${tierLabel(c.source_tier)}`}
                >
                  {c.connector}
                </span>
              ))}
            </div>
          </>
        )}
      </div>
    </main>
  );
}

function SectionLabel({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <h2
      className={`font-mono text-[11px] uppercase tracking-[0.1em] text-[var(--fg-3)] ${className ?? ""}`}
    >
      {children}
    </h2>
  );
}

function ConnectorCard({ connector: c }: { connector: Connector }) {
  const token = TIER_TOKEN[c.source_tier] ?? "var(--fg-3)";
  return (
    <div className="canvas-card flex flex-col p-5">
      <div className="flex items-start justify-between gap-2">
        <div className="text-[15px] font-medium text-[var(--fg-1)]">{c.connector}</div>
        <span
          className="rounded-[var(--r-round)] px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide"
          style={{ color: token, background: "color-mix(in srgb, currentColor 14%, transparent)" }}
        >
          {tierLabel(c.source_tier)}
        </span>
      </div>

      <div className="mt-1 text-[12px] text-[var(--fg-3)]">
        <span className="tabular-nums text-[var(--fg-1)]">{c.primitives_in_bank}</span> primitives ·{" "}
        {c.method_count} query method{c.method_count === 1 ? "" : "s"}
      </div>

      {c.capabilities[0] ? (
        <div className="mt-3 text-[12px] leading-relaxed text-[var(--fg-2)]">
          {c.capabilities[0].returns}
        </div>
      ) : null}

      {c.sample_primitive_slug ? (
        <Link
          href={`/p/${c.sample_primitive_slug}`}
          className="mt-auto pt-3 font-mono text-[11px] text-[var(--accent)] hover:underline"
        >
          sample → {c.sample_primitive_slug}
        </Link>
      ) : null}
    </div>
  );
}
