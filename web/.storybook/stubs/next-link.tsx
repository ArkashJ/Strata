// Minimal next/link stub for Storybook — renders a plain <a> so components
// that import Link from "next/link" work without the Next.js runtime.
import type { AnchorHTMLAttributes } from "react";

type LinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & {
  href: string;
  prefetch?: boolean;
};

export default function Link({ href, prefetch: _prefetch, children, ...rest }: LinkProps) {
  return (
    <a href={href} {...rest}>
      {children}
    </a>
  );
}
