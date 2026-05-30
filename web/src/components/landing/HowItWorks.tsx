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
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {STEPS.map((s, i) => (
          <Reveal key={s.n} delay={i * 0.07}>
            <div className="canvas-card h-full p-5">
              <span className="tam-num text-[13px] text-[var(--accent)]">{s.n}</span>
              <h3 className="mt-2 text-[15px] font-medium text-[var(--fg-1)]">{s.title}</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-[var(--fg-2)]">{s.body}</p>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
