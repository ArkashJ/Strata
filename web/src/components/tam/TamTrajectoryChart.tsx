"use client";

// TAM-over-time (PR13 · headline "current vs previous" view). The backend
// re-evaluates the TAM at each distinct primitive `as_of` date (GET
// /build/{slug}/trajectory). A low–high band traces the scenario spread at each
// date; the mid line is the triangulated estimate. The latest point is the
// "Current TAM" — emphasized and labelled — and earlier points are the
// trajectory it moved along.
//
// Honesty over decoration: most concepts currently share a single as_of, so the
// common case is ONE point. We render that as a plain snapshot, never a
// degenerate one-dot "chart" and never a fabricated curve. Zero points → empty.
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Dot,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatCompact } from "@/lib/format";
import type { TamTrajectory, TrajectoryPoint, Unit } from "@/lib/schemas";
import { trajectoryDelta } from "@/lib/tam";

interface Props {
  trajectory: TamTrajectory;
}

interface ChartDatum {
  as_of: string;
  mid: number;
  // Recharts draws a range area from a [low, high] tuple dataKey.
  band: [number, number];
  low: number;
  high: number;
  methods: number;
  isLatest: boolean;
}

// Compact YYYY-MM-DD → "Mon 'YY" without dragging in a date library. Falls back
// to the raw string if it isn't an ISO date (the backend may emit "latest").
function shortDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en", { month: "short", year: "2-digit" });
}

