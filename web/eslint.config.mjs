// ESLint runs ONLY Next.js-specific rules. Biome owns JS/TS lint + format
// (see biome.json). Prettier owns md/css/yaml format (see .prettierrc).
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";

const eslintConfig = defineConfig([
  ...nextVitals,
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "node_modules/**",
    "next-env.d.ts",
    "src/lib/api-schema.d.ts",
  ]),
]);

export default eslintConfig;
