import path from "node:path";
// Playwright global setup: obtain a Clerk Testing Token (bypasses bot
// detection) and sign in the standing test user, saving the authenticated
// storage state so every other spec runs signed-in under the new gate.
import { clerk, clerkSetup } from "@clerk/testing/playwright";
import { test as setup } from "@playwright/test";

// Serial: the token must be obtained before we sign in.
setup.describe.configure({ mode: "serial" });

setup("configure clerk testing token", async () => {
  await clerkSetup();
});

const authFile = path.join(import.meta.dirname, ".clerk", "user.json");

setup("authenticate test user", async ({ page }) => {
  // Clerk must be loaded on the page before clerk.signIn(); /sign-in is public.
  await page.goto("/sign-in");
  // The emailAddress form mints a server-side sign-in token (via the secret key)
  // and bypasses password + verification — the robust path for an existing user.
  await clerk.signIn({
    page,
    emailAddress: process.env.E2E_CLERK_USER_EMAIL ?? "strata+clerk_test@example.com",
  });
  // Prove we actually crossed the gate before trusting the session.
  await page.goto("/dashboard");
  await page.waitForSelector("h1:has-text('Dashboard')", { timeout: 20_000 });
  await page.context().storageState({ path: authFile });
});
