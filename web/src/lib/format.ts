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

// A content pin is the SHA-256 of the stored source snapshot (Q5). Some demo
// primitives carry a placeholder sentinel (a single hex pair repeated to fill
// the field, e.g. all-"d3") because no snapshot was ever stored — they are
// sourced but NOT content-pinned. Rendering the sentinel as if it were a real
// hash is the "fake green check" the trust audit flagged, so detect it.
// A genuinely-absent snapshot (composite inputs) is NOT a placeholder — the
// caller distinguishes that case.
export function isPlaceholderSnapshot(sha: string | null | undefined): boolean {
  if (!sha) return false;
  const hex = sha.trim().toLowerCase();
  if (hex.length < 64) return true;
  // Degenerate: a single hex pair repeated 32x (d3d3…d3 and friends).
  return /^(..)\1{31}$/.test(hex);
}

// Single source of truth for the "this isn't a real content pin" copy, so the
// trust-audit wording can't drift between the report's Sources table and the
// primitive detail page.
export const PLACEHOLDER_SNAPSHOT_LABEL = "not pinned (demo)";

// How a snapshot pin reads in a table cell: the short hash when genuine, an
// honest "not pinned" marker for the demo sentinel, an em-dash when absent
// (a composite input legitimately has no single snapshot).
export function formatSnapshot(sha: string | null | undefined): string {
  if (!sha) return "—";
  if (isPlaceholderSnapshot(sha)) return PLACEHOLDER_SNAPSHOT_LABEL;
  return sha.slice(0, 10);
}
