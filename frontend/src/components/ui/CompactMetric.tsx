import { type LucideIcon } from 'lucide-react';

interface Props {
  value: number | string;
  label: string;
  color?: 'green' | 'amber' | 'red' | 'slate';
  icon?: LucideIcon;
  className?: string;
}

export default function CompactMetric({
  value,
  label,
  color = 'slate',
  icon: Icon,
  className = ''
}: Props) {
  const colorMap = {
    green: 'bg-emerald-500',
    amber: 'bg-amber-500',
    red: 'bg-red-500',
    slate: 'bg-slate-500'
  };

  const iconColorMap = {
    green: 'text-emerald-500 dark:text-emerald-400',
    amber: 'text-amber-500 dark:text-amber-400',
    red: 'text-red-500 dark:text-red-400',
    slate: 'text-slate-500 dark:text-slate-400'
  };

  return (
    <div className={`inline-flex items-center gap-2 ${className}`}>
      {Icon ? (
        <Icon className={`w-4 h-4 shrink-0 ${iconColorMap[color]}`} />
      ) : (
        <div className={`w-2 h-2 rounded-full shrink-0 ${colorMap[color]}`} />
      )}
      <div className="flex items-baseline gap-1.5">
        <span className="font-bold text-slate-900 dark:text-slate-100">{value}</span>
        <span className="text-xs text-slate-500 dark:text-slate-400">{label}</span>
      </div>
    </div>
  );
}
