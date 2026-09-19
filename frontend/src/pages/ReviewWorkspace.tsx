import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ShieldCheck, 
  ShieldAlert,
  ArrowLeft, 
  CheckCircle2, 
  XCircle, 
  Edit3, 
  PlusCircle, 
  Trash2, 
  MessageSquare, 
  RotateCcw, 
  ArrowUpRight, 
  Clock, 
  UserCheck, 
  Layers, 
  Sparkles,
  GitCompare,
  AlertOctagon
} from 'lucide-react';
import { api } from '../services/api';
import { 
  type ReviewDetailResponse, 
  type AIvsHumanComparison
} from '../types';
import EvidenceViewer from '../components/EvidenceViewer';
import { useAuth } from '../context/AuthContext';

const FIELD_LABELS: Record<string, string> = {
  product_name: "Product Name",
  brand: "Brand",
  mrp: "Maximum Retail Price (MRP)",
  net_quantity: "Net Quantity",
  manufacturer: "Manufacturer Name & Address",
  marketed_by: "Marketed By",
  fssai_license: "FSSAI License Number",
  consumer_care: "Consumer Care Details",
  country_of_origin: "Country of Origin",
  manufacture_date: "Date of Manufacture",
  expiry_date: "Expiry / Best Before Date",
  batch_number: "Batch / Lot Number",
  ingredients: "Ingredients List",
  nutritional_info: "Nutrition Information Panel"
};

