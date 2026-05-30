import { BrandIcon } from "@/components/icons/BrandIcon";
import type { Integration } from "./integrations";

const STATUS_LABEL: Record<Integration["status"], string> = {
  connected: "Connected",
  available: "Connect",
  "coming-soon": "Coming soon",
};

const STATUS_DOT: Record<Integration["status"], string> = {
  connected: "var(--tier-regulator, #34d399)",
  available: "var(--accent)",
  "coming-soon": "var(--fg-4)",
};

export function IntegrationCard({ integration }: { integration: Integration }) {
  const disabled = integration.status === "coming-soon";
  return (
    <div className="canvas-card flex flex-col gap-3 p-4" style={{ borderRadius: "var(--r-3)" }}>
      <div className="flex items-center gap-3">
        <BrandIcon name={integration.name.replace(/\s*\(.*\)/, "")} size={34} />
        <div className="min-w-0 flex-1">
          <div className="text-[14px] font-medium text-[var(--fg-1)] truncate">
            {integration.name}
          </div>
          <div className="flex items-center gap-1.5 text-[11px] text-[var(--fg-3)]">
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: STATUS_DOT[integration.status] }}
            />
            {STATUS_LABEL[integration.status]}
          </div>
        </div>
      </div>
      <p className="text-[12px] leading-snug text-[var(--fg-3)]">{integration.blurb}</p>
      <button
        type="button"
        disabled={disabled}
        className="mt-auto rounded-[var(--r-2)] px-3 py-1.5 text-[12px] font-medium transition-colors"
        style={{
          background: disabled ? "var(--bg-2)" : "var(--accent)",
          color: disabled ? "var(--fg-4)" : "var(--accent-fg, #fff)",
          cursor: disabled ? "not-allowed" : "pointer",
        }}
      >
        {STATUS_LABEL[integration.status]}
      </button>
    </div>
  );
}
