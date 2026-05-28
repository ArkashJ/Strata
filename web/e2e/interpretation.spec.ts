/**
 * Interpretation branch tests — /?q=<query> shows fuzzy-matched concept
 * cards instead of navigating straight to /build.
 */

import { expect, test } from "@playwright/test";

test.describe("Interpretation branch (/?q=)", () => {
  test("shows interpretation header with the raw query", async ({ page }) => {
    await page.goto("/?q=doc-gen+insurance");
    await expect(page.getByText(/interpreting your query/i)).toBeVisible();
    await expect(page.getByText(/doc-gen/i)).toBeVisible();
  });

  test("shows at least one card or the direct-size fallback", async ({ page }) => {
    await page.goto("/?q=insurance+automation");
    await expect(
      page
        .getByRole("list", { name: /interpretation options/i })
        .or(page.getByText(/size it with live synthesis/i))
        .or(page.getByRole("button", { name: /size it directly/i })),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("'size it directly' button navigates to /build", async ({ page }) => {
    await page.goto("/?q=niche+market+nobody+has+heard+of");
    const btn = page
      .getByRole("button", { name: /size it directly/i })
      .or(page.getByText(/size it with live synthesis/i))
      .first();
    await expect(btn).toBeVisible({ timeout: 10_000 });
    await btn.click();
    await page.waitForURL(/\/build\?q=/);
    expect(page.url()).toContain("/build?q=");
  });

  test("clicking a card navigates to /build with concept name", async ({ page }) => {
    await page.goto("/?q=doc-gen+insurance");
    const list = page.getByRole("list", { name: /interpretation options/i });
    await expect(list).toBeVisible({ timeout: 10_000 });
    await list.getByRole("listitem").first().getByRole("button").click();
    await page.waitForURL(/\/build\?q=/);
    expect(page.url()).toContain("/build?q=");
  });

  test("logo link returns to plain landing", async ({ page }) => {
    await page.goto("/?q=insurance+automation");
    await page.getByRole("link", { name: "Strata" }).click();
    await page.waitForURL("/");
    expect(page.url()).toMatch(/\/$/);
  });

  test("nav links visible in interpretation branch", async ({ page }) => {
    await page.goto("/?q=some+query");
    await expect(page.getByRole("link", { name: "Data" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Browse" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Contribute" })).toBeVisible();
  });
});
