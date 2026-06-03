import { expect, test } from "@playwright/test";

// TAM-over-time chart (PR13) on the frozen artifact page. Seed primitives
// currently share one as_of date, so the honest single-snapshot state is the
// expected default — the chart must NOT fabricate a multi-point curve.
// The hash is derived at runtime (build-first) — hardcoding strands the file
// the moment the seed data re-mints, and never resolves on a cold backend.
const API = process.env.E2E_API_URL ?? "http://localhost:8000";
let KNOWN_HASH = "";

test.beforeEach(async ({ request }) => {
  if (KNOWN_HASH) return; // deterministic per backend — derive once, reuse
  const built = await request.get(`${API}/build/doc-gen-pc-insurance`);
  expect(built.ok()).toBeTruthy();
  KNOWN_HASH = (await built.json()).state_hash as string;
});

test.describe("TAM over time", () => {
  test("renders the TAM-over-time section on the artifact page", async ({ page }) => {
    await page.goto(`/tam/${KNOWN_HASH}`);
    await expect(page.getByRole("heading", { name: "TAM over time" })).toBeVisible({
      timeout: 15_000,
    });
    // The Current TAM headline appears in both the snapshot and chart states.
    await expect(page.getByText("Current TAM").first()).toBeVisible();
  });

  test("degrades to an honest single-snapshot state when sources share one as-of", async ({
    page,
  }) => {
    await page.goto(`/tam/${KNOWN_HASH}`);
    await expect(page.getByRole("heading", { name: "TAM over time" })).toBeVisible({
      timeout: 15_000,
    });
    // One dated point → no trajectory; the copy says so plainly rather than
    // drawing a degenerate one-dot chart.
    await expect(page.getByText(/single snapshot/i)).toBeVisible();
    // No delta callout is shown when there is no prior point to compare against.
    await expect(page.getByText(/vs previous/i)).toHaveCount(0);
  });
});
