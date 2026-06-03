import { readFileSync } from "node:fs";
import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

// Load web/.env.local (no dotenv dependency) so clerkSetup() and the dev
// webServer get the Clerk keys. .env.local values do not override anything
// already set in the real environment (CI provides its own).
function loadEnvLocal() {
  try {
    const raw = readFileSync(path.join(import.meta.dirname, ".env.local"), "utf8");
    for (const line of raw.split("\n")) {
      const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/);
      if (m?.[1] && process.env[m[1]] === undefined) process.env[m[1]] = m[2];
    }
  } catch {
    // No .env.local (e.g. CI) — rely on the real environment.
  }
}
loadEnvLocal();

// @clerk/testing reads CLERK_PUBLISHABLE_KEY (no NEXT_PUBLIC_ prefix).
if (!process.env.CLERK_PUBLISHABLE_KEY && process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) {
  process.env.CLERK_PUBLISHABLE_KEY = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
}

// Dedicated e2e port so the suite never collides with a hand-run dev server.
const PORT = Number(process.env.E2E_PORT ?? 3200);
const baseURL = process.env.E2E_BASE_URL ?? `http://localhost:${PORT}`;
const authFile = path.join(import.meta.dirname, "e2e", ".clerk", "user.json");

// Clerk-enabled only when a key is present. Without one the gate is inert, so
// the auth setup + gate spec are skipped and the rest run keyless (as before).
const clerkReady = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  // One local retry (CI keeps 2): the latency-sensitive specs rotate flakes
  // under full-suite load on the single-process backend; a retried pass is
  // reported as "flaky" — honest — while a real regression still fails twice.
  retries: process.env.CI ? 2 : 1,
  // Local cap, not cores/2: the e2e backend is ONE Python process whose sync
  // size_concept blocks its event loop, so 5-6 workers' build/sensitivity
  // traffic queues for minutes and starves latency-sensitive specs (featured
  // TAM rows, /tam SSR). Three workers keeps it honest AND fast enough.
  workers: process.env.CI ? 1 : 3,
  reporter: "html",

  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    navigationTimeout: 30_000,
  },

  projects: clerkReady
    ? [
        { name: "setup", testMatch: /global\.setup\.ts/ },
        {
          name: "chromium",
          use: { ...devices["Desktop Chrome"], storageState: authFile },
          dependencies: ["setup"],
          // The gate spec is signed-out; everything else runs authenticated.
          testIgnore: /auth-gate\.spec\.ts/,
        },
        {
          name: "public",
          use: { ...devices["Desktop Chrome"] },
          testMatch: /auth-gate\.spec\.ts/,
        },
      ]
    : [
        // Keyless (gate inert): run every spec signed-out, skip the auth setup.
        {
          name: "chromium",
          use: { ...devices["Desktop Chrome"] },
          testIgnore: /(global\.setup|auth-gate\.spec)\.ts/,
        },
      ],

  webServer: [
    {
      command: "cd ../backend && uv run uvicorn strata.api.app:app --port 8000",
      url: "http://localhost:8000/healthz",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      // Deterministic resolver: force the SDK backend with a key that can't
      // work, so /resolve settles to its honest error in ~1s everywhere. The
      // default backend shells out to the `claude` CLI, which EXISTS on dev
      // machines (subscription auth) — turning the resolve specs into real
      // 30–90s LLM calls locally while CI (no CLI) fails fast. Offline also
      // pins the goal pipeline's live/fallback steps off.
      env: {
        STRATA_LLM_BACKEND: "anthropic",
        ANTHROPIC_API_KEY: "e2e-invalid-key",
        STRATA_OFFLINE: "1",
      },
    },
    {
      command: `bun dev --port ${PORT}`,
      url: baseURL,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      // Point the e2e frontend at the LOCAL backend (CORS-open to localhost) and
      // hand it the Clerk keys so the gate engages during the run.
      env: {
        NEXT_PUBLIC_API_URL: "http://localhost:8000",
        NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ?? "",
        CLERK_SECRET_KEY: process.env.CLERK_SECRET_KEY ?? "",
        NEXT_PUBLIC_CLERK_SIGN_IN_URL: "/sign-in",
        NEXT_PUBLIC_CLERK_SIGN_UP_URL: "/sign-up",
        NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL: "/",
        NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL: "/",
      },
    },
  ],
});
