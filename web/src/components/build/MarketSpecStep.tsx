"use client";

// Market-spec step (sub-project 1.5 · design 2026-06-02). Before any number, the
// user pins *which market* they mean — vertical / persona / segment / geo /
// include-exclude. The Size button is the gate: sizing only runs once the spec is
// confirmed. Prefilled from the matched concept's declared scope (snap-to-truth on
// the /tam side), fully editable, one-click accept.
//
// v1 scope (per design): no live NAICS/SOC classifier — coded tags are typed/edited
// as code + label chips, seeded from the concept. `product` is display-only (the
// guard emits no PRODUCT warning yet) so it is not collected here.

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { codedTagLabel } from "@/lib/format";
import { type CodedTag, emptyMarketScope, type FirmSizeBand, type MarketScope } from "@/lib/schemas";

// Geo defaults to US (design): a fresh, geo-less concept still pins a concrete
// market. Existing geo on the concept is honoured as-is.
function withGeoDefault(scope: MarketScope): MarketScope {
  if (scope.geo_demand.length > 0 || scope.geo_supply.length > 0) return scope;
  return { ...scope, geo_demand: ["US"], geo_supply: ["US"] };
}

type SegmentPreset = { key: string; label: string; band: FirmSizeBand | null };

// "All firms" is the *absence* of a band (segment null), not a both-open band.
const SEGMENT_PRESETS: SegmentPreset[] = [
  { key: "all", label: "All firms", band: null },
  { key: "smb", label: "SMB (<100)", band: { min_emp: null, max_emp: 99, label: "SMB (<100)" } },
  {
    key: "mid",
    label: "Mid-market (100–999)",
    band: { min_emp: 100, max_emp: 999, label: "Mid-market (100–999)" },
  },
  {
    key: "ent",
    label: "Enterprise (1000+)",
    band: { min_emp: 1000, max_emp: null, label: "Enterprise (1000+)" },
  },
];

function bandMatchesPreset(band: FirmSizeBand | null | undefined, preset: SegmentPreset): boolean {
  if (preset.band === null) return !band;
  if (!band) return false;
  return (band.min_emp ?? null) === preset.band.min_emp && (band.max_emp ?? null) === preset.band.max_emp;
}

export interface MarketSpecStepProps {
  conceptName: string;
  // The concept's declared scope (from GET /c/<slug>); may be empty.
  initialScope: MarketScope;
  // Confirmed market → size it. The parent turns this into a recompute + redirect.
  onSize: (scope: MarketScope) => void;
  // True while the size→recompute round-trip is in flight.
  sizing?: boolean;
}

