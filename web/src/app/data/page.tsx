"use client";

import Link from "next/link";
import { useState } from "react";

import { JsonExplorer } from "@/components/JsonExplorer";
import { ScenarioBarChart } from "@/components/ScenarioBarChart";
import { WaterfallChart } from "@/components/WaterfallChart";
import { type BuildResponse, type Scenario, formatUSD, getBuild } from "@/lib/api";

const CONCEPT_SLUG = "pc-doc-gen-tam-us";

export default function DataDashboard() {
  const [build, setBuild] = useState<BuildResponse | null>(null);
  const [activeScenario, setActiveScenario] = useState<Scenario | null>(null);
  const [tab, setTab] = useState<"charts" | "json">("charts");

  if (!build) {
    getBuild(CONCEPT_SLUG).then(setBuild);
    return (
      <main className="flex-1 flex items-center justify-center text-[13px] text-[var(--fg-3)]">
        Loading data…
      </main>
    );
  }

  const midpoint = (build.triangulated_range.low + build.triangulated_range.high) / 2;

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
            href={`/build?q=${encodeURIComponent("Doc-gen P&C")}`}
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
            Data Dashboard · {build.target.geo} · {build.target.time}
          </div>
          <h1 className="display text-[36px] mt-2 text-[var(--fg-1)]">
            {build.target.concept_name}
          </h1>
          <div className="flex items-baseline gap-4 mt-3">
            <span className="tam-num text-[32px] text-[var(--fg-1)]">{formatUSD(midpoint)}</span>
            <span className="text-[13px] text-[var(--fg-2)]">
              range {formatUSD(build.triangulated_range.low)} –{" "}
              {formatUSD(build.triangulated_range.high)}
            </span>
          </div>
        </div>

        {tab === "charts" ? (
          <div className="flex flex-col gap-8">
            <section className="canvas-card p-6" style={{ borderRadius: "var(--r-4)" }}>
              <h2 className="text-[15px] font-medium text-[var(--fg-1)] mb-4">
                Scenario comparison
              </h2>
              <ScenarioBarChart scenarios={build.scenarios} />
            </section>

            <section className="canvas-card p-6" style={{ borderRadius: "var(--r-4)" }}>
              <h2 className="text-[15px] font-medium text-[var(--fg-1)] mb-2">Input waterfall</h2>
              <p className="text-[12px] text-[var(--fg-3)] mb-4">
                Select a scenario to see how its inputs multiply into the final TAM value.
              </p>
              <div className="flex gap-2 mb-4">
                {build.scenarios.map((s) => (
                  <button
                    type="button"
                    key={s.framework_slug}
                    onClick={() => setActiveScenario(s)}
                    className={`px-3 py-1.5 rounded-[var(--r-2)] text-[12px] font-medium transition-colors ${
                      activeScenario?.framework_slug === s.framework_slug
                        ? "bg-[var(--accent)] text-[var(--accent-fg-on)]"
                        : "bg-[var(--bg-2)] text-[var(--fg-2)] hover:bg-[var(--bg-3)]"
                    }`}
                  >
                    {s.framework_name}
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
                      <th className="pb-3 pr-4">Unit</th>
                      <th className="pb-3 pr-4">Role</th>
                      <th className="pb-3">Framework</th>
                    </tr>
                  </thead>
                  <tbody>
                    {build.scenarios.flatMap((s) =>
                      s.inputs_used.map((input) => (
                        <tr
                          key={`${s.framework_slug}-${input.primitive_slug}`}
                          className="border-t border-[var(--border-1)]"
                        >
                          <td className="py-2.5 pr-4 text-[var(--fg-1)]">{input.primitive_name}</td>
                          <td className="py-2.5 pr-4 font-mono tabular-nums text-[var(--fg-1)]">
                            {input.value >= 1000
                              ? Intl.NumberFormat("en", {
                                  notation: "compact",
                                  maximumFractionDigits: 1,
                                }).format(input.value)
                              : input.value}
                          </td>
                          <td className="py-2.5 pr-4 text-[var(--fg-3)]">{input.unit_label}</td>
                          <td className="py-2.5 pr-4">
                            <span className="role-chip">{input.role.replace(/_/g, " ")}</span>
                          </td>
                          <td className="py-2.5 text-[var(--fg-2)]">{s.framework_name}</td>
                        </tr>
                      )),
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="canvas-card p-6" style={{ borderRadius: "var(--r-4)" }}>
              <h2 className="text-[15px] font-medium text-[var(--fg-1)] mb-4">Architecture</h2>
              <pre className="font-mono text-[12px] text-[var(--fg-2)] leading-[1.6] overflow-x-auto whitespace-pre">
                {`
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STRATA  DATA  FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   data/*.yaml          backend/           API              web/             │
│  ┌───────────┐    ┌─────────────┐    ┌──────────┐    ┌──────────────┐      │
│  │ sources/  │───▶│   Loader    │───▶│ /p/{slug}│───▶│ Landing (/)  │      │
│  │ primitives│    │  (PyYAML)   │    │ /f/{slug}│    │   ↓ query    │      │
│  │ composites│    ├─────────────┤    │ /c/{slug}│    │ Build (/build)│     │
│  │ frameworks│───▶│  Registry   │───▶│/build/{s}│───▶│   ↓ graph   │      │
│  │ concepts/ │    │  (in-mem)   │    │ /tam/{h} │    │ Data (/data) │      │
│  │ tam_outs/ │    ├─────────────┤    └──────────┘    │   ↓ charts  │      │
│  └───────────┘    │ Validator   │                     └──────────────┘      │
│                    │  L1: struct │                                           │
│                    │  L2: semantic│                                          │
│                    │  L3: x-ref  │                                           │
│                    ├─────────────┤                                           │
│                    │  Evaluator  │                                           │
│                    │  (multiply) │                                           │
│                    └─────────────┘                                           │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                         FIVE-LAYER  MODEL                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Concept ─────── measured-by ──────▶ Atomic Primitive                      │
│      │                                     │                                │
│      │                              bundled-into                            │
│      │                                     ▼                                │
│      │                            Composite Primitive                       │
│      │                                     │                                │
│      │                              consumed-by                             │
│      │                                     ▼                                │
│      └──── sized-by ──────────▶   Framework                                │
│                                        │                                    │
│                                     emits                                   │
│                                        ▼                                    │
│                                  TAM Output                                 │
│                              (scenario tree)                                │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                      SCENARIO  TREE  SHAPE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                    ┌──────────────────┐                                      │
│                    │   TARGET TAM     │                                      │
│                    │   $113M midpoint │                                      │
│                    └────────┬─────────┘                                      │
│              ┌──────────────┼──────────────┐                                │
│              ▼              ▼              ▼                                 │
│   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                       │
│   │ Bottoms-up   │ │  Top-down    │ │   Analog     │                       │
│   │  $47M        │ │  $213M       │ │   $80M       │                       │
│   └──────┬───────┘ └──────┬───────┘ └──────┬───────┘                       │
│      ┌───┴───┐        ┌───┴───┐        ┌───┴───┐                           │
│      ▼       ▼        ▼       ▼        ▼       ▼                            │
│  ┌──────┐┌──────┐ ┌──────┐┌──────┐ ┌──────┐┌──────┐                       │
│  │2.8K  ││$480  │ │$14.2B││1.5%  │ │$450M ││0.18  │                       │
│  │carrs ││/seat │ │spend ││share │ │HC TAM││ratio │                       │
│  └──────┘└──────┘ └──────┘└──────┘ └──────┘└──────┘                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
`}
              </pre>
            </section>
          </div>
        ) : (
          <JsonExplorer data={build} />
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
