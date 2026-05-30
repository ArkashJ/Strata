"use client";

/**
 * Scroll-reveal wrapper for landing sections. Fades + slides content in the
 * first time it enters the viewport (whileInView, once). Honors
 * prefers-reduced-motion: reduced users get an instant, offset-free fade so
 * content never moves. Animations never gate render — children are always in
 * the DOM; motion only animates the wrapper's opacity/transform.
 */

import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

const EASE_OUT = [0.16, 1, 0.3, 1] as const;

export function Reveal({
  children,
  delay = 0,
  y = 16,
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
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "0px 0px -80px 0px" }}
      transition={{ duration: 0.34, ease: EASE_OUT, delay: reduce ? 0 : delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
