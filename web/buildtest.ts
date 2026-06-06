// Interactively exercise the 3 /build tabs to reproduce "none of them work".
import { clerk, clerkSetup } from "@clerk/testing/playwright";
import { chromium, type Page } from "@playwright/test";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const OUT = "/Users/arkashjain/.claude/jobs/d46d3c04/tmp";
const errors: string[] = [];
const failed: string[] = [];

async function shoot(page: Page, name: string) {
  await page.screenshot({ path: `${OUT}/bt-${name}.png`, fullPage: true });
  console.log(`   📸 ${name} (url ${page.url()})`);
}

async function main() {
  await clerkSetup({ publishableKey: process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } } as never);
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text().slice(0, 180)); });
  page.on("requestfailed", (r) => failed.push(`${r.method()} ${r.url().slice(0, 90)} :: ${r.failure()?.errorText}`));

  await page.goto(`${BASE}/sign-in`, { waitUntil: "domcontentloaded" });
  await clerk.signIn({ page, emailAddress: "strata+clerk_test@example.com" });
  await page.goto(`${BASE}/build`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);

  // TAB 1: Pin the market -> Size this market
  console.log("TAB 1: Pin the market -> click 'Size this market'");
  const sizeBtn = page.getByRole("button", { name: /size this market/i });
  console.log("   size button visible:", await sizeBtn.isVisible().catch(() => false));
  await sizeBtn.click().catch((e) => console.log("   click err:", e.message));
  await page.waitForTimeout(8000);
  console.log("   after click url:", page.url());
  await shoot(page, "1-after-size");

  // TAB 2: Watch it build
  console.log("TAB 2: Watch it build");
  await page.goto(`${BASE}/build`, { waitUntil: "domcontentloaded" });
  await page.getByRole("tab", { name: /watch it build/i }).click().catch(async () => {
    await page.getByText(/watch it build/i).first().click().catch((e) => console.log("   tab err:", e.message));
  });
  await page.waitForTimeout(4000);
  await shoot(page, "2-watch-it-build");
  console.log("   body snippet:", (await page.locator("main").innerText().catch(() => "")).slice(0, 200).replace(/\n+/g, " | "));

  // TAB 3: Compose a graph
  console.log("TAB 3: Compose a graph");
  await page.goto(`${BASE}/build`, { waitUntil: "domcontentloaded" });
  await page.getByText(/compose a graph/i).first().click().catch((e) => console.log("   tab err:", e.message));
  await page.waitForTimeout(4000);
  await shoot(page, "3-compose-graph");
  console.log("   body snippet:", (await page.locator("main").innerText().catch(() => "")).slice(0, 200).replace(/\n+/g, " | "));

  console.log(`\n=== console errors (${errors.length}):`); errors.slice(0, 10).forEach((e) => console.log("   • " + e));
  console.log(`=== failed requests (${failed.length}):`); failed.slice(0, 10).forEach((e) => console.log("   • " + e));
  await browser.close();
}
main();
