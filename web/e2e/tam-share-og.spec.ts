/**
 * Wave 0 / AC0.8 — a shared /tam/<hash> link resolves, is server-rendered, and
 * carries OpenGraph tags.
 *
 * Flow: build a TAM via the live backend (which now persists it, AC0.1), then
 * (1) fetch the page's RAW HTML and assert the TAM value is already in it (SSR,
 * not an empty #root that only fills in after hydration), and (2) assert the
 * og:image + og:title meta tags are present.
 */

import { expect, test } from "@playwright/test";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
// A concept seeded in every backend build, so this spec doesn't depend on
// freshly-added demo data being present in the running backend.
const CONCEPT = "doc-gen-pc-insurance";
const VALUE_RE = /\$[\d.,]+\s*[KMBT]/; // a formatted TAM figure, e.g. "$31.4B"

function distinctiveWord(conceptName: string): string {
  // Longest alpha token (≥5 chars) is a stable, distinctive headline word.
  const words = conceptName.toLowerCase().match(/[a-z]{5,}/g) ?? [];
  return words.sort((a, b) => b.length - a.length)[0] ?? "tam";
}

test.describe("AC0.8 — shareable, SSR'd, OG-tagged TAM permalink", () => {
  test("share link is server-rendered with the value and OG tags", async ({ page, request }) => {
    // 1. Build a TAM so the permalink exists (persisted in the backend process).
    const built = await request.get(`${API}/build/${CONCEPT}`);
    expect(built.ok()).toBeTruthy();
    const body = await built.json();
    const hash = body.state_hash as string;
    expect(hash).toBeTruthy();
    const word = distinctiveWord(body.target.concept_name ?? CONCEPT);

    // 2. Raw HTML must already contain the TAM value (proves SSR, not CSR-only).
    const raw = await request.get(`/tam/${hash}`);
    expect(raw.ok()).toBeTruthy();
    const html = await raw.text();
    expect(html).toMatch(VALUE_RE);
    expect(html.toLowerCase()).toContain(word);

    // 3. OpenGraph tags present (file-convention og:image + generateMetadata title).
    expect(html).toMatch(/<meta[^>]+property="og:image"/);
    expect(html).toMatch(/<meta[^>]+property="og:title"/);

    // 4. The rendered page shows the headline (sanity on the live route).
    await page.goto(`/tam/${hash}`);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    await expect(page.locator("body")).toContainText(VALUE_RE);
  });
});
