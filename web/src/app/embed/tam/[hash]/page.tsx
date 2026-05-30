// Wave 4 / AC4.2 — embeddable TAM widget. A compact, self-contained card (no app
// shell) meant to be iframed on a portfolio page or pitch deck. SSR'd so the
// number is in the initial HTML; frame policy relaxed for /embed in next.config.
import { formatCompact } from "@/lib/format";
import { midScenario, tamRange } from "@/lib/tam";
import { getTamServer } from "@/lib/tam-server";

type Props = { params: Promise<{ hash: string }> };

export default async function EmbedTam({ params }: Props) {
  const { hash } = await params;
  const tam = await getTamServer(hash);

  if (!tam) {
    return (
      <div style={{ padding: 24, fontFamily: "system-ui", color: "#737373" }}>TAM not found.</div>
    );
  }

  const unit = midScenario(tam).unit;
  const value = formatCompact(tamRange(tam).mid, unit);
  const concept = tam.target.concept_name ?? tam.target.concept.replace(/-/g, " ");
  const triangulated = tam.method_families_used.length >= 2;

  return (
    <div
      data-testid="embed-tam"
      style={{
        fontFamily: "system-ui, sans-serif",
        background: "#0a0a0a",
        color: "#fafafa",
        borderRadius: 14,
        padding: "20px 24px",
        maxWidth: 420,
        margin: 8,
      }}
    >
      <div style={{ fontSize: 12, letterSpacing: 1.5, color: "#a3a3a3" }}>STRATA · TAM</div>
      <div style={{ fontSize: 17, color: "#d4d4d4", marginTop: 6, textTransform: "capitalize" }}>
        {concept}
      </div>
      <div style={{ fontSize: 44, fontWeight: 700, lineHeight: 1.1, marginTop: 4 }}>{value}</div>
      <div style={{ fontSize: 12, color: "#a3a3a3", marginTop: 8 }}>
        {tam.scenarios.length} scenarios · {triangulated ? "triangulated" : "single method"} · every
        input sourced
      </div>
      <a
        href={`/tam/${hash}`}
        style={{ fontSize: 12, color: "#34d399", marginTop: 10, display: "inline-block" }}
      >
        View full TAM →
      </a>
    </div>
  );
}
