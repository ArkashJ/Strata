import { expect, test } from "@playwright/test";

// Frozen TAM artifact (/tam/[hash]). Uses a known state hash from the seed data.
// NOTE: persisted /tam/{hash} retrieval is not wired in the backend yet, so these
// run against integration once the route resolves; the lead runs Playwright.
const KNOWN_HASH = "fb1bab3e782196427c750cbc8a49124f7dbd1236e949014fd74a2f6681060541";

test.describe("TAM artifact page", () => {
  test("renders the headline mid scenario card", async ({ page }) => {
    await page.goto(`/tam/${KNOWN_HASH}`);
    await expect(page.getByText("Mid scenario")).toBeVisible({
      timeout: 15_000,
    });
    // Headline value renders in a mono number block.
    await expect(page.locator(".tam-num").first()).toBeVisible();
  });

  test("shows a non-dismissable provenance note only when flagged", async ({ page }) => {
    await page.goto(`/tam/${KNOWN_HASH}`);
    await expect(page.getByText("Mid scenario")).toBeVisible({
      timeout: 15_000,
    });
    // The doc-gen TAM uses neither synthetic primitives nor modeled composites,
    // so no provenance banner should appear. There is also no dismiss control.
    await expect(page.getByRole("button", { name: /dismiss/i })).toHaveCount(0);
  });

  test("renders the scenario tree graph", async ({ page }) => {
    await page.goto(`/tam/${KNOWN_HASH}`);
    await expect(page.getByRole("heading", { name: "Scenario tree" })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.locator(".react-flow").first()).toBeVisible();
  });

  test("Fork links to /build", async ({ page }) => {
    await page.goto(`/tam/${KNOWN_HASH}`);
    await expect(page.getByText("Mid scenario")).toBeVisible({
      timeout: 15_000,
    });
    const fork = page.getByRole("link", { name: "Fork" });
    await expect(fork).toBeVisible();
    await expect(fork).toHaveAttribute("href", "/build");
  });

  test("Export popover offers URL / Markdown / PDF", async ({ page }) => {
    await page.goto(`/tam/${KNOWN_HASH}`);
    await expect(page.getByText("Mid scenario")).toBeVisible({
      timeout: 15_000,
    });
    await page.getByRole("button", { name: "Export" }).first().click();
    const menu = page.getByRole("menu");
    await expect(menu.getByRole("menuitem", { name: "Copy URL" })).toBeVisible();
    await expect(menu.getByRole("menuitem", { name: "Download Markdown" })).toBeVisible();
    await expect(menu.getByRole("menuitem", { name: "Download PDF" })).toBeVisible();
  });

  test("unknown hash shows the not-found surface", async ({ page }) => {
    await page.goto("/tam/deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef");
    await expect(page.getByText(/not found/i)).toBeVisible({ timeout: 15_000 });
  });
});
