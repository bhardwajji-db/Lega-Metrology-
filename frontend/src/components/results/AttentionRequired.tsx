import React from 'react';
import { AlertTriangle, AlertCircle, Search } from 'lucide-react';
import { type ComplianceCheck } from '../../types';

interface AttentionRequiredProps {
  failedChecks: ComplianceCheck[];
  reviewChecks: ComplianceCheck[];
  onViewEvidence: (ruleId: string, imageLabel?: string | null) => void;
}

const AttentionRequired: React.FC<AttentionRequiredProps> = ({
  failedChecks,
  reviewChecks,
  onViewEvidence,
}) => {
  if (failedChecks.length === 0 && reviewChecks.length === 0) {
    return null;
  }

  const items = [
    ...failedChecks.map(c => ({ ...c, isFail: true })),
    ...reviewChecks.map(c => ({ ...c, isFail: false }))
  ];

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-2xs mb-6 overflow-hidden">
      <div className="bg-slate-50 dark:bg-slate-800/50 p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2 text-slate-900 dark:text-slate-100 font-semibold">
          <AlertTriangle className="w-5 h-5 text-amber-500" />
          ATTENTION REQUIRED
        </div>
        <div className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400">
          {items.length} Issue{items.length !== 1 ? 's' : ''}
        </div>
      </div>
      
      <div className="divide-y divide-slate-100 dark:divide-slate-800/60">
        {items.map((check) => (
          <div key={check.rule_id} className="p-3 sm:p-4 hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors flex flex-col sm:flex-row sm:items-center gap-3">
            <div className="flex-1 flex items-start gap-3">
              {check.isFail ? (
                <div className="p-1 rounded bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 mt-0.5">
                  <AlertCircle className="w-4 h-4" />
                </div>
              ) : (
                <div className="p-1 rounded bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400 mt-0.5">
                  <AlertTriangle className="w-4 h-4" />
                </div>
              )}
              <div>
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <span className="font-semibold text-slate-900 dark:text-slate-100 text-sm">
                    {check.field_label && check.field_label.length > 2 ? check.field_label : (check.field || check.rule_id)}
                  </span>
                  <span className="font-mono text-xs text-slate-500 bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded border border-slate-200 dark:border-slate-700">
                    {check.rule_id}
                  </span>
                  {check.detected_value && (
                    <span className="text-xs text-slate-500">
                      Detected: <strong className="text-slate-700 dark:text-slate-300">{check.detected_value}</strong>
                    </span>
                  )}
                </div>
                <div className="text-xs text-slate-600 dark:text-slate-400 line-clamp-2 sm:line-clamp-1">
                  {check.explanation || 'Manual verification recommended for this declaration.'}
                </div>
              </div>
            </div>
            
            <button
              onClick={() => onViewEvidence(check.rule_id, check.evidence_image_label)}
              className="self-start sm:self-center shrink-0 flex items-center gap-1.5 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/50 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 px-3 py-1.5 rounded-lg border border-indigo-200/50 dark:border-indigo-800/50 transition-colors cursor-pointer"
            >
              <Search className="w-3.5 h-3.5" />
              Inspect Evidence
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

export default AttentionRequired;
