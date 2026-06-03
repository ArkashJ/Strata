import { expect, test } from "@playwright/test";

test.describe("Landing page", () => {
  test("loads and shows headline", async ({ page }) => {
    await page.goto("/");
    // Signed-in home hero (Hero.tsx). "TAM" sits in an <em>, so the heading's
    // textContent is "Defensible TAM, fast." — match the real, current copy.
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Defensible TAM, fast.");
    // The brand wordmark lives in the sidebar header (desktop viewport ≥ lg, so
    // it's rendered, not sr-only).
    await expect(page.getByText("Strata").first()).toBeVisible();
  });

  test("search box is visible and accepts input", async ({ page }) => {
    await page.goto("/");
    const searchBox = page.getByLabel("Market sizing query");
    await expect(searchBox).toBeVisible();
    await searchBox.fill("AI agents marketplace");
    await expect(searchBox).toHaveValue("AI agents marketplace");
  });

  test("submitting the form navigates to /build", async ({ page }) => {
    await page.goto("/");
    await page.getByLabel("Market sizing query").fill("EV charging 2026");
    await page.getByRole("button", { name: /size it/i }).click();
    await page.waitForURL(/\/build\?q=/);
    expect(page.url()).toContain("EV");
  });

  test("nav links are present", async ({ page }) => {
    await page.goto("/");
    // The sidebar nav was restructured (Sidebar.tsx): top group + a LIBRARY
    // group. Assert the stable rail links by their current labels.
    const nav = page.getByRole("navigation", { name: "Primary" });
    await expect(nav.getByRole("link", { name: "Home", exact: true })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Dashboard" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Concepts" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Frameworks" })).toBeVisible();
  });

  test("Popular concepts section renders", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/popular concepts/i)).toBeVisible();
  });

  test("Featured TAMs section renders with TAM rows", async ({ page }) => {
    // The row wait below must fit inside the test budget (default 30s).
    test.setTimeout(110_000);
    await page.goto("/");
    // "Recently updated" was renamed "Featured TAMs" — the rows are now sized
    // live from real concepts (no hardcoded "Doc-gen…" row), so assert the
    // section heading and that a real TAM row (link to /tam/<hash>) renders.
    await expect(page.getByRole("heading", { name: "Featured TAMs" })).toBeVisible();
    // A row is a TamCard <button> that router.pushes to /tam/<hash> — there is
    // no <a> to select. Assert a sized row (dollar range) renders, then click
    // through to the frozen artifact. Patient wait: the rows are sized live and
    // the single-process e2e backend queues under full-suite load.
    const section = page
      .locator("section")
      .filter({ has: page.getByRole("heading", { name: "Featured TAMs" }) });
    const row = section.getByRole("button").first();
    await expect(row).toBeVisible({ timeout: 90_000 });
    await expect(row).toContainText("$");
    await row.click();
    await expect(page).toHaveURL(/\/tam\/[0-9a-f]{8,}/, { timeout: 20_000 });
  });

  test("pyramid CTA section renders with graph link", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/explore the data pyramid/i)).toBeVisible();
    await expect(page.getByRole("link", { name: /open graph/i })).toBeVisible();
  });

  test("stats footer shows concept and primitive counts", async ({ page }) => {
    await page.goto("/");
    // The labels also exist as sidebar nav links, so scope to the stats <footer>
    // (StatBlock labels) to keep the assertion unambiguous.
    const footer = page.locator("footer");
    await expect(footer.getByText("Concepts")).toBeVisible();
    await expect(footer.getByText("Primitives")).toBeVisible();
    await expect(footer.getByText("Frameworks")).toBeVisible();
  });

  test("Ctrl+K reaches a search affordance", async ({ page }) => {
    await page.goto("/");
    await page.locator("body").click();
    await page.keyboard.press("Control+k");
    // Two ⌘K handlers coexist on the signed-in home — the hero's focus handler
    // and the shell's command palette — and which wins depends on listener
    // registration order. Either outcome IS keyboard-to-search: the palette
    // dialog opens (its input takes focus) or the hero query box is focused.
    const palette = page.getByRole("dialog", { name: "Command palette" });
    const heroFocused = page.locator('input[aria-label="Market sizing query"]:focus');
    await expect(palette.or(heroFocused).first()).toBeVisible();
  });
});
