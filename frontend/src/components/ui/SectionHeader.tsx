import { type ReactNode } from 'react';
import { type LucideIcon } from 'lucide-react';

interface Props {
  icon?: LucideIcon;
  title: string;
  subtitle?: string;
  badge?: ReactNode;
  action?: ReactNode;
  className?: string;
  id?: string;
}

export default function SectionHeader({
  icon: Icon,
  title,
  subtitle,
  badge,
  action,
  className = '',
  id
}: Props) {
  return (
    <div id={id} className={`flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${className}`}>
      <div className="flex items-center gap-2">
        {Icon && (
          <div className="p-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400">
            <Icon className="w-4 h-4" />
          </div>
        )}
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">{title}</h2>
          {badge && <div>{badge}</div>}
        </div>
        {subtitle && (
          <span className="text-xs text-slate-500 dark:text-slate-400 hidden sm:inline-block border-l border-slate-300 dark:border-slate-700 pl-2 ml-1">
            {subtitle}
          </span>
        )}
      </div>
      
      {subtitle && (
        <p className="text-xs text-slate-500 dark:text-slate-400 sm:hidden">
          {subtitle}
        </p>
      )}

      {action && (
        <div className="shrink-0">
          {action}
        </div>
      )}
    </div>
  );
}
