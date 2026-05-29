/**
 * Empty-state — a query succeeded but returned nothing (no results, no
 * measurements yet). Centered title + optional description + optional action.
 */

import type { ReactNode } from "react";

export interface EmptyStateProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <p className="font-medium text-[var(--fg-1)] text-sm">{title}</p>
      {description ? <p className="max-w-sm text-[var(--fg-3)] text-sm">{description}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
