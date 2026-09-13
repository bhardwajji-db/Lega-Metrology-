import React, { useState, useRef, useEffect } from 'react';
import { 
  ArrowLeft, ChevronDown, AlertTriangle, Trash2, 
  FileText, FileSpreadsheet, FileJson, RotateCcw, Package
} from 'lucide-react';
import { formatAnalysisDateTime } from '../../utils/datetime';

interface ResultsHeaderProps {
  productName: string;
  brand: string | null;
  analysisId: string;
  createdAt: string;
  isDemo: boolean;
  imageCount: number;
  frontImageUrl?: string | null;
  canDelete: boolean;
  canUseEnforcement: boolean;
  onNavigateBack: () => void;
  onNavigateAnalyze: () => void;
  onShowNotice: () => void;
  onShowDelete: () => void;
  exportUrls: {
    csv: string;
    xlsx: string;
    json: string;
    pdf: string;
  };
}

const ResultsHeader: React.FC<ResultsHeaderProps> = ({
  productName,
  brand,
  analysisId,
  createdAt,
  isDemo,
  imageCount,
  frontImageUrl,
  canDelete,
  canUseEnforcement,
  onNavigateBack,
  onNavigateAnalyze,
  onShowNotice,
  onShowDelete,
  exportUrls,
}) => {
  const [showExport, setShowExport] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowExport(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setShowExport(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800/90 rounded-2xl p-4 sm:p-5 relative z-30 shadow-xs space-y-3.5">
      {/* ROW 1: Back Navigation & Action Controls */}
      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={onNavigateBack}
          className="inline-flex items-center gap-1.5 text-xs sm:text-sm font-medium text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 transition-colors cursor-pointer group"
        >
          <ArrowLeft className="w-4 h-4 transition-transform group-hover:-translate-x-0.5" />
          <span>{isDemo ? 'Demo Cases' : 'Screening History'}</span>
        </button>

        <div className="flex items-center gap-2 sm:gap-2.5">
          <button
            type="button"
            onClick={onNavigateAnalyze}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg border border-slate-200 dark:border-slate-700 transition-colors cursor-pointer"
            title="Re-scan Packaging Artwork"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Re-scan</span>
          </button>

          {canUseEnforcement && (
            <button
              type="button"
              onClick={onShowNotice}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 hover:bg-amber-100 dark:hover:bg-amber-900/50 rounded-lg border border-amber-200 dark:border-amber-800/80 transition-colors cursor-pointer"
            >
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
              <span>Notice</span>
            </button>
          )}

          {canDelete && (
            <button
              type="button"
              onClick={onShowDelete}
              className="p-1.5 text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 rounded-lg border border-transparent hover:border-rose-200 dark:hover:border-rose-900/50 transition-colors cursor-pointer"
              title="Delete Analysis"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}

          {/* Export Dropdown */}
          <div className="relative" ref={dropdownRef}>
            <button
              type="button"
              onClick={() => setShowExport(!showExport)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 rounded-lg transition-colors cursor-pointer"
              aria-expanded={showExport}
            >
              <span>Export</span>
              <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 ${showExport ? 'rotate-180' : ''}`} />
            </button>

            {showExport && (
              <div className="absolute right-0 top-full mt-2 w-52 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl py-1.5 z-50 ring-1 ring-black/5 animate-in fade-in duration-150">
                <a
                  href={exportUrls.csv}
                  onClick={() => setShowExport(false)}
                  className="flex items-center px-3.5 py-2 text-xs sm:text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                >
                  <FileSpreadsheet className="w-4 h-4 mr-2.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                  <span>CSV Spreadsheet</span>
                </a>
                <a
                  href={exportUrls.xlsx}
                  onClick={() => setShowExport(false)}
                  className="flex items-center px-3.5 py-2 text-xs sm:text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                >
                  <FileSpreadsheet className="w-4 h-4 mr-2.5 text-blue-600 dark:text-blue-400 shrink-0" />
                  <span>Excel (.xlsx)</span>
                </a>
                <a
                  href={exportUrls.json}
                  onClick={() => setShowExport(false)}
                  className="flex items-center px-3.5 py-2 text-xs sm:text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                >
                  <FileJson className="w-4 h-4 mr-2.5 text-amber-600 dark:text-amber-400 shrink-0" />
                  <span>JSON Payload</span>
                </a>
                <a
                  href={exportUrls.pdf}
                  onClick={() => setShowExport(false)}
                  className="flex items-center px-3.5 py-2 text-xs sm:text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer border-t border-slate-100 dark:border-slate-800 mt-1 pt-2"
                >
                  <FileText className="w-4 h-4 mr-2.5 text-red-600 dark:text-red-400 shrink-0" />
                  <span>PDF Inspection Report</span>
                </a>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ROW 2: Product Identity & Thumbnail & Metadata */}
      <div className="flex items-center gap-3.5 sm:gap-4 pt-2 border-t border-slate-100 dark:border-slate-800/80">
        {/* Product Front Thumbnail */}
        <div className="w-14 sm:w-16 h-16 sm:h-20 shrink-0 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-center overflow-hidden shadow-2xs">
          {frontImageUrl && frontImageUrl !== '/placeholder.png' ? (
            <img
              src={frontImageUrl}
              alt={productName}
              className="w-full h-full object-contain p-1"
              onError={(e) => {
                (e.target as HTMLElement).style.display = 'none';
              }}
            />
          ) : (
            <Package className="w-6 h-6 text-slate-600 dark:text-slate-500" />
          )}
        </div>

        {/* Identity & Metadata Details */}
        <div className="min-w-0 flex-1 space-y-0.5 sm:space-y-1">
          {/* Product Name */}
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white leading-tight tracking-tight truncate">
            {productName}
          </h1>

          {/* Brand */}
          {brand && (
            <p className="text-xs sm:text-sm font-medium text-slate-500 dark:text-slate-400 truncate">
              {brand}
            </p>
          )}

          {/* Metadata Row */}
          <div className="flex flex-wrap items-center gap-2 pt-0.5 text-xs text-slate-500 dark:text-slate-400">
            <span className="font-mono text-[11px] bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-2 py-0.5 rounded font-medium">
              ID: {analysisId ? (analysisId.length > 12 ? analysisId.substring(0, 12) + '...' : analysisId) : 'N/A'}
            </span>
            <span className="text-slate-300 dark:text-slate-700 select-none">•</span>
            <span className="text-[11px] sm:text-xs">
              {formatAnalysisDateTime(createdAt)}
            </span>
            <span className="text-slate-300 dark:text-slate-700 select-none">•</span>
            <span className="px-2 py-0.5 bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 rounded text-[11px] font-semibold border border-indigo-200/60 dark:border-indigo-900/60">
              {imageCount} Panel{imageCount !== 1 ? 's' : ''}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ResultsHeader;
