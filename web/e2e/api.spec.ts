import { expect, test } from "@playwright/test";

const API_URL = "http://localhost:8000";

test.describe("Backend API", () => {
  test("GET /healthz returns 200", async ({ request }) => {
    const res = await request.get(`${API_URL}/healthz`);
    expect(res.status()).toBe(200);
  });

  test("GET /c returns concepts array", async ({ request }) => {
    const res = await request.get(`${API_URL}/c`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);
    expect(body.length).toBeGreaterThan(0);
    // Each concept should have at least slug and name
    for (const concept of body) {
      expect(concept).toHaveProperty("slug");
      expect(concept).toHaveProperty("name");
    }
  });

  test("GET /p returns primitives array", async ({ request }) => {
    const res = await request.get(`${API_URL}/p`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);
    expect(body.length).toBeGreaterThan(0);
    for (const prim of body) {
      expect(prim).toHaveProperty("slug");
      expect(prim).toHaveProperty("name");
    }
  });

  test("GET /f returns frameworks array", async ({ request }) => {
    const res = await request.get(`${API_URL}/f`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);
    expect(body.length).toBeGreaterThan(0);
    for (const fw of body) {
      expect(fw).toHaveProperty("slug");
      expect(fw).toHaveProperty("name");
    }
  });

  test("GET /build/doc-gen-pc-insurance returns TAM data", async ({ request }) => {
    const res = await request.get(`${API_URL}/build/doc-gen-pc-insurance`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body).toHaveProperty("target");
    expect(body).toHaveProperty("scenarios");
    expect(body).toHaveProperty("state_hash");
    expect(body).toHaveProperty("independence_score");
    expect(Array.isArray(body.scenarios)).toBe(true);
    expect(body.scenarios.length).toBeGreaterThan(0);
  });
});
