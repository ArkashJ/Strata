import type { Meta, StoryObj } from "@storybook/react";
import { Button } from "./Button";

const meta = {
  title: "UI/Button",
  component: Button,
  parameters: { layout: "centered" },
  argTypes: {
    variant: { control: "radio", options: ["primary", "ghost"] },
    sm: { control: "boolean" },
    disabled: { control: "boolean" },
    children: { control: "text" },
  },
} satisfies Meta<typeof Button>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Primary: Story = {
  args: { variant: "primary", children: "Build a TAM" },
};

export const Ghost: Story = {
  args: { variant: "ghost", children: "Browse markets" },
};

export const PrimarySmall: Story = {
  name: "Primary (sm)",
  args: { variant: "primary", sm: true, children: "Export" },
};

export const GhostSmall: Story = {
  name: "Ghost (sm)",
  args: { variant: "ghost", sm: true, children: "Fork" },
};

export const Disabled: Story = {
  args: { variant: "primary", disabled: true, children: "Unavailable" },
};

// Render all variants side-by-side for a quick visual comparison
export const AllVariants: Story = {
  name: "All variants",
  render: () => (
    <div style={{ display: "flex", flexWrap: "wrap", gap: "12px", alignItems: "center" }}>
      <Button variant="primary">Primary</Button>
      <Button variant="ghost">Ghost</Button>
      <Button variant="primary" sm>
        Primary sm
      </Button>
      <Button variant="ghost" sm>
        Ghost sm
      </Button>
      <Button variant="primary" disabled>
        Disabled
      </Button>
    </div>
  ),
};
