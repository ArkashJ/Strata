import type { Meta, StoryObj } from "@storybook/react";
import { NightCanvas } from "./NightCanvas";
import { PublicLanding } from "./PublicLanding";

const meta = {
  title: "Landing/NightCanvas",
  component: NightCanvas,
  // Night canvas is full-screen by design; override the centering decorator padding
  parameters: {
    layout: "fullscreen",
    // Disable the global centering decorator's padding for this story group
  },
  decorators: [
    // Override the global centering decorator: NightCanvas must fill the viewport
    (Story) => (
      <div style={{ minHeight: "100vh", width: "100%" }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof NightCanvas>;

export default meta;
type Story = StoryObj<typeof meta>;

// NightCanvas as a bare shell with a glass panel child
export const WithGlassPanel: Story = {
  name: "Shell + glass panel",
  // children supplied by `render`; args satisfies the component's required prop.
  args: { children: null },
  render: () => (
    <NightCanvas>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
          padding: "2rem",
        }}
      >
        <div className="glass" style={{ padding: "2rem", maxWidth: "480px", width: "100%" }}>
          <p
            style={{
              margin: 0,
              color: "var(--night-fg-1)",
              fontFamily: "var(--font-ui, system-ui)",
              fontSize: "14px",
            }}
          >
            Glass panel on the night canvas. Backdrop blur + hairline border.
          </p>
          <p
            style={{
              margin: "8px 0 0",
              color: "var(--night-fg-3)",
              fontFamily: "var(--font-mono, monospace)",
              fontSize: "12px",
            }}
          >
            .glass + .strata-night tokens
          </p>
        </div>
      </div>
    </NightCanvas>
  ),
};

// Full PublicLanding inside NightCanvas — the real first-impression surface
export const WithPublicLanding: Story = {
  name: "PublicLanding (full)",
  args: { children: null },
  render: () => (
    <NightCanvas>
      <PublicLanding />
    </NightCanvas>
  ),
};
