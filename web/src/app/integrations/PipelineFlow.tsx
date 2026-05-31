"use client";

// Wave 5C / AC5C.4 — animated sources → engine → verifier → outputs flow. Uses
// the shared motion layer (FadeIn/Stagger), which collapses to an instant,
// offset-free render under prefers-reduced-motion.
import { FadeIn, Stagger, StaggerItem } from "@/components/ui/motion";

const STAGES: { title: string; items: string[] }[] = [
  { title: "Sources", items: ["Gov data (15)", "Web (Exa)", "Your SaaS"] },
  { title: "Strata engine", items: ["Documents", "Web", "Data analysis"] },
  { title: "Verifier", items: ["Citations", "Units", "Outliers"] },
  { title: "Outputs", items: ["TAM", "Report", "API", "MCP"] },
];

function Stage({ title, items, delay }: { title: string; items: string[]; delay: number }) {
  return (
    <FadeIn delay={delay} className="flex min-w-[150px] flex-1 flex-col gap-2">
      <div className="text-[11px] uppercase tracking-[0.08em] text-[var(--fg-3)]">{title}</div>
      <Stagger className="flex flex-col gap-1.5">
        {items.map((it) => (
          <StaggerItem key={it} className="canvas-card px-3 py-1.5 text-[12px] text-[var(--fg-1)]">
            {it}
          </StaggerItem>
        ))}
      </Stagger>
    </FadeIn>
  );
}

export function PipelineFlow() {
  return (
    <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-start">
      {STAGES.map((s, i) => (
        <div key={s.title} className="flex flex-1 items-start gap-3">
          <Stage title={s.title} items={s.items} delay={i * 0.08} />
          {i < STAGES.length - 1 ? (
            <div className="hidden self-center text-[var(--fg-4)] sm:block" aria-hidden="true">
              →
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
