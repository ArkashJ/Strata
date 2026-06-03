import { expect, test } from "@playwright/test";

// The command palette is mounted by the app shell on every route. We exercise it
// from a LIBRARY route (/c) rather than the home page: the signed-in home mounts
// its OWN ⌘K handler (LandingContent, which focuses the hero search box), so
// pressing ⌘K there races the shell's palette toggle. Every other route has only
// the shell handler, giving a deterministic open. These assertions touch chrome
// the shell owns — they don't depend on which concepts the backend serves, beyond
// needing the library to load for the typed-filter test.
test.describe("Command palette", () => {
  test("⌘K opens the palette and Escape closes it", async ({ page }) => {
    await page.goto("/c");
    const dialog = page.getByRole("dialog", { name: "Command palette" });
    await expect(dialog).toHaveCount(0);

    await page.keyboard.press("ControlOrMeta+k");
    await expect(dialog).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
  });

  test("the TopBar search button opens the palette", async ({ page }) => {
    await page.goto("/build?q=doc-gen-pc-insurance");
    await page
      .getByRole("button", {
        name: "Search concepts, primitives, frameworks, TAMs",
      })
      .click();
    await expect(page.getByRole("dialog", { name: "Command palette" })).toBeVisible();
  });

  test("typing filters results and arrow+Enter routes to a concept", async ({ page }) => {
    await page.goto("/c");
    await page.keyboard.press("ControlOrMeta+k");

    const dialog = page.getByRole("dialog", { name: "Command palette" });
    const input = dialog.getByPlaceholder(/Jump to concepts/i);
    // A broad term that any seeded concept library should partially match.
    await input.fill("a");

    // Result rows are buttons inside the dialog list; the last is "Size a
    // market", so a real entity row exists once the library loads.
    const firstResult = dialog.locator("ul li button").first();
    await expect(firstResult).toBeVisible({ timeout: 10_000 });

    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");

    // Selecting a result routes to one of the detail surfaces.
    await page.waitForURL(/\/(c|p|f)\/[^/]+/, { timeout: 10_000 });
  });

  test("free text submits a market-sizing query to /?q=", async ({ page }) => {
    await page.goto("/c");
    await page.keyboard.press("ControlOrMeta+k");

    const dialog = page.getByRole("dialog", { name: "Command palette" });
    await dialog.getByPlaceholder(/Jump to concepts/i).fill("quantum widgets market 2030");

    // The trailing "Size a market" action is always last; route through it. Its
    // label is `Size a market: “<query>”`, so match on the leading phrase.
    await dialog.getByRole("button", { name: /size a market/i }).click();
    await page.waitForURL(/\/\?q=/, { timeout: 10_000 });
    expect(page.url()).toContain("quantum");
  });
});
