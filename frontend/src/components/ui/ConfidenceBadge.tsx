interface Props {
  confidence?: number | null;
  size?: 'sm' | 'md';
  showPercent?: boolean;
  className?: string;
}

export default function ConfidenceBadge({ confidence, size = 'sm', showPercent = true, className = '' }: Props) {
  if (confidence === undefined || confidence === null) {
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-500 border border-slate-200 ${className}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-slate-400"></span>
        <span>Unrated</span>
      </span>
    );
  }

  const confVal = Math.round(Number(confidence));
  let colorClass = 'bg-red-50 text-red-700 border-red-200';
  let dotColor = 'bg-red-500';
  let label = 'Low';

  if (confVal >= 90) {
    colorClass = 'bg-emerald-50 text-emerald-800 border-emerald-200';
    dotColor = 'bg-emerald-500';
    label = 'High';
  } else if (confVal >= 70) {
    colorClass = 'bg-amber-50 text-amber-800 border-amber-200';
    dotColor = 'bg-amber-500';
    label = 'Med';
  }

  const sizeClass = size === 'md' ? 'px-2.5 py-1 text-xs font-semibold' : 'px-2 py-0.5 text-[11px] font-medium';

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md border shadow-2xs ${sizeClass} ${colorClass} ${className}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`}></span>
      <span>{showPercent ? `${confVal}%` : label}</span>
    </span>
  );
}
