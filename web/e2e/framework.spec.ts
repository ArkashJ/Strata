import { expect, test } from "@playwright/test";

// Seed slug verified live (GET /f/bottoms-up-cost-efficiency).
const SLUG = "bottoms-up-cost-efficiency";

test.describe("Framework detail", () => {
  test("renders the framework with formula, inputs, and variants", async ({ page }) => {
    await page.goto(`/f/${SLUG}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({
      timeout: 15_000,
    });
    // Target the section headings by role, not free text: the formula prose
    // ("Multiplies its inputs into a …") contains the word "inputs", so a bare
    // getByText("Inputs") matches two nodes and trips strict mode.
    await expect(page.getByRole("heading", { name: "Formula" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Inputs" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Variants" })).toBeVisible();
    // The mono formula string is rendered verbatim.
    await expect(page.getByText("persona_pool * cost_per_persona")).toBeVisible();
  });

  test("variant rows link to their bound primitives", async ({ page }) => {
    await page.goto(`/f/${SLUG}`);
    await expect(page.getByText("Variants")).toBeVisible({ timeout: 15_000 });
    const primitiveLink = page.locator("a[href^='/p/']").first();
    await expect(primitiveLink).toBeVisible();
  });

  test("unknown framework slug shows a not-found state", async ({ page }) => {
    await page.goto("/f/this-framework-does-not-exist-xyz");
    await expect(page.getByText(/not found/i)).toBeVisible({ timeout: 15_000 });
  });

  test("frameworks list links to a detail page", async ({ page }) => {
    await page.goto("/f");
    const firstCard = page.locator("a[href^='/f/']").first();
    await expect(firstCard).toBeVisible({ timeout: 15_000 });
    await firstCard.click();
    await page.waitForURL(/\/f\/[^/]+$/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });
});
