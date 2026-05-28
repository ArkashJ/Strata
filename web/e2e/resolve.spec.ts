/**
 * Resolve-flow tests — a query that matches no registry concept falls through
 * BuildView into ResolveView, which streams POST /resolve as a chain of thought.
 * The local backend has no LLM key, so resolution fails fast; these assertions
 * cover the streaming surface, the terminal controls (Retry / Back), and the
 * nearest-concept fallback that fires on failure. The success-path result card
 * is exercised by the unit test (ResolveView.test.tsx), not here.
 */

import { expect, test } from "@playwright/test";

const NOVEL = "quantum teleportation logistics market 2031";

test.describe("Resolve flow", () => {
  test("a novel query enters the dynamic resolution view", async ({ page }) => {
    await page.goto(`/build?q=${encodeURIComponent(NOVEL)}`);
    await expect(page.getByText(/dynamic tam resolution/i)).toBeVisible({
      timeout: 20_000,
    });
    // The raw query is echoed as the H1.
    await expect(page.getByRole("heading", { level: 1 })).toContainText("quantum teleportation");
  });

  test("shows a streaming or terminal status indicator", async ({ page }) => {
    await page.goto(`/build?q=${encodeURIComponent(NOVEL)}`);
    await expect(
      page
        .getByText(/resolving…/i)
        .or(page.getByText(/^resolved$/i))
        .or(page.getByText(/^failed$/i))
        .first(),
    ).toBeVisible({ timeout: 20_000 });
  });

  test("offers a retry control once the stream settles", async ({ page }) => {
    await page.goto(`/build?q=${encodeURIComponent(NOVEL)}`);
    await expect(page.getByRole("button", { name: /retry resolution/i })).toBeVisible({
      timeout: 25_000,
    });
  });

  test("surfaces nearest registry concepts on a dead-end query", async ({ page }) => {
    await page.goto(`/build?q=${encodeURIComponent(NOVEL)}`);
    // On failure (no LLM key locally) the fallback rail appears with /build links.
    const fallback = page.getByText(/closest concepts in the registry/i);
    await expect(fallback).toBeVisible({ timeout: 25_000 });
    const conceptLink = page.locator("a[href^='/build?q=']").first();
    await expect(conceptLink).toBeVisible();
  });

  test("back button returns to the landing page", async ({ page }) => {
    await page.goto(`/build?q=${encodeURIComponent(NOVEL)}`);
    await expect(page.getByText(/dynamic tam resolution/i)).toBeVisible({
      timeout: 20_000,
    });
    await page.getByRole("button", { name: "Back to search" }).click();
    await page.waitForURL("/");
  });
});
