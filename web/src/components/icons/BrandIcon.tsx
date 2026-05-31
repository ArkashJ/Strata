// Wave 5C / AC5C.1 — a brand mark in a circular chip with a source-tier ring.
// Known vendors render the simple-icons SVG path; everything else (gov sources,
// unknown names) degrades to a tinted monogram — never a crash.
import { brandHex, brandMark, monogram } from "./brand-registry";

export function BrandIcon({
  name,
  size = 28,
  ring,
}: {
  name: string;
  size?: number;
  ring?: string;
}) {
  const mark = brandMark(name);
  const hex = ring ?? brandHex(name);
  return (
    <span
      data-testid={`brand-icon-${name.toLowerCase().replace(/\s+/g, "-")}`}
      title={name}
      role="img"
      aria-label={name}
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--bg-2)",
        boxShadow: `inset 0 0 0 2px ${hex}`,
        flexShrink: 0,
      }}
    >
      {mark ? (
        <svg
          width={size * 0.55}
          height={size * 0.55}
          viewBox="0 0 24 24"
          fill={hex}
          aria-hidden="true"
        >
          <path d={mark.path} />
        </svg>
      ) : (
        <span
          style={{
            fontSize: size * 0.38,
            fontWeight: 600,
            color: hex,
            lineHeight: 1,
          }}
        >
          {monogram(name)}
        </span>
      )}
    </span>
  );
}
