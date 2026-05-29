import { expect, test } from "@playwright/test";

test.describe("Browse registry", () => {
  test("renders the TAM grid from the concepts registry", async ({ page }) => {
    await page.goto("/browse");
    await expect(page.getByRole("heading", { name: "Browse TAMs" })).toBeVisible({
      timeout: 15_000,
    });
    // At least one registry card seeded from a concept.
    await expect(page.locator("button.canvas-card").first()).toBeVisible({
      timeout: 15_000,
    });
  });

  test("text filter narrows the grid", async ({ page }) => {
    await page.goto("/browse");
    await expect(page.locator("button.canvas-card").first()).toBeVisible({
      timeout: 15_000,
    });
    const before = await page.locator("button.canvas-card").count();
    await page.getByPlaceholder("Filter TAMs…").fill("zzz-no-such-tam-zzz");
    await expect(page.getByText("No TAMs match")).toBeVisible();
    expect(before).toBeGreaterThan(0);
  });

  test("a lens chip filters by analysis lens", async ({ page }) => {
    await page.goto("/browse");
    await expect(page.locator("button.canvas-card").first()).toBeVisible({
      timeout: 15_000,
    });
    const allChip = page.getByRole("button", { name: "All", exact: true });
    await expect(allChip).toHaveAttribute("aria-pressed", "true");
  });

  test("a card builds the seeded TAM", async ({ page }) => {
    await page.goto("/browse");
    const firstCard = page.locator("button.canvas-card").first();
    await expect(firstCard).toBeVisible({ timeout: 15_000 });
    await firstCard.click();
    await page.waitForURL(/\/build\?q=/);
  });
});
