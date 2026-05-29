import { expect, test } from "@playwright/test";

// /build is the workhorse surface (U1, U2, U6). These specs exercise the real
// auto-mint flow end-to-end: the legacy ?q= entry redirects to a canonical
// /build/<hash>?s= URL, a meaningful change (deselecting a framework) mints a
// fresh hash, Back restores the prior state losslessly, and the rail renders in
// U2 order. Requires the live backend + web servers (playwright.config webServer).

const KNOWN = "doc-gen-pc-insurance";

// The auto-mint address: /build/<hex hash>?s=<encoded state>. We assert the path
// shape rather than an exact hash so the test survives data/eval changes.
const BUILD_HASH_URL = /\/build\/[a-f0-9]{16,}\?s=/;

test.describe("Build workhorse", () => {
  test("known concept redirects to a canonical /build/<hash> URL", async ({ page }) => {
    await page.goto(`/build?q=${KNOWN}`);
    // ?q= entry resolves the concept then replaces the URL with the minted one.
    await page.waitForURL(BUILD_HASH_URL, { timeout: 20_000 });
    // The headline renders (triangulated midpoint or single-method estimate).
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({
      timeout: 15_000,
    });
  });

  test("renders the TAM headline and a formatted figure", async ({ page }) => {
    await page.goto(`/build?q=${KNOWN}`);
    await page.waitForURL(BUILD_HASH_URL, { timeout: 20_000 });

    // Headline eyebrow is one of the two honesty modes — never a fake range.
    await expect(
      page.getByText(/Triangulated midpoint|Single-method estimate/).first(),
    ).toBeVisible({ timeout: 15_000 });

    // The headline figure is currency-formatted.
    const figure = page.locator(".tam-num").first();
    await expect(figure).toBeVisible();
    expect(await figure.textContent()).toMatch(/^\$/);
  });

  test("right rail renders in U2 accordion order", async ({ page }) => {
    await page.goto(`/build?q=${KNOWN}`);
    await page.waitForURL(BUILD_HASH_URL, { timeout: 20_000 });
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({
      timeout: 15_000,
    });

    // Target (pinned) → Frameworks → Scenarios → Independence → Lineage → Export.
    // Each section tags itself with data-rail-section; we read them in DOM order
    // and assert the U2 sequence. Banners is conditional (only when the data
    // layer flags something), so it's allowed to interleave and is ignored.
    const sections = page.locator("aside [data-rail-section]");
    const labels = await sections.evaluateAll((els) =>
      els.map((el) => el.getAttribute("data-rail-section") ?? ""),
    );
    const expected = ["Target", "Frameworks", "Scenarios", "Independence", "Lineage", "Export"];
    let cursor = 0;
    for (const label of labels) {
      if (cursor < expected.length && label.startsWith(expected[cursor])) cursor += 1;
    }
    expect(cursor).toBe(expected.length);
  });

  test("Frameworks and Scenarios are expanded; Independence/Lineage collapsed", async ({
    page,
  }) => {
    await page.goto(`/build?q=${KNOWN}`);
    await page.waitForURL(BUILD_HASH_URL, { timeout: 20_000 });
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({
      timeout: 15_000,
    });

    // Open sections expose their contents; collapsed ones show only the toggle.
    await expect(page.getByRole("switch").first()).toBeVisible(); // a framework row
    await expect(page.getByRole("button", { name: /Independence/ })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    await expect(page.getByRole("button", { name: /Lineage/ })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  test("deselecting a framework mints a new /build/<hash> URL, Back restores", async ({ page }) => {
    await page.goto(`/build?q=${KNOWN}`);
    await page.waitForURL(BUILD_HASH_URL, { timeout: 20_000 });
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({
      timeout: 15_000,
    });

    const switches = page.getByRole("switch");
    const count = await switches.count();
    // Toggling requires ≥2 frameworks (we refuse to clear the last one).
    test.skip(count < 2, "concept has a single framework — nothing meaningful to toggle");

    const before = page.url();
    // Deselect the first framework — a meaningful change → auto-mint.
    await switches.first().click();
    await page.waitForFunction((prev) => window.location.href !== prev, before, {
      timeout: 10_000,
    });
    const after = page.url();
    expect(after).not.toBe(before);
    expect(after).toMatch(BUILD_HASH_URL);

    // Back restores the prior minted state (lossless — U6).
    await page.goBack();
    await page.waitForFunction((next) => window.location.href !== next, after, {
      timeout: 10_000,
    });
    expect(page.url()).toBe(before);
  });

  test("a degenerate (single-method) TAM shows a point estimate, not a range", async ({ page }) => {
    await page.goto(`/build?q=${KNOWN}`);
    await page.waitForURL(BUILD_HASH_URL, { timeout: 20_000 });
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({
      timeout: 15_000,
    });

    const switches = page.getByRole("switch");
    const count = await switches.count();
    test.skip(count < 2, "cannot force a single-method state without ≥2 frameworks");

    // Deselect every framework but one → single method family → degenerate.
    for (let i = 0; i < count - 1; i++) {
      // Re-query each iteration: the rail re-renders after each mint.
      await page.getByRole("switch").nth(0).click();
      await page.waitForLoadState("networkidle").catch(() => {});
    }

    await expect(page.getByText("Single-method estimate").first()).toBeVisible({
      timeout: 10_000,
    });
    // Independence is greyed with the "needs ≥2 method families" caption.
    await expect(page.getByText(/needs ≥2 method families/).first()).toBeVisible();
  });

  test("unknown query falls back to ResolveView", async ({ page }) => {
    await page.goto(`/build?q=${encodeURIComponent("quantum computing TAM 2030")}`);
    await expect(
      page
        .getByText(/resolving/i)
        .or(page.getByText(/thinking/i))
        .or(page.getByText(/back/i))
        .first(),
    ).toBeVisible({ timeout: 20_000 });
  });
});
