/**
 * Shell iconography. Inline 16px stroke icons (Lucide-shaped) drawn with
 * `currentColor` so each one inherits the surrounding text color — active nav
 * rows tint to accent, idle rows sit at fg-2, no per-icon color wiring needed.
 *
 * Kept dependency-free on purpose: the rest of the app avoids an icon package
 * and these are the only glyphs the chrome needs.
 */

import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function Svg({ children, ...rest }: IconProps) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {children}
    </svg>
  );
}

export function HomeIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5 9.5V21h14V9.5" />
    </Svg>
  );
}

export function PyramidIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 3 3 20h18L12 3Z" />
    </Svg>
  );
}

export function IntegrationsIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
      <path d="M10 6.5h4a3 3 0 0 1 3 3V14" />
    </Svg>
  );
}

export function GuidesIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 4.5A1.5 1.5 0 0 1 5.5 3H12v16H5.5A1.5 1.5 0 0 0 4 20.5z" />
      <path d="M20 4.5A1.5 1.5 0 0 0 18.5 3H12v16h6.5A1.5 1.5 0 0 1 20 20.5z" />
    </Svg>
  );
}

export function SearchIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.2-3.2" />
    </Svg>
  );
}

export function ConceptsIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H11v16H5.5A1.5 1.5 0 0 1 4 18.5v-13Z" />
      <path d="M20 5.5A1.5 1.5 0 0 0 18.5 4H13v16h5.5a1.5 1.5 0 0 0 1.5-1.5v-13Z" />
    </Svg>
  );
}

export function PrimitivesIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="2.5" />
    </Svg>
  );
}

export function FrameworksIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 6h7M4 12h12M4 18h7" />
      <circle cx="18" cy="6" r="1.5" />
      <circle cx="18" cy="18" r="1.5" />
    </Svg>
  );
}

export function TamsIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M12 4 4 19h16L12 4Z" />
      <path d="M8.5 12.5h7" />
    </Svg>
  );
}

export function ConnectorsIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 4h16l-6 8v6l-4 2v-8L4 4Z" />
    </Svg>
  );
}

export function PortfolioIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M3 7h18v12H3z" />
      <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </Svg>
  );
}

export function SignalsIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M3 12h3l2.5 6 4-13 2.5 7H21" />
    </Svg>
  );
}

// Shown by ThemeToggle while in dark mode (click → switch to light).
export function SunIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M22 12h-2M4 12H2M19.07 4.93l-1.41 1.41M6.34 17.66l-1.41 1.41M19.07 19.07l-1.41-1.41M6.34 6.34 4.93 4.93" />
    </Svg>
  );
}

// Shown by ThemeToggle while in light mode (click → switch to dark).
export function MoonIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
    </Svg>
  );
}

export function DashboardIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </Svg>
  );
}

export function BellIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M6 9a6 6 0 1 1 12 0c0 5 1.5 6 1.5 6h-15S6 14 6 9Z" />
      <path d="M10 19a2 2 0 0 0 4 0" />
    </Svg>
  );
}

export function MenuIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </Svg>
  );
}
