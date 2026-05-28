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

export function PullRequestIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="6" cy="6" r="2.5" />
      <circle cx="6" cy="18" r="2.5" />
      <circle cx="18" cy="18" r="2.5" />
      <path d="M6 8.5v7" />
      <path d="M18 15.5V12a3 3 0 0 0-3-3h-3.5" />
      <path d="m13.5 6.5 2 2.5-2 2.5" />
    </Svg>
  );
}

export function AnnotationsIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M4 5h16v11H9l-4 3.5V5Z" />
    </Svg>
  );
}

export function ActivityIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1" />
      <path d="M5.5 4v3.5H9" />
      <path d="M12 8v4.5l3 1.8" />
    </Svg>
  );
}

export function StarIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <path d="m12 4 2.5 5.1 5.6.8-4 3.9 1 5.6L12 16.8 6.9 19.4l1-5.6-4-3.9 5.6-.8L12 4Z" />
    </Svg>
  );
}

export function SettingsIcon(props: IconProps) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2.5v2M12 19.5v2M21.5 12h-2M4.5 12h-2M18.4 5.6l-1.4 1.4M7 17l-1.4 1.4M18.4 18.4 17 17M7 7 5.6 5.6" />
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
