"use client";

/**
 * Signed-out first impression. Split editorial on the night canvas: the thesis +
 * value props + auth CTAs on the left, a live product glyph (the Strata pyramid
 * tracing into a concept→framework→primitive→TAM pipeline) on the right. No app
 * chrome — the sidebar only appears once you're in. Every figure here is abstract
 * or explicitly illustrative; no fabricated numbers (CLAUDE.md).
 */

import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";

import { Logo } from "@/components/shell/Logo";
import { PyramidGlyph } from "./PyramidGlyph";

const EASE_OUT = [0.16, 1, 0.3, 1] as const;

const VALUE_PROPS = [
  {
    title: "Sourced numbers",
    body: "Every input traces to a citation, pinned by content hash. No invented figures.",
  },
  {
    title: "Top-down ∧ bottoms-up",
    body: "Independent methods cross-checked against each other — a range, not one lonely guess.",
  },
  {
    title: "Cite it in a memo",
    body: "A shareable TAM with a full chain of custody you can paste straight into the deck.",
  },
];

export function PublicLanding() {
  const reduce = useReducedMotion();

  const rise = (delay: number) => ({
    initial: reduce ? { opacity: 0 } : { opacity: 0, y: 14 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.5, ease: EASE_OUT, delay: reduce ? 0 : delay },
  });

  return (
    <>
      {/* Slim brand bar — no sidebar. */}
      <header className="flex items-center justify-between px-6 py-5 sm:px-10">
        <div className="flex items-center gap-2.5">
          <Logo />
          <span className="display text-[18px] italic leading-none text-[var(--night-fg-1)]">
            Strata
          </span>
          <span className="font-mono text-[10px] text-[var(--night-fg-3)]">v0.42</span>
        </div>
        <Link
          href="/sign-in"
          className="rounded-[10px] border border-white/10 bg-white/[0.04] px-4 py-2 text-[13px] text-[var(--night-fg-1)] transition-colors hover:bg-white/[0.08]"
        >
          Sign in
        </Link>
      </header>

      {/* Hero grid */}
      <main className="flex flex-1 items-center px-6 py-10 sm:px-10">
        <div className="mx-auto grid w-full max-w-[1180px] grid-cols-1 items-center gap-10 lg:grid-cols-[1.05fr_0.95fr]">
          {/* Left: thesis */}
          <div>
            <motion.p
              {...rise(0)}
              className="mb-5 text-[11px] font-medium uppercase tracking-[0.16em] text-[var(--night-accent)]"
            >
              Defensible market sizing for VCs &amp; operators
            </motion.p>

            <motion.h1
              {...rise(0.06)}
              className="display text-[52px] leading-[1.0] text-[var(--night-fg-1)] sm:text-[68px]"
            >
              Defensible <span className="italic text-[var(--night-accent)]">TAM</span>, fast.
            </motion.h1>

            <motion.p
              {...rise(0.12)}
              className="mt-6 max-w-[480px] text-[15px] leading-relaxed text-[var(--night-fg-2)]"
            >
              Type any market. Strata picks the frameworks, pre-fills the primitives from sourced
              numbers, and gives you a range you can actually defend.
            </motion.p>

            <motion.ul {...rise(0.18)} className="mt-8 flex flex-col gap-3.5">
              {VALUE_PROPS.map((p) => (
                <li key={p.title} className="flex gap-3">
                  <span
                    aria-hidden="true"
                    className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--night-accent)]"
                  />
                  <span className="text-[13.5px] leading-snug text-[var(--night-fg-2)]">
                    <span className="font-medium text-[var(--night-fg-1)]">{p.title}</span>
                    <span className="text-[var(--night-fg-3)]"> — {p.body}</span>
                  </span>
                </li>
              ))}
            </motion.ul>

            <motion.div {...rise(0.26)} className="mt-9 flex flex-wrap items-center gap-3">
              <Link
                href="/sign-up"
                className="rounded-[10px] bg-[var(--night-accent)] px-5 py-2.5 text-[13.5px] font-medium text-[#0a0a0b] transition-opacity hover:opacity-90"
              >
                Create account →
              </Link>
              <Link
                href="/sign-in"
                className="rounded-[10px] border border-white/12 bg-white/[0.03] px-5 py-2.5 text-[13.5px] text-[var(--night-fg-1)] transition-colors hover:bg-white/[0.07]"
              >
                Sign in
              </Link>
              <span className="text-[12px] text-[var(--night-fg-3)]">
                Free while in beta · sign in to size a market
              </span>
            </motion.div>
          </div>

          {/* Right: product glyph on glass */}
          <motion.div
            initial={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.97, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.6, ease: EASE_OUT, delay: reduce ? 0 : 0.2 }}
            className="hidden lg:block"
          >
            <ProductGlass />
          </motion.div>
        </div>
      </main>

      <footer className="flex items-center justify-between px-6 py-6 text-[11px] text-[var(--night-fg-3)] sm:px-10">
        <span>Open-source · Apache-2.0</span>
        <a
          href="https://github.com/ArkashJ/Strata"
          target="_blank"
          rel="noopener noreferrer"
          className="uppercase tracking-[0.18em] transition-colors hover:text-[var(--night-fg-2)]"
        >
          GitHub
        </a>
      </footer>
    </>
  );
}

// The right-hand glass panel: the animated pyramid above the pipeline it feeds,
// plus an explicitly-illustrative range bar. Abstract topology only.
function ProductGlass() {
  const stages = ["concept", "framework", "primitive", "TAM"];
  return (
    <div className="glass relative mx-auto w-full max-w-[440px] p-7">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--night-fg-3)]">
          the pyramid
        </span>
        <span className="role-chip role-chip--accent">live synthesis</span>
      </div>

      <div className="mt-2 flex justify-center">
        <PyramidGlyph />
      </div>

      {/* Pipeline ribbon */}
      <div className="mt-4 flex items-center justify-between gap-1">
        {stages.map((s, i) => (
          <div key={s} className="flex items-center gap-1">
            <span className="glass-soft px-2.5 py-1 font-mono text-[10.5px] text-[var(--night-fg-2)]">
              {s}
            </span>
            {i < stages.length - 1 && (
              <span aria-hidden="true" className="text-[var(--night-fg-4,#4a5270)]">
                →
              </span>
            )}
          </div>
        ))}
      </div>

      {/* Illustrative range bar (labelled — never a fabricated figure) */}
      <div className="glass-soft mt-5 p-3.5">
        <div className="flex items-center justify-between text-[10.5px] text-[var(--night-fg-3)]">
          <span>illustrative range</span>
          <span className="font-mono">low · base · high</span>
        </div>
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
          <div className="h-full w-2/3 rounded-full bg-gradient-to-r from-[var(--night-accent)]/40 to-[var(--night-accent)]" />
        </div>
      </div>
    </div>
  );
}
