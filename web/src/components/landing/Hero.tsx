"use client";

/**
 * Animated landing hero. Owns presentation only — the search input is a
 * controlled component driven by the parent (page.tsx), which keeps the ⌘K
 * focus ref, /?q= prefill and routing in one place. The parent passes the
 * value, change + submit handlers and the input ref; Hero animates the thesis,
 * the query box and the abstract pyramid visual.
 *
 * No fabricated figures: the visual is abstract topology + tier words only.
 * All entrance motion honors prefers-reduced-motion (instant, offset-free) and
 * never gates render — text/input are always present even if motion fails.
 */

import { motion, useReducedMotion } from "motion/react";
import type { FormEvent, ReactNode, RefObject } from "react";

import { PyramidGlyph } from "./PyramidGlyph";

const EASE_OUT = [0.16, 1, 0.3, 1] as const;

export function Hero({
  inputRef,
  value,
  onChange,
  onSubmit,
  kbdHint,
}: {
  inputRef: RefObject<HTMLInputElement | null>;
  value: string;
  onChange: (v: string) => void;
  onSubmit: (e: FormEvent<HTMLFormElement>) => void;
  kbdHint?: ReactNode;
}) {
  const reduce = useReducedMotion();

  const item = (delay: number) => ({
    initial: reduce ? { opacity: 0 } : { opacity: 0, y: 12 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.32, ease: EASE_OUT, delay: reduce ? 0 : delay },
  });

  return (
    <section className="relative overflow-hidden px-8 pt-16 pb-12">
      <div className="mx-auto max-w-[1100px] grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-10 items-center">
        {/* Left: thesis + query box */}
        <div className="flex flex-col items-center lg:items-start text-center lg:text-left">
          <motion.p
            {...item(0)}
            className="text-[11px] font-medium uppercase tracking-[0.14em] text-[var(--fg-3)] mb-4"
          >
            Community-curated market sizing
          </motion.p>

          <motion.h1
            {...item(0.06)}
            className="display text-[44px] md:text-[60px] leading-[1.02] max-w-[600px] text-[var(--fg-1)]"
          >
            Defensible <em className="text-[var(--accent)] not-italic font-display italic">TAM</em>,
            fast.
          </motion.h1>

          <motion.p {...item(0.12)} className="mt-5 text-[15px] text-[var(--fg-2)] max-w-[520px]">
            Type any market. Strata picks the frameworks, pre-fills the primitives from sourced
            numbers, and shows you a range you can cite in a memo.
          </motion.p>

          <motion.form {...item(0.18)} onSubmit={onSubmit} className="mt-9 w-full max-w-[600px]">
            <div className="relative">
              <input
                ref={inputRef}
                type="text"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder="Doc-gen tooling for P&C insurance carriers, US"
                // biome-ignore lint/a11y/noAutofocus: intentional — search is the page's primary action
                autoFocus
                aria-label="Market sizing query"
                className="w-full h-[56px] pl-5 pr-36 rounded-[var(--r-3)]
                           bg-[var(--bg-1)] border border-[var(--border-2)]
                           text-[15px] text-[var(--fg-1)] placeholder:text-[var(--fg-3)]
                           shadow-[var(--shadow-pop)]
                           focus:border-[var(--accent)] transition-colors"
              />
              <button
                type="submit"
                className="absolute right-1.5 top-1.5 h-[44px] px-5 rounded-[var(--r-2)]
                           bg-[var(--accent)] text-[var(--accent-fg-on)]
                           text-[13px] font-medium tracking-[-0.01em]
                           hover:bg-[var(--accent-hover)] active:bg-[var(--accent-active)]
                           transition-colors"
              >
                Size it →
              </button>
            </div>
            {kbdHint ? <div className="mt-2 flex justify-end pr-1">{kbdHint}</div> : null}
          </motion.form>
        </div>

        {/* Right: abstract animated pyramid (decorative, hidden on small screens) */}
        <motion.div
          initial={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4, ease: EASE_OUT, delay: reduce ? 0 : 0.2 }}
          className="hidden lg:flex justify-center"
        >
          <PyramidGlyph />
        </motion.div>
      </div>
    </section>
  );
}
