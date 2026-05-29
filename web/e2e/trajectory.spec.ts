import { expect, test } from "@playwright/test";

// TAM-over-time chart (PR13) on the frozen artifact page. Reuses the seed state
// hash from tam.spec.ts. Seed primitives currently share one as_of date, so the
// honest single-snapshot state is the expected default — the chart must NOT
// fabricate a multi-point curve. The lead runs Playwright.
const KNOWN_HASH = "fb1bab3e782196427c750cbc8a49124f7dbd1236e949014fd74a2f6681060541";

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
