/**
 * Loading-state placeholder. A pulsing block tinted with the bg-2 surface
 * token — drop one (or a stack) wherever a query is `isPending`.
 */

export interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className = "" }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded-[var(--r-2)] bg-[var(--bg-2)] ${className}`}
    />
  );
}
