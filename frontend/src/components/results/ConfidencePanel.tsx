import React, { useState } from 'react';
import { Eye, ChevronDown } from 'lucide-react';
import { type ProductInfo } from '../../types';
import ConfidenceBar from '../ui/ConfidenceBar';

interface ConfidencePanelProps {
  productInfo: ProductInfo;
}

const ConfidencePanel: React.FC<ConfidencePanelProps> = ({ productInfo = {} as any }) => {
  const [expanded, setExpanded] = useState(false);
  const info = productInfo || ({} as any);

  // Extract from declaration_confidences or find field confidences
  const confidences = info.declaration_confidences || {};
  let confidenceData = Object.entries(confidences)
    .map(([key, score]) => ({
      label: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
      value: typeof score === 'number' ? score : 0,
    }))
    .filter(item => typeof item.value === 'number')
    .sort((a, b) => b.value - a.value);

  if (confidenceData.length === 0) {
    // Fallback: search keys ending with _confidence if any
    confidenceData = Object.entries(info)
      .filter(([key]) => key.endsWith('_confidence'))
      .map(([key, value]) => {
        const fieldKey = key.replace('_confidence', '');
        return {
          label: fieldKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
          value: typeof value === 'number' ? value : 0,
        };
      })
      .filter(item => typeof item.value === 'number')
      .sort((a, b) => b.value - a.value);
  }

  if (confidenceData.length === 0) return null;

  const topFields = confidenceData.slice(0, 8);
  const remainingFields = confidenceData.slice(8);

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-2xs mb-6 overflow-hidden">
      {/* Header */}
      <div className="bg-slate-50/70 dark:bg-slate-800/50 p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200/80 dark:border-indigo-800/60 text-indigo-600 dark:text-indigo-400">
            <Eye className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-bold text-xs sm:text-sm text-slate-900 dark:text-slate-100 uppercase tracking-wider">
              Data Extraction Confidence
            </h3>
            <span className="text-[11px] text-slate-500 dark:text-slate-400">
              Confidence scores for detected packaging declarations
            </span>
          </div>
        </div>
        <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400 font-semibold px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
          {confidenceData.length} Fields
        </span>
      </div>

      {/* Grid: 4 cols on desktop, 2 on tablet, 1 on mobile */}
      <div className="p-4 sm:p-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-3.5">
        {topFields.map((item) => (
          <ConfidenceBar key={item.label} value={item.value} label={item.label} />
        ))}
      </div>

      {/* Detailed fields toggle */}
      {remainingFields.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="w-full border-t border-slate-100 dark:border-slate-800/80 p-3 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 hover:bg-slate-50/80 dark:hover:bg-slate-800/40 flex items-center justify-center gap-1.5 transition-colors cursor-pointer select-none"
            aria-expanded={expanded}
          >
            <span>{expanded ? 'Hide Confidence Details' : 'Show Confidence Details'}</span>
            <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`} />
          </button>
          
          {expanded && (
            <div className="p-4 sm:p-5 pt-2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-3.5 border-t border-slate-100 dark:border-slate-800/80 bg-slate-50/30 dark:bg-slate-800/10 animate-in fade-in duration-150">
              {remainingFields.map((item) => (
                <ConfidenceBar key={item.label} value={item.value} label={item.label} />
              ))}
            </div>
          )}
        </>
      )}

      <div className="p-3 bg-slate-50/50 dark:bg-slate-800/40 border-t border-slate-200/80 dark:border-slate-800 text-[11px] text-center text-slate-500 dark:text-slate-400">
        Confidence reflects optical character recognition extraction certainty and does not determine legal statutory validity.
      </div>
    </div>
  );
};

export default ConfidencePanel;

