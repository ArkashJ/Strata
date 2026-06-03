/**
 * Design token showcase — renders the .glass panel and .role-chip classes
 * directly so reviewers can verify brand CSS variables resolve correctly in
 * Storybook (light and dark, via the toolbar toggle).
 */
import type { Meta, StoryObj } from "@storybook/react";

const meta = {
  title: "Design/Tokens",
  parameters: { layout: "centered" },
} satisfies Meta;

export default meta;
type Story = StoryObj;

// Glass panel — uses .strata-night + .glass so night-canvas variables are set
export const GlassPanel: Story = {
  name: ".glass panel",
  render: () => (
    <div
      className="strata-night"
      style={{
        padding: "48px",
        borderRadius: "24px",
        minWidth: "360px",
      }}
    >
      <div className="glass" style={{ padding: "24px" }}>
        <p
          style={{
            margin: 0,
            color: "var(--night-fg-1)",
            fontFamily: "var(--font-ui, system-ui)",
            fontSize: "14px",
            fontWeight: 500,
          }}
        >
          .glass — frosted panel
        </p>
        <p
          style={{
            margin: "6px 0 0",
            color: "var(--night-fg-3)",
            fontFamily: "var(--font-mono, monospace)",
            fontSize: "11px",
          }}
        >
          backdrop-filter: blur(22px) · hairline border · deep shadow
        </p>
      </div>
      <div className="glass-soft" style={{ padding: "16px", marginTop: "12px" }}>
        <p
          style={{
            margin: 0,
            color: "var(--night-fg-2)",
            fontFamily: "var(--font-mono, monospace)",
            fontSize: "11px",
          }}
        >
          .glass-soft — lighter blur (14px), tighter radius
        </p>
      </div>
    </div>
  ),
};

// Role chip variants — light surface
export const RoleChips: Story = {
  name: ".role-chip variants",
  render: () => (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: "8px",
        alignItems: "center",
        padding: "24px",
        background: "var(--bg-1)",
        borderRadius: "12px",
        border: "1px solid var(--border-1)",
      }}
    >
      <span className="role-chip">framework</span>
      <span className="role-chip">primitive</span>
      <span className="role-chip">concept</span>
      <span className="role-chip role-chip--accent">live synthesis</span>
      <span className="role-chip role-chip--accent">TAM output</span>
    </div>
  ),
};

// Combined: glass + chips inside the night canvas
export const NightChips: Story = {
  name: ".glass + .role-chip (night canvas)",
  render: () => (
    <div className="strata-night" style={{ padding: "48px", borderRadius: "24px" }}>
      <div className="glass" style={{ padding: "24px" }}>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          <span className="role-chip">framework</span>
          <span className="role-chip">primitive</span>
          <span className="role-chip role-chip--accent">live synthesis</span>
        </div>
        <p
          style={{
            margin: "12px 0 0",
            color: "var(--night-fg-2)",
            fontFamily: "var(--font-ui, system-ui)",
            fontSize: "13px",
          }}
        >
          Chips recolor automatically inside .strata-night via token re-points.
        </p>
      </div>
    </div>
  ),
};

// Accent + surface token swatch grid
export const TokenSwatches: Story = {
  name: "Surface + accent swatches",
  render: () => {
    const swatches: Array<{ label: string; var: string; dark?: boolean }> = [
      { label: "--bg-0", var: "--bg-0" },
      { label: "--bg-1", var: "--bg-1" },
      { label: "--bg-2", var: "--bg-2" },
      { label: "--bg-3", var: "--bg-3" },
      { label: "--accent", var: "--accent", dark: true },
      { label: "--accent-hover", var: "--accent-hover", dark: true },
      { label: "--accent-tint", var: "--accent-tint" },
      { label: "--fg-1", var: "--fg-1", dark: true },
      { label: "--fg-2", var: "--fg-2", dark: true },
      { label: "--fg-3", var: "--fg-3", dark: true },
    ];

    return (
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))",
          gap: "8px",
          padding: "24px",
          background: "var(--bg-0)",
          borderRadius: "12px",
          border: "1px solid var(--border-1)",
          minWidth: "360px",
        }}
      >
        {swatches.map(({ label, var: cssVar, dark }) => (
          <div key={label} style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            <div
              style={{
                height: "40px",
                borderRadius: "6px",
                background: `var(${cssVar})`,
                border: "1px solid var(--border-1)",
              }}
            />
            <span
              style={{
                fontFamily: "var(--font-mono, monospace)",
                fontSize: "10px",
                color: dark ? "var(--fg-1)" : "var(--fg-2)",
                wordBreak: "break-all",
              }}
            >
              {label}
            </span>
          </div>
        ))}
      </div>
    );
  },
};
