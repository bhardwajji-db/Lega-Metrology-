interface Props {
  severity?: 'high' | 'medium' | 'low' | string | null;
  className?: string;
}

export default function SeverityBadge({ severity, className = '' }: Props) {
  const norm = (severity || 'medium').toLowerCase();
  
  let colorClass = 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700';
  let dotColor = 'bg-slate-400 dark:bg-slate-500';
  
  if (norm === 'high') {
    colorClass = 'bg-red-50 dark:bg-red-950/60 text-red-700 dark:text-red-300 border-red-200/80 dark:border-red-800/60 font-bold';
    dotColor = 'bg-red-500 dark:bg-red-400';
  } else if (norm === 'medium') {
    colorClass = 'bg-amber-50 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border-amber-200/80 dark:border-amber-800/60 font-semibold';
    dotColor = 'bg-amber-500 dark:bg-amber-400';
  } else if (norm === 'low') {
    colorClass = 'bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border-blue-200/80 dark:border-blue-800/60 font-medium';
    dotColor = 'bg-blue-500 dark:bg-blue-400';
  }

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded-md border shadow-2xs select-none ${colorClass} ${className}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`}></span>
      <span>{norm}</span>
    </span>
  );
}