export function MarketSpecStep({
  conceptName,
  initialScope,
  onSize,
  sizing = false,
}: MarketSpecStepProps) {
  const [scope, setScope] = useState<MarketScope>(() =>
    withGeoDefault({ ...emptyMarketScope(), ...initialScope }),
  );
  // Whether the segment chip-row is in "custom range" entry mode (no preset matched
  // a non-null band, or the user clicked Custom).
  const presetMatch = SEGMENT_PRESETS.find((p) => bandMatchesPreset(scope.segment, p));
  const [customSegment, setCustomSegment] = useState<boolean>(!presetMatch && !!scope.segment);

  const setSegment = (band: FirmSizeBand | null) => setScope((s) => ({ ...s, segment: band }));

  return (
    <main className="mx-auto flex w-full max-w-[var(--content-max)] flex-1 flex-col px-8 py-10" data-testid="market-spec">
      <header className="flex flex-col gap-2">
        <div className="text-[11px] uppercase tracking-[0.06em] text-[var(--fg-3)]">
          Pin the market
        </div>
        <h1 className="display text-[34px] leading-[1.1] text-[var(--fg-1)] capitalize">
          {conceptName}
        </h1>
        <p className="max-w-[60ch] text-[14px] leading-[1.5] text-[var(--fg-2)]">
          These narrow the market so we pick the right primitives. Adjust anything,
          then size — a different market is a different TAM.
        </p>
      </header>

      <div className="mt-8 flex flex-col gap-7">
        <CodedTagField
          testid="scope-vertical"
          title="Vertical"
          hint="Industry (NAICS). Multiple tags union."
          system="NAICS"
          tags={scope.vertical}
          onChange={(vertical) => setScope((s) => ({ ...s, vertical }))}
        />

        <CodedTagField
          testid="scope-persona"
          title="Persona"
          hint="Occupation (SOC). Who buys / uses it."
          system="SOC"
          tags={scope.persona}
          onChange={(persona) => setScope((s) => ({ ...s, persona }))}
        />

        {/* Segment — firm-size band presets + custom range. */}
        <Field title="Segment" hint="Firm size. “All firms” means no band.">
          <div className="flex flex-wrap gap-1.5" data-testid="scope-segment">
            {SEGMENT_PRESETS.map((p) => {
              const active = !customSegment && bandMatchesPreset(scope.segment, p);
              return (
                <ChipButton
                  key={p.key}
                  active={active}
                  testid={`segment-${p.key}`}
                  onClick={() => {
                    setCustomSegment(false);
                    setSegment(p.band);
                  }}
                >
                  {p.label}
                </ChipButton>
              );
            })}
            <ChipButton
              active={customSegment}
              testid="segment-custom"
              onClick={() => setCustomSegment(true)}
            >
              Custom
            </ChipButton>
          </div>
          {customSegment ? (
            <CustomSegment band={scope.segment} onChange={setSegment} />
          ) : null}
        </Field>

        {/* Geo — demand + supply ISO codes. Supply usually mirrors demand. */}
        <Field title="Geography" hint="ISO codes. Demand = where buyers are; supply = where sellers are.">
          <div className="flex flex-col gap-3" data-testid="scope-geo">
            <GeoRow
              label="Demand"
              codes={scope.geo_demand}
              onChange={(geo_demand) => setScope((s) => ({ ...s, geo_demand }))}
            />
            <GeoRow
              label="Supply"
              codes={scope.geo_supply}
              onChange={(geo_supply) => setScope((s) => ({ ...s, geo_supply }))}
            />
          </div>
        </Field>

        {/* Include / Exclude — free-text rules (display-only on the guard side). */}
        <div className="grid gap-7 sm:grid-cols-2">
          <RuleField
            testid="scope-include"
            title="Include"
            hint="Sub-markets explicitly in scope."
            rules={scope.include}
            onChange={(include) => setScope((s) => ({ ...s, include }))}
          />
          <RuleField
            testid="scope-exclude"
            title="Exclude"
            hint="Sub-markets explicitly out of scope."
            rules={scope.exclude}
            onChange={(exclude) => setScope((s) => ({ ...s, exclude }))}
          />
        </div>
      </div>

      <div className="mt-9 flex items-center gap-3 border-t border-[var(--border-2)] pt-6">
        <Button onClick={() => onSize(scope)} disabled={sizing} data-testid="size-market">
          {sizing ? "Sizing…" : "Size this market →"}
        </Button>
        <span className="text-[12px] text-[var(--fg-3)]">
          The scope check on the result tells you when a source covers a narrower or
          broader market than this.
        </span>
      </div>
    </main>
  );
}

// ── field primitives ──────────────────────────────────────────────────────────

function Field({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline gap-2">
        <span className="text-[13px] font-medium text-[var(--fg-1)]">{title}</span>
        {hint ? <span className="text-[12px] text-[var(--fg-3)]">{hint}</span> : null}
      </div>
      {children}
    </div>
  );
}

function Chip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-[var(--r-round)] bg-[var(--bg-2)] py-1 pl-2.5 pr-1 text-[12px] text-[var(--fg-1)]">
      {label}
      <button
        type="button"
        aria-label={`Remove ${label}`}
        onClick={onRemove}
        className="grid size-4 place-items-center rounded-full text-[var(--fg-3)] hover:bg-[var(--bg-3)] hover:text-[var(--fg-1)]"
      >
        ×
      </button>
    </span>
  );
}

function ChipButton({
  active,
  onClick,
  children,
  testid,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  testid?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      data-testid={testid}
      className="rounded-[var(--r-round)] border px-3 py-1 text-[12px] transition-colors"
      style={{
        background: active ? "var(--accent)" : "transparent",
        color: active ? "var(--accent-fg-on)" : "var(--fg-2)",
        borderColor: active ? "var(--accent)" : "var(--border-2)",
      }}
    >
      {children}
    </button>
  );
}

const inputClass =
  "rounded-[var(--r-1)] border border-[var(--border-2)] bg-[var(--bg-0)] px-2.5 py-1.5 " +
  "text-[13px] text-[var(--fg-1)] placeholder:text-[var(--fg-4)] outline-none focus:border-[var(--accent)]";

