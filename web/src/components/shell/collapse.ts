/**
 * The sidebar hides its text in two situations: when the user has manually
 * collapsed it (store flag, applies at every width) or, by default, below the
 * `lg` breakpoint where it shrinks to an icon rail. Both the rail width
 * (AppShell) and every label/count use this same trigger so the chrome never
 * shows a label wider than its rail.
 */

// `sr-only` keeps the text in the accessibility tree while hiding it visually.
export function hideLabelClass(collapsed: boolean): string {
  return collapsed ? "sr-only" : "max-lg:sr-only";
}

// For purely decorative bits (the accent dot, the footer cog) that should drop
// out entirely rather than reserve a slot.
export function hideDecorClass(collapsed: boolean): string {
  return collapsed ? "hidden" : "max-lg:hidden";
}
