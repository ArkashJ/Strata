// Runtime brand-token resolution for the network graph. vis-network paints to a
// <canvas>, which can't read CSS custom properties — it needs concrete colour
// strings. Rather than hardcode hex (which would drift from globals.css and
// violate the brand-kit-only rule), we read the live computed values off
// :root at render time. One read per open; cached on the returned object.

import type { NetEntityKind, NetNode } from "@/lib/network-graph";

export interface NodePaint {
  background: string;
  border: string;
}

export interface NetworkPalette {
  // Per-entity-kind fills.
  node: (node: NetNode) => NodePaint;
  rootNode: NodePaint;
  // Edge stroke + its faded variant (for the hover-dim neighbourhood effect).
  edge: string;
  edgeFaded: string;
  // Node label colours.
  labelOnDark: string;
  labelOnLight: string;
  labelStroke: string;
  // Cluster (pattern-detected) edge stroke.
  cluster: string;
}

function cssVar(styles: CSSStyleDeclaration, name: string, fallback: string): string {
  const v = styles.getPropertyValue(name).trim();
  return v || fallback;
}

// Compose an `rgb(...)` / hex base with an alpha by layering it over the paper
// surface via color-mix — keeps the faded variant on-brand without a second
// token. color-mix is well-supported in the browsers Next 16 targets.
function fade(color: string, surface: string, keep = 22): string {
  return `color-mix(in srgb, ${color} ${keep}%, ${surface})`;
}

/**
 * Read the brand tokens off :root and return resolved paint functions. Call
 * once when the modal opens (the values don't change while it's open). Falls
 * back to the documented globals.css defaults when a var is missing (jsdom,
 * SSR-less test envs) so callers never get an empty string into the canvas.
 */
export function resolvePalette(): NetworkPalette {
  const root = typeof document !== "undefined" ? document.documentElement : null;
  const s = root ? getComputedStyle(root) : null;

  const get = (name: string, fallback: string) => (s ? cssVar(s, name, fallback) : fallback);

  const surface = get("--bg-1", "#ffffff");
  const accent = get("--accent", "#5b5bd6");
  const accentActive = get("--accent-active", "#4848c4");
  const analyst = get("--tier-analyst", "#c99846");
  const analystBorder = get("--tier-analyst", "#c99846");
  const regulator = get("--tier-regulator", "#3fa66b");
  const aggregator = get("--tier-aggregator", "#2ba39a");
  const border = get("--border-3", "#a1a1aa");
  const fg1 = get("--fg-1", "#0a0a0b");
  const danger = get("--danger", "#e5484d");

  // Node colour by entity type. Concepts use the accent (qualitative axis);
  // frameworks use the analyst tier token (per the brief); primitives key off
  // their kind — atomic = regulator green (a sourced number), composite =
  // aggregator teal (a derived set-op), both drawn from the tier palette.
  const node = (n: NetNode): NodePaint => {
    if (n.kind === "concept") return { background: accent, border: accentActive };
    if (n.kind === "framework") return { background: analyst, border: analystBorder };
    // primitive
    const composite = n.subKind === "composite_primitive";
    return composite
      ? { background: aggregator, border: aggregator }
      : { background: regulator, border: regulator };
  };

  return {
    node,
    rootNode: { background: accentActive, border: fg1 },
    edge: border,
    edgeFaded: fade(border, surface, 30),
    labelOnDark: get("--accent-fg-on", "#ffffff"),
    labelOnLight: fg1,
    labelStroke: surface,
    cluster: danger,
  };
}

// Convenience for the sidebar legend dots, which are styled with inline CSS
// custom-property refs (so they *do* go through the token, unlike the canvas).
export const LEGEND: {
  kind: NetEntityKind | "atomic" | "composite";
  label: string;
  cssVar: string;
}[] = [
  { kind: "concept", label: "Concept", cssVar: "--accent" },
  { kind: "framework", label: "Framework", cssVar: "--tier-analyst" },
  { kind: "atomic", label: "Atomic primitive", cssVar: "--tier-regulator" },
  {
    kind: "composite",
    label: "Composite primitive",
    cssVar: "--tier-aggregator",
  },
];
