import React, { useState } from 'react';
import { Ruler, ChevronDown, ChevronUp, AlertCircle, CheckCircle } from 'lucide-react';
import { type FontSizeAnalysis, type CalibrationResult } from '../../types';

interface Rule12SectionProps {
  fontSizeAnalysis: FontSizeAnalysis | undefined;
  calibrationResult: CalibrationResult | null | undefined;
}

const Rule12Section: React.FC<Rule12SectionProps> = ({ fontSizeAnalysis, calibrationResult }) => {
  const [expanded, setExpanded] = useState(false);

  if (!fontSizeAnalysis) return null;

  const isEstimated = !calibrationResult || calibrationResult.status !== 'PHYSICAL_MEASUREMENT_VERIFIED';

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-2xs mb-6 overflow-hidden">
      <div className="bg-slate-50 dark:bg-slate-800/50 p-4 border-b border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-slate-900 dark:text-slate-100 font-semibold">
          <Ruler className="w-5 h-5 text-indigo-500" />
          PHYSICAL READABILITY — Rule 12
        </div>
        <div className={`px-2.5 py-1 text-xs font-medium rounded-full flex items-center gap-1.5 ${
          isEstimated 
            ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400' 
            : 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
        }`}>
          {isEstimated ? <AlertCircle className="w-3.5 h-3.5" /> : <CheckCircle className="w-3.5 h-3.5" />}
          {isEstimated ? 'ESTIMATED MEASUREMENT' : 'CALIBRATED'}
        </div>
      </div>

      <div className="p-4">
        {isEstimated && (
          <div className="mb-4 text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/10 p-2.5 rounded-lg border border-amber-200 dark:border-amber-900/30 flex gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            No physical reference marker was detected. Measurement is estimated based on standard product dimensions.
          </div>
        )}
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <div className="text-xs text-slate-500 dark:text-slate-400 uppercase font-semibold mb-1">Net Qty Height</div>
            <div className="text-lg font-bold text-slate-900 dark:text-white">
              {fontSizeAnalysis.net_quantity_font_height_mm ? `${fontSizeAnalysis.net_quantity_font_height_mm.toFixed(1)} mm` : 'N/A'}
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-500 dark:text-slate-400 uppercase font-semibold mb-1">Required Height</div>
            <div className="text-lg font-bold text-slate-900 dark:text-white">
              {fontSizeAnalysis.min_required_font_height_mm ? `${fontSizeAnalysis.min_required_font_height_mm.toFixed(1)} mm` : 'N/A'}
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-500 dark:text-slate-400 uppercase font-semibold mb-1">MRP Height</div>
            <div className="text-lg font-bold text-slate-900 dark:text-white">
              {fontSizeAnalysis.mrp_font_height_mm ? `${fontSizeAnalysis.mrp_font_height_mm.toFixed(1)} mm` : 'N/A'}
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-500 dark:text-slate-400 uppercase font-semibold mb-1">Readability</div>
            <div className="text-lg font-bold text-slate-900 dark:text-white">
              {fontSizeAnalysis.readability_score !== null && fontSizeAnalysis.readability_score !== undefined
                ? `${fontSizeAnalysis.readability_score.toFixed(1)} / 100` 
                : 'N/A'}
            </div>
          </div>
        </div>
      </div>

      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full border-t border-slate-100 dark:border-slate-800 p-3 text-xs font-medium text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800/30 flex items-center justify-center gap-1 transition-colors cursor-pointer"
      >
        {expanded ? (
          <><ChevronUp className="w-4 h-4" /> Hide Technical Details</>
        ) : (
          <><ChevronDown className="w-4 h-4" /> Show Technical Details</>
        )}
      </button>

      {expanded && (
        <div className="p-4 bg-slate-50 dark:bg-slate-800/20 text-xs text-slate-600 dark:text-slate-400 border-t border-slate-100 dark:border-slate-800 grid gap-3">
          <div className="grid grid-cols-2 gap-2">
            <div><span className="font-semibold">Pixels per mm:</span> {fontSizeAnalysis.pixels_per_mm?.toFixed(2) || 'N/A'}</div>
            <div><span className="font-semibold">Verdict:</span> {fontSizeAnalysis.rule_12_verdict}</div>
          </div>
          {calibrationResult && (
            <div className="grid grid-cols-2 gap-2">
              <div><span className="font-semibold">Status:</span> {calibrationResult.status}</div>
              <div><span className="font-semibold">Target:</span> {calibrationResult.target_type || 'None'}</div>
            </div>
          )}
          {fontSizeAnalysis.details && (
            <div><span className="font-semibold block mb-1">Details:</span> {fontSizeAnalysis.details}</div>
          )}
        </div>
      )}
    </div>
  );
};

export default Rule12Section;
