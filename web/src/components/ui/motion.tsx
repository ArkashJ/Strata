"use client";

/**
 * Shared motion primitives (PR11). One place to keep entrance/stagger/hover
 * animations consistent and on-brand: timings mirror the brand-kit motion tokens
 * (--t-fast 120ms / --t-base 180ms / --t-slow 240ms) and every primitive honors
 * prefers-reduced-motion (collapses to an instant, offset-free render).
 */

import { type HTMLMotionProps, motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

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
