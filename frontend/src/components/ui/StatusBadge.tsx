import { CheckCircle2, AlertTriangle, XCircle, MinusCircle, HelpCircle } from 'lucide-react';

interface Props {
  status?: string | null;
  size?: 'xs' | 'sm' | 'md' | 'lg';
  showIcon?: boolean;
  className?: string;
}

export default function StatusBadge({ status, size = 'md', showIcon = true, className = '' }: Props) {
  const rawStatus = (status || 'UNKNOWN').toUpperCase().replace(/-/g, '_');
  
  let colorClass = 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700';
  let displayText = rawStatus.replace(/_/g, ' ');
  let Icon = HelpCircle;

  if (rawStatus === 'COMPLIANT' || rawStatus === 'PASS') {
    colorClass = 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border-emerald-200/80 dark:border-emerald-800/80 font-semibold';
    displayText = rawStatus === 'COMPLIANT' ? 'COMPLIANT' : 'PASS';
    Icon = CheckCircle2;
  } else if (rawStatus === 'REVIEW_REQUIRED' || rawStatus === 'NEEDS_REVIEW') {
    colorClass = 'bg-amber-50 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border-amber-300/80 dark:border-amber-800/80 font-semibold';
    displayText = rawStatus === 'REVIEW_REQUIRED' ? 'REVIEW REQUIRED' : 'NEEDS REVIEW';
    Icon = AlertTriangle;
  } else if (rawStatus === 'WARNING') {
    colorClass = 'bg-amber-50 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border-amber-300/80 dark:border-amber-800/80 font-semibold';
    displayText = 'WARNING';
    Icon = AlertTriangle;
  } else if (rawStatus === 'NOT_APPLICABLE' || rawStatus === 'N/A') {
    colorClass = 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700 font-medium';
    displayText = 'N/A';
    Icon = MinusCircle;
  } else if (rawStatus.includes('NON_COMPLIANCE') || rawStatus === 'FAIL') {
    colorClass = 'bg-red-50 dark:bg-red-950/60 text-red-800 dark:text-red-300 border-red-200 dark:border-red-800/80 font-semibold';
    displayText = rawStatus === 'FAIL' ? 'FAIL' : 'POTENTIAL NON-COMPLIANCE';
    Icon = XCircle;
  }

  const sizeClasses = {
    xs: 'px-1.5 py-0.5 text-[10px] gap-0.5',
    sm: 'px-2 py-0.5 text-[11px] gap-1',
    md: 'px-2.5 py-1 text-xs gap-1.5',
    lg: 'px-3.5 py-1.5 text-sm gap-2'
  };

  const iconSizes = {
    xs: 'w-2.5 h-2.5',
    sm: 'w-3 h-3',
    md: 'w-3.5 h-3.5',
    lg: 'w-4 h-4'
  };

  return (
    <span className={`inline-flex items-center rounded-full border shadow-2xs transition-colors select-none ${sizeClasses[size]} ${colorClass} ${className}`}>
      {showIcon && <Icon className={`${iconSizes[size]} shrink-0`} />}
      <span>{displayText}</span>
    </span>
  );
}
