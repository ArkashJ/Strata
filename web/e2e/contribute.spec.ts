import { expect, test } from "@playwright/test";

test.describe("Contribute splash", () => {
  test("renders the why / what / schema / licensing sections", async ({ page }) => {
    await page.goto("/contribute");
    await expect(page.getByRole("heading", { name: /Help curate/ })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole("heading", { name: "Why contribute" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "What you contribute" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Record schemas" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Licensing" })).toBeVisible();
  });

  test("states the proprietary license, not open source", async ({ page }) => {
    await page.goto("/contribute");
    await expect(page.getByText(/proprietary and confidential/i)).toBeVisible({
      timeout: 15_000,
    });
  });
});
