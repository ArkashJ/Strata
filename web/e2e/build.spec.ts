import { type Page, expect, test } from "@playwright/test";

// /build is the workhorse surface (U1, U2, U6). The legacy ?q= entry no longer
// auto-sizes: for a matched concept it renders the MARKET-SPEC GATE first
// (sub-project 1.5) — the user pins the market and clicks "Size this market" to
// recompute + redirect to the canonical /build/<hash>?s=<state> URL. These specs
// drive that gate end-to-end, then exercise the same workhorse invariants as
// before: the headline renders, the rail is in U2 accordion order, a meaningful
// change (deselecting a framework) mints a fresh hash, Back restores losslessly,
// and a single-method state reads as a point estimate. An unknown query still
// streams ResolveView (no gate). Requires the live backend + web servers and an
// authenticated storageState (set by playwright.config).

const KNOWN = "doc-gen-pc-insurance";

// The auto-mint address: /build/<hex hash>?s=<encoded state>. We assert the path
// shape rather than an exact hash so the test survives data/eval changes.
const BUILD_HASH_URL = /\/build\/[a-f0-9]{16,}\?s=/;

// Drive the market-spec gate: from a matched ?q= concept, wait for the gate,
// optionally pick a segment preset, then Size → land on the minted workhorse URL.
// Returns the minted URL so callers can assert on it. The gate is prefilled from
// the concept's declared scope and geo-defaults to US, so a bare Size is valid.
async function sizeThroughGate(
  page: Page,
  query: string,
  opts: { segment?: "all" | "smb" | "mid" | "ent" } = {},
): Promise<string> {
  await page.goto(`/build?q=${query}`);
  // The gate, not an auto-redirect: the concept matched, so we pin the market.
  await expect(page.getByTestId("market-spec")).toBeVisible({ timeout: 20_000 });
  if (opts.segment) {
    await page.getByTestId(`segment-${opts.segment}`).click();
  }
  // The Size button is the only thing that triggers sizing + the redirect.
  await page.getByTestId("size-market").click();
  await page.waitForURL(BUILD_HASH_URL, { timeout: 20_000 });
  // The workhorse headline confirms we left the gate and the TAM resolved.
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible({
    timeout: 15_000,
  });
  return page.url();
}

test.describe("Build workhorse", () => {
  test("market-spec gate sizes to a canonical /build/<hash> URL", async ({ page }) => {
    await page.goto(`/build?q=${KNOWN}`);
    // A matched concept renders the gate first — it does NOT auto-redirect.
    await expect(page.getByTestId("market-spec")).toBeVisible({ timeout: 20_000 });
    expect(page.url()).not.toMatch(BUILD_HASH_URL);

    // Sizing pins the market and replaces the URL with the minted one.
    await page.getByTestId("size-market").click();
    await page.waitForURL(BUILD_HASH_URL, { timeout: 20_000 });
    // The headline renders (triangulated midpoint or single-method estimate).
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({
      timeout: 15_000,
    });
  });

  test("renders the TAM headline and a formatted figure", async ({ page }) => {
    await sizeThroughGate(page, KNOWN);

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
    await sizeThroughGate(page, KNOWN);

    // Target (pinned) → Frameworks → Scenarios → Independence → Lineage → Export.
    // Each section tags itself with data-rail-section; we read them in DOM order
    // and assert the U2 sequence. The Market and Banners sections are conditional
    // (only when the data layer flags scope/provenance), so they're allowed to
    // interleave and are ignored by the subsequence match.
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
    await sizeThroughGate(page, KNOWN);

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

  test("deselecting a framework mints a new /build/<hash> URL, reload restores", async ({ page }) => {
    const before = await sizeThroughGate(page, KNOWN);

    const switches = page.getByRole("switch");
    const count = await switches.count();
    // Toggling requires ≥2 frameworks (we refuse to clear the last one).
    test.skip(count < 2, "concept has a single framework — nothing meaningful to toggle");

    // Deselect the first framework — a meaningful change → auto-mint.
    await switches.first().click();
    await page.waitForFunction((prev) => window.location.href !== prev, before, {
      timeout: 10_000,
    });
    const after = page.url();
    expect(after).not.toBe(before);
    expect(after).toMatch(BUILD_HASH_URL);

    // Mints use router.replace, deliberately (U6: "the current state IS the URL",
    // no history spam for in-flight tweaks) — so Back does NOT step through mints.
    // Losslessness is instead guaranteed by ?s=: a cold reload of the minted URL
    // reconstructs the exact diverged state (framework still deselected).
    await page.reload();
    await expect(page.getByRole("switch").first()).toBeVisible({ timeout: 20_000 });
    expect(page.url()).toBe(after);
    await expect(page.getByRole("switch").first()).toHaveAttribute("aria-checked", "false");
  });

  test("a degenerate (single-method) TAM shows a point estimate, not a range", async ({ page }) => {
    await sizeThroughGate(page, KNOWN);

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

  test("a segment preset pins the market before sizing", async ({ page }) => {
    // Picking a firm-size band on the gate folds into the pinned scope, so the
    // sized URL carries it in ?s= and the workhorse still renders a headline.
    const url = await sizeThroughGate(page, KNOWN, { segment: "mid" });
    expect(url).toMatch(BUILD_HASH_URL);
    await expect(
      page.getByText(/Triangulated midpoint|Single-method estimate/).first(),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("unknown query falls back to ResolveView (no market-spec gate)", async ({ page }) => {
    await page.goto(`/build?q=${encodeURIComponent("quantum computing TAM 2030")}`);
    // No concept matched → no gate; the dynamic resolver streams instead.
    await expect(page.getByTestId("market-spec")).toHaveCount(0);
    await expect(
      page
        .getByText(/resolving/i)
        .or(page.getByText(/thinking/i))
        .or(page.getByText(/back/i))
        .first(),
    ).toBeVisible({ timeout: 20_000 });
  });
});
