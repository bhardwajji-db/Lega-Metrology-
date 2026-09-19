import React from 'react';
import { AlertTriangle, ShieldAlert, ShieldCheck, Info, TrendingDown } from 'lucide-react';
import { type RiskAssessment, type CategoryScore, type ConfidenceSummary } from '../../types';

interface RiskFactorBreakdownProps {
  riskAssessment?: RiskAssessment | null;
  categoryScores?: Record<string, CategoryScore> | null;
  confidenceSummary?: ConfidenceSummary | null;
  score?: number;
}

export const RiskFactorBreakdown: React.FC<RiskFactorBreakdownProps> = ({
  riskAssessment,
  categoryScores,
  confidenceSummary,
  score = 0,
}) => {
  if (!riskAssessment && !categoryScores && !confidenceSummary) {
    return null;
  }

  const riskLevel = (riskAssessment?.risk_level || riskAssessment?.level || 'LOW').toUpperCase();

  const getRiskBadge = (level: string) => {
    switch (level) {
      case 'CRITICAL':
        return {
          bg: 'bg-red-600 text-white border-red-700',
          text: 'CRITICAL RISK',
          icon: ShieldAlert,
          desc: 'Immediate statutory violation detected. Package is legally non-compliant.'
        };
      case 'HIGH':
        return {
          bg: 'bg-amber-600 text-white border-amber-700',
          text: 'HIGH RISK',
          icon: AlertTriangle,
          desc: 'Multiple missing declarations or severe compliance issues detected.'
        };
      case 'MEDIUM':
        return {
          bg: 'bg-blue-600 text-white border-blue-700',
          text: 'MEDIUM RISK',
          icon: Info,
          desc: 'Screening ambiguities or missing secondary declarations require verification.'
        };
      default:
        return {
          bg: 'bg-emerald-600 text-white border-emerald-700',
          text: 'LOW RISK',
          icon: ShieldCheck,
          desc: 'All mandatory statutory declarations detected and verified.'
        };
    }
  };

  const badgeInfo = getRiskBadge(riskLevel);
  const BadgeIcon = badgeInfo.icon;

  return (
    <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 sm:p-6 mb-6 shadow-xs space-y-5">
      {/* Header with Risk Level & Grounded Explanation */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-100 dark:border-slate-800">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-black tracking-wider border shadow-xs ${badgeInfo.bg}`}>
              <BadgeIcon className="w-3.5 h-3.5" />
              <span>{badgeInfo.text}</span>
            </span>
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
              Risk &amp; Scoring Assessment
            </span>
          </div>
          <p className="text-xs sm:text-sm text-slate-700 dark:text-slate-300 font-medium leading-relaxed pt-1">
            {riskAssessment?.grounded_explanation || badgeInfo.desc}
          </p>
        </div>

        {/* Confidence Adjusted Score Badge */}
        {riskAssessment && (
          <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200/90 dark:border-slate-700 shrink-0">
            <div>
              <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest block">
                CONFIDENCE-ADJUSTED SCORE
              </span>
              <div className="flex items-baseline gap-1.5">
                <span className="text-lg font-black font-mono text-slate-900 dark:text-slate-100">
                  {Number(riskAssessment.confidence_adjusted_score ?? score).toFixed(1)}
                </span>
                <span className="text-xs text-slate-400 dark:text-slate-500 font-medium">
                  (Raw: {Number(score).toFixed(1)})
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 4 Risk Metrics Breakdown */}
      {riskAssessment && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block">
              Missing Declarations
            </span>
            <span className={`text-base font-black font-mono ${riskAssessment.missing_declaration_count > 0 ? 'text-red-600 dark:text-red-400' : 'text-emerald-600 dark:text-emerald-400'}`}>
              {riskAssessment.missing_declaration_count}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block">
              Critical Violations
            </span>
            <span className={`text-base font-black font-mono ${riskAssessment.critical_violation_count > 0 ? 'text-red-600 dark:text-red-400' : 'text-emerald-600 dark:text-emerald-400'}`}>
              {riskAssessment.critical_violation_count}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block">
              Review Required
            </span>
            <span className={`text-base font-black font-mono ${riskAssessment.review_required_count > 0 ? 'text-amber-600 dark:text-amber-400' : 'text-slate-600 dark:text-slate-400'}`}>
              {riskAssessment.review_required_count}
            </span>
          </div>

          <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block">
              Aggregate Confidence
            </span>
            <span className="text-base font-black font-mono text-indigo-600 dark:text-indigo-400">
              {Number(confidenceSummary?.aggregate_confidence ?? 90).toFixed(1)}%
            </span>
          </div>
        </div>
      )}

      {/* Category Scores (Legal Metrology vs FSSAI) */}
      {categoryScores && Object.keys(categoryScores).length > 0 && (
        <div className="space-y-2">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block">
            Category Breakdown
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {Object.entries(categoryScores).map(([catKey, cat]) => (
              <div key={catKey} className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100">{cat.category}</h4>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400">
                    {cat.passed_rules} Passed • {cat.failed_rules} Failed • {cat.review_rules} Review
                  </p>
                </div>
                <div className="text-right">
                  <span className="text-sm font-black font-mono text-slate-900 dark:text-slate-100">
                    {Number(cat.score).toFixed(1)}%
                  </span>
                  <span className="text-[10px] text-slate-400 block">
                    {cat.earned_points} / {cat.max_points} pts
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Detailed Risk Factors List */}
      {riskAssessment && riskAssessment.risk_factors && riskAssessment.risk_factors.length > 0 && (
        <div className="space-y-2.5 pt-2">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block">
            Identified Risk Factors ({riskAssessment.risk_factors.length})
          </span>
          <div className="space-y-2">
            {riskAssessment.risk_factors.map((factor, idx) => (
              <div
                key={factor.factor_id || idx}
                className="p-3 rounded-xl border border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5"
              >
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      factor.severity === 'CRITICAL' ? 'bg-red-100 text-red-800 dark:bg-red-950/80 dark:text-red-300' :
                      factor.severity === 'HIGH' ? 'bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300' :
                      'bg-blue-100 text-blue-800 dark:bg-blue-950/80 dark:text-blue-300'
                    }`}>
                      {factor.severity}
                    </span>
                    <span className="text-xs font-bold text-slate-900 dark:text-slate-100">
                      {factor.title}
                    </span>
                    <span className="text-[10px] font-mono text-slate-400">
                      [{factor.factor_id}]
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 dark:text-slate-400">
                    {factor.description}
                  </p>
                  <span className="text-[10px] text-slate-400 italic">
                    Legal Reference: {factor.source_reference}
                  </span>
                </div>

                <div className="shrink-0 text-right">
                  <span className="inline-flex items-center gap-1 text-xs font-bold font-mono text-red-600 dark:text-red-400">
                    <TrendingDown className="w-3.5 h-3.5" />
                    <span>-{factor.impact_on_score} pts</span>
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default RiskFactorBreakdown;
