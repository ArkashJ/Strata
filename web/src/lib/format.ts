export function formatUSD(value: number): string {
  if (!Number.isFinite(value)) return "—";
  if (value < 0) return `-${formatUSD(-value)}`;
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(0)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value.toLocaleString()}`;
}

export function formatCompact(
  value: number,
  unit?: { dimension?: string; currency?: string | null; denominator?: string | null } | null,
): string {
  if (!Number.isFinite(value)) return "—";
  if (unit?.dimension === "currency") {
    return formatUSD(value);
  }
  const formatted = Intl.NumberFormat("en", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
  const suffix = unit?.denominator ? `/${unit.denominator}` : "";
  return `${formatted}${suffix}`;
}

export function tierLabel(tier: string): string {
  return tier
    .split(/[_-]/)
    .map((s) => (s[0]?.toUpperCase() ?? "") + s.slice(1))
    .join(" ");
}

export function lensLabel(lens: string): string {
  return lens
    .split("_")
    .map((s) => (s[0]?.toUpperCase() ?? "") + s.slice(1))
    .join(" ");
}
