"use client";

/**
 * Abstract animated pyramid/graph visual for the hero. Draws the three-tier
 * Strata pyramid (concept → framework → primitives) with edges that "trace" in
 * and nodes that settle, then a slow ambient pulse on the apex. Deliberately
 * abstract — no dollar figures, no fabricated numbers — it evokes the data
 * topology, nothing more. Reduced-motion users get the static, fully-drawn
 * glyph (no tracing, no pulse).
 */

import { motion, useReducedMotion } from "motion/react";

const EASE_OUT = [0.16, 1, 0.3, 1] as const;

// Pyramid geometry: apex, two mid nodes, three base nodes.
const APEX = { x: 110, y: 16 };
const MID = [
  { x: 64, y: 96 },
  { x: 156, y: 96 },
];
const BASE = [
  { x: 28, y: 168 },
  { x: 110, y: 168 },
  { x: 192, y: 168 },
];

const EDGES = [
  [APEX, MID[0]],
  [APEX, MID[1]],
  [MID[0], BASE[0]],
  [MID[0], BASE[1]],
  [MID[1], BASE[1]],
  [MID[1], BASE[2]],
];

export function PyramidGlyph() {
  const reduce = useReducedMotion();

  return (
    <svg
      width="220"
      height="184"
      viewBox="0 0 220 184"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      className="overflow-visible"
    >
      <title>Strata data pyramid</title>

      {/* Edges trace in. Reduced-motion: drawn instantly. */}
      {EDGES.map(([a, b], i) => (
        <motion.line
          // biome-ignore lint/suspicious/noArrayIndexKey: fixed, ordered geometry
          key={`e${i}`}
          x1={a.x}
          y1={a.y}
          x2={b.x}
          y2={b.y}
          stroke="var(--border-2)"
          strokeWidth={1.5}
          initial={reduce ? { pathLength: 1, opacity: 1 } : { pathLength: 0, opacity: 0 }}
          animate={{ pathLength: 1, opacity: 1 }}
          transition={{
            duration: reduce ? 0 : 0.4,
            ease: EASE_OUT,
            delay: reduce ? 0 : 0.1 + i * 0.05,
          }}
        />
      ))}

      {/* Base nodes */}
      {BASE.map((n, i) => (
        <motion.circle
          // biome-ignore lint/suspicious/noArrayIndexKey: fixed geometry
          key={`b${i}`}
          cx={n.x}
          cy={n.y}
          r={5}
          fill="var(--fg-3)"
          initial={reduce ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.4 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{
            duration: reduce ? 0 : 0.3,
            ease: EASE_OUT,
            delay: reduce ? 0 : 0.1 + i * 0.06,
          }}
        />
      ))}

      {/* Mid nodes */}
      {MID.map((n, i) => (
        <motion.circle
          // biome-ignore lint/suspicious/noArrayIndexKey: fixed geometry
          key={`m${i}`}
          cx={n.x}
          cy={n.y}
          r={6}
          fill="var(--accent)"
          fillOpacity={0.55}
          initial={reduce ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.4 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{
            duration: reduce ? 0 : 0.3,
            ease: EASE_OUT,
            delay: reduce ? 0 : 0.3 + i * 0.06,
          }}
        />
      ))}

      {/* Apex — settles, then a slow ambient pulse ring (skipped if reduced). */}
      <motion.circle
        cx={APEX.x}
        cy={APEX.y}
        r={7}
        fill="var(--accent)"
        initial={reduce ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.4 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: reduce ? 0 : 0.3, ease: EASE_OUT, delay: reduce ? 0 : 0.45 }}
      />
      {!reduce && (
        <motion.circle
          cx={APEX.x}
          cy={APEX.y}
          r={7}
          fill="none"
          stroke="var(--accent)"
          strokeWidth={1.5}
          initial={{ opacity: 0.5, scale: 1 }}
          animate={{ opacity: 0, scale: 2.4 }}
          transition={{
            duration: 2.4,
            ease: "easeOut",
            repeat: Number.POSITIVE_INFINITY,
            repeatDelay: 1.2,
            delay: 1,
          }}
        />
      )}

      {/* Tier labels — abstract, no numbers. */}
      <text
        x={APEX.x + 16}
        y={APEX.y + 4}
        fill="var(--fg-3)"
        fontSize="10"
        fontFamily="var(--font-mono, monospace)"
      >
        concept
      </text>
      <text
        x={MID[1].x + 14}
        y={MID[1].y + 4}
        fill="var(--fg-4)"
        fontSize="10"
        fontFamily="var(--font-mono, monospace)"
      >
        frameworks
      </text>
      <text
        x={BASE[2].x + 14}
        y={BASE[2].y + 4}
        fill="var(--fg-4)"
        fontSize="10"
        fontFamily="var(--font-mono, monospace)"
      >
        primitives
      </text>
    </svg>
  );
}
