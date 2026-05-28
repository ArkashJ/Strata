/**
 * Pipeline trace component — renders ``ResolverResult.events`` as a vertical
 * step list. Mirrors what ``strata goal --stream`` prints in the terminal,
 * styled for the build view's right rail.
 */

"use client";

import type { PipelineEvent } from "@/lib/resolver-schemas";

function eventLabel(event: PipelineEvent): string {
  const payload = event.payload as Record<string, unknown>;
  switch (event.kind) {
    case "parsing":
      return `Parsing: ${String(payload.query ?? "")}`;
    case "slug_resolved": {
      const intent = payload.intent ?? "?";
      const hint = payload.framework_hint;
      return `Slug resolver: intent=${intent}${hint ? `, framework_hint=${hint}` : ""}`;
    }
    case "concept_hit":
      return `Step 1: concept hit → ${payload.concept_slug}`;
    case "primitive_hit":
      return `Step 2: primitive hit → ${payload.slug} = ${payload.value}`;
    case "router_decision":
      return `Step 3: router → ${payload.connector}.${payload.method} (conf=${payload.confidence})`;
    case "connector_call":
      return `Step 3: calling ${payload.connector}.${payload.method}`;
    case "wrote_primitive":
      return `wrote ${payload.path}`;
    case "budget_exceeded":
      return `expansion budget exceeded (${payload.budget})`;
    case "searching": {
      const role = payload.role ?? payload.primitive_name;
      return `Step 4: searching ${role}`;
    }
    case "framework_selected":
      return `Step 4: framework=${payload.framework}`;
    case "evaluating":
      return "evaluating...";
    case "result":
      return "done";
    case "error":
      return `error[${event.step}]: ${event.message ?? payload.error ?? "unknown"}`;
    default:
      return `${event.kind}[${event.step}]`;
  }
}

function stepColor(step: PipelineEvent["step"]): string {
  switch (step) {
    case "pre":
      return "text-[var(--fg-2)]";
    case "1":
      return "text-emerald-500";
    case "2":
      return "text-sky-500";
    case "3":
      return "text-amber-500";
    case "4":
      return "text-violet-500";
    default:
      return "text-[var(--fg-2)]";
  }
}

export type PipelineTraceProps = {
  events: PipelineEvent[];
  emptyMessage?: string;
};

export function PipelineTrace({
  events,
  emptyMessage = "No pipeline events yet.",
}: PipelineTraceProps) {
  if (events.length === 0) {
    return <p className="text-sm text-[var(--fg-2)]">{emptyMessage}</p>;
  }
  return (
    <ol className="space-y-1 font-mono text-xs">
      {events.map((event, idx) => (
        <li
          key={`${event.kind}-${event.step}-${idx}`}
          className={`flex gap-2 ${event.kind === "error" ? "text-rose-500" : "text-[var(--fg-1)]"}`}
        >
          <span className={`shrink-0 ${stepColor(event.step)}`}>[{event.step}]</span>
          <span>{eventLabel(event)}</span>
        </li>
      ))}
    </ol>
  );
}
