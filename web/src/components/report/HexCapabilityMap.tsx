"use client";

// HexCapabilityMap — the Gartner "honeycomb" capability diagram: a center hex
// (the core capability) ringed by six satellite hexes (the surrounding
// capabilities). Pure SVG, props-driven, tokenized. Filled hexes use the accent
// voice at graded opacity by `weight` (0–1) so the eye ranks coverage; an
// unfilled hex reads as a gap.
//
// This is a qualitative "what the platform does" map, not a quantitative chart —
// so it carries no numeric axis; the frame is title + optional source only.

export interface HexCell {
  label: string;
  // 0–1 coverage; drives fill opacity. Undefined → outline-only (a gap).
  weight?: number;
}

// Flat-top hexagon points for a unit hex of the given radius, centered at (cx,cy).
function hexPoints(cx: number, cy: number, r: number): string {
  const pts: string[] = [];
  for (let i = 0; i < 6; i++) {
    const a = (Math.PI / 180) * (60 * i);
    pts.push(`${(cx + r * Math.cos(a)).toFixed(2)},${(cy + r * Math.sin(a)).toFixed(2)}`);
  }
  return pts.join(" ");
}

function Hex({ cx, cy, r, cell }: { cx: number; cy: number; r: number; cell: HexCell }) {
  const w = cell.weight;
  const filled = w != null && w > 0;
  const opacity = filled ? 0.18 + 0.62 * Math.min(1, Math.max(0, w)) : 0;
  return (
    <g>
      <polygon
        points={hexPoints(cx, cy, r)}
        fill="var(--accent)"
        fillOpacity={opacity}
        stroke={filled ? "var(--accent)" : "var(--border-2)"}
        strokeWidth={1.5}
        strokeDasharray={filled ? undefined : "4 3"}
      />
      <foreignObject x={cx - r * 0.82} y={cy - r * 0.55} width={r * 1.64} height={r * 1.1}>
        <div
          className="flex h-full w-full items-center justify-center text-center text-[10px] leading-tight"
          style={{ color: filled ? "var(--fg-1)" : "var(--fg-3)" }}
        >
          {cell.label}
        </div>
      </foreignObject>
    </g>
  );
}

export function HexCapabilityMap({
  center,
  satellites,
  headline,
  subtitle,
  source,
  size = 360,
  className,
}: {
  center: HexCell;
  // Up to 6 surrounding capabilities (extras ignored).
  satellites: HexCell[];
  headline?: string;
  subtitle?: string;
  source?: string | null;
  size?: number;
  className?: string;
}) {
  const cx = size / 2;
  const cy = size / 2;
  // Radius sized so the ring of 6 hexes tessellates around the center.
  const r = size / 6.2;
  const ring = r * Math.sqrt(3);

  const sats = satellites.slice(0, 6);

  return (
    <figure className={className}>
      {headline ? (
        <figcaption className="mb-3">
          <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--fg-2)]">
            {headline}
          </div>
          {subtitle ? (
            <div className="mt-0.5 text-[12px] text-[var(--fg-3)]">{subtitle}</div>
          ) : null}
        </figcaption>
      ) : null}

      <svg
        width="100%"
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={`Capability map: ${center.label} surrounded by ${sats.map((s) => s.label).join(", ")}`}
        className="mx-auto block max-w-[360px]"
      >
        {sats.map((cell, i) => {
          const a = (Math.PI / 180) * (60 * i - 90);
          return (
            <Hex
              key={cell.label}
              cx={cx + ring * Math.cos(a)}
              cy={cy + ring * Math.sin(a)}
              r={r}
              cell={cell}
            />
          );
        })}
        <Hex cx={cx} cy={cy} r={r} cell={{ ...center, weight: center.weight ?? 1 }} />
      </svg>

      {source ? (
        <div className="mt-3 border-t border-[var(--border-1)] pt-2 font-mono text-[10px] text-[var(--fg-3)]">
          {source}
        </div>
      ) : null}
    </figure>
  );
}
