import { expect, test } from "@playwright/test";

// Seed slug verified live against the backend (GET /c/doc-gen-pc-insurance).
const SLUG = "doc-gen-pc-insurance";

test.describe("Concept detail", () => {
  test("renders the concept name, lede, and disagreement view", async ({ page }) => {
    await page.goto(`/c/${SLUG}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText("Disagreement view")).toBeVisible({
      timeout: 15_000,
    });
    // Metadata strip surfaces the measurement count. Exact match: the
    // disagreement-view subtitle ("N measurements · …") would otherwise also
    // match the case-insensitive substring and trip strict mode.
    await expect(page.getByText("Measurements", { exact: true })).toBeVisible();
  });

  test("disagreement toggle switches to the table view", async ({ page }) => {
    await page.goto(`/c/${SLUG}`);
    await expect(page.getByText("Disagreement view")).toBeVisible({
      timeout: 15_000,
    });
    await page.getByRole("tab", { name: "TABLE" }).click();
    // Table header column appears.
    await expect(page.getByRole("columnheader", { name: "Tier" })).toBeVisible();
  });

  test("Build a TAM links to /build seeded with the concept", async ({ page }) => {
    await page.goto(`/c/${SLUG}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({
      timeout: 15_000,
    });
    const buildLink = page.getByRole("link", { name: /Build a TAM/ });
    await expect(buildLink).toHaveAttribute("href", new RegExp(`/build\\?q=${SLUG}`));
  });

  test("unknown concept slug shows a not-found state", async ({ page }) => {
    await page.goto("/c/this-concept-does-not-exist-xyz");
    await expect(page.getByText(/not found/i)).toBeVisible({ timeout: 15_000 });
  });

  test("concepts list links to a detail page", async ({ page }) => {
    await page.goto("/c");
    const firstCard = page.locator("a[href^='/c/']").first();
    await expect(firstCard).toBeVisible({ timeout: 15_000 });
    await firstCard.click();
    await page.waitForURL(/\/c\/[^/]+$/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });
});
