import { type Locator, expect, test } from "@playwright/test";

// /graph renders the read-only pyramid: three pillar columns (Qualitative /
// Quantitative / Industry) with the converging TAM apex above. The renderer
// lays nodes out at EXPLICIT positions, so these checks assert on geometry +
// the click/shift-click narrowing behaviour rather than on data values.

// ReactFlow wraps every node in a `.react-flow__node` div whose CSS transform
// carries the node's canvas position. Pull the translate-x so we can assert the
// pillar columns sit at distinct horizontal bands.
async function translateX(node: Locator): Promise<number> {
  const transform = await node.evaluate((el) => getComputedStyle(el).transform);
  // matrix(a, b, c, d, tx, ty) — tx is index 4.
  const m = transform.match(/matrix\(([^)]+)\)/);
  if (!m) return Number.NaN;
  return Number.parseFloat(m[1].split(",")[4]);
}

async function waitForPyramid(page: import("@playwright/test").Page) {
  // The pyramid now lives under the Explore hub.
  await page.goto("/explore/pyramid");
  await expect(page.getByTestId("pyramid-canvas")).toBeVisible({
    timeout: 15_000,
  });
  // At least one selectable leaf has rendered.
  await expect(page.locator("button[data-pillar]").first()).toBeVisible({
    timeout: 15_000,
  });
}

test.describe("Pyramid graph", () => {
  test("renders three pillar heads laid out as separated columns", async ({ page }) => {
    await waitForPyramid(page);

    for (const label of ["Qualitative", "Quantitative", "Industry"]) {
      await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
    }

    // Each pillar's leaves should cluster at a distinct x band — i.e. the three
    // columns do not overlap into one squished horizontal row.
    const xByPillar: Record<string, number> = {};
    for (const pillar of ["qualitative", "quantitative", "industry"]) {
      const leaf = page.locator(`.react-flow__node:has(button[data-pillar="${pillar}"])`).first();
      xByPillar[pillar] = await translateX(leaf);
    }
    // Qualitative left of Quantitative left of Industry, with real gaps.
    expect(xByPillar.qualitative).toBeLessThan(xByPillar.quantitative);
    expect(xByPillar.quantitative).toBeLessThan(xByPillar.industry);
    expect(xByPillar.quantitative - xByPillar.qualitative).toBeGreaterThan(100);
  });

  test("stacks a pillar's leaves vertically (not in one horizontal band)", async ({ page }) => {
    await waitForPyramid(page);
    const qualNodes = page.locator(`.react-flow__node:has(button[data-pillar="qualitative"])`);
    const count = await qualNodes.count();
    test.skip(count < 2, "needs >=2 qualitative leaves to assert vertical stacking");

    const box0 = await qualNodes.nth(0).boundingBox();
    const box1 = await qualNodes.nth(1).boundingBox();
    // Same column (x within a node width) but different rows (y differs).
    expect(Math.abs((box0?.x ?? 0) - (box1?.x ?? 0))).toBeLessThan(80);
    expect(Math.abs((box0?.y ?? 0) - (box1?.y ?? 0))).toBeGreaterThan(20);
  });

  test("clicking a node narrows the view and greys incompatible siblings", async ({ page }) => {
    await waitForPyramid(page);
    const qualLeaves = page.locator(`button[data-pillar="qualitative"]`);
    test.skip((await qualLeaves.count()) < 2, "needs >=2 qualitative leaves");

    const first = qualLeaves.first();
    await first.click();
    await expect(first).toHaveAttribute("aria-pressed", "true");

    // At least one un-selected sibling somewhere is now greyed.
    await expect(page.locator(`button[data-greyed="true"]`).first()).toBeVisible();

    // The right-rail framework counter narrows below the total.
    await expect(page.getByText(/Compatible frameworks/)).toBeVisible();
  });

  test("shift-click ORs a second node within the same pillar", async ({ page }) => {
    await waitForPyramid(page);
    const qualLeaves = page.locator(`button[data-pillar="qualitative"]`);
    test.skip((await qualLeaves.count()) < 2, "needs >=2 qualitative leaves to OR");

    await qualLeaves.nth(0).click();
    await qualLeaves.nth(1).click({ modifiers: ["Shift"] });

    // Both stay pressed — the pillar holds two OR'd choices.
    await expect(qualLeaves.nth(0)).toHaveAttribute("aria-pressed", "true");
    await expect(qualLeaves.nth(1)).toHaveAttribute("aria-pressed", "true");
  });

  test("selecting a single industry concept surfaces the resulting-TAM donut", async ({ page }) => {
    await waitForPyramid(page);
    const industryLeaves = page.locator(`button[data-pillar="industry"]`);
    test.skip((await industryLeaves.count()) < 1, "needs >=1 industry concept");

    await industryLeaves.first().click();

    // RESULTING TAM card appears with the independence donut and a build link.
    await expect(page.getByText("Resulting TAM")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole("img", { name: /Independence score/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /Open this TAM/ })).toHaveAttribute(
      "href",
      /\/build\?q=/,
    );
    // SOURCES panel lists the concept's primitives. Scope to the heading — the
    // sidebar now has a "Sources" nav group that also matches the bare text.
    await expect(page.getByRole("heading", { name: /^Sources/ })).toBeVisible();
  });

  test("STAGE filter chips toggle", async ({ page }) => {
    await waitForPyramid(page);
    const adjacent = page.getByRole("button", { name: "adjacent" });
    await adjacent.click();
    await expect(adjacent).toHaveAttribute("aria-pressed", "true");
  });
});
