import { expect, test } from "@playwright/test";

const API_URL = "http://localhost:8000";
// A concept sized by two independent method families (bottoms-up + top-down),
// so it exercises both the convergence cross-check and a multi-row provenance table.
const CONCEPT = "doc-gen-pc-insurance";

async function buildHash(request: import("@playwright/test").APIRequestContext): Promise<string> {
  const res = await request.get(`${API_URL}/build/${CONCEPT}`);
  expect(res.status()).toBe(200);
  return (await res.json()).state_hash as string;
}

test.describe("Convergence cross-check (MV2)", () => {
  test("GET /build exposes a convergence object for a multi-family concept", async ({
    request,
  }) => {
    const res = await request.get(`${API_URL}/build/${CONCEPT}`);
    const tam = await res.json();
    expect(tam.method_families_used.length).toBeGreaterThanOrEqual(2);
    expect(tam.convergence).toBeTruthy();
    expect(tam.convergence.ratio).toBeGreaterThanOrEqual(1);
    expect(tam.convergence.low_value).toBeLessThanOrEqual(tam.convergence.high_value);
  });

  test("a single-method concept has no convergence (no fabricated method)", async ({ request }) => {
    const res = await request.get(`${API_URL}/build/software-eng-productivity`);
    const tam = await res.json();
    expect(tam.method_families_used.length).toBe(1);
    expect(tam.convergence).toBeNull();
  });
});

test.describe("Market sizing report", () => {
  test("renders the report with cross-check, methods, and provenance", async ({
    page,
    request,
  }) => {
    const hash = await buildHash(request);
    await page.goto(`/tam/${hash}/report`);

    await expect(page.getByRole("heading", { level: 1 })).toContainText(/insurance/i, {
      timeout: 15_000,
    });
    // The visible letterhead eyebrow (scope to the report main; the <title> also
    // contains "Market Sizing Report").
    await expect(
      page.locator(".tam-report").getByText("Strata · Market Sizing Report"),
    ).toBeVisible();
    await expect(page.getByText("The cross-check")).toBeVisible();
    await expect(page.getByText("How it was sized")).toBeVisible();
    // The provenance table lists at least one sourced input with a tier.
    await expect(page.getByText(/Sources/i).first()).toBeVisible();
    await expect(page.locator("table tbody tr").first()).toBeVisible();

    // Number-level provenance (sub-project 3): the displayed figure itself links
    // to the source behind it — a real http(s) URL from the primitive's source.
    const sourced = page.getByTestId("sourced-number").first();
    await expect(sourced).toBeVisible();
    await expect(sourced).toHaveAttribute("href", /^https?:\/\//);

    // Both-directions honesty (sub-project 2): the report names the canonical
    // directions backing this number.
    await expect(page.getByTestId("method-directions")).toContainText(/Top-down/i);
    await expect(page.getByTestId("method-directions")).toContainText(/Bottoms-up/i);
  });

  test("the interactive TAM links to the report", async ({ page, request }) => {
    const hash = await buildHash(request);
    await page.goto(`/tam/${hash}`);
    await expect(page.getByRole("link", { name: /Generate report/i })).toBeVisible({
      timeout: 15_000,
    });
  });
});
