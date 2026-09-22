import React, { useState, useMemo } from 'react';
import {
  Scale,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  ShieldAlert,
  Search,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Clock,
  Layers,
  Info,
  ShieldCheck,
  FileText
} from 'lucide-react';
import {
  type ClaimAnalysisResult,
  type ClaimFinding,
  type ClaimStatus
} from '../../types';

interface ClaimsAnalysisSectionProps {
  claimsAnalysis?: ClaimAnalysisResult | null;
  onViewEvidence?: (ruleId?: string | null, imageLabel?: string | null) => void;
}

const STATUS_CONFIG: Record<ClaimStatus, {
  label: string;
  bg: string;
  text: string;
  border: string;
  icon: React.ComponentType<{ className?: string }>;
  badgeColor: string;
}> = {
  SUPPORTED: {
    label: 'Supported by Declarations',
    bg: 'bg-emerald-50 dark:bg-emerald-950/30',
    text: 'text-emerald-700 dark:text-emerald-300',
    border: 'border-emerald-200 dark:border-emerald-800',
    icon: CheckCircle2,
    badgeColor: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300'
  },
  INSUFFICIENT_EVIDENCE: {
    label: 'Insufficient Evidence (Requires Verification)',
    bg: 'bg-amber-50/70 dark:bg-amber-950/20',
    text: 'text-amber-800 dark:text-amber-300',
    border: 'border-amber-200 dark:border-amber-800/60',
    icon: HelpCircle,
    badgeColor: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300'
  },
  POTENTIAL_CONTRADICTION: {
    label: 'Potential Contradiction Detected',
    bg: 'bg-rose-50 dark:bg-rose-950/30',
    text: 'text-rose-700 dark:text-rose-300',
    border: 'border-rose-200 dark:border-rose-800',
    icon: AlertCircle,
    badgeColor: 'bg-rose-100 text-rose-800 dark:bg-rose-900/50 dark:text-rose-300'
  },
  HIGH_RISK_REVIEW: {
    label: 'High-Risk Review Required',
    bg: 'bg-orange-50 dark:bg-orange-950/30',
    text: 'text-orange-800 dark:text-orange-300',
    border: 'border-orange-200 dark:border-orange-800',
    icon: ShieldAlert,
    badgeColor: 'bg-orange-100 text-orange-800 dark:bg-orange-900/50 dark:text-orange-300'
  },
  NOT_ASSESSABLE: {
    label: 'Not Assessable from Imagery',
    bg: 'bg-slate-50 dark:bg-slate-800/40',
    text: 'text-slate-700 dark:text-slate-300',
    border: 'border-slate-200 dark:border-slate-700',
    icon: Info,
    badgeColor: 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300'
  }
};

const CATEGORY_COLORS: Record<string, string> = {
  NUTRITIONAL: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300',
  HEALTH: 'bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300',
  MEDICAL: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
  INGREDIENT: 'bg-lime-100 text-lime-800 dark:bg-lime-900/40 dark:text-lime-300',
  QUALITY: 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300',
  ABSOLUTE: 'bg-fuchsia-100 text-fuchsia-800 dark:bg-fuchsia-900/40 dark:text-fuchsia-300',
  COMPARATIVE: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300',
  CERTIFICATION: 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/40 dark:text-cyan-300',
  ENVIRONMENTAL: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300',
  ORIGIN: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
  PROCESSED_NATURE: 'bg-stone-100 text-stone-800 dark:bg-stone-900/40 dark:text-stone-300',
  OTHER: 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300'
};

