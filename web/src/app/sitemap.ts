// Wave 4 / AC4.1 — sitemap including static routes, curated concept pages, and
// promoted TAMs (the indexable growth surface). Best-effort: a backend hiccup
// degrades to the static routes rather than failing the build.
import type { MetadataRoute } from "next";

import { env } from "@/lib/env";

const SITE =
	process.env.NEXT_PUBLIC_SITE_URL ?? "https://strata-pied-three.vercel.app";

async function safeJson<T>(path: string): Promise<T | null> {
	try {
		const res = await fetch(`${env.NEXT_PUBLIC_API_URL}${path}`, {
			next: { revalidate: 3600 },
		});
		if (!res.ok) return null;
		return (await res.json()) as T;
	} catch {
		return null;
	}
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
	const staticRoutes = [
		"",
		"/browse",
		"/graph",
		"/integrations",
		"/c",
		"/p",
		"/f",
	].map((p) => ({
		url: `${SITE}${p}`,
		changeFrequency: "weekly" as const,
		priority: p === "" ? 1 : 0.6,
	}));

	const concepts = (await safeJson<{ slug: string }[]>("/c")) ?? [];
	const conceptRoutes = concepts.map((c) => ({
		url: `${SITE}/c/${c.slug}`,
		changeFrequency: "monthly" as const,
		priority: 0.5,
	}));

	const promoted = (await safeJson<{ state_hash: string }[]>("/browse")) ?? [];
	const tamRoutes = promoted.map((t) => ({
		url: `${SITE}/tam/${t.state_hash}`,
		changeFrequency: "weekly" as const,
		priority: 0.7,
	}));

	return [...staticRoutes, ...conceptRoutes, ...tamRoutes];
}
