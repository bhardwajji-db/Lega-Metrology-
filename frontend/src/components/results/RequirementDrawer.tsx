import React from 'react';
import { ExternalLink, Search, Shield } from 'lucide-react';
import { type ComplianceCheck } from '../../types';
import Drawer from '../ui/Drawer';
import StatusBadge from '../ui/StatusBadge';
import ConfidenceBar from '../ui/ConfidenceBar';

interface RequirementDrawerProps {
  check: ComplianceCheck | null;
  onClose: () => void;
  onViewEvidence: (ruleId: string, imageLabel?: string | null) => void;
}

const RequirementDrawer: React.FC<RequirementDrawerProps> = ({
  check,
  onClose,
  onViewEvidence,
}) => {
  return (
    <Drawer open={check !== null} onClose={onClose} title="Requirement Details">
      {check && (
        <div className="flex flex-col h-full">
          <div className="p-6 space-y-6 flex-1 overflow-y-auto">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="font-mono text-xs bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 px-2 py-1 rounded">
                  {check.rule_id}
                </span>
                <StatusBadge status={check.status} size="lg" />
              </div>
              <h3 className="text-xl font-bold text-slate-900 dark:text-white">
                {check.field_label && check.field_label.length > 2 ? check.field_label : (check.field || check.rule_id)}
              </h3>
            </div>

            <section>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Detected Value</h4>
              <div className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-slate-100 font-medium break-words">
                {check.detected_value || <span className="italic text-slate-400">Not reliably detected</span>}
              </div>
            </section>

            {check.explanation && (
              <section>
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Analysis Explanation</h4>
                <p className="text-sm text-slate-700 dark:text-slate-300">
                  {check.explanation}
                </p>
              </section>
            )}

            {check.confidence !== undefined && check.confidence !== null && (
              <section>
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Detection Confidence</h4>
                <ConfidenceBar value={check.confidence} label="Confidence" />
              </section>
            )}

            <section>
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">Legal Basis</h4>
              <div className="bg-indigo-50 dark:bg-indigo-900/10 border border-indigo-100 dark:border-indigo-900/30 rounded-lg p-4">
                <div className="flex items-start gap-2">
                  <Shield className="w-5 h-5 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
                  <div>
                    <div className="font-medium text-indigo-900 dark:text-indigo-300 text-sm">
                      {check.source_name || 'Legal Metrology Rules'}
                    </div>
                    <div className="text-indigo-700 dark:text-indigo-400 text-xs mt-1">
                      {check.source_reference}
                    </div>
                  </div>
                </div>
              </div>
            </section>
          </div>

          <div className="p-6 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50 flex flex-col gap-3">
            <button
              onClick={() => {
                onClose();
                onViewEvidence(check.rule_id, check.evidence_image_label);
              }}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium transition-colors cursor-pointer"
            >
              <Search className="w-4 h-4" />
              Inspect Evidence
            </button>
            {check.source_url && (
              <a
                href={check.source_url}
                target="_blank"
                rel="noreferrer"
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-lg font-medium transition-colors cursor-pointer"
              >
                <ExternalLink className="w-4 h-4" />
                View Legal Source
              </a>
            )}
          </div>
        </div>
      )}
    </Drawer>
  );
};

export default RequirementDrawer;
