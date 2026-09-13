import React from 'react';
import StatusBadge from '../ui/StatusBadge';
import ScoreCircle from '../ui/ScoreCircle';

interface ExecutiveSummaryProps {
  score: number;
  status: string;
  passedCount: number;
  needsReviewCount: number;
  failedCount: number;
  notApplicableCount: number;
  applicableCount: number;
  statusExplanation: string;
  isCompliant: boolean;
  isReviewRequired: boolean;
}

const ExecutiveSummary: React.FC<ExecutiveSummaryProps> = ({
  score,
  status,
  passedCount,
  needsReviewCount,
  failedCount,
  notApplicableCount,
  statusExplanation,
  isCompliant,
  isReviewRequired,
}) => {
  let bgClass = 'bg-slate-50 dark:bg-slate-900';
  let borderClass = 'border-slate-200/90 dark:border-slate-800';
  
  if (isCompliant) {
    bgClass = 'bg-emerald-50/70 dark:bg-emerald-950/20';
    borderClass = 'border-emerald-200/80 dark:border-emerald-800/60';
  } else if (isReviewRequired) {
    bgClass = 'bg-amber-50/70 dark:bg-amber-950/20';
    borderClass = 'border-amber-200/80 dark:border-amber-800/60';
  } else if (failedCount > 0) {
    bgClass = 'bg-red-50/70 dark:bg-red-950/20';
    borderClass = 'border-red-200/80 dark:border-red-800/60';
  }

  return (
    <div className={`rounded-2xl border ${bgClass} ${borderClass} p-4 sm:p-5 mb-6 shadow-2xs transition-all duration-200 space-y-4`}>
      {/* Top Section: Overall Verdict Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3.5 border-b border-slate-200/70 dark:border-slate-800/70">
        <div className="flex items-center gap-3 flex-wrap">
          <StatusBadge status={status} size="lg" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            Compliance Verdict
          </span>
        </div>
        <p className="text-xs sm:text-sm text-slate-700 dark:text-slate-300 font-medium leading-relaxed sm:text-right">
          {statusExplanation}
        </p>
      </div>

      {/* Bottom Section: 4 Metric Badges + Compliance Score Card */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        {/* Metric Badges Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 sm:gap-3 flex-1">
          {/* Passed */}
          <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl bg-white dark:bg-slate-900 border border-emerald-200/90 dark:border-emerald-900/60 shadow-2xs">
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 shrink-0" />
            <div className="min-w-0">
              <div className="text-xs sm:text-sm font-black text-emerald-950 dark:text-emerald-200 font-mono tracking-tight">
                {passedCount} Passed
              </div>
              <div className="text-[10px] text-emerald-700 dark:text-emerald-400 font-semibold truncate">
                Verified
              </div>
            </div>
          </div>

          {/* Needs Review */}
          <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl bg-white dark:bg-slate-900 border border-amber-200/90 dark:border-amber-900/60 shadow-2xs">
            <div className="w-2.5 h-2.5 rounded-full bg-amber-500 shrink-0" />
            <div className="min-w-0">
              <div className="text-xs sm:text-sm font-black text-amber-950 dark:text-amber-200 font-mono tracking-tight">
                {needsReviewCount} Review
              </div>
              <div className="text-[10px] text-amber-700 dark:text-amber-400 font-semibold truncate">
                Check required
              </div>
            </div>
          </div>

          {/* Failed */}
          <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl bg-white dark:bg-slate-900 border border-red-200/90 dark:border-red-900/60 shadow-2xs">
            <div className="w-2.5 h-2.5 rounded-full bg-red-500 shrink-0" />
            <div className="min-w-0">
              <div className="text-xs sm:text-sm font-black text-red-950 dark:text-red-200 font-mono tracking-tight">
                {failedCount} Failed
              </div>
              <div className="text-[10px] text-red-700 dark:text-red-400 font-semibold truncate">
                Non-compliant
              </div>
            </div>
          </div>

          {/* N/A */}
          <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 shadow-2xs">
            <div className="w-2.5 h-2.5 rounded-full bg-slate-400 shrink-0" />
            <div className="min-w-0">
              <div className="text-xs sm:text-sm font-black text-slate-800 dark:text-slate-200 font-mono tracking-tight">
                {notApplicableCount} N/A
              </div>
              <div className="text-[10px] text-slate-500 dark:text-slate-400 font-semibold truncate">
                Not applicable
              </div>
            </div>
          </div>
        </div>

        {/* Dedicated Compliance Score Box */}
        <div className="flex items-center justify-between sm:justify-end gap-3.5 px-4 py-2.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 shrink-0 shadow-2xs">
          <div className="text-left sm:text-right">
            <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest block">
              COMPLIANCE SCORE
            </span>
            <div className="flex items-baseline gap-1">
              <span className="text-base sm:text-lg font-black text-slate-900 dark:text-slate-100 font-mono">
                {Number(score || 0).toFixed(1)}
              </span>
              <span className="text-xs text-slate-400 dark:text-slate-500 font-semibold">
                / 100
              </span>
            </div>
          </div>

          <ScoreCircle score={score ?? 0} size={44} strokeWidth={4.5} showOutOf={false} />
        </div>
      </div>
    </div>
  );
};

export default ExecutiveSummary;
