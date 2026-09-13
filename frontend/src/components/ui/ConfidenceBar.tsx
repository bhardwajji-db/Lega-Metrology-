interface Props {
  label: string;
  value: number;
  className?: string;
}

export default function ConfidenceBar({ label, value, className = '' }: Props) {
  // Determine color and badge style based on threshold
  let colorClass = 'bg-emerald-500 dark:bg-emerald-400';
  let badgeClass = 'text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/60 border-emerald-200 dark:border-emerald-800/80';
  if (value < 70) {
    colorClass = 'bg-red-500 dark:bg-red-400';
    badgeClass = 'text-red-700 dark:text-red-300 bg-red-50 dark:bg-red-950/60 border-red-200 dark:border-red-800/80';
  } else if (value < 90) {
    colorClass = 'bg-amber-500 dark:bg-amber-400';
    badgeClass = 'text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/60 border-amber-200 dark:border-amber-800/80';
  }

  // Ensure value is between 0 and 100
  const normalizedValue = Math.min(Math.max(value, 0), 100);
  const roundedPercent = Math.round(normalizedValue);

  return (
    <div className={`bg-slate-50/80 dark:bg-slate-800/40 p-3 rounded-xl border border-slate-200/70 dark:border-slate-800 flex flex-col justify-between gap-2.5 min-w-0 transition-colors ${className}`}>
      <div className="flex items-start justify-between gap-2 min-w-0">
        <span 
          className="text-xs font-semibold text-slate-700 dark:text-slate-200 truncate leading-snug"
          title={label}
        >
          {label}
        </span>
        <span className={`text-[11px] font-bold font-mono px-1.5 py-0.5 rounded-md border shrink-0 ${badgeClass}`}>
          {roundedPercent}%
        </span>
      </div>
      
      <div className="w-full h-1.5 bg-slate-200 dark:bg-slate-700/80 rounded-full overflow-hidden flex items-center">
        <div 
          className={`h-full rounded-full transition-all duration-500 ${colorClass}`} 
          style={{ width: `${normalizedValue}%` }}
        />
      </div>
    </div>
  );
}

