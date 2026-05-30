"use client";

/**
 * Shared motion primitives (PR11). One place to keep entrance/stagger/hover
 * animations consistent and on-brand: timings mirror the brand-kit motion tokens
 * (--t-fast 120ms / --t-base 180ms / --t-slow 240ms) and every primitive honors
 * prefers-reduced-motion (collapses to an instant, offset-free render).
 */

import { type HTMLMotionProps, motion, useReducedMotion } from "motion/react";
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";

// Expressive-out easing — a soft overshoot-free curve that reads like the
// brand's --ease-out without hardcoding a cubic-bezier per call site.
const EASE_OUT = [0.16, 1, 0.3, 1] as const;

// Fade + slight rise on mount. `delay` lets callers cascade a few elements
// without a full stagger container.
export function FadeIn({
  children,
  delay = 0,
  y = 8,
  className,
}: {
  children: ReactNode;
  delay?: number;
  y?: number;
  className?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? { opacity: 0 } : { opacity: 0, y }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: EASE_OUT, delay: reduce ? 0 : delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

// Stagger container — children using <StaggerItem> animate in sequence.
export function Stagger({
  children,
  className,
  gap = 0.04,
}: {
  children: ReactNode;
  className?: string;
  gap?: number;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={{ show: { transition: { staggerChildren: reduce ? 0 : gap } } }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      variants={{
        hidden: reduce ? { opacity: 0 } : { opacity: 0, y: 10 },
        show: {
          opacity: 1,
          y: 0,
          transition: { duration: 0.28, ease: EASE_OUT },
        },
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

// ── Recompute payoff (Wave 2) ────────────────────────────────────────────────

// rAF count-up from the previous value to the new one. Reduced-motion users get
// the final value instantly (no animation frames). `format` renders each frame's
// interpolated number (e.g. compact USD). The animation re-runs whenever `value`
// changes — wiring this into the TAM headline gives the recompute its payoff.
export function CountUp({
  value,
  format = (n) => String(Math.round(n)),
  durationMs = 650,
  className,
}: {
  value: number;
  format?: (n: number) => string;
  durationMs?: number;
  className?: string;
}) {
  const reduce = useReducedMotion();
  const [display, setDisplay] = useState(value);
  const fromRef = useRef(value);

  useEffect(() => {
    const from = fromRef.current;
    if (reduce || from === value || durationMs <= 0) {
      fromRef.current = value;
      setDisplay(value);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      const eased = 1 - (1 - t) ** 3; // ease-out cubic
      setDisplay(from + (value - from) * eased);
      if (t < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        fromRef.current = value;
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, reduce, durationMs]);

  return (
    <span className={className} data-testid="count-up">
      {format(display)}
    </span>
  );
}

// A one-shot pulse ring (scale + fade) used to draw the eye to graph nodes whose
// inputs changed on recompute. Reduced-motion → renders children with no pulse.
export function Pulse({
  children,
  pulseKey,
  className,
}: {
  children: ReactNode;
  // Change this to re-trigger the pulse (e.g. the new TAM state hash).
  pulseKey?: string | number;
  className?: string;
}) {
  const reduce = useReducedMotion();
  if (reduce) return <div className={className}>{children}</div>;
  return (
    <motion.div
      key={pulseKey}
      initial={{ boxShadow: "0 0 0 0 var(--accent)" }}
      animate={{ boxShadow: ["0 0 0 0 var(--accent)", "0 0 0 8px transparent"] }}
      transition={{ duration: 0.6, ease: EASE_OUT }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

// Hover-intent: only fires `onIntent(true)` after the pointer rests for `delay`
// ms (250ms ghost-card pattern, AC2.2), and `onIntent(false)` immediately on
// leave. Returns the handlers to spread onto the target element.
export function useHoverIntent(onIntent: (hovering: boolean) => void, delay = 250) {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clear = useCallback(() => {
    if (timer.current !== null) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  const onMouseEnter = useCallback(() => {
    clear();
    timer.current = setTimeout(() => onIntent(true), delay);
  }, [clear, onIntent, delay]);

  const onMouseLeave = useCallback(() => {
    clear();
    onIntent(false);
  }, [clear, onIntent]);

  useEffect(() => clear, [clear]);

  return { onMouseEnter, onMouseLeave };
}

// A card-like surface that lifts subtly on hover/tap. Reduced-motion users get
// the static surface (no transform), so it degrades to a plain div.
export function HoverLift({
  children,
  className,
  ...rest
}: HTMLMotionProps<"div"> & { children: ReactNode; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      whileHover={reduce ? undefined : { y: -2 }}
      whileTap={reduce ? undefined : { scale: 0.995 }}
      transition={{ duration: 0.18, ease: EASE_OUT }}
      className={className}
      {...rest}
    >
      {children}
    </motion.div>
  );
}
