"use client";

import { useEffect, useRef, useState } from "react";

import { env } from "@/lib/env";
import { formatCompact, formatUSD, lensLabel, tierLabel } from "@/lib/format";

interface PrimitiveNeeded {
  role: string;
  description: string;
}

interface PrimitiveUsed {
  role: string;
  name: string;
  value: number;
  source_url: string;
}

interface StepUnit {
  kind: string;
  dimension: string;
  currency?: string | null;
  denominator?: string | null;
}

interface Step {
  type: string;
  message?: string;
  // parsed
  lens?: string;
  concept_name?: string;
  definition?: string;
  primitives_needed?: PrimitiveNeeded[];
  // primitive_found
  role?: string;
  name?: string;
  value?: number;
  unit?: StepUnit;
  source_url?: string;
  source_tier?: string;
  // framework_selected
  formula?: string;
  // result fields
  tam_value?: number;
  formatted_tam?: string;
  framework_name?: string;
  primitives_used?: PrimitiveUsed[];
}

export function ResolveView({ query, onBack }: { query: string; onBack: () => void }) {
  const [steps, setSteps] = useState<Step[]>([]);
  const [result, setResult] = useState<Step | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const abortController = new AbortController();

    async function stream() {
      try {
        const res = await fetch(`${env.NEXT_PUBLIC_API_URL}/resolve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query }),
          signal: abortController.signal,
        });

        if (!res.ok || !res.body) {
          setError("Failed to start resolution");
          setDone(true);
          return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        try {
          while (true) {
            const { done: streamDone, value } = await reader.read();
            if (streamDone) break;

            buffer += decoder.decode(value, { stream: true });

            // Parse SSE events from buffer — events are separated by double newlines
            const events = buffer.split("\n\n");
            buffer = events.pop() ?? ""; // Keep incomplete event in buffer

            for (const eventBlock of events) {
              if (!eventBlock.trim()) continue;
              const lines = eventBlock.split("\n");
              let eventType = "";
              const dataLines: string[] = [];
              for (const line of lines) {
                if (line.startsWith("event: ")) eventType = line.slice(7).trim();
                if (line.startsWith("data: ")) dataLines.push(line.slice(6).trim());
              }
              const data = dataLines.join("\n");

              if (!data) continue;

              let parsed: Step;
              try {
                parsed = JSON.parse(data) as Step;
              } catch {
                continue;
              }

              if (eventType === "step") {
                setSteps((prev) => [...prev, parsed]);
              } else if (eventType === "result") {
                setResult(parsed);
              } else if (eventType === "error") {
                setError(parsed.message ?? "Unknown error");
              } else if (eventType === "done") {
                setDone(true);
              }
            }
          }
        } finally {
          reader.releaseLock();
        }

        setDone(true);
      } catch (e) {
        if (!abortController.signal.aborted) {
          setError(e instanceof Error ? e.message : "Stream failed");
          setDone(true);
        }
      }
    }

    void stream();
    return () => abortController.abort();
  }, [query]);

  // Auto-scroll to bottom as steps arrive
  // biome-ignore lint/correctness/useExhaustiveDependencies: intentional — scroll on every step/result change
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [steps, result]);

  return (
    <main className="flex-1 flex flex-col">
      {/* Header */}
      <header className="w-full px-8 py-5 flex items-center justify-between border-b border-[var(--border-1)]">
        <button
          type="button"
          aria-label="Back to search"
          onClick={onBack}
          className="display text-[20px] text-[var(--fg-1)] hover:text-[var(--accent)] transition-colors"
        >
          ← Strata
        </button>
        <div className="text-[12px] text-[var(--fg-3)] font-mono">
          {done ? "resolved" : "resolving…"}
        </div>
      </header>

      <div className="flex-1 flex flex-col px-8 py-8 max-w-[800px] mx-auto w-full gap-4">
        {/* Label + query title */}
        <div className="text-[11px] tracking-[0.04em] uppercase text-[var(--fg-3)]">
          Dynamic TAM Resolution
        </div>
        <h1 className="display text-[32px] text-[var(--fg-1)] leading-[1.1]">
          &ldquo;{query}&rdquo;
        </h1>

        {/* Step feed */}
        <div className="flex flex-col gap-3 mt-6">
          {steps.map((step, i) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: append-only stream, index is stable
            <StepCard key={i} step={step} />
          ))}
        </div>

        {/* Result card */}
        {result && (
          <div className="canvas-card px-6 py-5 mt-4" style={{ borderRadius: "var(--r-3)" }}>
            <div className="text-[11px] tracking-[0.04em] uppercase text-[var(--fg-3)]">Result</div>
            <div className="text-[18px] text-[var(--fg-1)] font-medium mt-1">
              {result.concept_name}
            </div>
            <div className="tam-num text-[48px] text-[var(--fg-1)] mt-2">
              {result.formatted_tam ??
                (result.tam_value !== undefined ? formatUSD(result.tam_value) : "—")}
            </div>
            <div className="text-[13px] text-[var(--fg-2)] mt-2">
              {result.framework_name}
              {result.lens ? ` · ${lensLabel(result.lens)}` : ""}
            </div>
            {result.primitives_used && result.primitives_used.length > 0 && (
              <div className="mt-4 flex flex-col gap-2">
                {result.primitives_used.map((p, idx) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: static result list
                  <div key={idx} className="flex items-center justify-between text-[13px]">
                    <span className="text-[var(--fg-2)]">{p.name}</span>
                    <a
                      href={p.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[var(--accent)] hover:underline tabular-nums"
                    >
                      {formatCompactValue(p.value)} ↗
                    </a>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="px-4 py-3 rounded-[var(--r-3)] bg-red-50 text-red-700 text-[13px]">
            {error}
          </div>
        )}

        {/* Loading pulse */}
        {!done && (
          <div className="flex items-center gap-2 text-[13px] text-[var(--fg-3)]">
            <span className="animate-pulse">●</span> Thinking…
          </div>
        )}

        <div ref={scrollRef} />
      </div>
    </main>
  );
}

function StepCard({ step }: { step: Step }) {
  switch (step.type) {
    case "parsing":
    case "searching":
    case "evaluating":
      return (
        <div className="flex items-center gap-2 text-[13px] text-[var(--fg-2)]">
          <span className="text-[var(--accent)]">→</span>
          {step.message}
        </div>
      );

    case "parsed":
      return (
        <div className="canvas-card px-4 py-3" style={{ borderRadius: "var(--r-2)" }}>
          <div className="text-[12px] text-[var(--fg-1)] font-medium">{step.concept_name}</div>
          {step.definition && (
            <div className="text-[11px] text-[var(--fg-3)] mt-1">{step.definition}</div>
          )}
          {step.lens && (
            <div className="flex gap-2 mt-2">
              <span className="role-chip uppercase tracking-[0.04em]">{lensLabel(step.lens)}</span>
            </div>
          )}
          {step.primitives_needed && step.primitives_needed.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {step.primitives_needed.map((p) => (
                <span
                  key={p.role}
                  className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--bg-2)] text-[var(--fg-3)]"
                >
                  {p.role.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          )}
        </div>
      );

    case "primitive_found":
      return (
        <div
          className="flex items-center justify-between px-4 py-2.5 canvas-card"
          style={{ borderRadius: "var(--r-2)" }}
        >
          <div className="flex flex-col gap-0.5">
            <span className="text-[12px] text-[var(--fg-1)]">{step.name}</span>
            <span className="text-[10px] text-[var(--fg-3)]">
              {step.source_tier ? tierLabel(step.source_tier) : ""}
              {step.source_tier && step.role ? " · " : ""}
              {step.role?.replace(/_/g, " ")}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="tam-num text-[15px] text-[var(--fg-1)] tabular-nums">
              {step.value !== undefined ? formatCompactValue(step.value, step.unit) : "—"}
            </span>
            {step.source_url && (
              <a
                href={step.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[10px] text-[var(--accent)] hover:underline"
              >
                source ↗
              </a>
            )}
          </div>
        </div>
      );

    case "framework_selected":
      return (
        <div className="flex items-center gap-2 text-[13px] text-[var(--fg-2)]">
          <span className="text-[var(--accent)]">◆</span>
          Framework: <span className="text-[var(--fg-1)] font-medium">{step.name}</span>
          {step.formula && (
            <span className="text-[var(--fg-3)] font-mono text-[11px]">{step.formula}</span>
          )}
        </div>
      );

    default:
      return (
        <div className="text-[13px] text-[var(--fg-3)]">{step.message ?? JSON.stringify(step)}</div>
      );
  }
}

function formatCompactValue(value: number, unit?: StepUnit | null): string {
  // Delegate to the shared formatCompact when unit info is available
  if (unit) {
    return formatCompact(value, {
      dimension: unit.dimension,
      currency: unit.currency ?? null,
      denominator: unit.denominator ?? null,
    });
  }
  // Fallback: compact notation without unit context
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(1)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  if (value > 0 && value < 1) return `${(value * 100).toFixed(1)}%`;
  return value.toLocaleString();
}
