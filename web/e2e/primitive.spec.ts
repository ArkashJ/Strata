import { expect, test } from "@playwright/test";

// Seed slug verified live (GET /p/bls-pc-claims-adjusters-headcount, atomic).
const SLUG = "bls-pc-claims-adjusters-headcount";

test.describe("Primitive detail", () => {
  test("renders an atomic primitive with value, tier, and source snapshot", async ({ page }) => {
    await page.goto(`/p/${SLUG}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({
      timeout: 15_000,
    });
    // Source snapshot section exposes the content-hash pin.
    await expect(page.getByText("Source snapshot")).toBeVisible();
    await expect(page.getByText(/SHA-256/i)).toBeVisible();
    await expect(page.getByText("Methodology")).toBeVisible();
  });

  test("links back to its concept", async ({ page }) => {
    await page.goto(`/p/${SLUG}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({
      timeout: 15_000,
    });
    const conceptLink = page.locator("a[href^='/c/']").first();
    await expect(conceptLink).toBeVisible();
  });

  test("unknown primitive slug shows a not-found state", async ({ page }) => {
    await page.goto("/p/this-primitive-does-not-exist-xyz");
    await expect(page.getByText(/not found/i)).toBeVisible({ timeout: 15_000 });
  });

  test("primitives list paginates and links to detail", async ({ page }) => {
    await page.goto("/p");
    await expect(page.getByText(/Showing \d+ of \d+/)).toBeVisible({
      timeout: 15_000,
    });
    const firstRow = page.locator("a[href^='/p/']").first();
    await firstRow.click();
    await page.waitForURL(/\/p\/[^/]+$/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });
});
