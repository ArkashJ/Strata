import type { ReactNode } from "react";

/**
 * Full-screen deep-navy grid + glass surface for the signed-out experience
 * (public landing, /sign-in, /sign-up). The infinite grid + ambient glow sit
 * fixed behind (pointer-events-none); children render above in a scroll column.
 * `.strata-night` re-points the app tokens to navy so anything rendered inside
 * (PyramidGlyph, cards, accent buttons) recolors automatically.
 */
export function NightCanvas({ children }: { children: ReactNode }) {
  return (
    <div className="strata-night relative min-h-dvh w-full overflow-x-hidden">
      <div className="grid-canvas" aria-hidden="true" />
      <div className="relative z-10 flex min-h-dvh flex-col">{children}</div>
    </div>
  );
}
