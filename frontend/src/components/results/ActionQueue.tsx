import React, { useState } from 'react';
import { ListChecks, ChevronDown, ChevronUp, CheckCircle } from 'lucide-react';
import { type Recommendation } from '../../types';

interface ActionQueueProps {
  recommendations: Recommendation[];
  passedRecs: Recommendation[];
  onViewEvidence: (ruleId: string, imageLabel?: string | null) => void;
  onNavigateAnalyze: () => void;
}

const ActionRow: React.FC<{ rec: Recommendation, onViewEvidence: (r: string) => void }> = ({ rec, onViewEvidence }) => {
  const [expanded, setExpanded] = useState(false);
  const isHigh = rec.priority === 'HIGH';

  return (
    <div className="border-b border-slate-100 dark:border-slate-800/60 last:border-0">
      <div 
        className="p-3 sm:p-4 hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors cursor-pointer flex items-center gap-3"
        onClick={() => setExpanded(!expanded)}
      >
        <div className={`shrink-0 w-2 h-8 rounded-full ${isHigh ? 'bg-red-500' : 'bg-amber-500'}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider ${
              isHigh ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
            }`}>
              {rec.priority}
            </span>
            <span className="font-semibold text-slate-900 dark:text-slate-100 truncate text-sm">
              {rec.issue}
            </span>
          </div>
          <div className="text-xs text-slate-500 dark:text-slate-400 mt-1 truncate">
            {rec.recommended_action}
          </div>
        </div>
        <div className="shrink-0 text-slate-400">
          {expanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 pt-1 bg-slate-50/50 dark:bg-slate-800/20 text-sm">
          <div className="grid gap-3 pl-5">
            <div>
              <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-1">Corrective Action</span>
              <p className="text-slate-600 dark:text-slate-400">{rec.corrective_action || rec.recommended_action}</p>
            </div>
            {rec.verification_step && (
              <div>
                <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-1">Verification Step</span>
                <p className="text-slate-600 dark:text-slate-400">{rec.verification_step}</p>
              </div>
            )}
            {rec.source_reference && (
              <div>
                <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-1">Legal Source</span>
                <a href={rec.source_url || undefined} target="_blank" rel="noreferrer" className="text-indigo-600 dark:text-indigo-400 hover:underline">
                  {rec.source_reference}
                </a>
              </div>
            )}
            <div className="mt-2">
               <button
                onClick={(e) => { e.stopPropagation(); onViewEvidence(rec.rule_id); }}
                className="text-indigo-600 dark:text-indigo-400 font-medium hover:underline text-sm cursor-pointer"
              >
                Inspect Associated Evidence →
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const ActionQueue: React.FC<ActionQueueProps> = ({
  recommendations,
  passedRecs,
  onViewEvidence,
}) => {
  const actionable = recommendations.filter(r => r.status !== 'PASS');
  const [showPassed, setShowPassed] = useState(false);

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-2xs mb-6 overflow-hidden">
      <div className="bg-slate-50 dark:bg-slate-800/50 p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2 text-slate-900 dark:text-slate-100 font-semibold">
          <ListChecks className="w-5 h-5 text-indigo-500" />
          ACTION QUEUE
        </div>
        <div className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-300">
          {actionable.length} Action{actionable.length !== 1 ? 's' : ''}
        </div>
      </div>

      {actionable.length === 0 ? (
        <div className="p-6 text-center text-green-600 dark:text-green-400 font-medium flex items-center justify-center gap-2 bg-green-50/50 dark:bg-green-900/10">
          <CheckCircle className="w-5 h-5" />
          No Corrective Actions Required
        </div>
      ) : (
        <div className="divide-y divide-slate-100 dark:divide-slate-800/60">
          {actionable.map(rec => (
            <ActionRow key={rec.rule_id} rec={rec} onViewEvidence={onViewEvidence} />
          ))}
        </div>
      )}

      {passedRecs.length > 0 && (
        <div className="border-t border-slate-200 dark:border-slate-800">
          <button
            onClick={() => setShowPassed(!showPassed)}
            className="w-full p-3 text-sm font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/30 flex items-center justify-between transition-colors cursor-pointer"
          >
            <span className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4" />
              Passed & Verified ({passedRecs.length})
            </span>
            {showPassed ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          
          {showPassed && (
            <div className="bg-slate-50/50 dark:bg-slate-800/20 p-4 text-sm text-slate-500 dark:text-slate-400 grid gap-2">
              {passedRecs.map(rec => (
                <div key={rec.rule_id} className="flex items-center gap-2">
                  <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                  <span className="font-mono text-[10px]">{rec.rule_id}</span>
                  <span className="truncate">{rec.issue}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ActionQueue;
