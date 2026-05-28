/**
 * Not-found state — a 404 from a detail route (unknown concept / primitive /
 * framework slug). Shows the missing label and an optional link back.
 */

import type { ReactNode } from "react";

export interface NotFoundStateProps {
  label?: string;
  slug?: string;
  action?: ReactNode;
}

export function NotFoundState({ label = "Record", slug, action }: NotFoundStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <p className="font-medium text-[var(--fg-1)] text-sm">{label} not found</p>
      {slug ? (
        <p className="max-w-sm text-[var(--fg-3)] text-sm">
          No record matches <code className="font-mono">{slug}</code>.
        </p>
      ) : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
