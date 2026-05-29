"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { JsonExplorer } from "@/components/JsonExplorer";
import { ScenarioBarChart } from "@/components/ScenarioBarChart";
import { WaterfallChart } from "@/components/WaterfallChart";
import { formatCompact, formatUSD } from "@/lib/format";
import { buildQuery } from "@/lib/queries";
import type { Scenario } from "@/lib/schemas";

// A real, registry-backed concept so /data exercises the live /build endpoint.
const CONCEPT_SLUG = "doc-gen-pc-insurance";

export default function DataDashboard() {
  const build = useQuery(buildQuery(CONCEPT_SLUG));
  const [activeScenario, setActiveScenario] = useState<Scenario | null>(null);
  const [tab, setTab] = useState<"charts" | "json">("charts");

  if (build.isLoading) {
    return (
      <main className="flex-1 flex items-center justify-center text-[13px] text-[var(--fg-3)]">
        Loading data…
      </main>
    );
  }

  if (build.error || !build.data) {
    return (
      <main className="flex-1 flex items-center justify-center text-[13px] text-[var(--fg-3)]">
        Could not load TAM for “{CONCEPT_SLUG}”.
      </main>
    );
  }

  const tam = build.data;
  const values = tam.scenarios.map((s) => s.value);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const midpoint = values.reduce((a, b) => a + b, 0) / values.length;

  return (
    <main className="flex-1 flex flex-col">
      {/* Page-specific controls — global chrome lives in AppShell. */}
      <header className="w-full px-8 py-3 flex items-center justify-end border-b border-[var(--border-1)]">
        <div className="flex items-center gap-4">
          <nav className="flex gap-1 p-1 bg-[var(--bg-2)] rounded-[var(--r-2)]">
            <TabButton active={tab === "charts"} onClick={() => setTab("charts")}>
              Charts
            </TabButton>
            <TabButton active={tab === "json"} onClick={() => setTab("json")}>
              JSON
            </TabButton>
          </nav>
          <Link
            href={`/build?q=${encodeURIComponent(CONCEPT_SLUG)}`}
            className="px-3 py-1.5 rounded-[var(--r-2)] bg-[var(--accent)] text-[var(--accent-fg-on)]
                       text-[12px] font-medium hover:bg-[var(--accent-hover)] transition-colors"
          >
            Open in Build →
          </Link>
        </div>
      </header>

      <div className="flex-1 px-8 py-8 max-w-[1280px] mx-auto w-full">
        <div className="mb-8">
          <div className="text-[11px] tracking-[0.04em] uppercase text-[var(--fg-3)]">
            Data Dashboard · {tam.target.geo ?? "Global"} · {tam.target.time ?? "latest"}
          </div>
          <h1 className="display text-[36px] mt-2 text-[var(--fg-1)]">
            {tam.target.concept_name ?? tam.target.concept.replace(/-/g, " ")}
          </h1>
          <div className="flex items-baseline gap-4 mt-3">
            <span className="tam-num text-[32px] text-[var(--fg-1)]">{formatUSD(midpoint)}</span>
            <span className="text-[13px] text-[var(--fg-2)]">
              range {formatUSD(low)} – {formatUSD(high)}
            </span>
          </div>
        </div>

        {tab === "charts" ? (
          <div className="flex flex-col gap-8">
            <section className="canvas-card p-6" style={{ borderRadius: "var(--r-4)" }}>
              <h2 className="text-[15px] font-medium text-[var(--fg-1)] mb-4">
                Scenario comparison
              </h2>
              <ScenarioBarChart scenarios={tam.scenarios} />
            </section>

            <section className="canvas-card p-6" style={{ borderRadius: "var(--r-4)" }}>
              <h2 className="text-[15px] font-medium text-[var(--fg-1)] mb-2">Input waterfall</h2>
              <p className="text-[12px] text-[var(--fg-3)] mb-4">
                Select a scenario to see how its inputs multiply into the final TAM value.
              </p>
              <div className="flex gap-2 mb-4 flex-wrap">
                {tam.scenarios.map((s) => (
                  <button
                    type="button"
                    key={s.framework}
                    onClick={() => setActiveScenario(s)}
                    className={`px-3 py-1.5 rounded-[var(--r-2)] text-[12px] font-medium transition-colors ${
                      activeScenario?.framework === s.framework
                        ? "bg-[var(--accent)] text-[var(--accent-fg-on)]"
                        : "bg-[var(--bg-2)] text-[var(--fg-2)] hover:bg-[var(--bg-3)]"
                    }`}
                  >
                    {s.definition}
                  </button>
                ))}
              </div>
              {activeScenario ? (
                <WaterfallChart scenario={activeScenario} />
              ) : (
                <div className="h-[300px] flex items-center justify-center text-[13px] text-[var(--fg-3)]">
                  Click a scenario above
                </div>
              )}
            </section>

            <section className="canvas-card p-6" style={{ borderRadius: "var(--r-4)" }}>
              <h2 className="text-[15px] font-medium text-[var(--fg-1)] mb-4">Primitives table</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-[13px]">
                  <thead>
                    <tr className="text-left text-[11px] uppercase tracking-[0.04em] text-[var(--fg-3)]">
                      <th className="pb-3 pr-4">Primitive</th>
                      <th className="pb-3 pr-4">Value</th>
                      <th className="pb-3 pr-4">Role</th>
                      <th className="pb-3">Framework</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tam.scenarios.flatMap((s) =>
                      s.inputs_used.map((input) => (
                        <tr
                          key={`${s.framework}-${input.primitive_slug}`}
                          className="border-t border-[var(--border-1)]"
                        >
                          <td className="py-2.5 pr-4 text-[var(--fg-1)]">
                            {input.name ?? input.primitive_slug.replace(/-/g, " ")}
                          </td>
                          <td className="py-2.5 pr-4 font-mono tabular-nums text-[var(--fg-1)]">
                            {input.value != null
                              ? formatCompact(input.value, input.unit)
                              : input.role_name}
                          </td>
                          <td className="py-2.5 pr-4">
                            <span className="role-chip">{input.role.replace(/_/g, " ")}</span>
                          </td>
                          <td className="py-2.5 text-[var(--fg-2)]">{s.definition}</td>
                        </tr>
                      )),
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        ) : (
          <JsonExplorer data={tam} />
        )}
      </div>
    </main>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-1 rounded-[var(--r-1)] text-[12px] font-medium transition-colors ${
        active
          ? "bg-[var(--bg-1)] text-[var(--fg-1)] shadow-sm"
          : "text-[var(--fg-3)] hover:text-[var(--fg-2)]"
      }`}
    >
      {children}
    </button>
  );
}
