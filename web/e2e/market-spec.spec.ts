/**
 * Market-spec step (sub-project 1.5) — authenticated. The /build?q= entry now
 * gates sizing behind pinning a market: the user confirms vertical / persona /
 * segment / geo before any number. A different pinned market is a different
 * /build/<hash>, and the pinned scope drives the scope check on the result.
 *
 * Runs in the `chromium` project (signed in via storageState). Targets the
 * seeded demo concept demo-ai-sales-ops-us, whose declared market is "all
 * employer firms"; pinning Mid-market makes its all-firms inputs read off-scope,
 * so the ScopeReport is non-ok and the scope check renders real warnings.
 */

import { expect, test } from "@playwright/test";

test.describe("market-spec step", () => {
  test("gates /build?q= behind pinning a market (no auto-size)", async ({ page }) => {
    await page.goto("/build?q=demo-ai-sales-ops-us");

    // The market-spec form is the gate — we must NOT have auto-redirected to a
    // /build/<hash> artifact.
    await expect(page.getByTestId("market-spec")).toBeVisible({ timeout: 20_000 });
    expect(new URL(page.url()).pathname).toBe("/build");

    // Prefilled from the concept's declared scope (its B2B sales-rep personas).
    await expect(page.getByTestId("scope-persona")).toContainText("41-3000");
    await expect(page.getByTestId("size-market")).toBeVisible();
  });

  test("pinning Mid-market sizes the market and surfaces the scope check", async ({ page }) => {
    await page.goto("/build?q=demo-ai-sales-ops-us");
    await expect(page.getByTestId("market-spec")).toBeVisible({ timeout: 20_000 });

    // Pin the segment to Mid-market, then size — the Size button is the gate.
    await page.getByTestId("segment-mid").click();
    await page.getByTestId("size-market").click();

    // Lands on the auto-mint workhorse address (backend state hash folds the
    // pinned market in, so this hash is specific to *this* market).
    await expect(page).toHaveURL(/\/build\/[0-9a-f]{8,}/, { timeout: 30_000 });

    // The pinned market is visible as a chip strip…
    await expect(page.getByTestId("scope-strip")).toContainText(/Mid-market/i, {
      timeout: 20_000,
    });

    // …and the scope check explains why the sources disagree with the pinned
    // market (all-firms inputs read narrower/broader than Mid-market).
    const scopeCheck = page.getByTestId("scope-check");
    await expect(scopeCheck).toBeVisible();
    await expect(scopeCheck).toContainText(/narrower|broader/i);
  });

  test("a different pinned market mints a different /build hash", async ({ page }) => {
    // All firms → one market…
    await page.goto("/build?q=demo-ai-sales-ops-us");
    await expect(page.getByTestId("market-spec")).toBeVisible({ timeout: 20_000 });
    await page.getByTestId("segment-all").click();
    await page.getByTestId("size-market").click();
    await expect(page).toHaveURL(/\/build\/[0-9a-f]{8,}/, { timeout: 30_000 });
    const allFirmsHash = new URL(page.url()).pathname;

    // …Enterprise → a genuinely different market, so a different artifact URL.
    await page.goto("/build?q=demo-ai-sales-ops-us");
    await expect(page.getByTestId("market-spec")).toBeVisible({ timeout: 20_000 });
    await page.getByTestId("segment-ent").click();
    await page.getByTestId("size-market").click();
    await expect(page).toHaveURL(/\/build\/[0-9a-f]{8,}/, { timeout: 30_000 });
    const enterpriseHash = new URL(page.url()).pathname;

    expect(enterpriseHash).not.toBe(allFirmsHash);
  });
});
