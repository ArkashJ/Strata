/**
 * IndependenceDonut — SVG ring gauge for a TAM's independence score (0–1, the
 * share of distinct method families behind the estimate). Accent arc sweeps
 * over a `--border-1` track; the clamped score sits in the center in `.tam-num`,
 * under an `INDEPENDENCE` eyebrow. Purely presentational.
 */

export interface IndependenceDonutProps {
  // 0–1; values outside the range are clamped.
  score: number;
  size?: number;
  strokeWidth?: number;
  className?: string;
}

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

export function IndependenceDonut({
  score,
  size = 96,
  strokeWidth = 8,
  className = "",
}: IndependenceDonutProps) {
  const clamped = clamp01(score);
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference * (1 - clamped);
  const center = size / 2;

  return (
    <div className={`inline-flex flex-col items-center gap-1 ${className}`}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          role="img"
          aria-label={`Independence score ${clamped.toFixed(2)} out of 1`}
        >
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="var(--border-1)"
            strokeWidth={strokeWidth}
          />
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="var(--accent)"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            transform={`rotate(-90 ${center} ${center})`}
          />
        </svg>
        <span className="-translate-x-1/2 -translate-y-1/2 tam-num absolute top-1/2 left-1/2 text-[var(--fg-1)] text-lg">
          {clamped.toFixed(2)}
        </span>
      </div>
      <span className="font-medium text-[10px] text-[var(--fg-3)] uppercase tracking-wider">
        Independence
      </span>
    </div>
  );
}
