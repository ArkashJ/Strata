/**
 * Strata mark — the indigo triangle over a two-node base. Extracted from the
 * landing page so the sidebar header and the home hero render the identical
 * glyph. Colors are brand tokens; size is caller-controlled.
 */

export interface LogoProps {
  size?: number;
}

export function Logo({ size = 20 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 1200 800"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        d="M 0 -160 L 180 140 L -180 140 Z"
        fill="none"
        stroke="var(--accent)"
        strokeWidth="60"
        strokeLinejoin="round"
        transform="translate(600 400)"
      />
      <circle cx="600" cy="330" r="80" fill="var(--accent)" />
      <circle cx="510" cy="480" r="80" fill="var(--fg-1)" />
      <circle cx="690" cy="480" r="80" fill="var(--fg-1)" />
    </svg>
  );
}
