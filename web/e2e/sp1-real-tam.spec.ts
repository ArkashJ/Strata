/**
 * SP-1 current-UI smoke — proves the app renders live backend data and a query
 * routes into the build flow, against the v0.42 UI.
 *
 * NOTE: the other e2e specs in this directory predate the v0.42 frontend
 * rebuild (PR #54) and assert removed surfaces (e.g. the Contribute nav link),
 * so they are stale/red independent of SP-1. This spec targets the current UI.
 */

import { expect, test } from "@playwright/test";

test.describe("SP-1 — real, live TAM (v0.42 UI)", () => {
  test("home renders live and the query box routes to /build", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 }).first()).toContainText(/TAM/i);
    await expect(page.getByText("Featured TAMs")).toBeVisible({ timeout: 20_000 });

    const box = page.getByRole("textbox", { name: "Market sizing query" });
    await expect(box).toBeVisible();
    await box.fill("AI coding assistants in the US");
    await box.press("Enter");
    await expect(page).toHaveURL(/\/build/, { timeout: 20_000 });
  });

  test("the SP-1 composite-backed concept is live in the UI", async ({ page }) => {
    // ai-coding-assistants-us was seeded in SP-1 W2; its persona pool is the
    // composite us-software-engineering-workforce (5112 U 5415 Census employees).
    await page.goto("/c/ai-coding-assistants-us");
    await expect(page.getByRole("heading", { level: 1 }).first()).toContainText(
      /coding assistants/i,
    );
    await expect(
      page.getByText(/software.engineering.workforce|software engineering/i),
    ).toBeVisible({ timeout: 20_000 });
  });
});
