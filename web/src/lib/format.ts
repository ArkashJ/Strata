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

// One map for the five method families — ConvergenceBanner and MethodDirections
// both label them; a sixth family is added here once, not hunted across views.
const FAMILY_LABEL: Record<string, string> = {
  bottoms_up_seats: "Bottoms-up · seats",
  top_down_spend: "Top-down · spend",
  comparable_revenue: "Comparable revenue",
  analog_penetration: "Analog penetration",
  value_chain: "Value chain",
};

export function familyLabel(family: string): string {
  return FAMILY_LABEL[family] ?? family.replace(/_/g, " ");
}

// The canonical rendering of a coded scope tag ("SOC 41-4012 · Sales reps…") —
// shared by the /tam scope strip and the market-spec form chips.
export function codedTagLabel(tag: { system: string; code: string; label: string }): string {
  return `${tag.system} ${tag.code} · ${tag.label}`;
}