export function TamTrajectoryChart({ trajectory }: Props) {
  const { points, unit } = trajectory;

  if (points.length === 0) {
    return (
      <div className="text-[13px] text-[var(--fg-3)]">No dated estimates yet for this concept.</div>
    );
  }

  // One point is the common case — present the single estimate honestly rather
  // than a chart that implies a trend from a single observation.
  if (points.length === 1) {
    return <SingleSnapshot point={points[0]} unit={unit} />;
  }

  const data: ChartDatum[] = points.map((p, i) => ({
    as_of: shortDate(p.as_of),
    mid: p.value,
    band: [p.low, p.high],
    low: p.low,
    high: p.high,
    methods: p.method_families.length,
    isLatest: i === points.length - 1,
  }));

  const latest = points[points.length - 1];
  const delta = trajectoryDelta(points);

  return (
    <div className="flex flex-col gap-4">
      {/* Headline row: Current TAM value + the delta callout vs the prior point. */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[11px] uppercase tracking-[0.06em] text-[var(--fg-3)]">
            Current TAM
          </div>
          <div className="tam-num mt-1 text-[32px] leading-[1] text-[var(--fg-1)]">
            {formatCompact(latest.value, unit)}
          </div>
          <div className="mt-1 text-[12px] text-[var(--fg-3)]">
            {formatCompact(latest.low, unit)} – {formatCompact(latest.high, unit)}
            <span className="mx-1.5 text-[var(--fg-4)]">·</span>
            {shortDate(latest.as_of)}
          </div>
        </div>
        {delta ? <DeltaCallout delta={delta} /> : null}
      </div>

      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={data} margin={{ top: 12, right: 24, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-1)" vertical={false} />
          <XAxis
            dataKey="as_of"
            tick={{ fontSize: 11, fill: "var(--fg-3)" }}
            axisLine={{ stroke: "var(--border-1)" }}
            tickLine={false}
          />
          <YAxis
            tickFormatter={(v: number) => formatCompact(v, unit)}
            tick={{ fontSize: 11, fill: "var(--fg-3)" }}
            axisLine={false}
            tickLine={false}
            width={72}
          />
          {/* Low–high spread, drawn first so the mid line and dots sit on top.
					    `band` is a [low, high] tuple — Recharts renders that as a range area. */}
          <Area
            type="monotone"
            dataKey="band"
            stroke="var(--border-2)"
            strokeWidth={1}
            fill="var(--bg-2)"
            fillOpacity={0.7}
            isAnimationActive
            animationDuration={600}
            activeDot={false}
          />
          <Line
            type="monotone"
            dataKey="mid"
            stroke="var(--accent)"
            strokeWidth={2}
            isAnimationActive
            animationDuration={600}
            dot={<TrajectoryDot />}
            activeDot={{ r: 5, fill: "var(--accent)", stroke: "var(--bg-1)" }}
          />
          <Tooltip content={<TrajectoryTooltip unit={unit} />} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

// The latest point gets a larger, filled accent dot to read as "you are here";
// earlier points are hollow markers along the path travelled.
function TrajectoryDot(props: {
  cx?: number;
  cy?: number;
  payload?: ChartDatum;
}) {
  const { cx, cy, payload } = props;
  if (cx == null || cy == null || !payload) return null;
  if (payload.isLatest) {
    return <Dot cx={cx} cy={cy} r={6} fill="var(--accent)" stroke="var(--bg-1)" strokeWidth={2} />;
  }
  return (
    <Dot cx={cx} cy={cy} r={3.5} fill="var(--bg-1)" stroke="var(--accent)" strokeWidth={1.5} />
  );
}

function DeltaCallout({
  delta,
}: {
  delta: NonNullable<ReturnType<typeof trajectoryDelta>>;
}) {
  const pct = Math.abs(delta.pct * 100);
  const arrow = delta.direction === "up" ? "▲" : delta.direction === "down" ? "▼" : "—";
  // Up is green, down is red; a flat move stays neutral so we never colour noise.
  const color =
    delta.direction === "up"
      ? "var(--success)"
      : delta.direction === "down"
        ? "var(--danger)"
        : "var(--fg-3)";
  return (
    <div
      className="flex items-baseline gap-1.5 rounded-[var(--r-2)] px-2.5 py-1"
      style={{ background: "var(--bg-2)" }}
    >
      <span aria-hidden className="text-[12px]" style={{ color }}>
        {arrow}
      </span>
      <span className="text-[14px] font-medium tabular-nums" style={{ color }}>
        {pct.toFixed(1)}%
      </span>
      <span className="text-[11px] text-[var(--fg-3)]">vs previous</span>
    </div>
  );
}

function TrajectoryTooltip({
  active,
  payload,
  unit,
}: {
  active?: boolean;
  payload?: { payload: ChartDatum }[];
  unit: Unit;
}) {
  if (!active || !payload?.[0]) return null;
  const d = payload[0].payload;
  return (
    <div className="canvas-card px-3 py-2" style={{ borderRadius: "var(--r-2)" }}>
      <div className="text-[12px] font-medium text-[var(--fg-1)]">{d.as_of}</div>
      <div className="tam-num mt-1 text-[16px] text-[var(--fg-1)]">
        {formatCompact(d.mid, unit)}
      </div>
      <div className="mt-0.5 text-[11px] text-[var(--fg-3)]">
        {formatCompact(d.low, unit)} – {formatCompact(d.high, unit)}
        <span className="mx-1 text-[var(--fg-4)]">·</span>
        {d.methods} {d.methods === 1 ? "method" : "methods"}
      </div>
    </div>
  );
}

// Single-snapshot fallback — the honest state when every primitive shares one
// as_of date. Shows the one estimate and says plainly why there is no curve.
function SingleSnapshot({
  point,
  unit,
}: {
  point: TrajectoryPoint;
  unit: Unit;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div>
        <div className="text-[11px] uppercase tracking-[0.06em] text-[var(--fg-3)]">
          Current TAM
        </div>
        <div className="tam-num mt-1 text-[32px] leading-[1] text-[var(--fg-1)]">
          {formatCompact(point.value, unit)}
        </div>
        <div className="mt-1 text-[12px] text-[var(--fg-3)]">
          {formatCompact(point.low, unit)} – {formatCompact(point.high, unit)}
          <span className="mx-1.5 text-[var(--fg-4)]">·</span>
          {shortDate(point.as_of)}
        </div>
      </div>
      <p className="text-[12px] text-[var(--fg-3)]">
        Single snapshot · no trajectory yet (sources share one as-of date).
      </p>
    </div>
  );
}
