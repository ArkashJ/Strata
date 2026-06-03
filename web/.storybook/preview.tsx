import type { Preview } from "@storybook/react";
import "../src/app/globals.css";

// Toggle the `dark` class on <html> when the toolbar theme global changes.
// This mirrors what ThemeToggle does in the real app.
const withTheme = (Story: React.ComponentType, context: { globals: { theme?: string } }) => {
  const isDark = context.globals.theme === "dark";
  if (typeof document !== "undefined") {
    document.documentElement.classList.toggle("dark", isDark);
    document.documentElement.style.colorScheme = isDark ? "dark" : "light";
  }
  return <Story />;
};

const preview: Preview = {
  globalTypes: {
    theme: {
      description: "Color theme",
      defaultValue: "light",
      toolbar: {
        title: "Theme",
        icon: "circlehollow",
        items: [
          { value: "light", icon: "sun", title: "Light" },
          { value: "dark", icon: "moon", title: "Dark" },
        ],
        dynamicTitle: true,
      },
    },
  },
  decorators: [
    withTheme,
    // Center stories on the background token so brand tokens are always resolved
    (Story) => (
      <div
        style={{
          minHeight: "100vh",
          backgroundColor: "var(--bg-0)",
          color: "var(--fg-1)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "2rem",
          fontFamily: "var(--font-ui, system-ui, sans-serif)",
        }}
      >
        <Story />
      </div>
    ),
  ],
  parameters: {
    controls: { matchers: { color: /(background|color)$/i, date: /Date$/i } },
    backgrounds: { disable: true },
  },
};

export default preview;
