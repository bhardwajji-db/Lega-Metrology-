import { type ReactNode } from 'react';
import { type LucideIcon } from 'lucide-react';

interface GridItem {
  label: string;
  value: string | ReactNode;
  icon?: LucideIcon;
  truncate?: boolean;
}

interface Props {
  items: GridItem[];
  columns?: 2 | 3;
  className?: string;
}

export default function DataGrid({ items, columns = 2, className = '' }: Props) {
  const gridCols = columns === 3 
    ? 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3' 
    : 'grid-cols-1 sm:grid-cols-2';

  return (
    <div className={`grid gap-4 ${gridCols} ${className}`}>
      {items.map((item, idx) => {
        const isStringValue = typeof item.value === 'string';
        const strVal = isStringValue ? (item.value as string) : '';
        const shouldTruncate = Boolean(item.truncate && isStringValue && strVal.length > 60);
        
        return (
          <div key={idx} className="flex flex-col gap-1">
            <div className="flex items-center gap-1.5">
              {item.icon && <item.icon className="w-3 h-3 text-slate-400" />}
              <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-400 dark:text-slate-500">
                {item.label}
              </span>
            </div>
            
            <div 
              className={`text-xs font-semibold text-slate-900 dark:text-slate-100 ${shouldTruncate ? 'truncate' : ''}`}
              title={shouldTruncate ? strVal : undefined}
            >
              {item.value}
            </div>
          </div>
        );
      })}
    </div>
  );
}
