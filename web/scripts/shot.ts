// Authenticated screenshot tool. Reuses the saved Clerk session from the e2e
// setup so headless captures land INSIDE the app instead of the sign-in wall.
//
// Usage:
//   bunx playwright run scripts/shot.ts            (defaults to /bank)
//   ROUTE=/build bunx tsx scripts/shot.ts          (any path)
//   ROUTE=/tam/abc FULL=1 bunx tsx scripts/shot.ts (full-page)
//
// If the saved session is expired it lands on /sign-in — this script DETECTS
// that and exits non-zero with a loud message instead of saving a useless
// blank. Refresh the session with:  bunx playwright test --project=setup
import { existsSync } from "node:fs";
import path from "node:path";
import { chromium } from "@playwright/test";

const ROUTE = process.env.ROUTE ?? "/bank";
const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const FULL = process.env.FULL === "1";
const authFile = path.join(import.meta.dirname, "..", "e2e", ".clerk", "user.json");

const slug = ROUTE.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "") || "home";
const outPath = path.join(import.meta.dirname, "..", `.shot-${slug}.png`);

async function main() {
  if (!existsSync(authFile)) {
    console.error(`❌ No saved session at ${authFile}\n   Run: bunx playwright test --project=setup`);
    process.exit(2);
  }

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ storageState: authFile, viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  const res = await page.goto(`${BASE}${ROUTE}`, { waitUntil: "networkidle", timeout: 30_000 }).catch((e) => {
    console.error(`❌ Could not reach ${BASE}${ROUTE} — is the dev server up? (bun dev)\n   ${e.message}`);
    return null;
  });
  if (!res) { await browser.close(); process.exit(3); }

  // Honesty check: did we actually cross the gate?
  const landedUrl = page.url();
  if (/\/sign-in|\/sign-up/.test(landedUrl)) {
    console.error(`❌ Bounced to ${landedUrl} — the saved session is expired.\n   Refresh: bunx playwright test --project=setup`);
    await browser.close();
    process.exit(4);
  }

  await page.screenshot({ path: outPath, fullPage: FULL });
  await browser.close();

  // Print the absolute path so it's clickable and verifiable.
  console.log(`✅ ${ROUTE}  ->  ${outPath}`);
  console.log(`   landed at: ${landedUrl}`);
}

main();
