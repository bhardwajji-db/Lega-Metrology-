import { type ReactNode } from 'react';
import { type LucideIcon } from 'lucide-react';

interface Props {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: ReactNode;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

export default function EmptyState({ 
  icon: Icon, 
  title, 
  description, 
  action, 
  actionLabel, 
  onAction, 
  className = '' 
}: Props) {
  return (
    <div className={`flex flex-col items-center justify-center p-12 text-center bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-200 dark:border-slate-800 shadow-2xs ${className}`}>
      <div className="w-14 h-14 bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-100 dark:border-indigo-800/60 rounded-2xl flex items-center justify-center mb-4 shadow-2xs">
        <Icon className="w-7 h-7 text-indigo-600 dark:text-indigo-400" />
      </div>
      <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 tracking-tight mb-1.5">{title}</h3>
      <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md leading-relaxed mb-6">{description}</p>
      {action ? (
        action
      ) : actionLabel && onAction ? (
        <button
          onClick={onAction}
          className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-xl font-semibold text-xs shadow-2xs hover:shadow-indigo-500/25 transition-all cursor-pointer"
        >
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}

