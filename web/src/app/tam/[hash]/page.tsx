// Frozen TAM artifact (U6, U11). The route segment is the canonical state hash —
// the "permanent URL" promise. Server-rendered (AC0.8): the TAM is fetched on the
// server so the initial HTML carries the headline (crawlers + link previews see
// the real value) and generateMetadata can emit OpenGraph tags. The interactive
// surface (Copy/Export, ScenarioGraph, tanstack cache) still lives in the client
// TamDetailView, seeded with the server data so it hydrates without a flash.
import type { Metadata } from "next";

import { TamDetailView } from "@/components/tam/TamDetailView";
import { formatCompact } from "@/lib/format";
import { midScenario, tamRange } from "@/lib/tam";
import { getTamServer } from "@/lib/tam-server";

type Props = { params: Promise<{ hash: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { hash } = await params;
  const tam = await getTamServer(hash);
  if (!tam) {
    return {
      title: "TAM not found · Strata",
      description: "This market-size artifact could not be found.",
    };
  }
  const unit = midScenario(tam).unit;
  const value = formatCompact(tamRange(tam).mid, unit);
  const concept = tam.target.concept_name ?? tam.target.concept.replace(/-/g, " ");
  const title = `${concept} TAM — ${value} · Strata`;
  const description = `Triangulated market size for ${concept}: ${value} across ${
    tam.scenarios.length
  } scenario${tam.scenarios.length === 1 ? "" : "s"} and ${
    tam.method_families_used.length
  } method famil${tam.method_families_used.length === 1 ? "y" : "ies"}, every input sourced.`;
  return {
    title,
    description,
    openGraph: { title, description, type: "article" },
    twitter: { card: "summary_large_image", title, description },
  };
}

export default async function TamPage({ params }: Props) {
  const { hash } = await params;
  const tam = await getTamServer(hash);
  return <TamDetailView hash={hash} initialTam={tam ?? undefined} />;
}
