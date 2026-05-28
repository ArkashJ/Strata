import { expect, test } from "@playwright/test";

test.describe("Build view", () => {
  test("loads for a known concept query", async ({ page }) => {
    await page.goto("/build?q=doc-gen-pc-insurance");
    // Wait for either the build result or the resolve fallback to appear
    await expect(
      page.getByRole("heading", { level: 1 }).or(page.getByText("Sizing")).first(),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("shows TAM midpoint and scenario count for known concept", async ({ page }) => {
    await page.goto("/build?q=doc-gen-pc-insurance");
    // Wait for the build result to fully load — look for "Triangulated midpoint"
    await expect(page.getByText("Triangulated midpoint")).toBeVisible({
      timeout: 15_000,
    });

    // The midpoint value should be formatted as currency
    const midpointEl = page.locator(".tam-num").first();
    await expect(midpointEl).toBeVisible();
    const text = await midpointEl.textContent();
    expect(text).toMatch(/^\$/);

    // Scenario count visible
    await expect(page.getByText(/scenarios/)).toBeVisible();
  });

  test("frameworks accordion is expanded by default", async ({ page }) => {
    await page.goto("/build?q=doc-gen-pc-insurance");
    await expect(page.getByText("Triangulated midpoint")).toBeVisible({
      timeout: 15_000,
    });

    // "Frameworks" section should be expanded (aria-expanded=true)
    const frameworksButton = page.getByRole("button", { name: /Frameworks/ });
    await expect(frameworksButton).toHaveAttribute("aria-expanded", "true");
  });

  test("scenario cards show framework definition and value", async ({ page }) => {
    await page.goto("/build?q=doc-gen-pc-insurance");
    await expect(page.getByText("Triangulated midpoint")).toBeVisible({
      timeout: 15_000,
    });

    // Each scenario card has a lens chip and a dollar value
    const scenarioCards = page.locator("aside li.canvas-card");
    const count = await scenarioCards.count();
    expect(count).toBeGreaterThan(0);

    for (let i = 0; i < count; i++) {
      const card = scenarioCards.nth(i);
      // Has a lens chip (uppercase text like "COST EFFICIENCY")
      await expect(card.locator(".role-chip")).toBeVisible();
      // Has a dollar value
      const valueEl = card.locator(".tam-num");
      await expect(valueEl).toBeVisible();
      const val = await valueEl.textContent();
      expect(val).toMatch(/^\$/);
    }
  });

  test("sidebar Home link navigates to landing", async ({ page }) => {
    await page.goto("/build?q=doc-gen-pc-insurance");
    await expect(page.getByText("Triangulated midpoint")).toBeVisible({
      timeout: 15_000,
    });

    // The per-page back button moved into the app shell — Home returns to "/".
    await page
      .getByRole("navigation", { name: "Primary" })
      .getByRole("link", { name: "Home" })
      .click();
    await page.waitForURL("/");
  });

  test("unknown query falls back to ResolveView", async ({ page }) => {
    await page.goto(`/build?q=${encodeURIComponent("quantum computing TAM 2030")}`);
    // ResolveView should appear with streaming indicators or back button
    // Wait for either the resolve streaming UI or an error/loading state
    await expect(
      page
        .getByText(/resolving/i)
        .or(page.getByText(/thinking/i))
        .or(page.getByText(/back/i))
        .first(),
    ).toBeVisible({ timeout: 20_000 });
  });
});
