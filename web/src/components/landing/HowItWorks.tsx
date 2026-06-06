"use client";

/**
 * Concise three-step "how it works" strip: ask → compute → edit & recompute.
 * Text only — no fabricated numbers. Each step reveals on scroll with a small
 * stagger via <Reveal>; reduced-motion users get an instant fade.
 */

import { Reveal } from "./Reveal";

const STEPS = [
  {
    n: "01",
    title: "Ask",
    body: "Describe a market in plain language. Strata parses it into constraints and picks the analysis lens.",
  },
  {
    n: "02",
    title: "Compute",
    body: "It wires sourced primitives into a framework and emits a scenario-tree range — every input traces to a citation.",
  },
  {
    n: "03",
    title: "Edit & recompute",
    body: "Swap a primitive, adjust an assumption, toggle a framework. The range recomputes live, with a fresh shareable URL.",
  },
];

export function HowItWorks() {
  return (
    <section className="px-8 pb-12 max-w-[1280px] mx-auto w-full">
      <Reveal>
        <h2 className="text-[11px] font-medium uppercase tracking-[0.1em] text-[var(--fg-3)] mb-5">
          How it works
        </h2>
      </Reveal>
      {/* A numbered ledger sequence, not a feature-card grid: the step numbers
          are a connected spine on a hairline rule (editorial, flat-by-default),
          so the eye reads ask → compute → edit as one process, not three
          isolated boxes. Stacks on mobile. */}
      <div className="grid grid-cols-1 gap-8 border-t border-[var(--border-1)] pt-6 md:grid-cols-3 md:gap-6">
        {STEPS.map((s, i) => (
          <Reveal key={s.n} delay={i * 0.07}>
            <div className="flex flex-col">
              <div className="flex items-baseline gap-2.5">
                <span className="tam-num text-[24px] leading-none text-[var(--accent)]">{s.n}</span>
                <h3 className="text-[15px] font-medium text-[var(--fg-1)]">{s.title}</h3>
              </div>
              <p className="mt-2.5 max-w-[34ch] text-[13px] leading-relaxed text-[var(--fg-2)]">
                {s.body}
              </p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
