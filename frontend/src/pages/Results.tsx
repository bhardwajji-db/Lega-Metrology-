import { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import {
  Sparkles,
  ShieldCheck,
  Info,
  AlertCircle,
  X,
  Loader2,
  Gavel,
  Printer,
  Copy,
  Check,
  ChevronUp,
  ChevronDown,
  Trash2,
} from 'lucide-react';
import { api } from '../services/api';
import { type AnalysisResponse, type ProductImageEvidence, type ComplianceCheck } from '../types';
import LoadingSkeleton from '../components/ui/LoadingSkeleton';
import EvidenceViewer from '../components/EvidenceViewer';
import StickySectionNav, { scrollToSectionId } from '../components/ui/StickySectionNav';
import { formatAnalysisDateTime } from '../utils/datetime';

import { useAuth } from '../context/AuthContext';
import { useRole } from '../context/RoleContext';
import { useWorkspace } from '../context/WorkspaceContext';

// Results sub-components
import ResultsHeader from '../components/results/ResultsHeader';
import ExecutiveSummary from '../components/results/ExecutiveSummary';
import RiskFactorBreakdown from '../components/results/RiskFactorBreakdown';
import PackagePreview from '../components/results/PackagePreview';
import AttentionRequired from '../components/results/AttentionRequired';
import ActionQueue from '../components/results/ActionQueue';
import ComplianceTable from '../components/results/ComplianceTable';
import RequirementDrawer from '../components/results/RequirementDrawer';
import PackageSnapshot from '../components/results/PackageSnapshot';
import Rule12Section from '../components/results/Rule12Section';
import ExternalVerification from '../components/results/ExternalVerification';
import ConfidencePanel from '../components/results/ConfidencePanel';
import { VisionAnalysisPanel } from '../components/results/VisionAnalysisPanel';
import { BarcodeVerificationCard } from '../components/BarcodeVerificationCard';
import { ProductIdentitySection } from '../components/results/ProductIdentitySection';
import ClaimsAnalysisSection from '../components/results/ClaimsAnalysisSection';

export default function Results() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const [data, setData] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedEvidenceRuleId, setSelectedEvidenceRuleId] = useState<string | null>(null);
  const [selectedEvidenceNonce, setSelectedEvidenceNonce] = useState<number>(0);
  const { officerId, jurisdiction, roleInfo } = useRole();
  const { canUseEnforcementFeatures, canDeleteAnalyses } = useWorkspace();
  const [showNoticeModal, setShowNoticeModal] = useState(false);
  const [noticeCopied, setNoticeCopied] = useState(false);
  const [showDemoGuide, setShowDemoGuide] = useState<boolean>(false);

  // Drawer state for requirement detail
  const [selectedCheck, setSelectedCheck] = useState<ComplianceCheck | null>(null);

  // Delete modal state
  const [showDeleteModal, setShowDeleteModal] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const isDemo = Boolean(
    (location.state as any)?.isDemo ||
    id?.startsWith('demo-') ||
    data?.product_info?.extraction_mode === 'demo'
  );

  useEffect(() => {
    // Check if data was passed via navigation state (demo cases or analyze navigation)
    const stateData = (location.state as any)?.analysisData as AnalysisResponse | undefined;
    if (stateData && stateData.id) {
      setData(stateData);
      setLoading(false);
      return;
    }

    // Otherwise fetch from API (direct URL navigation or reload)
    const fetchData = async () => {
      if (!id) {
        setError('No analysis ID provided.');
        setLoading(false);
        return;
      }
      try {
        let result: AnalysisResponse;
        if (id.startsWith('demo-') || id === '1' || id === '2' || id === '3') {
          const caseNum = id.startsWith('demo-') ? id.split('-')[1] || '1' : id;
          try {
            result = await api.getAnalysis(id);
          } catch {
            result = await api.getDemoCase(caseNum);
          }
        } else {
          result = await api.getAnalysis(id);
        }
        setData(result);
      } catch (err: any) {
        setError(err.message || 'Failed to load analysis results. Please check if the record exists.');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [id, location.state]);

  // Handle Escape key to dismiss modals & drawers
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showDeleteModal) setShowDeleteModal(false);
        if (showNoticeModal) setShowNoticeModal(false);
        if (selectedCheck) setSelectedCheck(null);
      }
    };
    if (showDeleteModal || showNoticeModal || selectedCheck) {
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [showDeleteModal, showNoticeModal, selectedCheck]);

  // Resolve and normalize images array (deduplicates identical images and guarantees Front is primary)
  // Must execute unconditionally on EVERY render to comply with React Rules of Hooks
  const imageList: ProductImageEvidence[] = useMemo(() => {
    if (!data) return [];
    let rawList: ProductImageEvidence[] = [];
    if (data.images && data.images.length > 0) {
      rawList = data.images.filter(img => img.image_url && img.image_url !== '/placeholder.png');
    } else if (data.image_url && data.image_url !== '/placeholder.png') {
      rawList = [{
        filename: 'Product Label',
        image_url: data.image_url,
        label: 'Front',
        ocr_text: data.ocr_result?.full_text || 'No OCR text available.',
        word_count: data.ocr_result?.words?.length || 0
      }];
    }

    if (rawList.length === 0) return [];

    // 1. Deduplicate identical image entries by identity
    const seen = new Set<string>();
    const uniqueList: ProductImageEvidence[] = [];
    for (const img of rawList) {
      const id = (img.image_url && img.image_url !== '/placeholder.png')
        ? img.image_url
        : `${img.filename || ''}_${img.label || ''}_${(img.ocr_text || '').substring(0, 40)}`;
      if (!seen.has(id)) {
        seen.add(id);
        uniqueList.push(img);
      }
    }

    // 2. Disambiguate duplicate labels if genuinely distinct images share the same label
    const labelCounts: Record<string, number> = {};
    uniqueList.forEach(img => {
      const l = (img.label || 'Panel').trim();
      labelCounts[l] = (labelCounts[l] || 0) + 1;
    });

    const labelSeen: Record<string, number> = {};
    const normalized = uniqueList.map((img, idx) => {
      let l = (img.label || `Panel ${idx + 1}`).trim();
      if (labelCounts[l] > 1) {
        labelSeen[l] = (labelSeen[l] || 0) + 1;
        if (labelSeen[l] > 1) {
          l = `${l} ${labelSeen[l]}`;
        }
      }
      return { ...img, label: l };
    });

    // 3. Preserve canonical image array order (index 0..n matches backend image_index 1:1)
    return normalized;
  }, [data]);

  if (loading) {
    return (
      <div className="p-8 max-w-5xl mx-auto">
        <LoadingSkeleton />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-2xl mx-auto my-12 p-8 bg-white dark:bg-slate-900 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800 text-center space-y-4">
        <h2 className="text-xl font-bold text-slate-800 dark:text-slate-100">Unable to Load Analysis</h2>
        <p className="text-slate-600 dark:text-slate-400 text-sm">{error || 'No analysis data found for this product.'}</p>
        <div className="pt-4 flex flex-wrap justify-center gap-3">
          <button
            onClick={() => navigate('/demo')}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors text-sm shadow-sm cursor-pointer"
          >
            <Sparkles className="w-4 h-4 text-amber-300" />
            <span>Open Demo Benchmarks</span>
          </button>
          <button
            onClick={() => navigate('/analyze')}
            className="px-5 py-2.5 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-lg font-medium hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors text-sm cursor-pointer"
          >
            Upload Real Images
          </button>
          <button
            onClick={() => navigate('/history')}
            className="px-5 py-2.5 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-lg font-medium hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors text-sm cursor-pointer"
          >
            View History
          </button>
        </div>
      </div>
    );
  }

  // ── Derived data (preserved from original) ──────────────────────────
  const cr = data.compliance_result || {
    score: 0,
    status: 'UNKNOWN',
    checks: [],
    issues: [],
    passed_rules: 0,
    total_rules: 0,
    failed_rules: 0
  };
  const product_info = data.product_info || ({} as any);

  // Authoritative rule counts directly from backend
  const totalRules = cr.total_rules ?? (cr.checks || []).length;
  const passedCount = cr.passed_rules ?? (cr.checks || []).filter(c => ['PASS', 'COMPLIANT'].includes((c.status || '').toUpperCase())).length;
  const needsReviewCount = cr.needs_review_rules ?? (cr.checks || []).filter(c => ['NEEDS_REVIEW', 'WARNING'].includes((c.status || '').toUpperCase())).length;
  const failedCount = cr.failed_rules ?? (cr.checks || []).filter(c => ['FAIL', 'NON_COMPLIANT'].includes((c.status || '').toUpperCase())).length;
  const notApplicableCount = cr.not_applicable_rules ?? (cr.checks || []).filter(c => (c.status || '').toUpperCase() === 'NOT_APPLICABLE').length;
  const applicableCount = totalRules - notApplicableCount;

  // Actionable recommendations
  const recommendations = data.recommendations || cr.recommendations || [];
  const actionableRecs = recommendations.filter(r =>
    ['FAIL', 'WARNING', 'NEEDS_REVIEW'].includes((r.status || '').toUpperCase())
  );
  const passedRecs = recommendations.filter(r =>
    ['PASS', 'NOT_APPLICABLE'].includes((r.status || '').toUpperCase())
  );

  // Checks needing review / failed
  const failedChecks = (cr.checks || []).filter(c => {
    const s = (c.status || '').toUpperCase();
    return s === 'FAIL' || s.includes('NON_COMPLIANCE');
  });
  const reviewChecks = (cr.checks || []).filter(c => {
    const s = (c.status || '').toUpperCase();
    return s === 'NEEDS_REVIEW' || s === 'WARNING';
  });

  // Overall status classification
  const isReviewRequired = (cr.status || '').toUpperCase().includes('REVIEW') || (needsReviewCount > 0 && failedCount === 0);
  const isCompliant = (cr.status || '').toUpperCase() === 'COMPLIANT' || (failedCount === 0 && needsReviewCount === 0);

  // Status explanation derived strictly from backend results
  const getStatusExplanation = () => {
    if (isCompliant) {
      return "All applicable checks passed the current automated screening.";
    }
    if (isReviewRequired) {
      if (failedCount === 0) {
        return `No confirmed screening failures were detected, but ${needsReviewCount} applicable check${needsReviewCount > 1 ? 's require' : ' requires'} manual verification.`;
      }
      return "No confirmed failures were detected, but one or more applicable checks require manual verification.";
    }
    return "One or more applicable requirements have a confirmed screening failure and should be reviewed.";
  };

  const getCleanProductName = () => {
    if (data.product_name && data.product_name.trim()) {
      return data.product_name;
    }
    return 'Product name not reliably extracted';
  };

  const handleViewEvidence = (ruleId?: string | null, _imageLabel?: string | null) => {
    if (ruleId) {
      setSelectedEvidenceRuleId(ruleId);
      setSelectedEvidenceNonce(prev => prev + 1);
    }
    if (!scrollToSectionId('section-evidence', 64)) {
      scrollToSectionId('evidence-panel', 64);
    }
  };

  const handleReturnToRecommendations = () => {
    scrollToSectionId('section-actions', 64);
  };

  const handleDeleteAnalysis = async () => {
    if (!id) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await api.deleteAnalysis(id);
      navigate('/history');
    } catch (err: any) {
      setDeleteError(err?.message || 'Failed to delete analysis. Please try again.');
      setIsDeleting(false);
    }
  };

  // ── Sticky section nav config ──────────────────────────────────────
  const sectionNavItems = [
    { id: 'section-summary', label: 'Summary' },
    ...((cr.risk_assessment || cr.category_scores) ? [{ id: 'section-risk', label: 'Risk Factors' }] : []),
    ...(imageList.length > 0 ? [{ id: 'section-preview', label: 'Package Preview' }] : []),
    ...(failedChecks.length > 0 || reviewChecks.length > 0 ? [{ id: 'section-attention', label: 'Attention' }] : []),
    ...(actionableRecs.length > 0 ? [{ id: 'section-actions', label: 'Actions' }] : []),
    { id: 'section-requirements', label: 'Requirements' },
    ...(data.claims_analysis ? [{ id: 'section-claims', label: `Claims (${data.claims_analysis.claims_detected})` }] : []),
    ...(data.product_identity ? [{ id: 'section-identity', label: 'Product Identity' }] : []),
    { id: 'section-package-data', label: 'Package Data' },
    ...(data.font_size_analysis ? [{ id: 'section-rule12', label: 'Rule 12' }] : []),
    ...((data.vision_analysis || imageList.some(img => img.vision_analysis)) ? [{ id: 'section-vision', label: 'Computer Vision' }] : []),
    ...((data.fssai_verification || data.gs1_verification || product_info?.barcode_detected || (data.barcode_scan_results && data.barcode_scan_results.length > 0)) ? [{ id: 'section-verification', label: 'Verification' }] : []),
    { id: 'section-evidence', label: 'Evidence' },
  ];

  return (
    <div className="space-y-5 pb-12 animate-in fade-in duration-300">
      {/* Results Header */}
      <ResultsHeader
        productName={getCleanProductName()}
        brand={product_info.brand}
        analysisId={data.id}
        createdAt={data.created_at}
        isDemo={isDemo}
        imageCount={imageList.length}
        frontImageUrl={imageList[0]?.image_url}
        canDelete={!isDemo && (canDeleteAnalyses || Boolean(data.owner_user_id && user?.username && data.owner_user_id.toLowerCase() === user.username.toLowerCase()))}
        canUseEnforcement={canUseEnforcementFeatures}
        multilingual={data.multilingual}
        onNavigateBack={() => navigate(isDemo ? '/demo' : '/history')}
        onNavigateAnalyze={() => navigate('/analyze')}
        onShowNotice={() => setShowNoticeModal(true)}
        onShowDelete={() => { setDeleteError(null); setShowDeleteModal(true); }}
        exportUrls={{
          csv: api.getCsvReportUrl(id || ''),
          xlsx: api.getXlsxReportUrl(id || ''),
          json: api.getJsonReportUrl(id || ''),
          pdf: api.getReportUrl(id || ''),
        }}
      />

      {/* Demo Notice Banner */}
      {isDemo && (
        <div className="bg-gradient-to-r from-amber-500/10 via-indigo-500/10 to-amber-500/10 dark:from-amber-950/30 dark:via-indigo-950/30 dark:to-amber-950/30 border border-amber-300/80 dark:border-amber-800/60 rounded-xl p-3 flex items-center justify-between gap-3 text-amber-950 dark:text-amber-200">
          <div className="flex items-center gap-2.5">
            <Sparkles className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
            <div>
              <span className="font-bold text-xs">SIH Demonstration Benchmark</span>
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-amber-200 dark:bg-amber-900/60 text-amber-800 dark:text-amber-200 uppercase tracking-wider ml-2">
                Fixture
              </span>
            </div>
          </div>
          <button
            onClick={() => setShowDemoGuide(!showDemoGuide)}
            className="inline-flex items-center gap-1 px-2.5 py-1 bg-white dark:bg-slate-900 border border-amber-300 dark:border-amber-700 hover:bg-amber-50 dark:hover:bg-amber-950/40 text-amber-900 dark:text-amber-200 rounded-lg text-[11px] font-semibold transition-all shrink-0 cursor-pointer"
          >
            <Info className="w-3 h-3" />
            <span>{showDemoGuide ? 'Hide' : 'Guide'}</span>
            {showDemoGuide ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
        </div>
      )}

      {/* Collapsible Demo Guide */}
      {isDemo && showDemoGuide && (
        <div className="bg-indigo-50/40 dark:bg-indigo-950/30 rounded-xl border border-indigo-100 dark:border-indigo-900/60 p-4">
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-[11px]">
            {['1. Product Context', '2. Screening Score', '3. Review Items', '4. Inspect Evidence', '5. Enforcement Tools'].map(step => (
              <div key={step} className="bg-white dark:bg-slate-900 p-2.5 rounded-lg border border-indigo-100 dark:border-indigo-900/50">
                <span className="font-bold text-indigo-900 dark:text-indigo-300">{step}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sticky Section Navigation */}
      <StickySectionNav sections={sectionNavItems} />

      {/* ── SECTION: Executive Summary ─────────────────────────────── */}
      <div id="section-summary" className="scroll-mt-16">
        <ExecutiveSummary
          score={cr.score ?? 0}
          status={cr.status}
          passedCount={passedCount}
          needsReviewCount={needsReviewCount}
          failedCount={failedCount}
          notApplicableCount={notApplicableCount}
          applicableCount={applicableCount}
          statusExplanation={getStatusExplanation()}
          isCompliant={isCompliant}
          isReviewRequired={isReviewRequired}
          riskAssessment={cr.risk_assessment}
          categoryScores={cr.category_scores}
          confidenceSummary={cr.confidence_summary}
        />
      </div>

      {/* ── SECTION: Risk Factor Breakdown ─────────────────────────── */}
      {(cr.risk_assessment || cr.category_scores) && (
        <div id="section-risk" className="scroll-mt-16">
          <RiskFactorBreakdown
            riskAssessment={cr.risk_assessment}
            categoryScores={cr.category_scores}
            confidenceSummary={cr.confidence_summary}
            score={cr.score ?? 0}
          />
        </div>
      )}

      {/* ── SECTION: Package Preview (Prominent Front View) ────────── */}
      {imageList.length > 0 && (
        <div id="section-preview" className="scroll-mt-16">
          <PackagePreview
            images={imageList}
            productName={getCleanProductName()}
            brand={product_info.brand}
          />
        </div>
      )}

      {/* ── SECTION: Attention Required ────────────────────────────── */}
      {(failedChecks.length > 0 || reviewChecks.length > 0) && (
        <div id="section-attention" className="scroll-mt-16">
          <AttentionRequired
            failedChecks={failedChecks}
            reviewChecks={reviewChecks}
            onViewEvidence={handleViewEvidence}
          />
        </div>
      )}

      {/* ── SECTION: Action Queue ──────────────────────────────────── */}
      {actionableRecs.length > 0 && (
        <div id="section-actions" className="scroll-mt-16">
          <ActionQueue
            recommendations={actionableRecs}
            passedRecs={passedRecs}
            onViewEvidence={handleViewEvidence}
            onNavigateAnalyze={() => navigate('/analyze')}
          />
        </div>
      )}

      {/* ── SECTION: Compliance Requirements Table ─────────────────── */}
      <div id="section-requirements" className="scroll-mt-16">
        <ComplianceTable
          checks={cr.checks || []}
          onViewEvidence={handleViewEvidence}
          onSelectRequirement={(check) => setSelectedCheck(check)}
        />
      </div>

      {/* Requirement Detail Drawer */}
      <RequirementDrawer
        check={selectedCheck}
        onClose={() => setSelectedCheck(null)}
        onViewEvidence={handleViewEvidence}
      />

      {/* ── SECTION: Misleading Claim Detection Engine ─────────────── */}
      {data.claims_analysis && (
        <div id="section-claims" className="scroll-mt-16">
          <ClaimsAnalysisSection
            claimsAnalysis={data.claims_analysis}
            onViewEvidence={handleViewEvidence}
          />
        </div>
      )}

      {/* ── SECTION: Product Identity & Multi-Source Verification ── */}
      {(data.product_identity || data.external_product_verification) && (
        <div id="section-identity" className="scroll-mt-16">
          <ProductIdentitySection 
            identity={data.product_identity} 
            externalProductVerification={data.external_product_verification}
            onSelectEvidence={(fieldKey, _bbox, imgLabel) => handleViewEvidence(fieldKey, imgLabel)}
          />
        </div>
      )}

      {/* ── SECTION: Package Data (Package Snapshot & Confidence) ──── */}
      <div id="section-package-data" className="scroll-mt-16 space-y-6">
        <PackageSnapshot productInfo={product_info} />
        <ConfidencePanel productInfo={product_info} />
      </div>

      {/* ── SECTION: Rule 12 ───────────────────────────────────────── */}
      {data.font_size_analysis && (
        <div id="section-rule12" className="scroll-mt-16">
          <Rule12Section
            fontSizeAnalysis={data.font_size_analysis}
            calibrationResult={data.calibration_result}
          />
        </div>
      )}

      {/* ── SECTION: Computer Vision Intelligence Layer ─────────────── */}
      {(data.vision_analysis || imageList.some(img => img.vision_analysis)) && (
        <div id="section-vision" className="scroll-mt-16">
          <VisionAnalysisPanel
            visionAnalysis={data.vision_analysis || imageList.find(img => img.vision_analysis)?.vision_analysis}
          />
        </div>
      )}

      {/* ── SECTION: External Verification ─────────────────────────── */}
      {(data.fssai_verification || data.gs1_verification || product_info?.barcode_detected || (data.barcode_scan_results && data.barcode_scan_results.length > 0)) && (
        <div id="section-verification" className="scroll-mt-16 space-y-4">
          <BarcodeVerificationCard
            barcode={product_info?.barcode_detected ? {
              raw_value: product_info.barcode_detected,
              symbology: 'EAN-13',
              country_of_origin: 'India',
              country_flag: '🇮🇳',
              is_valid_checksum: true
            } : (data.barcode_scan_results && data.barcode_scan_results.length > 0 ? data.barcode_scan_results[0] : null)}
            scanResults={data.barcode_scan_results}
            productInfo={product_info}
          />
          <ExternalVerification
            fssaiVerification={data.fssai_verification}
            gs1Verification={data.gs1_verification}
            fssaiLicense={product_info.fssai_license}
            externalVerification={data.external_verification}
          />
        </div>
      )}

      {/* ── SECTION: Evidence Viewer ───────────────────────────────── */}
      <div id="section-evidence" className="scroll-mt-16">
        <EvidenceViewer
          analysisId={data.id}
          images={imageList}
          checks={cr.checks || []}
          recommendations={recommendations}
          ocrResult={data.ocr_result}
          selectedRuleId={selectedEvidenceRuleId}
          selectionNonce={selectedEvidenceNonce}
          onSelectRule={(ruleId) => setSelectedEvidenceRuleId(ruleId)}
          onReturnToRecommendations={handleReturnToRecommendations}
        />
      </div>

      {/* ── Regulatory Screening Notice Banner ─────────────────────── */}
      <div className="bg-slate-900 text-slate-200 rounded-xl p-4 border border-slate-800 flex items-start gap-3 text-[11px] leading-relaxed">
        <ShieldCheck className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <h4 className="text-xs font-semibold text-white">Automated Statutory Compliance Screening</h4>
          <p className="text-slate-400">
            MetrCheck AI evaluates labels against the <strong className="text-slate-300">Legal Metrology (Packaged Commodities) Rules, 2011</strong> and <strong className="text-slate-300">FSSAI Labelling Regulations, 2020</strong>. Non-detection does not confirm physical absence. Declarations marked <span className="text-indigo-400 font-semibold">NEEDS REVIEW</span> must be verified manually.
          </p>
        </div>
      </div>

      {/* ── Delete Analysis Confirmation Modal ─────────────────────── */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 dark:bg-slate-950/80 backdrop-blur-xs p-4 animate-in fade-in duration-200">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl max-w-md w-full p-6 space-y-4 border border-slate-200 dark:border-slate-800">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-red-50 dark:bg-red-950/60 text-red-600 dark:text-red-400 rounded-xl">
                  <AlertCircle className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">Delete Analysis Record?</h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">This action is permanent and cannot be undone</p>
                </div>
              </div>
              <button
                onClick={() => setShowDeleteModal(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                disabled={isDeleting}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-3 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200/80 dark:border-slate-700/60 text-xs space-y-1.5">
              <div className="flex justify-between">
                <span className="text-slate-500 dark:text-slate-400 font-medium">Product:</span>
                <span className="text-slate-800 dark:text-slate-200 font-bold line-clamp-1">{data?.product_name || 'Unknown Product'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 dark:text-slate-400 font-medium">Screening Date:</span>
                <span className="text-slate-800 dark:text-slate-200">{formatAnalysisDateTime(data?.created_at)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500 dark:text-slate-400 font-medium">Status / Score:</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">{cr.status} ({Number(cr.score).toFixed(1)} / 100)</span>
              </div>
            </div>

            <p className="text-xs text-slate-600 dark:text-slate-400">
              This will permanently delete the compliance screening record and its uploaded images. You will be redirected to the History page.
            </p>

            {deleteError && (
              <div className="p-3 bg-red-50 dark:bg-red-950/60 border border-red-200 dark:border-red-800 text-xs text-red-700 dark:text-red-300 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-red-500" />
                <span>{deleteError}</span>
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowDeleteModal(false)}
                disabled={isDeleting}
                className="px-4 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg font-semibold text-xs transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteAnalysis}
                disabled={isDeleting}
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-semibold text-xs shadow-sm transition-colors cursor-pointer disabled:opacity-50"
              >
                {isDeleting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Deleting...</span>
                  </>
                ) : (
                  <>
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Delete Record</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Statutory Show-Cause Notice Generator Modal (Enforcement Officer Mode) ── */}
      {showNoticeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 dark:bg-slate-950/80 backdrop-blur-xs p-4 animate-in fade-in duration-200">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl max-w-3xl w-full p-6 sm:p-8 space-y-5 border border-slate-200 dark:border-slate-800 max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-slate-200 dark:border-slate-800 pb-4">
              <div className="flex items-center gap-3">
                <div className="p-3 bg-amber-500/10 text-amber-600 dark:text-amber-400 rounded-2xl border border-amber-500/20">
                  <Gavel className="w-6 h-6" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">Statutory Show-Cause Notice Draft</h3>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 dark:bg-amber-950/70 text-amber-800 dark:text-amber-300">SECTION 36 / 38</span>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">Official legal notice generated by Enforcement Authority for non-compliant commodity</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowNoticeModal(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Notice Printable Document Preview */}
            <div id="printable-notice" className="p-6 rounded-2xl bg-amber-50/30 dark:bg-slate-950/60 border border-amber-200/80 dark:border-slate-800 space-y-4 font-serif text-slate-900 dark:text-slate-100 text-xs leading-relaxed">
              {/* Government Header */}
              <div className="text-center space-y-1 pb-3 border-b border-slate-200 dark:border-slate-800">
                <span className="text-[11px] font-bold uppercase tracking-widest text-slate-500 dark:text-slate-400 block font-sans">GOVERNMENT OF INDIA • ENFORCEMENT WING</span>
                <h4 className="text-sm font-bold uppercase font-sans tracking-tight">DIRECTORATE OF LEGAL METROLOGY</h4>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 font-sans">{jurisdiction}</p>
              </div>

              {/* Notice Metadata */}
              <div className="flex justify-between items-center text-[11px] font-mono border-b border-slate-100 dark:border-slate-800 pb-2">
                <span><strong>Notice Ref:</strong> LM/ENF/2026/SCN-{(data?.id || '0000').substring(0, 8).toUpperCase()}</span>
                <span><strong>Date:</strong> {new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'long', year: 'numeric' })}</span>
              </div>

              {/* Addressee */}
              <div className="space-y-0.5 font-sans">
                <span className="text-[10px] uppercase font-bold text-slate-400">TO / NOTICE RECIPIENT:</span>
                <p className="font-bold text-xs">{data?.product_info?.manufacturer || data?.product_name || 'Manufacturer / Packer / Importer of the Commodity'}</p>
                <p className="text-[11px] text-slate-600 dark:text-slate-400">Product: <strong>{data?.product_name}</strong></p>
              </div>

              {/* Subject */}
              <div className="p-2.5 bg-amber-100/50 dark:bg-amber-950/40 rounded-lg border border-amber-300/80 dark:border-amber-800/60 font-sans font-bold text-xs text-amber-950 dark:text-amber-200">
                SUBJECT: STATUTORY NOTICE FOR CONTRAVENTION OF THE LEGAL METROLOGY ACT, 2009 READ WITH THE LEGAL METROLOGY (PACKAGED COMMODITIES) RULES, 2011.
              </div>

              {/* Notice Body */}
              <div className="space-y-2 text-slate-800 dark:text-slate-200">
                <p>
                  WHEREAS an automated and evidence-linked statutory inspection of the packaged commodity <strong>"{data?.product_name}"</strong> was executed under the supervision of the authorized Enforcement Officer (ID: <code>{officerId}</code>);
                </p>
                <p>
                  AND WHEREAS digital computer vision and optical verification confirmed the following statutory defects, omissions, and contraventions under the Legal Metrology (Packaged Commodities) Rules, 2011:
                </p>

                {data?.compliance_result?.checks?.filter(c => c.status === 'FAIL').length ? (
                  data.compliance_result.checks.filter(c => c.status === 'FAIL').map((fc, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs">
                      <span className="font-mono font-bold text-red-600 dark:text-red-400 shrink-0">[{fc.rule_id}]:</span>
                      <span><strong>{fc.field_label}:</strong> {fc.reason || fc.explanation || 'Mandatory statutory declaration missing or non-compliant.'} (Ref: {fc.source_reference || 'Rule 6'})</span>
                    </div>
                  ))
                ) : (
                  <div className="text-xs text-slate-500">
                    • Non-compliance findings: Declarations under Review require physical verification under Rule 6(1).
                  </div>
                )}

                <p>
                  NOW THEREFORE, under the powers conferred by <strong>Section 36 &amp; Section 38 of the Legal Metrology Act, 2009</strong>, you are hereby called upon to show cause within <strong>fifteen (15) working days</strong> from the receipt of this notice as to why penal proceedings should not be initiated against your enterprise.
                </p>

                <div className="p-3 bg-red-50 dark:bg-red-950/40 rounded-xl border border-red-200 dark:border-red-900/60 font-sans text-xs text-red-900 dark:text-red-200 space-y-1">
                  <span className="font-bold block">STATUTORY PENALTY CLAUSES APPLICABLE:</span>
                  <p>• <strong>Section 36(1) First Offense:</strong> Fine extending up to <strong>₹25,000</strong> for non-standard packaging or missing declarations.</p>
                  <p>• <strong>Section 36(2) Subsequent Offense:</strong> Fine extending up to <strong>₹50,000</strong> and/or imprisonment for a term up to one year.</p>
                </div>
              </div>

              {/* Signature Block */}
              <div className="pt-4 flex justify-between items-end border-t border-slate-200 dark:border-slate-800 font-sans">
                <div className="text-[10px] text-slate-400">
                  <span>Digital Inspection ID: {data?.id}</span><br/>
                  <span>Compliance Screening Score: {Number(cr.score).toFixed(1)} / 100</span>
                </div>
                <div className="text-right space-y-0.5">
                  <div className="inline-block border-b border-slate-400 dark:border-slate-600 px-6 py-1 font-mono font-bold text-xs">
                    [Signed Electronically]
                  </div>
                  <span className="block font-bold text-xs">Enforcement Officer (Legal Metrology)</span>
                  <span className="block text-[11px] text-slate-500">Badge ID: {officerId}</span>
                </div>
              </div>
            </div>

            {/* Modal Action Controls */}
            <div className="flex items-center justify-between gap-3 pt-2">
              <span className="text-xs text-slate-500">
                Officer: <strong>{officerId}</strong> ({roleInfo.label})
              </span>
              <div className="flex items-center gap-2.5">
                <button
                  type="button"
                  onClick={() => {
                    const noticeText = document.getElementById('printable-notice')?.innerText || '';
                    navigator.clipboard.writeText(noticeText);
                    setNoticeCopied(true);
                    setTimeout(() => setNoticeCopied(false), 2500);
                  }}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-xl font-semibold text-xs transition-colors cursor-pointer"
                >
                  {noticeCopied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{noticeCopied ? 'Notice Copied!' : 'Copy Notice Text'}</span>
                </button>
                <button
                  type="button"
                  onClick={() => window.print()}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-semibold text-xs shadow-md shadow-indigo-600/20 transition-all cursor-pointer"
                >
                  <Printer className="w-3.5 h-3.5" />
                  <span>Print / Save PDF Notice</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
