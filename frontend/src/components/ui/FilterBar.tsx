import { Search } from 'lucide-react';

interface FilterOption {
  value: string;
  label: string;
  count?: number;
}

interface Props {
  statusFilter: string;
  onStatusFilter: (status: string) => void;
  domainFilter?: string;
  onDomainFilter?: (domain: string) => void;
  searchQuery?: string;
  onSearch?: (query: string) => void;
  statusOptions?: FilterOption[];
  domainOptions?: FilterOption[];
  className?: string;
}

export default function FilterBar({
  statusFilter,
  onStatusFilter,
  domainFilter,
  onDomainFilter,
  searchQuery,
  onSearch,
  statusOptions = [],
  domainOptions = [],
  className = ''
}: Props) {
  return (
    <div className={`flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${className}`}>
      {/* Search Input */}
      {onSearch !== undefined && (
        <div className="relative max-w-md w-full sm:w-64 shrink-0">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search requirements..."
            value={searchQuery || ''}
            onChange={(e) => onSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-sm bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/50 dark:text-slate-200 transition-colors"
          />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 lg:gap-4 overflow-x-auto pb-1 sm:pb-0 scrollbar-hide">
        {/* Status Filter Pills */}
        {statusOptions.length > 0 && (
          <div className="flex items-center gap-1.5">
            {statusOptions.map(option => (
              <button
                key={option.value}
                onClick={() => onStatusFilter(option.value)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors whitespace-nowrap cursor-pointer ${
                  statusFilter === option.value
                    ? 'bg-slate-900 dark:bg-indigo-600 text-white shadow-2xs'
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
                }`}
              >
                {option.label}
                {option.count !== undefined && (
                  <span className={`ml-1.5 px-1.5 py-0.5 rounded-full text-[10px] ${
                    statusFilter === option.value
                      ? 'bg-white/20 text-white'
                      : 'bg-slate-200 dark:bg-slate-700 text-slate-500 dark:text-slate-400'
                  }`}>
                    {option.count}
                  </span>
                )}
              </button>
            ))}
          </div>
        )}

        {/* Domain Filter Pills */}
        {domainOptions.length > 0 && onDomainFilter && (
          <>
            <div className="hidden sm:block w-px h-6 bg-slate-200 dark:bg-slate-800" />
            <div className="flex items-center gap-1.5">
              {domainOptions.map(option => (
                <button
                  key={option.value}
                  onClick={() => onDomainFilter(option.value)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors whitespace-nowrap cursor-pointer ${
                    domainFilter === option.value
                      ? 'bg-slate-900 dark:bg-indigo-600 text-white shadow-2xs'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
                  }`}
                >
                  {option.label}
                  {option.count !== undefined && (
                    <span className={`ml-1.5 px-1.5 py-0.5 rounded-full text-[10px] ${
                      domainFilter === option.value
                        ? 'bg-white/20 text-white'
                        : 'bg-slate-200 dark:bg-slate-700 text-slate-500 dark:text-slate-400'
                    }`}>
                      {option.count}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
