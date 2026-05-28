"use client";

// Geo + Time are filter chips above the graph (U1 / Q12) — deliberately NOT
// pillars. They are view-state only: the read-only renderer surfaces them as
// the active geo/time lens for the pyramid, matching the /build target shape
// (geo + time) without re-sizing anything client-side.

export const GEO_CHIPS = ["Global", "US", "EU"] as const;
export const TIME_CHIPS = ["2025", "2026", "2027"] as const;

export type GeoChip = (typeof GEO_CHIPS)[number];
export type TimeChip = (typeof TIME_CHIPS)[number];

export function PyramidFilters({
  geo,
  time,
  onGeo,
  onTime,
}: {
  geo: GeoChip;
  time: TimeChip;
  onGeo: (g: GeoChip) => void;
  onTime: (t: TimeChip) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-4">
      <ChipGroup label="Geo">
        {GEO_CHIPS.map((g) => (
          <Chip key={g} active={g === geo} onClick={() => onGeo(g)}>
            {g}
          </Chip>
        ))}
      </ChipGroup>
      <span className="w-px h-5 bg-[var(--border-1)]" aria-hidden />
      <ChipGroup label="Time">
        {TIME_CHIPS.map((t) => (
          <Chip key={t} active={t === time} onClick={() => onTime(t)}>
            {t}
          </Chip>
        ))}
      </ChipGroup>
    </div>
  );
}

function ChipGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] uppercase tracking-[0.08em] text-[var(--fg-3)]">{label}</span>
      <div className="flex gap-1">{children}</div>
    </div>
  );
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`px-2.5 py-1 rounded-[var(--r-round)] text-[12px] font-medium transition-colors ${
        active
          ? "bg-[var(--accent)] text-[var(--accent-fg-on)]"
          : "bg-[var(--bg-2)] text-[var(--fg-2)] hover:bg-[var(--bg-3)]"
      }`}
    >
      {children}
    </button>
  );
}