// Editable code+label chips for a NAICS/SOC dimension.
function CodedTagField({
  title,
  hint,
  system,
  tags,
  onChange,
  testid,
}: {
  title: string;
  hint?: string;
  system: string;
  tags: CodedTag[];
  onChange: (tags: CodedTag[]) => void;
  testid?: string;
}) {
  const [code, setCode] = useState("");
  const [label, setLabel] = useState("");

  const add = () => {
    const c = code.trim();
    const l = label.trim();
    if (!c || !l) return;
    if (tags.some((t) => t.code === c)) return;
    onChange([...tags, { system, code: c, label: l }]);
    setCode("");
    setLabel("");
  };

  return (
    <Field title={title} hint={hint}>
      <div className="flex flex-col gap-2" data-testid={testid}>
        {tags.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {tags.map((t) => (
              <Chip
                key={t.code}
                label={codedTagLabel(t)}
                onRemove={() => onChange(tags.filter((x) => x.code !== t.code))}
              />
            ))}
          </div>
        ) : null}
        <div className="flex flex-wrap items-center gap-2">
          <input
            className={`${inputClass} w-24`}
            placeholder={`${system} code`}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && add()}
          />
          <input
            className={`${inputClass} min-w-[12rem] flex-1`}
            placeholder="Label"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && add()}
          />
          <Button variant="ghost" sm onClick={add} disabled={!code.trim() || !label.trim()}>
            Add
          </Button>
        </div>
      </div>
    </Field>
  );
}

function CustomSegment({
  band,
  onChange,
}: {
  band: FirmSizeBand | null | undefined;
  onChange: (band: FirmSizeBand) => void;
}) {
  const [min, setMin] = useState<string>(band?.min_emp != null ? String(band.min_emp) : "");
  const [max, setMax] = useState<string>(band?.max_emp != null ? String(band.max_emp) : "");

  const commit = (nextMin: string, nextMax: string) => {
    const minN = nextMin.trim() === "" ? null : Number(nextMin);
    const maxN = nextMax.trim() === "" ? null : Number(nextMax);
    const lo = minN ?? 0;
    const hi = maxN != null ? maxN : "∞";
    onChange({ min_emp: minN, max_emp: maxN, label: `${lo}–${hi} employees` });
  };

  return (
    <div className="mt-2 flex items-center gap-2 text-[13px] text-[var(--fg-2)]">
      <input
        className={`${inputClass} w-20`}
        inputMode="numeric"
        placeholder="min"
        value={min}
        onChange={(e) => {
          setMin(e.target.value);
          commit(e.target.value, max);
        }}
      />
      <span className="text-[var(--fg-4)]">–</span>
      <input
        className={`${inputClass} w-20`}
        inputMode="numeric"
        placeholder="max"
        value={max}
        onChange={(e) => {
          setMax(e.target.value);
          commit(min, e.target.value);
        }}
      />
      <span className="text-[12px] text-[var(--fg-3)]">employees (blank = open-ended)</span>
    </div>
  );
}

function GeoRow({
  label,
  codes,
  onChange,
}: {
  label: string;
  codes: string[];
  onChange: (codes: string[]) => void;
}) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const c = draft.trim().toUpperCase();
    if (!c || codes.includes(c)) return;
    onChange([...codes, c]);
    setDraft("");
  };
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="w-16 shrink-0 text-[12px] text-[var(--fg-3)]">{label}</span>
      {codes.map((c) => (
        <Chip key={c} label={c} onRemove={() => onChange(codes.filter((x) => x !== c))} />
      ))}
      <input
        className={`${inputClass} w-20`}
        placeholder="ISO"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && add()}
      />
      <Button variant="ghost" sm onClick={add} disabled={!draft.trim()}>
        Add
      </Button>
    </div>
  );
}

function RuleField({
  title,
  hint,
  rules,
  onChange,
  testid,
}: {
  title: string;
  hint?: string;
  rules: string[];
  onChange: (rules: string[]) => void;
  testid?: string;
}) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const r = draft.trim();
    if (!r || rules.includes(r)) return;
    onChange([...rules, r]);
    setDraft("");
  };
  return (
    <Field title={title} hint={hint}>
      <div className="flex flex-col gap-2" data-testid={testid}>
        {rules.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {rules.map((r) => (
              <Chip key={r} label={r} onRemove={() => onChange(rules.filter((x) => x !== r))} />
            ))}
          </div>
        ) : null}
        <div className="flex items-center gap-2">
          <input
            className={`${inputClass} min-w-0 flex-1`}
            placeholder="Add a rule…"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && add()}
          />
          <Button variant="ghost" sm onClick={add} disabled={!draft.trim()}>
            Add
          </Button>
        </div>
      </div>
    </Field>
  );
}
