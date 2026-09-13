interface Props {
  variant?: 'page' | 'card' | 'table';
  rows?: number;
}

export default function LoadingSkeleton({ variant = 'page', rows = 4 }: Props) {
  if (variant === 'card') {
    return (
      <div className="animate-pulse bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200/80 dark:border-slate-800 space-y-4">
        <div className="h-5 bg-slate-200 dark:bg-slate-800 rounded-lg w-1/3"></div>
        <div className="space-y-2">
          <div className="h-3.5 bg-slate-100 dark:bg-slate-800/60 rounded w-full"></div>
          <div className="h-3.5 bg-slate-100 dark:bg-slate-800/60 rounded w-5/6"></div>
        </div>
      </div>
    );
  }

  if (variant === 'table') {
    return (
      <div className="animate-pulse bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 overflow-hidden">
        <div className="h-12 bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200/80 dark:border-slate-800"></div>
        <div className="p-6 space-y-4">
          {Array.from({ length: rows }).map((_, i) => (
            <div key={i} className="flex items-center gap-4">
              <div className="w-10 h-10 bg-slate-200 dark:bg-slate-800 rounded-lg shrink-0"></div>
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-slate-200 dark:bg-slate-800 rounded w-1/3"></div>
                <div className="h-3 bg-slate-100 dark:bg-slate-800/60 rounded w-1/4"></div>
              </div>
              <div className="w-16 h-6 bg-slate-100 dark:bg-slate-800 rounded-full"></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="animate-pulse space-y-6 w-full max-w-5xl mx-auto py-6">
      {/* Header skeleton */}
      <div className="space-y-2">
        <div className="h-7 bg-slate-200 dark:bg-slate-800 rounded-lg w-1/4"></div>
        <div className="h-4 bg-slate-100 dark:bg-slate-800/60 rounded w-1/3"></div>
      </div>

      {/* Hero card skeleton */}
      <div className="bg-white dark:bg-slate-900 p-8 rounded-2xl border border-slate-200/80 dark:border-slate-800 space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-2 flex-1">
            <div className="h-6 bg-slate-200 dark:bg-slate-800 rounded-lg w-1/2"></div>
            <div className="h-4 bg-slate-100 dark:bg-slate-800/60 rounded w-1/3"></div>
          </div>
          <div className="w-24 h-24 rounded-full bg-slate-100 dark:bg-slate-800"></div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-slate-100 dark:border-slate-800">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-14 bg-slate-50 dark:bg-slate-800/40 rounded-xl"></div>
          ))}
        </div>
      </div>

      {/* Content skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200/80 dark:border-slate-800 h-64"></div>
        <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200/80 dark:border-slate-800 h-64"></div>
      </div>
    </div>
  );
}
