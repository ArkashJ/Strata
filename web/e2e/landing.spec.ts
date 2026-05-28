import { expect, test } from "@playwright/test";

test.describe("Landing page", () => {
  test("loads and shows headline", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("defensible");
    await expect(page.getByText("Strata")).toBeVisible();
  });

  test("search box is visible and accepts input", async ({ page }) => {
    await page.goto("/");
    const searchBox = page.getByPlaceholder("Doc-gen tooling for P&C insurance carriers, US");
    await expect(searchBox).toBeVisible();
    await searchBox.fill("AI agents marketplace");
    await expect(searchBox).toHaveValue("AI agents marketplace");
  });

  test("suggestion chips are visible and clickable", async ({ page }) => {
    await page.goto("/");
    const chips = [
      "Doc-gen tooling for P&C insurance carriers, US",
      "Stripe TAM",
      "AI agents marketplace 2027",
    ];

    for (const chip of chips) {
      await expect(page.getByRole("button", { name: chip })).toBeVisible();
    }
  });

  test("clicking a suggestion chip navigates to /build", async ({ page }) => {
    await page.goto("/");
    const chip = page.getByRole("button", { name: "Stripe TAM" });
    await chip.click();
    await page.waitForURL(/\/build\?q=/);
    expect(page.url()).toContain("/build?q=");
    expect(page.url()).toContain("Stripe");
  });

  test("submitting the form navigates to /build", async ({ page }) => {
    await page.goto("/");
    const searchBox = page.getByPlaceholder("Doc-gen tooling for P&C insurance carriers, US");
    await searchBox.fill("EV charging 2026");
    await page.getByRole("button", { name: /size it/i }).click();
    await page.waitForURL(/\/build\?q=/);
    expect(page.url()).toContain("EV+charging+2026");
  });

  test("shell chrome is present (sidebar nav + topbar)", async ({ page }) => {
    await page.goto("/");
    // Primary nav lives in the app-shell sidebar now, not a per-page header.
    const nav = page.getByRole("navigation", { name: "Primary" });
    await expect(nav.getByRole("link", { name: "Home" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Pyramid explorer" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Concepts" })).toBeVisible();
    // Contribute is a TopBar action.
    await expect(page.getByRole("link", { name: "Contribute" })).toBeVisible();
  });
});
