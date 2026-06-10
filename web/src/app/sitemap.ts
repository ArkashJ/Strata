// The web surface is landing + auth + OAuth consent only — the sole indexable
// page is the landing. No backend fetch: the app routes are retired (see the
// `frontend-archive` branch for the full app).
import type { MetadataRoute } from "next";

const SITE = process.env.NEXT_PUBLIC_SITE_URL ?? "https://stratabank.vercel.app";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: `${SITE}/`,
      changeFrequency: "weekly",
      priority: 1,
    },
  ];
}
