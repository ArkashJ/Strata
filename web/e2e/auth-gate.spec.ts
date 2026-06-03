// Signed-OUT behaviour of the gate. Runs in the `public` project (no saved
// auth state), so it exercises a fresh visitor.
import { expect, test } from "@playwright/test";

test("a gated feature route redirects a signed-out visitor to sign-in", async ({ page }) => {
  await page.goto("/build");
  // Clerk does a dev-browser handshake first, then lands on /sign-in.
  await page.waitForURL(/\/sign-in/, { timeout: 25_000 });
  await expect(page.getByText(/sign in to strata/i)).toBeVisible();
});

test("the public landing renders with no app sidebar", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Defensible TAM, fast/i })).toBeVisible();
  // The app nav only exists in the signed-in shell — it must be absent here.
  await expect(page.getByRole("link", { name: "Pyramid explorer" })).toHaveCount(0);
});
