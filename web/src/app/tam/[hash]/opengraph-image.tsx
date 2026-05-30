// Generated OpenGraph image for a shared TAM (Wave 0 / AC0.8). Renders the
// triangulated value + concept + a source-tier ring via next/og so a pasted
// /tam/<hash> link unfurls into a branded card on Slack / X / iMessage.
import { ImageResponse } from "next/og";

import { formatCompact } from "@/lib/format";
import { midScenario, tamRange } from "@/lib/tam";
import { getTamServer } from "@/lib/tam-server";

export const alt = "Strata TAM";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

type Props = { params: Promise<{ hash: string }> };

export default async function Image({ params }: Props) {
  const { hash } = await params;
  const tam = await getTamServer(hash);

  if (!tam) {
    return new ImageResponse(
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0a0a0a",
          color: "#fafafa",
          fontSize: 64,
        }}
      >
        Strata · TAM not found
      </div>,
      size,
    );
  }

  const unit = midScenario(tam).unit;
  const value = formatCompact(tamRange(tam).mid, unit);
  const concept = tam.target.concept_name ?? tam.target.concept.replace(/-/g, " ");

  // Ring + label by the honesty signal the TAM actually carries: a TAM that
  // spans ≥2 method families is triangulated (green); a single-method estimate
  // is amber. (Per-input source tier isn't on the TAM scenario tree.)
  const triangulated = tam.method_families_used.length >= 2;
  const ring = triangulated ? "#34d399" : "#fbbf24";
  const label = triangulated ? "Triangulated" : "Single method";

  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        background: "#0a0a0a",
        color: "#fafafa",
        padding: "72px 80px",
        fontFamily: "sans-serif",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <div style={{ width: 28, height: 28, borderRadius: 8, background: ring }} />
        <div style={{ fontSize: 30, letterSpacing: 2, color: "#a3a3a3" }}>STRATA · TAM</div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ fontSize: 40, color: "#d4d4d4", textTransform: "capitalize" }}>{concept}</div>
        <div style={{ fontSize: 132, fontWeight: 700, lineHeight: 1 }}>{value}</div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 24, fontSize: 28 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            border: `3px solid ${ring}`,
            borderRadius: 999,
            padding: "10px 24px",
            color: ring,
          }}
        >
          {label}
        </div>
        <div style={{ color: "#a3a3a3" }}>
          {tam.scenarios.length} scenarios · {tam.method_families_used.length} method families
        </div>
      </div>
    </div>,
    size,
  );
}
