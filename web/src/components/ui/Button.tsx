/**
 * Button — the one button primitive. Two variants (primary indigo / ghost
 * outline) and an optional `sm` size. Wraps a native <button> so type, onClick,
 * disabled, aria-*, etc. all pass through. Colors are brand tokens only.
 */

import type { ButtonHTMLAttributes } from "react";

export type ButtonVariant = "primary" | "ghost";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  sm?: boolean;
}

const base =
  "inline-flex items-center justify-center gap-2 rounded-[var(--r-2)] font-medium " +
  "transition-colors disabled:cursor-not-allowed disabled:opacity-50";

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-[var(--accent)] text-[var(--accent-fg-on)] hover:bg-[var(--accent-hover)] " +
    "active:bg-[var(--accent-active)]",
  ghost:
    "bg-transparent text-[var(--fg-1)] border border-[var(--border-2)] " +
    "hover:bg-[var(--bg-2)] active:bg-[var(--bg-3)]",
};

export function Button({
  variant = "primary",
  sm = false,
  className = "",
  type = "button",
  ...rest
}: ButtonProps) {
  const size = sm ? "px-3 py-1 text-xs" : "px-4 py-2 text-sm";
  return (
    <button type={type} className={`${base} ${variants[variant]} ${size} ${className}`} {...rest} />
  );
}
