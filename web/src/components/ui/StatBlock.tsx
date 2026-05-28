/**
 * StatBlock — labelled number tile used in the landing page stats footer.
 */

interface StatBlockProps {
  value: string | number;
  label: string;
  className?: string;
}

export function StatBlock({ value, label, className = "" }: StatBlockProps) {
  return (
    <div className={`flex flex-col items-center gap-0.5 ${className}`}>
      <span className="tam-num text-[22px] text-[var(--fg-1)]">{value}</span>
      <span className="text-[11px] text-[var(--fg-3)] uppercase tracking-[0.08em]">{label}</span>
    </div>
  );
}
