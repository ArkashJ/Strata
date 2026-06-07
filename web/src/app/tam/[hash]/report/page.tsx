// Forwardable report view of a frozen TAM (P2.4). Server-fetches the artifact so
// the report is shareable/crawlable like /tam/<hash>; the print-first rendering
// lives in the client TamReport. No new data — a presentation of the same TAM.
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PremiumTamReport } from "@/components/report/PremiumTamReport";
import { TamReport } from "@/components/tam/TamReport";
import { formatCompact } from "@/lib/format";
import { midScenario, tamRange } from "@/lib/tam";
import { getTamServer } from "@/lib/tam-server";

type Props = {
  params: Promise<{ hash: string }>;
  searchParams: Promise<{ print?: string; classic?: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { hash } = await params;
  const tam = await getTamServer(hash);
  if (!tam) return { title: "Report not found · Strata" };
  const concept = tam.target.concept_name ?? tam.target.concept.replace(/-/g, " ");
  const value = formatCompact(tamRange(tam).mid, midScenario(tam).unit);
  return {
    title: `${concept} — market sizing report (${value}) · Strata`,
    description: `Forwardable, sourced market-sizing report for ${concept}: ${value}.`,
  };
}

export default async function ReportPage({ params, searchParams }: Props) {
  const { hash } = await params;
  const { print, classic } = await searchParams;
  const tam = await getTamServer(hash);
  if (!tam) notFound();
  // The classic print-first one-pager stays the PDF target (other surfaces open
  // it with ?print=1) and is reachable via ?classic=1. The default on-screen
  // report is the premium Coatue/Gartner section system.
  if (print != null || classic != null) return <TamReport tam={tam} />;
  return <PremiumTamReport tam={tam} />;
}
