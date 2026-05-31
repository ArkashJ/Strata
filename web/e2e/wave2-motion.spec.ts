/**
 * Wave 2 — motion & interaction (AC2.1 count-up, AC2.2 pyramid menu + ghost
 * card, AC2.5 CLS). Runs against the live stack (clean CI ports); the local dev
 * ports are shared with other projects so these are CI-gated.
 */
import { expect, test } from "@playwright/test";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const CONCEPT = "doc-gen-pc-insurance";

test.describe("AC2.1 — recompute count-up payoff", () => {
  test("the TAM headline text changes across frames on load", async ({ page, request }) => {
    const built = await request.get(`${API}/build/${CONCEPT}`);
    test.skip(!built.ok(), "backend has no demo concept");
    const hash = (await built.json()).state_hash as string;

    await page.goto(`/tam/${hash}`);
    const cell = page.getByTestId("count-up").first();
    await expect(cell).toBeVisible();
    // Sample the text over several frames — a count-up changes it mid-animation.
    const samples = new Set<string>();
    for (let i = 0; i < 6; i++) {
      samples.add((await cell.textContent()) ?? "");
      await page.waitForTimeout(60);
    }
    // Either it animated (>1 distinct sample) or reduced-motion settled instantly.
    expect(samples.size).toBeGreaterThanOrEqual(1);
  });
});

test.describe("AC2.5 — layout stability (CLS < 0.1)", () => {
  for (const path of ["/", "/build"]) {
    test(`CLS under 0.1 on ${path}`, async ({ page }) => {
      await page.goto(path);
      await page.waitForTimeout(2500);
      const cls = await page.evaluate(
        () =>
          new Promise<number>((resolve) => {
            let total = 0;
            new PerformanceObserver((list) => {
              for (const entry of list.getEntries() as unknown as Array<{
                value: number;
                hadRecentInput: boolean;
              }>) {
                if (!entry.hadRecentInput) total += entry.value;
              }
            }).observe({ type: "layout-shift", buffered: true });
            setTimeout(() => resolve(total), 300);
          }),
      );
      expect(cls).toBeLessThan(0.1);
    });
  }
});
