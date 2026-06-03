import { expect, test } from "@playwright/test";

import { buildHash } from "./helpers";

// Frozen TAM artifact (/tam/[hash]). The hash is derived at runtime (see
// helpers.buildHash) — deterministic per backend, derived once and reused.
let KNOWN_HASH = "";

test.beforeEach(async ({ request }) => {
  if (KNOWN_HASH) return;
  KNOWN_HASH = await buildHash(request);
});

test.describe("TAM artifact page", () => {
  test("renders the headline mid scenario card", async ({ page }) => {
    await page.goto(`/tam/${KNOWN_HASH}`);
    // The headline is the triangulated mid scenario card (eyebrow copy).
    await expect(page.getByText("Triangulated midpoint")).toBeVisible({
      timeout: 15_000,
    });
    // Headline value renders in a mono number block.
    await expect(page.locator(".tam-num").first()).toBeVisible();
  });

  test("shows a non-dismissable provenance note only when flagged", async ({ page }) => {
    await page.goto(`/tam/${KNOWN_HASH}`);
    await expect(page.getByText("Triangulated midpoint")).toBeVisible({
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
    await expect(page.getByText("Triangulated midpoint")).toBeVisible({
      timeout: 15_000,
    });
    const fork = page.getByRole("link", { name: "Fork" });
    await expect(fork).toBeVisible();
    await expect(fork).toHaveAttribute("href", "/build");
  });

  test("Export popover offers URL / Markdown / PDF", async ({ page }) => {
    await page.goto(`/tam/${KNOWN_HASH}`);
    await expect(page.getByText("Triangulated midpoint")).toBeVisible({
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
    // NotFoundState renders "{label} not found"; the TAM surface labels it "TAM".
    // Target that exact heading text so we don't strict-mode-collide with the
    // document <title> ("TAM not found · Strata") or the "Browse TAMs" action.
    await expect(page.getByText("TAM not found", { exact: true })).toBeVisible({
      timeout: 15_000,
    });
  });
});
