"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { LineageGraph } from "@/components/LineageGraph";
import { ScenarioGraph } from "@/components/ScenarioGraph";
import { formatUSD } from "@/lib/format";
import { buildQuery, conceptsQuery } from "@/lib/queries";
import type { TAMOutput } from "@/lib/schemas";

export function BuildView() {
  const router = useRouter();
  const params = useSearchParams();
  const query = params.get("q") ?? "";

  const concepts = useQuery(conceptsQuery);
  const matchedSlug = concepts.data?.find(
    (c) => c.name.toLowerCase().includes(query.toLowerCase()),
  )?.slug ?? concepts.data?.[0]?.slug ?? "";

  const build = useQuery(buildQuery(matchedSlug));

  if (concepts.isLoading || build.isLoading) {
    return (
      <main className="flex-1 flex items-center justify-center text-[13px] text-[var(--fg-3)]">
        Sizing…
      </main>
    );
  }

  if (build.error || !build.data) {
    return (
      <main className="flex-1 flex flex-col items-center justify-center px-8 gap-4">
        <p className="text-[14px] text-[var(--fg-2)]">
          {build.error instanceof Error ? build.error.message : "No build available for this query."}
        </p>
        <Link href="/" className="text-[13px] text-[var(--accent)] hover:underline">
          ← Back to search
        </Link>
      </main>
    );
  }

  return <BuildResult tam={build.data} onBack={() => router.push("/")} />;
}

function BuildResult({ tam, onBack }: { tam: TAMOutput; onBack: () => void }) {
  const [lineageOpen, setLineageOpen] = useState(false);
  const values = tam.scenarios.map((s) => s.value);
  const midpoint = values.reduce((a, b) => a + b, 0) / values.length;
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);

  return (
    <main className="flex-1 flex flex-col">
      <header className="w-full px-8 py-5 flex items-center justify-between border-b border-[var(--border-1)]">
        <button
          onClick={onBack}
          className="display text-[20px] text-[var(--fg-1)] hover:text-[var(--accent)] transition-colors"
        >
          ← Strata
        </button>
        <div className="flex items-center gap-3 text-[12px] text-[var(--fg-3)]">
          <span className="font-mono">
            /build/{tam.state_hash.slice(0, 8)}
          </span>
          <CopyButton />
        </div>
      </header>

      <div className="flex-1 flex flex-row gap-8 px-8 py-8 max-w-[1280px] mx-auto w-full">
        <section className="flex-1 flex flex-col gap-6 min-w-0">
          <div>
            <div className="text-[11px] tracking-[0.04em] uppercase text-[var(--fg-3)]">
              TAM · {tam.target.geo ?? "Global"} · {tam.target.time ?? "latest"}
            </div>
            <h1 className="display text-[40px] mt-2 text-[var(--fg-1)] leading-[1.05]">
              {tam.target.concept_name ?? tam.target.concept.replace(/-/g, " ")}
            </h1>
          </div>

          <div className="flex items-baseline gap-6">
            <div>
              <div className="text-[11px] tracking-[0.04em] uppercase text-[var(--fg-3)]">
                Triangulated midpoint
              </div>
              <div className="tam-num text-[48px] text-[var(--fg-1)] mt-1">
                {formatUSD(midpoint)}
              </div>
              <div className="text-[13px] text-[var(--fg-3)] mt-1">
                Range: {formatUSD(minVal)} — {formatUSD(maxVal)}
              </div>
            </div>
            <div className="text-[13px] text-[var(--fg-2)] pb-2">
              {tam.scenarios.length} scenarios
              <span className="mx-2 text-[var(--fg-4)]">·</span>
              independence{" "}
              <span className="text-[var(--fg-1)] font-medium">
                {tam.independence_score.toFixed(2)}
              </span>
            </div>
          </div>

          <ScenarioGraph tam={tam} />

          {tam.uses_modeled_composites && (
            <div className="flex items-start gap-3 px-4 py-3 rounded-[var(--r-3)]
                            bg-[var(--tier-analyst-tint)] text-[13px] text-[var(--fg-2)]">
              <span className="font-medium text-[var(--tier-analyst)]">Modeled composite</span>
              <span>
                One scenario uses an analog-penetration composite.
                Result depends on the analog assumption.
              </span>
            </div>
          )}
        </section>

        <aside className="w-[320px] shrink-0 flex flex-col gap-3">
          <RailSection title="Frameworks" count={tam.scenarios.length} defaultOpen>
            <ul className="flex flex-col gap-2 mt-1">
              {tam.scenarios.map((s) => (
                <li
                  key={s.framework}
                  className="canvas-card flex items-center justify-between px-3 py-2.5"
                  style={{ borderRadius: "var(--r-2)" }}
                >
                  <div className="flex flex-col min-w-0 gap-1">
                    <span className="text-[13px] text-[var(--fg-1)] truncate">
                      {s.definition}
                    </span>
                    <span className="role-chip self-start uppercase tracking-[0.04em]">
                      {s.lens.replace(/_/g, " ")}
                    </span>
                  </div>
                  <span className="tam-num text-[15px] text-[var(--fg-1)] tabular-nums">
                    {formatUSD(s.value)}
                  </span>
                </li>
              ))}
            </ul>
          </RailSection>
          <RailSection title="Independence" badge={tam.independence_score.toFixed(2)}>
            <div className="text-[13px] text-[var(--fg-2)] leading-[1.5]">
              {tam.method_families_used.length} method families ·{" "}
              {tam.scenarios.length} scenarios. Higher is better.
            </div>
          </RailSection>
          <RailSection title="Lineage graph">
            <button
              onClick={() => setLineageOpen(true)}
              className="text-[13px] text-[var(--accent)] hover:underline"
            >
              Open lineage modal →
            </button>
          </RailSection>
        </aside>
      </div>

      <LineageGraph tam={tam} open={lineageOpen} onClose={() => setLineageOpen(false)} />
    </main>
  );
}

function CopyButton() {
  return (
    <button
      className="px-3 py-1.5 rounded-[var(--r-2)] bg-[var(--bg-2)] text-[var(--fg-2)]
                 hover:bg-[var(--bg-3)] hover:text-[var(--fg-1)] transition-colors"
      onClick={() => {
        if (typeof window !== "undefined") {
          navigator.clipboard.writeText(window.location.href);
        }
      }}
    >
      Copy link
    </button>
  );
}

function RailSection({
  title,
  badge,
  count,
  defaultOpen = false,
  children,
}: {
  title: string;
  badge?: string;
  count?: number;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="canvas-card" style={{ borderRadius: "var(--r-3)" }}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-left"
      >
        <span className="text-[13px] font-medium text-[var(--fg-1)] flex items-center gap-2">
          <span className="text-[var(--fg-3)]">{open ? "▾" : "▸"}</span>
          {title}
          {count !== undefined && (
            <span className="text-[var(--fg-3)] font-normal">{count}</span>
          )}
        </span>
        {badge && (
          <span className="text-[12px] text-[var(--fg-2)] tabular-nums">{badge}</span>
        )}
      </button>
      {open && <div className="px-4 pb-3">{children}</div>}
    </section>
  );
}