export default function ReviewWorkspace() {
  const { reviewId } = useParams<{ reviewId: string }>();
  const navigate = useNavigate();

  const { user } = useAuth();
  const [review, setReview] = useState<ReviewDetailResponse | null>(null);
  const [diffComparison, setDiffComparison] = useState<AIvsHumanComparison | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'EVIDENCE' | 'CORRECTIONS' | 'DIFF' | 'HISTORY'>('EVIDENCE');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isUnauthorized, setIsUnauthorized] = useState<boolean>(false);

  // Modals state
  const [modalType, setModalType] = useState<'ACCEPT' | 'REJECT' | 'CORRECT' | 'ADD_EVIDENCE' | 'REMOVE_EVIDENCE' | 'COMMENT' | 'ESCALATE' | 'REOPEN' | 'ASSIGN' | null>(null);
  
  // Form states
  const [commentText, setCommentText] = useState<string>('');
  const [rejectionReason, setRejectionReason] = useState<string>('INCORRECT_EXTRACTION');
  const [selectedField, setSelectedField] = useState<string>('mrp');
  const [correctedValue, setCorrectedValue] = useState<string>('');
  const [correctionReason, setCorrectionReason] = useState<string>('');
  const [escalationReason, setEscalationReason] = useState<string>('');
  const [escalationTarget, setEscalationTarget] = useState<string>('ADMIN');
  const [reopenReason, setReopenReason] = useState<string>('');
  const [officers, setOfficers] = useState<Array<{ username: string; full_name: string; role: string }>>([]);
  const [assignedOfficer, setAssignedOfficer] = useState<string>('');

  // Evidence removal state
  const [targetEvidenceId, setTargetEvidenceId] = useState<string>('');
  const [removeEvidenceReason, setRemoveEvidenceReason] = useState<string>('');

  // Missing Evidence state
  const [missingEvidenceText, setMissingEvidenceText] = useState<string>('');
  const [missingLinkedRule, setMissingLinkedRule] = useState<string>('LM-001');
  const [missingLinkedField, setMissingLinkedField] = useState<string>('manufacturer');

  const loadReviewData = async () => {
    if (!reviewId) return;
    try {
      setLoading(true);
      setError(null);
      setIsUnauthorized(false);
      const [revData, offRes] = await Promise.all([
        api.getReviewDetails(reviewId),
        api.getAvailableOfficers()
      ]);
      setReview(revData);
      setOfficers(offRes.officers || []);

      // Load diff comparison
      try {
        const diffData = await api.getAIvsHumanDiff(reviewId);
        setDiffComparison(diffData);
      } catch (err) {
        console.warn("Could not load diff comparison:", err);
      }
    } catch (err: any) {
      const msg = err?.message || '';
      if (
        msg.includes('403') || 
        msg.toLowerCase().includes('forbidden') || 
        msg.toLowerCase().includes('privilege') || 
        msg.toLowerCase().includes('unauthorized') ||
        msg.toLowerCase().includes('not authorized')
      ) {
        setIsUnauthorized(true);
        setError('Officer privileges are required to access this review workspace.');
      } else {
        setError(msg || 'Failed to load review workspace.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReviewData();
  }, [reviewId]);

  const handleAcceptSubmit = async () => {
    if (!review) return;
    setSubmitting(true);
    try {
      await api.acceptReview(review.review_id, commentText);
      setModalType(null);
      setCommentText('');
      await loadReviewData();
    } catch (err: any) {
      alert(err.message || 'Failed to accept AI result.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRejectSubmit = async () => {
    if (!review || !commentText.trim()) return;
    setSubmitting(true);
    try {
      await api.rejectReview(review.review_id, rejectionReason, commentText);
      setModalType(null);
      setCommentText('');
      await loadReviewData();
    } catch (err: any) {
      alert(err.message || 'Failed to reject AI result.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCorrectFieldSubmit = async () => {
    if (!review || !correctedValue.trim()) return;
    setSubmitting(true);
    try {
      await api.correctReviewField(
        review.review_id,
        selectedField,
        FIELD_LABELS[selectedField] || selectedField,
        correctedValue,
        correctionReason
      );
      setModalType(null);
      setCorrectedValue('');
      setCorrectionReason('');
      await loadReviewData();
    } catch (err: any) {
      alert(err.message || 'Failed to apply field correction.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAddEvidenceSubmit = async () => {
    if (!review || !missingEvidenceText.trim()) return;
    setSubmitting(true);
    try {
      await api.addReviewEvidence(review.review_id, {
        image_index: 0,
        image_label: "Front",
        text: missingEvidenceText,
        linked_rule_id: missingLinkedRule,
        linked_field: missingLinkedField,
        comments: commentText
      });
      setModalType(null);
      setMissingEvidenceText('');
      setCommentText('');
      await loadReviewData();
    } catch (err: any) {
      alert(err.message || 'Failed to add missing evidence.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRemoveEvidenceSubmit = async () => {
    if (!review || !targetEvidenceId || !removeEvidenceReason.trim()) return;
    setSubmitting(true);
    try {
      await api.removeReviewEvidence(review.review_id, targetEvidenceId, removeEvidenceReason);
      setModalType(null);
      setTargetEvidenceId('');
      setRemoveEvidenceReason('');
      await loadReviewData();
    } catch (err: any) {
      alert(err.message || 'Failed to remove evidence.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCommentSubmit = async () => {
    if (!review || !commentText.trim()) return;
    setSubmitting(true);
    try {
      await api.addReviewComment(review.review_id, commentText);
      setModalType(null);
      setCommentText('');
      await loadReviewData();
    } catch (err: any) {
      alert(err.message || 'Failed to add comment.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEscalateSubmit = async () => {
    if (!review || !escalationReason.trim()) return;
    setSubmitting(true);
    try {
      await api.escalateReview(review.review_id, escalationReason, commentText, escalationTarget);
      setModalType(null);
      setEscalationReason('');
      setCommentText('');
      await loadReviewData();
    } catch (err: any) {
      alert(err.message || 'Failed to escalate review.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReopenSubmit = async () => {
    if (!review || !reopenReason.trim()) return;
    setSubmitting(true);
    try {
      await api.reopenReview(review.review_id, reopenReason, commentText);
      setModalType(null);
      setReopenReason('');
      setCommentText('');
      await loadReviewData();
    } catch (err: any) {
      alert(err.message || 'Failed to reopen review.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAssignSubmit = async () => {
    if (!review || !assignedOfficer) return;
    setSubmitting(true);
    try {
      await api.assignReview(review.review_id, assignedOfficer, commentText);
      setModalType(null);
      setAssignedOfficer('');
      setCommentText('');
      await loadReviewData();
    } catch (err: any) {
      alert(err.message || 'Failed to assign review.');
    } finally {
      setSubmitting(false);
    }
  };

  if (isUnauthorized) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center p-4">
        <div className="p-8 rounded-2xl bg-slate-900/90 border border-amber-500/40 shadow-2xl text-center space-y-4 max-w-lg mx-auto">
          <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center mx-auto text-amber-400">
            <ShieldAlert className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold text-white">Officer Privileges Required</h2>
          <p className="text-xs text-slate-300 leading-relaxed">
            Officer privileges are required to access this review workspace. You are currently logged in with a Merchant/Public account. Only verified Enforcement Officers and Administrators can inspect and override statutory packaging findings.
          </p>
          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-400">
            Active Account: <span className="font-mono text-amber-300 font-semibold">{user?.username || 'User'}</span> • Role: <span className="font-mono text-slate-300 font-semibold">{user?.role || 'MERCHANT_PUBLIC'}</span>
          </div>
          <div className="flex items-center justify-center gap-3 pt-2">
            <button
              onClick={() => navigate('/login')}
              className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl transition-all shadow-md cursor-pointer"
            >
              Switch Account (Login as Officer)
            </button>
            <button
              onClick={() => navigate('/reviews')}
              className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold rounded-xl border border-slate-700 transition-all cursor-pointer"
            >
              Back to Queue
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (error && !review && !loading) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center p-4">
        <div className="p-8 rounded-2xl bg-slate-900/90 border border-rose-500/40 shadow-2xl text-center space-y-4 max-w-lg mx-auto">
          <div className="w-16 h-16 rounded-2xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center mx-auto text-rose-400">
            <AlertOctagon className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold text-white">Review Workspace Error</h2>
          <p className="text-xs text-slate-300 leading-relaxed">{error}</p>
          <div className="flex items-center justify-center gap-3 pt-2">
            <button
              onClick={() => loadReviewData()}
              className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl transition-all shadow-md cursor-pointer"
            >
              Retry
            </button>
            <button
              onClick={() => navigate('/reviews')}
              className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold rounded-xl border border-slate-700 transition-all cursor-pointer"
            >
              Back to Review Queue
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (loading || !review) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-400">
        <div className="flex items-center gap-3">
          <Clock className="w-6 h-6 animate-spin text-indigo-500" />
          <span>Loading Inspection Workspace...</span>
        </div>
      </div>
    );
  }

  const aiSnap = review.ai_snapshot || {};
  const humanRes = review.human_verified_result || {};
  const images = aiSnap.images || [];
  const compResult = aiSnap.compliance_result || {};
  const checks = compResult.checks || [];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8 space-y-6">
      {/* Top Navigation & Status Bar */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/reviews')}
            className="p-2 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 hover:text-white transition-colors cursor-pointer"
            title="Back to Review Dashboard"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h1 className="text-xl md:text-2xl font-black text-white tracking-tight">
                {review.product_name}
              </h1>
              <span className="font-mono text-xs px-2.5 py-0.5 rounded-md bg-slate-900 border border-slate-800 text-slate-400">
                {review.analysis_id.slice(0, 14)}
              </span>
              <span className={`px-2.5 py-1 text-xs font-bold rounded-full ${
                review.status.startsWith('VERIFIED') 
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                  : (review.status === 'REJECTED' 
                      ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30' 
                      : 'bg-amber-500/20 text-amber-300 border border-amber-500/30')
              }`}>
                Status: {review.status.replace('_', ' ')}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Assigned: <strong className="text-indigo-300">{review.assigned_officer ? `@${review.assigned_officer}` : 'Unassigned'}</strong>
              {review.verified_by && <> • Verified by: <strong className="text-emerald-300">@{review.verified_by}</strong> ({new Date(review.verified_at || '').toLocaleString()})</>}
            </p>
          </div>
        </div>

        {/* Action Buttons Toolbar */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setModalType('ASSIGN')}
            className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-semibold text-slate-300 flex items-center gap-1.5 cursor-pointer"
          >
            <UserCheck className="w-4 h-4 text-blue-400" />
            <span>Assign</span>
          </button>

          <button
            onClick={() => {
              setSelectedField('mrp');
              setCorrectedValue('');
              setModalType('CORRECT');
            }}
            className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-semibold text-slate-300 flex items-center gap-1.5 cursor-pointer"
          >
            <Edit3 className="w-4 h-4 text-amber-400" />
            <span>Correct Field</span>
          </button>

          <button
            onClick={() => setModalType('ADD_EVIDENCE')}
            className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-semibold text-slate-300 flex items-center gap-1.5 cursor-pointer"
          >
            <PlusCircle className="w-4 h-4 text-emerald-400" />
            <span>Add Evidence</span>
          </button>

          <button
            onClick={() => setModalType('ACCEPT')}
            className="px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-sm shadow-emerald-950 cursor-pointer"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>Accept AI</span>
          </button>

          <button
            onClick={() => setModalType('REJECT')}
            className="px-3.5 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-sm shadow-rose-950 cursor-pointer"
          >
            <XCircle className="w-4 h-4" />
            <span>Reject AI</span>
          </button>

          <button
            onClick={() => setModalType('ESCALATE')}
            className="px-3 py-2 rounded-xl bg-purple-900/40 border border-purple-500/30 text-purple-300 hover:bg-purple-900/60 text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
          >
            <ArrowUpRight className="w-4 h-4" />
            <span>Escalate</span>
          </button>

          <button
            onClick={() => setModalType('COMMENT')}
            className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-semibold text-slate-300 flex items-center gap-1.5 cursor-pointer"
          >
            <MessageSquare className="w-4 h-4 text-sky-400" />
            <span>Add Comment</span>
          </button>

          <button
            onClick={() => setModalType('REMOVE_EVIDENCE')}
            className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-semibold text-slate-300 flex items-center gap-1.5 cursor-pointer"
          >
            <Trash2 className="w-4 h-4 text-rose-400" />
            <span>Remove Evidence</span>
          </button>

          {['VERIFIED_PASS', 'VERIFIED_FAIL', 'VERIFIED_NEEDS_REVIEW', 'REJECTED', 'CLOSED'].includes(review.status) && (
            <button
              onClick={() => setModalType('REOPEN')}
              className="px-3 py-2 rounded-xl bg-cyan-900/40 border border-cyan-500/30 text-cyan-300 hover:bg-cyan-900/60 text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
            >
              <RotateCcw className="w-4 h-4" />
              <span>Reopen</span>
            </button>
          )}
        </div>
      </div>

      {/* Comparison Summary Banner: AI Result vs Human-Verified Working Result */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Left: AI Automated Output */}
        <div className="p-4 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
              Automated AI Result (Immutable)
            </span>
            <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
              review.ai_status === 'PASS' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
            }`}>
              {review.ai_status}
            </span>
          </div>
          <div className="flex items-baseline gap-3">
            <span className="text-2xl font-black text-white">{review.ai_score.toFixed(1)}/100</span>
            <span className="text-xs text-slate-400">Risk: <strong className="text-slate-300">{review.ai_risk_level}</strong></span>
            <span className="text-xs text-slate-400">Critical Issues: <strong className="text-red-400">{review.critical_issues_count}</strong></span>
          </div>
          <p className="text-[11px] text-slate-400">
            Original snapshot captured at {new Date(review.created_at).toLocaleString()}.
          </p>
        </div>

        {/* Right: Human Verified Result */}
        <div className="p-4 rounded-2xl bg-indigo-950/20 border border-indigo-500/30 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-indigo-300 uppercase tracking-wider flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
              Human Verified Result (Authoritative)
            </span>
            <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
              {review.final_human_status || review.status}
            </span>
          </div>
          <div className="flex items-baseline gap-3">
            <span className="text-2xl font-black text-indigo-300">
              {review.human_score !== null && review.human_score !== undefined ? `${review.human_score.toFixed(1)}/100` : `${review.ai_score.toFixed(1)}/100`}
            </span>
            <span className="text-xs text-indigo-200/70">
              Risk: <strong className="text-indigo-200">{review.human_risk_level || review.ai_risk_level}</strong>
            </span>
            <span className="text-xs text-indigo-200/70">
              Corrections Applied: <strong className="text-amber-300">{review.field_corrections.length}</strong>
            </span>
          </div>
          <p className="text-[11px] text-indigo-200/60">
            Authoritative officer verification state. {humanRes.last_recalculated_at ? `(Recalculated: ${new Date(humanRes.last_recalculated_at).toLocaleTimeString()})` : ''}
          </p>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
        <button
          onClick={() => setActiveTab('EVIDENCE')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeTab === 'EVIDENCE' ? 'bg-indigo-600 text-white shadow-xs shadow-indigo-950' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>Evidence &amp; Rule Inspection</span>
        </button>

        <button
          onClick={() => setActiveTab('CORRECTIONS')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeTab === 'CORRECTIONS' ? 'bg-indigo-600 text-white shadow-xs shadow-indigo-950' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
          }`}
        >
          <Edit3 className="w-4 h-4" />
          <span>Officer Corrections ({review.field_corrections.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('DIFF')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeTab === 'DIFF' ? 'bg-indigo-600 text-white shadow-xs shadow-indigo-950' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
          }`}
        >
          <GitCompare className="w-4 h-4" />
          <span>AI vs Human Diff</span>
        </button>

        <button
          onClick={() => setActiveTab('HISTORY')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeTab === 'HISTORY' ? 'bg-indigo-600 text-white shadow-xs shadow-indigo-950' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
          }`}
        >
          <Clock className="w-4 h-4" />
          <span>Review Audit History ({review.history.length})</span>
        </button>
      </div>

      {/* Tab 1: Evidence Viewer & Checks */}
      {activeTab === 'EVIDENCE' && (
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-4 md:p-6 space-y-6">
          <EvidenceViewer
            analysisId={review.analysis_id}
            images={images}
            checks={checks}
          />
        </div>
      )}

      {/* Tab 2: Officer Field Corrections & Evidence Modifications */}
      {activeTab === 'CORRECTIONS' && (
        <div className="space-y-6">
          <div className="rounded-2xl bg-slate-900 border border-slate-800 p-6 space-y-4 shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Edit3 className="w-5 h-5 text-amber-400" />
                <h3 className="text-base font-bold text-white">Statutory Declaration Corrections</h3>
              </div>
              <button
                onClick={() => setModalType('CORRECT')}
                className="px-3 py-1.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold cursor-pointer"
              >
                + Add New Correction
              </button>
            </div>

            {review.field_corrections.length === 0 ? (
              <p className="text-xs text-slate-400 py-4">No field corrections have been recorded for this review.</p>
            ) : (
              <div className="divide-y divide-slate-800">
                {review.field_corrections.map((corr, idx) => (
                  <div key={idx} className="py-3 flex flex-col md:flex-row items-start md:items-center justify-between gap-2">
                    <div>
                      <span className="text-xs font-bold text-white block">{corr.field_label} ({corr.field_name})</span>
                      <div className="flex items-center gap-2 text-xs mt-1">
                        <span className="text-slate-400 line-through">Original: {corr.original_value || 'None'}</span>
                        <span className="text-slate-400">→</span>
                        <span className="text-emerald-400 font-bold">Corrected: {corr.corrected_value}</span>
                      </div>
                      <p className="text-[11px] text-slate-400 mt-0.5">Reason: {corr.reason}</p>
                    </div>
                    <div className="text-right text-[10px] text-slate-400">
                      <span>By: @{corr.officer_username} ({corr.officer_role})</span>
                      <span className="block">{new Date(corr.timestamp).toLocaleString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-2xl bg-slate-900 border border-slate-800 p-6 space-y-4 shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <PlusCircle className="w-5 h-5 text-emerald-400" />
                <h3 className="text-base font-bold text-white">Evidence Annotations &amp; Soft-Removals</h3>
              </div>
            </div>

            {review.evidence_modifications.length === 0 ? (
              <p className="text-xs text-slate-400 py-4">No evidence annotations or removals recorded.</p>
            ) : (
              <div className="divide-y divide-slate-800">
                {review.evidence_modifications.map((mod, idx) => (
                  <div key={idx} className="py-3 flex items-start justify-between gap-2">
                    <div>
                      <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                        mod.action === 'ADDED' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                      }`}>
                        {mod.action}
                      </span>
                      {mod.action === 'ADDED' ? (
                        <p className="text-xs text-slate-300 mt-1">
                          Rule: <strong>{mod.evidence?.linked_rule_id}</strong> — Text: "{mod.evidence?.text}"
                        </p>
                      ) : (
                        <p className="text-xs text-slate-300 mt-1">
                          Evidence ID: <strong>{mod.evidence_id}</strong> — Reason: {mod.reason}
                        </p>
                      )}
                    </div>
                    <span className="text-[10px] text-slate-400">
                      @{mod.officer_username} • {new Date(mod.timestamp).toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 3: AI vs Human Diff */}
      {activeTab === 'DIFF' && diffComparison && (
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-6 space-y-6 shadow-sm">
          <div className="border-b border-slate-800 pb-4">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <GitCompare className="w-5 h-5 text-indigo-400" />
              AI Automated Output vs Final Human Verified Result
            </h3>
            <p className="text-xs text-slate-400 mt-1">{diffComparison.summary}</p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 uppercase font-bold text-[10px]">
                  <th className="py-2.5 px-3">Statutory Field</th>
                  <th className="py-2.5 px-3">AI Automated Value</th>
                  <th className="py-2.5 px-3">Human Verified Value</th>
                  <th className="py-2.5 px-3">Diff State</th>
                  <th className="py-2.5 px-3">Reviewer Attribution</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {diffComparison.field_diffs.map((fd, i) => (
                  <tr key={i} className={`hover:bg-slate-800/30 ${fd.is_changed ? 'bg-indigo-950/20' : ''}`}>
                    <td className="py-2.5 px-3 font-semibold text-slate-200">{fd.field_label}</td>
                    <td className="py-2.5 px-3 text-slate-400">{fd.ai_value || '—'}</td>
                    <td className="py-2.5 px-3 font-bold text-white">{fd.human_value || '—'}</td>
                    <td className="py-2.5 px-3">
                      {fd.is_changed ? (
                        <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-semibold text-[10px]">
                          {fd.change_type}
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px]">
                          UNCHANGED
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-slate-400">
                      {fd.officer_username ? `@${fd.officer_username}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 4: Review History Timeline */}
      {activeTab === 'HISTORY' && (
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-6 space-y-6 shadow-sm">
          <div className="border-b border-slate-800 pb-3">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Clock className="w-5 h-5 text-indigo-400" />
              Chronological Audit Trail
            </h3>
          </div>

          <div className="relative pl-6 space-y-6 before:content-[''] before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
            {review.history.map((evt, idx) => (
              <div key={idx} className="relative space-y-1">
                <span className="absolute -left-6 top-1 w-3 h-3 rounded-full bg-indigo-500 ring-4 ring-slate-950" />
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-white">{evt.action}</span>
                  <span className="text-[10px] text-slate-400">{new Date(evt.timestamp).toLocaleString()}</span>
                </div>
                <p className="text-xs text-slate-300">{evt.details}</p>
                <span className="text-[10px] text-slate-400 block">Actor: @{evt.actor_username} ({evt.actor_role})</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action Modals */}

      {/* Modal 1: Correct Field */}
      {modalType === 'CORRECT' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Edit3 className="w-4 h-4 text-amber-400" />
              Correct Statutory Extracted Field
            </h3>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Select Field</label>
                <select
                  value={selectedField}
                  onChange={(e) => setSelectedField(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200"
                >
                  <option value="mrp">Maximum Retail Price (MRP)</option>
                  <option value="net_quantity">Net Quantity</option>
                  <option value="manufacturer">Manufacturer Name & Address</option>
                  <option value="marketed_by">Marketed By</option>
                  <option value="fssai_license">FSSAI License Number</option>
                  <option value="consumer_care">Consumer Care Details</option>
                  <option value="country_of_origin">Country of Origin</option>
                  <option value="manufacture_date">Date of Manufacture</option>
                  <option value="expiry_date">Expiry / Best Before Date</option>
                  <option value="batch_number">Batch Number</option>
                  <option value="ingredients">Ingredients List</option>
                  <option value="nutritional_info">Nutritional Information Panel</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Corrected Value</label>
                <input
                  type="text"
                  placeholder="Enter verified statutory value..."
                  value={correctedValue}
                  onChange={(e) => setCorrectedValue(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Reason for Correction</label>
                <textarea
                  placeholder="e.g., OCR misread currency symbol; verified from front panel image."
                  value={correctionReason}
                  onChange={(e) => setCorrectionReason(e.target.value)}
                  rows={2}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
              <button onClick={() => setModalType(null)} className="px-4 py-2 rounded-xl bg-slate-800 text-xs font-semibold text-slate-300">
                Cancel
              </button>
              <button
                onClick={handleCorrectFieldSubmit}
                disabled={!correctedValue.trim() || submitting}
                className="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-xs font-bold text-white"
              >
                {submitting ? 'Applying...' : 'Apply Correction & Recalculate'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 2: Accept AI Result */}
      {modalType === 'ACCEPT' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              Accept AI Outcome as Human-Verified
            </h3>

            <p className="text-xs text-slate-300 leading-relaxed">
              Confirming this audit establishes the current evaluation as the authoritative human verified outcome. The original AI result remains permanently snapshotted.
            </p>

            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">Officer Notes (Optional)</label>
              <textarea
                placeholder="Enter sign-off comments..."
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                rows={3}
                className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 resize-none"
              />
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
              <button onClick={() => setModalType(null)} className="px-4 py-2 rounded-xl bg-slate-800 text-xs font-semibold text-slate-300">
                Cancel
              </button>
              <button
                onClick={handleAcceptSubmit}
                disabled={submitting}
                className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-xs font-bold text-white"
              >
                {submitting ? 'Confirming...' : 'Sign-Off & Accept'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 3: Reject AI Result */}
      {modalType === 'REJECT' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <XCircle className="w-4 h-4 text-rose-400" />
              Reject AI Outcome
            </h3>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Rejection Reason</label>
                <select
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200"
                >
                  <option value="INCORRECT_EXTRACTION">Incorrect Information Extraction</option>
                  <option value="INSUFFICIENT_EVIDENCE">Insufficient Visual Evidence</option>
                  <option value="WRONG_RULE_EVALUATION">Incorrect Rule Evaluation</option>
                  <option value="IMAGE_QUALITY_ISSUE">Package Image Quality Issue</option>
                  <option value="OTHER">Other Enforcement Grounds</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Officer Explanation (Mandatory)</label>
                <textarea
                  placeholder="Provide detailed reasons for overturning AI outcome..."
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  rows={3}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
              <button onClick={() => setModalType(null)} className="px-4 py-2 rounded-xl bg-slate-800 text-xs font-semibold text-slate-300">
                Cancel
              </button>
              <button
                onClick={handleRejectSubmit}
                disabled={!commentText.trim() || submitting}
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-xs font-bold text-white"
              >
                {submitting ? 'Rejecting...' : 'Confirm Rejection'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 4: Assign */}
      {modalType === 'ASSIGN' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <UserCheck className="w-4 h-4 text-indigo-400" />
              Assign Review
            </h3>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Select Officer</label>
                <select
                  value={assignedOfficer}
                  onChange={(e) => setAssignedOfficer(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200"
                >
                  <option value="">-- Choose an Officer --</option>
                  {officers.map(o => (
                    <option key={o.username} value={o.username}>
                      {o.full_name || o.username} ({o.role})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Notes (Optional)</label>
                <textarea
                  placeholder="Enter instructions..."
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  rows={2}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
              <button onClick={() => setModalType(null)} className="px-4 py-2 rounded-xl bg-slate-800 text-xs font-semibold text-slate-300">
                Cancel
              </button>
              <button
                onClick={handleAssignSubmit}
                disabled={!assignedOfficer || submitting}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-bold text-white"
              >
                {submitting ? 'Assigning...' : 'Confirm Assignment'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 5: Add Missing Evidence */}
      {modalType === 'ADD_EVIDENCE' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <PlusCircle className="w-4 h-4 text-emerald-400" />
              Add Missing Evidence Annotation
            </h3>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Linked Rule ID</label>
                <input
                  type="text"
                  placeholder="e.g. LM-001, FS-001, LM-004"
                  value={missingLinkedRule}
                  onChange={(e) => setMissingLinkedRule(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Linked Declaration Field</label>
                <select
                  value={missingLinkedField}
                  onChange={(e) => setMissingLinkedField(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200"
                >
                  {Object.entries(FIELD_LABELS).map(([fKey, fLabel]) => (
                    <option key={fKey} value={fKey}>{fLabel}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Evidence Text Found</label>
                <input
                  type="text"
                  placeholder="e.g. Mfd By: XYZ Industries Ltd, 110001"
                  value={missingEvidenceText}
                  onChange={(e) => setMissingEvidenceText(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Officer Notes (Optional)</label>
                <textarea
                  placeholder="Annotation notes..."
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  rows={2}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
              <button onClick={() => setModalType(null)} className="px-4 py-2 rounded-xl bg-slate-800 text-xs font-semibold text-slate-300">
                Cancel
              </button>
              <button
                onClick={handleAddEvidenceSubmit}
                disabled={!missingEvidenceText.trim() || submitting}
                className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-xs font-bold text-white"
              >
                {submitting ? 'Saving...' : 'Add Evidence'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 6: Escalate */}
      {modalType === 'ESCALATE' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <ArrowUpRight className="w-4 h-4 text-purple-400" />
              Escalate Audit Review
            </h3>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Escalation Target</label>
                <select
                  value={escalationTarget}
                  onChange={(e) => setEscalationTarget(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200"
                >
                  <option value="ADMIN">System Administrator</option>
                  <option value="ENFORCEMENT_DIRECTOR">Enforcement Director</option>
                  <option value="LEGAL_COUNSEL">Legal Metrology Counsel</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Escalation Reason</label>
                <textarea
                  placeholder="State the statutory or technical dispute requiring escalation..."
                  value={escalationReason}
                  onChange={(e) => setEscalationReason(e.target.value)}
                  rows={3}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
              <button onClick={() => setModalType(null)} className="px-4 py-2 rounded-xl bg-slate-800 text-xs font-semibold text-slate-300">
                Cancel
              </button>
              <button
                onClick={handleEscalateSubmit}
                disabled={!escalationReason.trim() || submitting}
                className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-xs font-bold text-white"
              >
                {submitting ? 'Escalating...' : 'Confirm Escalation'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 7: Reopen */}
      {modalType === 'REOPEN' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <RotateCcw className="w-4 h-4 text-cyan-400" />
              Reopen Completed Audit
            </h3>

            <p className="text-xs text-slate-300 leading-relaxed">
              Reopening will reactivate this audit into an active review state while preserving all prior verification history.
            </p>

            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">Reason for Reopening</label>
              <textarea
                placeholder="e.g. New laboratory test report received; supplementary packaging evidence submitted."
                value={reopenReason}
                onChange={(e) => setReopenReason(e.target.value)}
                rows={3}
                className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 resize-none"
              />
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
              <button onClick={() => setModalType(null)} className="px-4 py-2 rounded-xl bg-slate-800 text-xs font-semibold text-slate-300">
                Cancel
              </button>
              <button
                onClick={handleReopenSubmit}
                disabled={!reopenReason.trim() || submitting}
                className="px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-xs font-bold text-white"
              >
                {submitting ? 'Reopening...' : 'Reopen Audit'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 8: Add Comment */}
      {modalType === 'COMMENT' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-sky-400" />
              Add Officer Comment
            </h3>

            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">Comment / Inspection Note</label>
              <textarea
                placeholder="Enter observation, test measurement, or statutory finding..."
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                rows={3}
                className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 resize-none"
              />
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
              <button onClick={() => setModalType(null)} className="px-4 py-2 rounded-xl bg-slate-800 text-xs font-semibold text-slate-300">
                Cancel
              </button>
              <button
                onClick={handleCommentSubmit}
                disabled={!commentText.trim() || submitting}
                className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-xs font-bold text-white"
              >
                {submitting ? 'Saving...' : 'Add Comment'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 9: Remove Evidence */}
      {modalType === 'REMOVE_EVIDENCE' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Trash2 className="w-4 h-4 text-rose-400" />
              Soft-Remove Incorrect Evidence
            </h3>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Evidence ID</label>
                <input
                  type="text"
                  placeholder="e.g. ev-001"
                  value={targetEvidenceId}
                  onChange={(e) => setTargetEvidenceId(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Removal Reason</label>
                <textarea
                  placeholder="State why this evidence item is incorrect or a false positive..."
                  value={removeEvidenceReason}
                  onChange={(e) => setRemoveEvidenceReason(e.target.value)}
                  rows={3}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
              <button onClick={() => setModalType(null)} className="px-4 py-2 rounded-xl bg-slate-800 text-xs font-semibold text-slate-300">
                Cancel
              </button>
              <button
                onClick={handleRemoveEvidenceSubmit}
                disabled={!targetEvidenceId.trim() || !removeEvidenceReason.trim() || submitting}
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-xs font-bold text-white"
              >
                {submitting ? 'Removing...' : 'Confirm Soft Removal'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
