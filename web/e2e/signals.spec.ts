import { expect, test } from "@playwright/test";

import { API } from "./helpers";

test.describe("Signals — prediction-market surface (T1)", () => {
  test("GET /signals returns prediction_market rows with a source pin", async ({ request }) => {
    const res = await request.get(`${API}/signals`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);
    expect(body.length).toBeGreaterThan(0);
    for (const sig of body) {
      expect(sig.source_tier).toBe("prediction_market");
      expect(sig.source_url).toBeTruthy();
      expect(String(sig.snapshot_sha256)).toHaveLength(64);
    }
  });

  test("signals never leak into /p (Q20 quarantine)", async ({ request }) => {
    const signalSlugs = new Set(
      ((await (await request.get(`${API}/signals`)).json()) as { slug: string }[]).map(
        (s) => s.slug,
      ),
    );
    const primitiveSlugs = new Set(
      ((await (await request.get(`${API}/p`)).json()) as { slug: string }[]).map((p) => p.slug),
    );
    for (const slug of signalSlugs) {
      expect(primitiveSlugs.has(slug)).toBe(false);
    }
  });

  test("page renders the quarantine banner and a sourced signal row", async ({ page }) => {
    // Signals now lives under the Explore hub as a tab.
    await page.goto("/explore/signals");
    // The honesty banner must lead — signals are never used to size a TAM.
    await expect(page.getByText("never used to size a TAM")).toBeVisible({ timeout: 15_000 });
    // At least one signal row links out to its source.
    await expect(page.getByRole("link", { name: /source/i }).first()).toBeVisible({
      timeout: 15_000,
    });
  });

  test("Explore exposes a Signals tab", async ({ page }) => {
    await page.goto("/explore");
    await expect(page.getByRole("tab", { name: "Signals" })).toBeVisible({ timeout: 15_000 });
  });
});
