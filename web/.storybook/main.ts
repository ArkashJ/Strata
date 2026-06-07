import path from "node:path";
import { fileURLToPath } from "node:url";
import type { StorybookConfig } from "@storybook/react-vite";
import tailwindcss from "@tailwindcss/vite";

// ESM-safe __dirname equivalent (package.json has "type":"module")
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const config: StorybookConfig = {
  stories: ["../src/**/*.stories.@(ts|tsx)"],
  // Storybook 10 bundles essentials internally; no addon entry needed.
  addons: [],
  framework: {
    name: "@storybook/react-vite",
    options: {},
  },
  async viteFinal(cfg) {
    const { mergeConfig } = await import("vite");
    return mergeConfig(cfg, {
      plugins: [tailwindcss()],
      // Force-prebundle React so Vite's CJS→ESM interop synthesizes a `default`
      // export (React 19's index.js otherwise serves raw CJS and the preview
      // dies with "does not provide an export named 'default'").
      optimizeDeps: {
        include: ["react", "react-dom", "react/jsx-runtime", "react/jsx-dev-runtime"],
      },
      resolve: {
        alias: {
          // Map the @/* path alias defined in tsconfig.json
          "@": path.resolve(__dirname, "../src"),
          // next/link → plain <a> wrapper so stories don't need the Next.js runtime
          "next/link": path.resolve(__dirname, "./stubs/next-link.tsx"),
          // next/navigation stubs — guard against transitive router imports
          "next/navigation": path.resolve(__dirname, "./stubs/next-navigation.ts"),
          // next/font/google — strip font loaders; CSS already has the variable declarations
          "next/font/google": path.resolve(__dirname, "./stubs/next-font.ts"),
          // next/image — lightweight pass-through
          "next/image": path.resolve(__dirname, "./stubs/next-image.tsx"),
        },
      },
    });
  },
};

export default config;
