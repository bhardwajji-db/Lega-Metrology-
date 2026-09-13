import { type ReactNode, useState } from 'react';
import { type LucideIcon, ChevronUp, ChevronDown } from 'lucide-react';

interface Props {
  id?: string;
  title?: string;
  subtitle?: string;
  icon?: LucideIcon;
  iconColor?: string;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  action?: ReactNode;
  compact?: boolean;
  collapsible?: boolean;
}

export default function Card({ 
  id,
  title, 
  subtitle,
  icon: Icon, 
  iconColor = 'text-indigo-600',
  children, 
  className = '', 
  bodyClassName,
  action,
  compact = false,
  collapsible = false
}: Props) {
  const [isOpen, setIsOpen] = useState(true);

  const headerPadding = compact ? 'px-4 py-2.5' : 'px-6 py-4';
  const resolvedBodyClassName = bodyClassName !== undefined ? bodyClassName : (compact ? 'p-4' : 'p-6');

  return (
    <div id={id} className={`bg-white dark:bg-slate-900 rounded-2xl shadow-2xs border border-slate-200/90 dark:border-slate-800 overflow-hidden transition-all duration-200 ${className}`}>
      {(title || Icon || action || collapsible) && (
        <div 
          className={`${headerPadding} border-b border-slate-100 dark:border-slate-800 flex items-center justify-between gap-3 bg-slate-50/60 dark:bg-slate-800/40 ${collapsible ? 'cursor-pointer hover:bg-slate-100/60 dark:hover:bg-slate-800/60 transition-colors' : ''}`}
          onClick={() => collapsible && setIsOpen(!isOpen)}
        >
          <div className="flex items-center gap-3">
            {Icon && (
              <div className="p-2 rounded-xl bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 shadow-2xs">
                <Icon className={`w-4 h-4 ${iconColor}`} />
              </div>
            )}
            <div>
              {title && <h3 className="font-bold text-sm text-slate-900 dark:text-slate-100 tracking-tight">{title}</h3>}
              {subtitle && <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{subtitle}</p>}
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {action && (
              <div onClick={(e) => collapsible && e.stopPropagation()}>
                {action}
              </div>
            )}
            {collapsible && (
              <div className="p-1 rounded-md text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors">
                {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </div>
            )}
          </div>
        </div>
      )}
      {(!collapsible || isOpen) && (
        <div className={resolvedBodyClassName}>
          {children}
        </div>
      )}
    </div>
  );
}
