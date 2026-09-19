import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  ShieldCheck, 
  ShieldAlert,
  Clock, 
  AlertTriangle, 
  CheckCircle2, 
  Users, 
  RefreshCw, 
  Search, 
  SlidersHorizontal,
  ChevronRight,
  UserCheck
} from 'lucide-react';
import { api } from '../services/api';
import { 
  type ReviewItem, 
  type OfficerDashboardSummary, 
  type ReviewStatus 
} from '../types';
import { useAuth } from '../context/AuthContext';

export default function OfficerDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [summary, setSummary] = useState<OfficerDashboardSummary | null>(null);
  const [queue, setQueue] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [officers, setOfficers] = useState<Array<{ username: string; full_name: string; role: string }>>([]);
  const [error, setError] = useState<string | null>(null);
  const [isUnauthorized, setIsUnauthorized] = useState<boolean>(false);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [riskFilter, setRiskFilter] = useState<string>('ALL');
  const [officerFilter, setOfficerFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Quick Assignment Modal
  const [assignModalReview, setAssignModalReview] = useState<ReviewItem | null>(null);
  const [selectedOfficer, setSelectedOfficer] = useState<string>('');
  const [assignComments, setAssignComments] = useState<string>('');
  const [assigning, setAssigning] = useState<boolean>(false);

  const loadData = async () => {
    try {
      setRefreshing(true);
      setError(null);
      setIsUnauthorized(false);
      const [sumRes, qRes, offRes] = await Promise.all([
        api.getReviewDashboard(),
        api.getReviewQueue(),
        api.getAvailableOfficers()
      ]);
      setSummary(sumRes);
      setQueue(qRes);
      setOfficers(offRes.officers || []);
    } catch (err: any) {
      console.error("Failed to load officer dashboard data:", err);
      const errMsg = err?.message || '';
      if (
        errMsg.includes('403') || 
        errMsg.toLowerCase().includes('forbidden') || 
        errMsg.toLowerCase().includes('privilege') || 
        errMsg.toLowerCase().includes('unauthorized') ||
        errMsg.toLowerCase().includes('not authorized')
      ) {
        setIsUnauthorized(true);
        setError('Officer privileges are required to access the enforcement review queue.');
      } else {
        setError(errMsg || 'Failed to load officer review queue. Please verify that the backend server is active.');
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleAssignSubmit = async () => {
    if (!assignModalReview || !selectedOfficer) return;
    setAssigning(true);
    try {
      await api.assignReview(assignModalReview.review_id, selectedOfficer, assignComments);
      setAssignModalReview(null);
      setSelectedOfficer('');
      setAssignComments('');
      await loadData();
    } catch (err: any) {
      alert(err.message || 'Failed to assign review.');
    } finally {
      setAssigning(false);
    }
  };

  // Filter queue items
  const filteredQueue = useMemo(() => {
    return queue.filter(item => {
      if (statusFilter !== 'ALL') {
        if (statusFilter === 'PENDING' && item.status !== 'PENDING_REVIEW') return false;
        if (statusFilter === 'ASSIGNED' && item.status !== 'ASSIGNED') return false;
        if (statusFilter === 'IN_REVIEW' && !['IN_REVIEW', 'CORRECTION_REQUIRED'].includes(item.status)) return false;
        if (statusFilter === 'VERIFIED' && !item.status.startsWith('VERIFIED')) return false;
        if (statusFilter === 'REJECTED' && item.status !== 'REJECTED') return false;
        if (statusFilter === 'ESCALATED' && item.status !== 'ESCALATED') return false;
        if (statusFilter === 'REOPENED' && item.status !== 'REOPENED') return false;
      }
      if (riskFilter !== 'ALL' && item.ai_risk_level.toUpperCase() !== riskFilter.toUpperCase()) {
        return false;
      }
      if (officerFilter !== 'ALL') {
        if (officerFilter === 'UNASSIGNED' && item.assigned_officer) return false;
        if (officerFilter === 'MY_ASSIGNMENTS' && item.assigned_officer?.toLowerCase() !== user?.username.toLowerCase()) return false;
        if (officerFilter !== 'UNASSIGNED' && officerFilter !== 'MY_ASSIGNMENTS' && item.assigned_officer?.toLowerCase() !== officerFilter.toLowerCase()) return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          item.product_name.toLowerCase().includes(q) ||
          item.analysis_id.toLowerCase().includes(q) ||
          (item.assigned_officer && item.assigned_officer.toLowerCase().includes(q))
        );
      }
      return true;
    });
  }, [queue, statusFilter, riskFilter, officerFilter, searchQuery, user]);

  const getStatusBadge = (st: ReviewStatus) => {
    switch (st) {
      case 'PENDING_REVIEW':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">Pending Review</span>;
      case 'ASSIGNED':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">Assigned</span>;
      case 'IN_REVIEW':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">In Review</span>;
      case 'CORRECTION_REQUIRED':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-orange-500/10 text-orange-400 border border-orange-500/20">Corrections Active</span>;
      case 'VERIFIED_PASS':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Verified Pass</span>;
      case 'VERIFIED_FAIL':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-red-500/10 text-red-400 border border-red-500/20">Verified Fail</span>;
      case 'VERIFIED_NEEDS_REVIEW':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">Verified Caution</span>;
      case 'REJECTED':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">Rejected</span>;
      case 'ESCALATED':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20">Escalated</span>;
      case 'REOPENED':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">Reopened</span>;
      default:
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-slate-800 text-slate-400 border border-slate-700">{st}</span>;
    }
  };

  const getRiskBadge = (risk: string) => {
    const r = risk.toUpperCase();
    if (r === 'CRITICAL') return <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-red-500/20 text-red-400 border border-red-500/30">CRITICAL RISK</span>;
    if (r === 'HIGH') return <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">HIGH RISK</span>;
    if (r === 'MEDIUM') return <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">MEDIUM RISK</span>;
    return <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">LOW RISK</span>;
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-400">
        <div className="flex items-center gap-3">
          <RefreshCw className="w-6 h-6 animate-spin text-indigo-500" />
          <span>Loading Officer Review Dashboard...</span>
        </div>
      </div>
    );
  }

  if (isUnauthorized) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center p-4">
        <div className="p-8 rounded-2xl bg-slate-900/90 border border-amber-500/40 shadow-2xl text-center space-y-4 max-w-lg mx-auto">
          <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center mx-auto text-amber-400">
            <ShieldAlert className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold text-white">Officer Privileges Required</h2>
          <p className="text-xs text-slate-300 leading-relaxed">
            Officer privileges are required to access the enforcement review queue. You are currently logged in with a Merchant/Public account. Only verified Enforcement Officers and Administrators can inspect and override statutory packaging findings.
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
              onClick={() => navigate('/')}
              className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold rounded-xl border border-slate-700 transition-all cursor-pointer"
            >
              Back to Dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8 space-y-8">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="p-2 rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
              <ShieldCheck className="w-6 h-6" />
            </span>
            <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
              Officer Review Dashboard
            </h1>
            <span className="text-xs font-bold px-2.5 py-1 rounded-md bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
              Sec 10 Human Verification
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Authoritative human verification layer, review queue triage, statutory declaration corrections, and officer workload management.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadData}
            disabled={refreshing}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-700 hover:border-slate-600 text-sm font-medium text-slate-200 transition-all cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin text-indigo-400' : ''}`} />
            <span>Refresh Queue</span>
          </button>
        </div>
      </div>

      {error && !isUnauthorized && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => loadData()} className="underline hover:no-underline font-semibold text-red-200 cursor-pointer">
            Retry
          </button>
        </div>
      )}

      {/* KPI Metrics Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
        <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-sm flex flex-col justify-between">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Queue</span>
          <div className="text-2xl font-black text-white mt-2">{summary?.total_queue ?? 0}</div>
          <span className="text-[10px] text-slate-400 mt-1">Audits indexed</span>
        </div>

        <div className="p-4 rounded-2xl bg-amber-950/20 border border-amber-500/30 shadow-sm flex flex-col justify-between">
          <span className="text-xs font-semibold text-amber-300 uppercase tracking-wider">Pending</span>
          <div className="text-2xl font-black text-amber-400 mt-2">{summary?.pending_review ?? 0}</div>
          <span className="text-[10px] text-amber-400/70 mt-1">Awaiting triage</span>
        </div>

        <div className="p-4 rounded-2xl bg-blue-950/20 border border-blue-500/30 shadow-sm flex flex-col justify-between">
          <span className="text-xs font-semibold text-blue-300 uppercase tracking-wider">Assigned</span>
          <div className="text-2xl font-black text-blue-400 mt-2">{summary?.assigned ?? 0}</div>
          <span className="text-[10px] text-blue-400/70 mt-1">Officers allocated</span>
        </div>

        <div className="p-4 rounded-2xl bg-indigo-950/20 border border-indigo-500/30 shadow-sm flex flex-col justify-between">
          <span className="text-xs font-semibold text-indigo-300 uppercase tracking-wider">In Review</span>
          <div className="text-2xl font-black text-indigo-400 mt-2">{summary?.in_review ?? 0}</div>
          <span className="text-[10px] text-indigo-400/70 mt-1">Active verification</span>
        </div>

        <div className="p-4 rounded-2xl bg-emerald-950/20 border border-emerald-500/30 shadow-sm flex flex-col justify-between">
          <span className="text-xs font-semibold text-emerald-300 uppercase tracking-wider">Verified</span>
          <div className="text-2xl font-black text-emerald-400 mt-2">{summary?.verified ?? 0}</div>
          <span className="text-[10px] text-emerald-400/70 mt-1">Sign-off complete</span>
        </div>

        <div className="p-4 rounded-2xl bg-red-950/20 border border-red-500/30 shadow-sm flex flex-col justify-between">
          <span className="text-xs font-semibold text-red-300 uppercase tracking-wider">Rejected</span>
          <div className="text-2xl font-black text-red-400 mt-2">{summary?.rejected ?? 0}</div>
          <span className="text-[10px] text-red-400/70 mt-1">AI result overturned</span>
        </div>

        <div className="p-4 rounded-2xl bg-purple-950/20 border border-purple-500/30 shadow-sm flex flex-col justify-between">
          <span className="text-xs font-semibold text-purple-300 uppercase tracking-wider">Escalated</span>
          <div className="text-2xl font-black text-purple-400 mt-2">{summary?.escalated ?? 0}</div>
          <span className="text-[10px] text-purple-400/70 mt-1">Senior review</span>
        </div>
      </div>

      {/* Main Content Layout: Queue + Workload Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left 3 Columns: Review Queue */}
        <div className="lg:col-span-3 space-y-4">
          {/* Filters Bar */}
          <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-3">
            <div className="flex flex-col md:flex-row items-center gap-3 justify-between">
              <div className="relative flex-1 w-full">
                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search product name, analysis ID, or assigned officer..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200 placeholder-slate-400 focus:outline-hidden focus:border-indigo-500"
                />
              </div>

              <div className="flex items-center gap-2 w-full md:w-auto overflow-x-auto">
                <div className="flex items-center gap-1.5 shrink-0">
                  <SlidersHorizontal className="w-3.5 h-3.5 text-slate-400" />
                  <span className="text-xs text-slate-400 font-medium">Status:</span>
                </div>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300 focus:outline-hidden focus:border-indigo-500 cursor-pointer"
                >
                  <option value="ALL">All Statuses</option>
                  <option value="PENDING">Pending Review</option>
                  <option value="ASSIGNED">Assigned</option>
                  <option value="IN_REVIEW">In Review</option>
                  <option value="VERIFIED">Verified (Pass/Fail)</option>
                  <option value="REJECTED">Rejected</option>
                  <option value="ESCALATED">Escalated</option>
                  <option value="REOPENED">Reopened</option>
                </select>

                <select
                  value={riskFilter}
                  onChange={(e) => setRiskFilter(e.target.value)}
                  className="px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300 focus:outline-hidden focus:border-indigo-500 cursor-pointer"
                >
                  <option value="ALL">All Risk Levels</option>
                  <option value="CRITICAL">Critical Risk</option>
                  <option value="HIGH">High Risk</option>
                  <option value="MEDIUM">Medium Risk</option>
                  <option value="LOW">Low Risk</option>
                </select>

                <select
                  value={officerFilter}
                  onChange={(e) => setOfficerFilter(e.target.value)}
                  className="px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300 focus:outline-hidden focus:border-indigo-500 cursor-pointer"
                >
                  <option value="ALL">All Officers</option>
                  <option value="MY_ASSIGNMENTS">My Assigned Audits</option>
                  <option value="UNASSIGNED">Unassigned Only</option>
                  {officers.map(o => (
                    <option key={o.username} value={o.username}>{o.full_name || o.username}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Queue Items Table */}
          <div className="rounded-2xl bg-slate-900 border border-slate-800 overflow-hidden shadow-sm">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm text-white">Active Review Queue</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono">
                  {filteredQueue.length} item{filteredQueue.length === 1 ? '' : 's'}
                </span>
              </div>
              <span className="text-xs text-slate-400">
                Ordered by Deterministic Priority (Critical Risk &gt; Age)
              </span>
            </div>

            {filteredQueue.length === 0 ? (
              <div className="p-12 text-center text-slate-400 space-y-2">
                <CheckCircle2 className="w-10 h-10 text-emerald-400/40 mx-auto" />
                <p className="text-sm font-semibold text-slate-300">No review audits match your current filter</p>
                <p className="text-xs text-slate-400">All pending statutory screenings are up to date.</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-800/80">
                {filteredQueue.map(item => (
                  <div
                    key={item.review_id}
                    className="p-4 hover:bg-slate-800/40 transition-colors flex flex-col md:flex-row items-start md:items-center justify-between gap-4"
                  >
                    <div className="flex items-start gap-3.5 min-w-0 flex-1">
                      <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 shrink-0 mt-0.5">
                        <AlertTriangle className={`w-5 h-5 ${item.ai_risk_level === 'CRITICAL' ? 'text-red-400' : (item.ai_risk_level === 'HIGH' ? 'text-amber-400' : 'text-slate-400')}`} />
                      </div>

                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-bold text-sm text-white hover:text-indigo-400 transition-colors cursor-pointer" onClick={() => navigate(`/reviews/${item.review_id}`)}>
                            {item.product_name}
                          </span>
                          {getRiskBadge(item.ai_risk_level)}
                          {getStatusBadge(item.status)}
                        </div>

                        <div className="flex items-center gap-4 text-xs text-slate-400 flex-wrap">
                          <span className="font-mono text-slate-400">ID: {item.analysis_id.slice(0, 12)}</span>
                          <span>AI Score: <strong className="text-slate-200">{item.ai_score.toFixed(1)}/100</strong></span>
                          <span>Critical Violations: <strong className={item.critical_issues_count > 0 ? 'text-red-400' : 'text-slate-200'}>{item.critical_issues_count}</strong></span>
                          {item.assigned_officer ? (
                            <span className="text-indigo-300 font-medium">Assigned: @{item.assigned_officer}</span>
                          ) : (
                            <span className="text-amber-400/80 font-medium">Unassigned</span>
                          )}
                          <span className="flex items-center gap-1 text-slate-400">
                            <Clock className="w-3 h-3" />
                            {item.age_hours < 24 ? `${item.age_hours}h in queue` : `${(item.age_hours / 24).toFixed(1)}d in queue`}
                          </span>
                        </div>

                        {item.review_reasons.length > 0 && (
                          <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
                            {item.review_reasons.slice(0, 3).map((r, i) => (
                              <span key={i} className="text-[10px] px-2 py-0.5 rounded bg-slate-950 text-slate-400 border border-slate-800">
                                {r}
                              </span>
                            ))}
                            {item.review_reasons.length > 3 && (
                              <span className="text-[10px] text-slate-400">+{item.review_reasons.length - 3} more issues</span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0 self-end md:self-center">
                      <button
                        onClick={() => {
                          setAssignModalReview(item);
                          setSelectedOfficer(item.assigned_officer || '');
                        }}
                        className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors cursor-pointer"
                        title="Assign to Officer"
                      >
                        <UserCheck className="w-4 h-4" />
                      </button>

                      <button
                        onClick={() => navigate(`/reviews/${item.review_id}`)}
                        className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all shadow-xs shadow-indigo-950 cursor-pointer"
                      >
                        <span>Inspect &amp; Verify</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right 1 Column: Officer Workload Dashboard */}
        <div className="space-y-4">
          <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-4 shadow-sm">
            <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
              <Users className="w-4 h-4 text-indigo-400" />
              <h2 className="font-bold text-sm text-white">Officer Workload Allocation</h2>
            </div>

            {summary?.workload.length === 0 ? (
              <p className="text-xs text-slate-400">No active officers registered.</p>
            ) : (
              <div className="space-y-3">
                {summary?.workload.map(off => (
                  <div key={off.officer_username} className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-200">
                        {off.officer_name}
                      </span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-indigo-300">
                        {off.officer_role === 'ADMIN' ? 'Admin' : (off.officer_role === 'ENFORCEMENT_OFFICER' ? 'Enforcement' : 'Audit')}
                      </span>
                    </div>

                    <div className="grid grid-cols-4 gap-1 text-center text-[10px]">
                      <div className="p-1 rounded bg-slate-900 border border-slate-800">
                        <span className="text-slate-400 block">Total</span>
                        <span className="font-bold text-white">{off.total_assigned}</span>
                      </div>
                      <div className="p-1 rounded bg-amber-950/20 border border-amber-500/20">
                        <span className="text-amber-400/70 block">Pending</span>
                        <span className="font-bold text-amber-400">{off.pending_count}</span>
                      </div>
                      <div className="p-1 rounded bg-indigo-950/20 border border-indigo-500/20">
                        <span className="text-indigo-400/70 block">Active</span>
                        <span className="font-bold text-indigo-400">{off.in_review_count}</span>
                      </div>
                      <div className="p-1 rounded bg-emerald-950/20 border border-emerald-500/20">
                        <span className="text-emerald-400/70 block">Done</span>
                        <span className="font-bold text-emerald-400">{off.completed_count}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="p-3 rounded-xl bg-indigo-950/30 border border-indigo-500/20 text-xs text-indigo-300 space-y-1">
              <div className="font-bold flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5" />
                Statutory Human Authority
              </div>
              <p className="text-[11px] text-indigo-200/70 leading-relaxed">
                MetrCheck AI provides automated evidence extraction and rule checking. Officers hold authoritative sign-off power under Legal Metrology enforcement protocols.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Assign Modal */}
      {assignModalReview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl animate-in fade-in zoom-in duration-200">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <UserCheck className="w-4 h-4 text-indigo-400" />
                Assign Audit to Officer
              </h3>
              <button
                onClick={() => setAssignModalReview(null)}
                className="text-slate-400 hover:text-white cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <span className="text-xs text-slate-400">Target Audit</span>
                <p className="text-sm font-bold text-white">{assignModalReview.product_name}</p>
                <p className="text-[10px] font-mono text-slate-400">ID: {assignModalReview.analysis_id}</p>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Select Officer</label>
                <select
                  value={selectedOfficer}
                  onChange={(e) => setSelectedOfficer(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200 focus:outline-hidden focus:border-indigo-500"
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
                <label className="text-xs font-semibold text-slate-300 block mb-1">Assignment Instructions / Notes (Optional)</label>
                <textarea
                  value={assignComments}
                  onChange={(e) => setAssignComments(e.target.value)}
                  placeholder="e.g., Please verify net quantity and manufacturer pincode against state registry."
                  rows={3}
                  className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:outline-hidden focus:border-indigo-500 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
              <button
                onClick={() => setAssignModalReview(null)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleAssignSubmit}
                disabled={!selectedOfficer || assigning}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-bold text-white cursor-pointer"
              >
                {assigning ? 'Assigning...' : 'Confirm Assignment'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