export const ClaimsAnalysisSection: React.FC<ClaimsAnalysisSectionProps> = ({
  claimsAnalysis,
  onViewEvidence
}) => {
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [expandedClaimId, setExpandedClaimId] = useState<string | null>(null);

  const claims = claimsAnalysis?.claims || [];

  const filteredClaims = useMemo(() => {
    if (!claimsAnalysis) return [];
    return claims.filter((claim: ClaimFinding) => {
      if (selectedCategory !== 'ALL' && claim.category !== selectedCategory) {
        return false;
      }
      if (selectedStatus !== 'ALL' && claim.assessment.status !== selectedStatus) {
        return false;
      }
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const textMatch = claim.claim_text.toLowerCase().includes(query);
        const normMatch = claim.normalized_claim.toLowerCase().includes(query);
        const reasonMatch = claim.assessment.reason.toLowerCase().includes(query);
        const ruleMatch = (claim.assessment.rule_id || '').toLowerCase().includes(query);
        if (!textMatch && !normMatch && !reasonMatch && !ruleMatch) {
          return false;
        }
      }
      return true;
    });
  }, [claimsAnalysis, claims, selectedCategory, selectedStatus, searchQuery]);

  const uniqueCategories = useMemo(() => {
    if (!claimsAnalysis) return [];
    const cats = new Set<string>();
    claims.forEach(c => cats.add(c.category));
    return Array.from(cats);
  }, [claimsAnalysis, claims]);

  if (!claimsAnalysis) return null;

  const { summary, processing_time_ms, engine_version, analyzed_panels } = claimsAnalysis;

  const toggleExpand = (claimId: string) => {
    setExpandedClaimId(prev => (prev === claimId ? null : claimId));
  };

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden space-y-6 p-6">
      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-100 dark:border-slate-800 pb-5">
        <div className="flex items-start gap-3.5">
          <div className="p-3 bg-gradient-to-br from-indigo-500 to-indigo-600 text-white rounded-xl shadow-sm">
            <Scale className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                Misleading Claim Detection Engine
              </h3>
              <span className="px-2 py-0.5 text-[10px] font-mono font-semibold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 rounded border border-indigo-200/60 dark:border-indigo-800/60">
                v{engine_version}
              </span>
              <span className="inline-flex items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400">
                <Clock className="w-3.5 h-3.5" />
                {processing_time_ms}ms
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Deterministic statutory verification under FSSAI (Advertising & Claims) 2018, CCPA 2022, and Legal Metrology Rules
            </p>
          </div>
        </div>

        {analyzed_panels && analyzed_panels.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap text-xs text-slate-500 dark:text-slate-400">
            <Layers className="w-4 h-4 text-slate-400" />
            <span className="font-medium">Cross-Panel:</span>
            {analyzed_panels.map(p => (
              <span
                key={p}
                className="px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-[11px] font-medium"
              >
                {p}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* ── 4 KPI Summary Cards ─────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
        <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/80 dark:border-slate-700/80">
          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 text-xs font-semibold uppercase tracking-wider mb-1.5">
            <span>Claims Screened</span>
            <FileText className="w-4 h-4 text-slate-400" />
          </div>
          <div className="text-2xl font-black text-slate-900 dark:text-slate-100">
            {summary.total_detected}
          </div>
          <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
            Detected across packaging panels
          </p>
        </div>

        <div className={`p-4 rounded-xl border ${
          summary.potential_contradictions > 0
            ? 'bg-rose-50/60 dark:bg-rose-950/20 border-rose-200 dark:border-rose-900/60'
            : 'bg-slate-50 dark:bg-slate-800/50 border-slate-200/80 dark:border-slate-700/80'
        }`}>
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider mb-1.5 text-rose-700 dark:text-rose-400">
            <span>Contradictions</span>
            <AlertCircle className="w-4 h-4" />
          </div>
          <div className="text-2xl font-black text-rose-700 dark:text-rose-400">
            {summary.potential_contradictions}
          </div>
          <p className="text-[11px] text-rose-600/80 dark:text-rose-400/80 mt-1">
            Conflicts with back-panel facts
          </p>
        </div>

        <div className={`p-4 rounded-xl border ${
          (summary.high_risk_review + summary.insufficient_evidence) > 0
            ? 'bg-amber-50/60 dark:bg-amber-950/20 border-amber-200 dark:border-amber-900/60'
            : 'bg-slate-50 dark:bg-slate-800/50 border-slate-200/80 dark:border-slate-700/80'
        }`}>
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider mb-1.5 text-amber-700 dark:text-amber-400">
            <span>Officer Review</span>
            <AlertTriangle className="w-4 h-4" />
          </div>
          <div className="text-2xl font-black text-amber-700 dark:text-amber-400">
            {summary.high_risk_review + summary.insufficient_evidence}
          </div>
          <p className="text-[11px] text-amber-600/80 dark:text-amber-400/80 mt-1">
            {summary.high_risk_review} high-risk, {summary.insufficient_evidence} insufficient evidence
          </p>
        </div>

        <div className="p-4 rounded-xl bg-emerald-50/60 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-900/60">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider mb-1.5 text-emerald-700 dark:text-emerald-400">
            <span>Supported</span>
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div className="text-2xl font-black text-emerald-700 dark:text-emerald-400">
            {summary.supported}
          </div>
          <p className="text-[11px] text-emerald-600/80 dark:text-emerald-400/80 mt-1">
            Substantiated by package facts
          </p>
        </div>
      </div>

      {/* ── Search and Filter Controls ──────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-2">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search claims, rules, or ingredients..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
          />
        </div>

        <div className="flex items-center gap-2 flex-wrap text-xs">
          <span className="text-slate-500 dark:text-slate-400 font-medium">Status:</span>
          <select
            value={selectedStatus}
            onChange={e => setSelectedStatus(e.target.value)}
            className="px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="ALL">All Statuses ({claims.length})</option>
            <option value="POTENTIAL_CONTRADICTION">Contradiction ({summary.potential_contradictions})</option>
            <option value="HIGH_RISK_REVIEW">High Risk ({summary.high_risk_review})</option>
            <option value="INSUFFICIENT_EVIDENCE">Insufficient Evidence ({summary.insufficient_evidence})</option>
            <option value="SUPPORTED">Supported ({summary.supported})</option>
            <option value="NOT_ASSESSABLE">Not Assessable ({summary.not_assessable})</option>
          </select>
        </div>
      </div>

      {/* Category Pills */}
      {uniqueCategories.length > 0 && (
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs no-scrollbar">
          <button
            type="button"
            onClick={() => setSelectedCategory('ALL')}
            className={`px-3 py-1 rounded-full text-xs font-medium cursor-pointer transition-colors ${
              selectedCategory === 'ALL'
                ? 'bg-indigo-600 text-white shadow-2xs'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
            }`}
          >
            All Categories
          </button>
          {uniqueCategories.map(cat => (
            <button
              key={cat}
              type="button"
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1 rounded-full text-xs font-medium cursor-pointer transition-colors ${
                selectedCategory === cat
                  ? 'bg-indigo-600 text-white shadow-2xs'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      )}

      {/* ── Claims Finding Cards ────────────────────────────────────────── */}
      {filteredClaims.length === 0 ? (
        <div className="p-8 text-center rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/80 dark:border-slate-800 text-xs space-y-2">
          <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto" />
          <h4 className="font-semibold text-slate-800 dark:text-slate-200">
            No Claims Match Current Filters
          </h4>
          <p className="text-slate-500 dark:text-slate-400 max-w-md mx-auto">
            {claims.length === 0
              ? 'No promotional, health, nutritional, or comparative marketing claims detected on the screened panels.'
              : 'Try clearing your search query or selecting a different status/category filter.'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredClaims.map((claim: ClaimFinding) => {
            const statusConfig = STATUS_CONFIG[claim.assessment.status] || STATUS_CONFIG.NOT_ASSESSABLE;
            const StatusIcon = statusConfig.icon;
            const isExpanded = expandedClaimId === claim.claim_id;
            const catColor = CATEGORY_COLORS[claim.category] || CATEGORY_COLORS.OTHER;

            return (
              <div
                key={claim.claim_id}
                className={`rounded-xl border transition-all duration-200 ${statusConfig.border} ${statusConfig.bg}`}
              >
                {/* Main Card Header */}
                <div className="p-4 sm:p-5 space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    <div className="space-y-1.5 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`px-2.5 py-0.5 rounded-md text-[11px] font-bold ${catColor}`}>
                          {claim.category}
                        </span>
                        <span className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-200/60 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                          Panel: {claim.source_panel}
                        </span>
                        {claim.assessment.is_absolute && (
                          <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-purple-100 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300">
                            ABSOLUTE CLAIM
                          </span>
                        )}
                        {claim.assessment.is_comparative && (
                          <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-indigo-100 text-indigo-800 dark:bg-indigo-950/60 dark:text-indigo-300">
                            COMPARATIVE CLAIM
                          </span>
                        )}
                      </div>

                      {/* Prominent Claim Text */}
                      <div className="text-base font-bold text-slate-900 dark:text-slate-100 leading-snug">
                        "{claim.claim_text}"
                      </div>
                      {claim.normalized_claim !== claim.claim_text.toLowerCase() && (
                        <div className="text-xs text-slate-500 dark:text-slate-400 italic">
                          Normalized: "{claim.normalized_claim}"
                        </div>
                      )}
                    </div>

                    {/* Status Pill & Confidence */}
                    <div className="flex sm:flex-col items-end gap-1.5 shrink-0">
                      <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${statusConfig.badgeColor}`}>
                        <StatusIcon className="w-3.5 h-3.5" />
                        <span>{claim.assessment.status.replace(/_/g, ' ')}</span>
                      </div>
                      <div className="text-[11px] text-slate-500 dark:text-slate-400 font-mono">
                        Confidence: {(claim.confidence * 100).toFixed(0)}%
                      </div>
                    </div>
                  </div>

                  {/* Reason & Core Finding */}
                  <div className="text-xs text-slate-800 dark:text-slate-200 bg-white/80 dark:bg-slate-900/80 p-3 rounded-lg border border-slate-200/60 dark:border-slate-800/60 leading-relaxed">
                    <strong>Finding:</strong> {claim.assessment.reason}
                  </div>

                  {/* Statutory Reference Banner */}
                  {claim.assessment.rule_id && (
                    <div className="flex items-center justify-between text-[11px] text-slate-600 dark:text-slate-400 bg-slate-100/70 dark:bg-slate-800/60 px-3 py-1.5 rounded-lg border border-slate-200/50 dark:border-slate-700/50">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-slate-800 dark:text-slate-200">
                          {claim.assessment.rule_source || 'Statutory Rule'}:
                        </span>
                        <span className="font-mono text-indigo-600 dark:text-indigo-400">
                          {claim.assessment.rule_reference || claim.assessment.rule_id}
                        </span>
                      </div>
                      <span className="text-[10px] font-medium text-slate-500 dark:text-slate-400 uppercase">
                        {claim.assessment.jurisdiction}
                      </span>
                    </div>
                  )}

                  {/* Human Review Required Banner */}
                  {claim.assessment.requires_human_review && (
                    <div className="flex items-center gap-2 text-xs text-amber-800 dark:text-amber-300 bg-amber-100/60 dark:bg-amber-950/40 px-3 py-2 rounded-lg border border-amber-300/40 dark:border-amber-800/40">
                      <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
                      <span>
                        <strong>Officer Review Required:</strong> {claim.assessment.verdict_distinction || 'Automated screening requires statutory verification before formal enforcement.'}
                      </span>
                    </div>
                  )}

                  {/* Expand / Collapse Action */}
                  <div className="flex items-center justify-between pt-1">
                    <div className="flex items-center gap-2">
                      {onViewEvidence && claim.bounding_box && (
                        <button
                          type="button"
                          onClick={() => onViewEvidence(claim.claim_id, claim.source_panel)}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-800 dark:hover:text-indigo-300 transition-colors cursor-pointer"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                          <span>View on Package ({claim.source_panel})</span>
                        </button>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={() => toggleExpand(claim.claim_id)}
                      className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 transition-colors cursor-pointer"
                    >
                      <span>{isExpanded ? 'Hide Details' : 'View Full Evidence & Analysis'}</span>
                      {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* Expanded Detailed Section */}
                {isExpanded && (
                  <div className="border-t border-slate-200/60 dark:border-slate-800/80 p-4 sm:p-5 bg-white/90 dark:bg-slate-900/90 space-y-4">
                    {/* Detailed Legal Explanation */}
                    {claim.assessment.detailed_explanation && (
                      <div className="space-y-1 text-xs">
                        <span className="font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider text-[10px]">
                          Regulatory Compliance Analysis:
                        </span>
                        <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                          {claim.assessment.detailed_explanation}
                        </p>
                      </div>
                    )}

                    {/* Confidence Breakdown Grid */}
                    <div className="space-y-1.5">
                      <span className="font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider text-[10px]">
                        Multi-Factor Confidence Breakdown:
                      </span>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                        <div className="p-2 rounded bg-slate-50 dark:bg-slate-800/60 border border-slate-200/60 dark:border-slate-700/60">
                          <div className="text-[10px] text-slate-500 dark:text-slate-400">OCR Confidence</div>
                          <div className="font-bold text-slate-800 dark:text-slate-200">
                            {(claim.confidence_breakdown.ocr_confidence * 100).toFixed(0)}%
                          </div>
                        </div>
                        <div className="p-2 rounded bg-slate-50 dark:bg-slate-800/60 border border-slate-200/60 dark:border-slate-700/60">
                          <div className="text-[10px] text-slate-500 dark:text-slate-400">Extraction Conf</div>
                          <div className="font-bold text-slate-800 dark:text-slate-200">
                            {(claim.confidence_breakdown.extraction_confidence * 100).toFixed(0)}%
                          </div>
                        </div>
                        <div className="p-2 rounded bg-slate-50 dark:bg-slate-800/60 border border-slate-200/60 dark:border-slate-700/60">
                          <div className="text-[10px] text-slate-500 dark:text-slate-400">Evidence Conf</div>
                          <div className="font-bold text-slate-800 dark:text-slate-200">
                            {(claim.confidence_breakdown.evidence_confidence * 100).toFixed(0)}%
                          </div>
                        </div>
                        <div className="p-2 rounded bg-slate-50 dark:bg-slate-800/60 border border-slate-200/60 dark:border-slate-700/60">
                          <div className="text-[10px] text-slate-500 dark:text-slate-400">Cross-Panel Consistency</div>
                          <div className="font-bold text-slate-800 dark:text-slate-200">
                            {(claim.confidence_breakdown.cross_panel_consistency * 100).toFixed(0)}%
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Cross-Panel Evidence Links */}
                    {claim.evidence && claim.evidence.length > 0 && (
                      <div className="space-y-2">
                        <span className="font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider text-[10px]">
                          Cross-Panel Linked Evidence ({claim.evidence.length}):
                        </span>
                        <div className="space-y-1.5">
                          {claim.evidence.map((ev, idx) => (
                            <div
                              key={idx}
                              className="flex items-start justify-between gap-3 p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200/60 dark:border-slate-700/60 text-xs"
                            >
                              <div className="space-y-0.5 flex-1">
                                <div className="flex items-center gap-2">
                                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                                    ev.relationship === 'CONTRADICTED_BY'
                                      ? 'bg-rose-100 text-rose-800 dark:bg-rose-900/60 dark:text-rose-300'
                                      : ev.relationship === 'SUPPORTED_BY'
                                      ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-300'
                                      : 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/60 dark:text-indigo-300'
                                  }`}>
                                    {ev.relationship.replace(/_/g, ' ')}
                                  </span>
                                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                                    {ev.panel} Panel ({ev.type})
                                  </span>
                                </div>
                                <div className="text-slate-700 dark:text-slate-300 font-mono text-[11px]">
                                  {ev.text}
                                </div>
                                {ev.explanation && (
                                  <div className="text-slate-500 dark:text-slate-400 text-[11px] italic">
                                    {ev.explanation}
                                  </div>
                                )}
                              </div>

                              <div className="text-right shrink-0">
                                <span className="text-[10px] font-mono text-slate-400 block">
                                  {(ev.confidence * 100).toFixed(0)}% conf
                                </span>
                                {onViewEvidence && ev.bounding_box && (
                                  <button
                                    type="button"
                                    onClick={() => onViewEvidence(claim.claim_id, ev.panel)}
                                    className="text-[11px] text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer font-medium"
                                  >
                                    View
                                  </button>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── Statutory Adjudication Disclaimer ────────────────────────────── */}
      <div className="bg-slate-50 dark:bg-slate-800/40 rounded-xl p-4 border border-slate-200/80 dark:border-slate-800 flex items-start gap-3 text-[11px] leading-relaxed text-slate-500 dark:text-slate-400">
        <ShieldCheck className="w-5 h-5 text-indigo-500 shrink-0 mt-0.5" />
        <div>
          <strong className="text-slate-700 dark:text-slate-300 block mb-0.5">
            Statutory Claim Verification Standard
          </strong>
          MetrCheck AI evaluates packaging claims deterministically against codified regulatory rules. Unverified or unsupported claims are flagged as <span className="font-semibold text-amber-600 dark:text-amber-400">INSUFFICIENT EVIDENCE</span> or <span className="font-semibold text-rose-600 dark:text-rose-400">POTENTIAL CONTRADICTION</span> for officer scrutiny and are NEVER declared conclusively false by automated AI systems alone without human adjudication.
        </div>
      </div>
    </div>
  );
};

export default ClaimsAnalysisSection;
