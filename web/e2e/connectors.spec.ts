import { expect, test } from "@playwright/test";

import { API } from "./helpers";

test.describe("Connector explorer", () => {
  test("GET /connectors returns the catalog with live bank counts", async ({ request }) => {
    const res = await request.get(`${API}/connectors`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);
    expect(body.length).toBeGreaterThan(10);
    // At least one connector has actually produced primitives, with a sample.
    const producing = body.filter((c: { primitives_in_bank: number }) => c.primitives_in_bank > 0);
    expect(producing.length).toBeGreaterThan(0);
    for (const c of producing) {
      expect(c.sample_primitive_slug).toBeTruthy();
      expect(c.source_tier).toBeTruthy();
    }
  });

  test("page shows the pipeline, producing connectors, and a sample link", async ({ page }) => {
    await page.goto("/connectors");
    // "Connectors" appears as both the TopBar route title and the page heading —
    // .first() avoids the strict-mode collision; visibility is what matters.
    await expect(page.getByRole("heading", { name: "Connectors" }).first()).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText("How a number gets here")).toBeVisible();
    await expect(page.getByText(/Producing data now/i)).toBeVisible();
    // A sample primitive link routes into the data bank.
    await expect(page.getByRole("link", { name: /sample →/i }).first()).toBeVisible();
  });

  test("sidebar exposes a Connectors nav link", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Connectors" })).toBeVisible({ timeout: 15_000 });
  });
});
