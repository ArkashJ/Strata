import { expect, test } from "@playwright/test";

test.describe("Landing page", () => {
  test("loads and shows headline", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("defensible");
    await expect(page.getByText("Strata")).toBeVisible();
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
    await expect(page.getByRole("link", { name: "Data" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Browse" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Contribute" })).toBeVisible();
  });

  test("Popular concepts section renders", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/popular concepts/i)).toBeVisible();
  });

  test("Recently updated section renders with TAM rows", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/recently updated/i)).toBeVisible();
    await expect(page.getByText("Doc-gen tooling for P&C insurance carriers, US")).toBeVisible();
  });

  test("pyramid CTA section renders with graph link", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/explore the data pyramid/i)).toBeVisible();
    await expect(page.getByRole("link", { name: /open graph/i })).toBeVisible();
  });

  test("stats footer shows concept and primitive counts", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("Concepts")).toBeVisible();
    await expect(page.getByText("Primitives")).toBeVisible();
    await expect(page.getByText("Frameworks")).toBeVisible();
  });

  test("Ctrl+K focuses search input", async ({ page }) => {
    await page.goto("/");
    await page.locator("body").click();
    await page.keyboard.press("Control+k");
    await expect(page.getByLabel("Market sizing query")).toBeFocused();
  });
});
