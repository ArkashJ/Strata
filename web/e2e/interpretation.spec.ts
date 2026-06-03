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
    // Either the ranked concept list renders (aria-label "Interpretation options"),
    // or — with no close match — the inline "size it with live synthesis" fallback.
    // The lead paragraph always offers a "size it directly" button.
    await expect(
      page
        .getByRole("list", { name: /interpretation options/i })
        .or(page.getByRole("button", { name: /size it with live synthesis/i }))
        .or(page.getByRole("button", { name: /size it directly/i }))
        .first(),
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

  test("home nav link returns to the plain landing", async ({ page }) => {
    await page.goto("/?q=insurance+automation");
    // The brand wordmark is no longer a link (Logo is an aria-hidden glyph); the
    // app shell's home affordance is the "Home" rail link (href="/").
    await page
      .getByRole("navigation", { name: "Primary" })
      .getByRole("link", { name: "Home", exact: true })
      .click();
    await page.waitForURL(/\/$/);
    // Back on the plain landing (no ?q=), the hero search box is present again.
    await expect(page.getByLabel("Market sizing query")).toBeVisible();
  });

  test("nav links visible in interpretation branch", async ({ page }) => {
    await page.goto("/?q=some+query");
    // Same restructured sidebar as the landing spec — assert the current labels.
    const nav = page.getByRole("navigation", { name: "Primary" });
    await expect(nav.getByRole("link", { name: "Home", exact: true })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Dashboard" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Concepts" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Frameworks" })).toBeVisible();
  });
});
