import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  FileCheck, 
  CheckCircle2, 
  AlertTriangle, 
  ScanSearch, 
  ArrowRight, 
  ShieldCheck, 
  Cpu, 
  FileText, 
  Search, 
  History, 
  BookOpen, 
  XCircle,
  Info
} from 'lucide-react';

import { type DashboardStats } from '../types';
import { api } from '../services/api';
import StatusBadge from '../components/ui/StatusBadge';
import LoadingSkeleton from '../components/ui/LoadingSkeleton';
import EmptyState from '../components/ui/EmptyState';
import { formatAnalysisDateTime } from '../utils/datetime';
import { useAuth } from '../context/AuthContext';
import { useWorkspace } from '../context/WorkspaceContext';

export default function Dashboard() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { workspaceInfo } = useWorkspace();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const data = await api.getDashboardStats();
        setStats(data);
      } catch (err) {
        setError('Failed to load dashboard statistics. Please ensure the backend server is active.');
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <LoadingSkeleton variant="page" />
      </div>
    );
  }

  const dashboardData: DashboardStats = stats || {
    total_analyzed: 0,
    compliant: 0,
    needs_review: 0,
    failures: 0,
    violations: 0,
    average_score: 0,
    recent: []
  };

  const packagesScreened = dashboardData.packages_screened ?? dashboardData.total_analyzed;
  const compliantPackages = dashboardData.compliant_packages ?? dashboardData.compliant;
  const reviewFindings = dashboardData.review_findings ?? dashboardData.needs_review ?? 0;
  const failedFindings = dashboardData.failed_findings ?? dashboardData.failures ?? 0;
  const nonCompliantPackages = Math.max(0, packagesScreened - compliantPackages);

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 18) return 'Good afternoon';
    return 'Good evening';
  };

  const userName = user?.full_name || user?.username || 'User';

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {error && (
        <div className="p-4 rounded-xl bg-red-50/90 dark:bg-red-950/60 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button 
            onClick={() => window.location.reload()} 
            className="text-xs font-semibold text-red-800 dark:text-red-200 underline hover:no-underline cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {/* Header: Greeting & Quick Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
              {getGreeting()}, {userName}
            </h1>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 font-mono uppercase tracking-wider">
              {workspaceInfo.label}
            </span>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Your compliance overview
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => navigate('/analyze')}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold transition-colors cursor-pointer shadow-sm"
          >
            <ScanSearch className="w-3.5 h-3.5" />
            Analyze Package
          </button>
          <button
            onClick={() => navigate('/history')}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/80 text-slate-700 dark:text-slate-200 rounded-lg text-xs font-semibold transition-colors cursor-pointer shadow-sm"
          >
            <History className="w-3.5 h-3.5" />
            Screening History
          </button>
          <button
            onClick={() => navigate('/rules')}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/80 text-slate-700 dark:text-slate-200 rounded-lg text-xs font-semibold transition-colors cursor-pointer shadow-sm"
          >
            <BookOpen className="w-3.5 h-3.5" />
            Compliance Rules
          </button>
        </div>
      </div>

      {/* Compact KPI Row */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm p-4">
        <div className="flex flex-wrap divide-y sm:divide-y-0 sm:divide-x divide-slate-100 dark:divide-slate-800">
          <div className="flex-1 min-w-[150px] p-2 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400">
              <FileCheck className="w-5 h-5" />
            </div>
            <div>
              <p className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Packages Screened</p>
              <p className="text-xl font-bold text-slate-900 dark:text-slate-100">{packagesScreened}</p>
            </div>
          </div>
          <div className="flex-1 min-w-[150px] p-2 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <div>
              <p className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Compliant Packages</p>
              <p className="text-xl font-bold text-slate-900 dark:text-slate-100">{compliantPackages}</p>
            </div>
          </div>
          <div className="flex-1 min-w-[150px] p-2 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-amber-50 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <p className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Review Findings</p>
              <p className="text-xl font-bold text-slate-900 dark:text-slate-100">{reviewFindings}</p>
            </div>
          </div>
          <div className="flex-1 min-w-[150px] p-2 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-red-50 dark:bg-red-950/50 text-red-600 dark:text-red-400">
              <XCircle className="w-5 h-5" />
            </div>
            <div>
              <p className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Failed Findings</p>
              <p className="text-xl font-bold text-slate-900 dark:text-slate-100">
                {failedFindings}
              </p>
            </div>
          </div>
        </div>
        <div className="mt-2.5 pt-2.5 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-400 dark:text-slate-500 flex items-center gap-1.5 px-1">
          <Info className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500 shrink-0" />
          <span>Finding counts represent individual compliance requirements; package status represents the overall screening verdict.</span>
        </div>
      </div>

      {/* Action Required Callout */}
      {(nonCompliantPackages > 0 || failedFindings > 0 || reviewFindings > 0) && (
        <div className={`border rounded-xl p-4 flex items-center justify-between gap-4 ${
          failedFindings > 0 
            ? 'bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-800/60' 
            : 'bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800/60'
        }`}>
          <div className="flex items-center gap-3">
            {failedFindings > 0 ? (
              <XCircle className="w-5 h-5 text-red-600 dark:text-red-500 shrink-0" />
            ) : (
              <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-500 shrink-0" />
            )}
            <p className={`text-sm font-medium ${failedFindings > 0 ? 'text-red-900 dark:text-red-200' : 'text-amber-900 dark:text-amber-200'}`}>
              <span className="font-bold">{nonCompliantPackages} {nonCompliantPackages === 1 ? 'package requires' : 'packages require'}</span> manual verification or {nonCompliantPackages === 1 ? 'has' : 'have'} identified discrepancies.
            </p>
          </div>
          <button
            onClick={() => navigate('/history')}
            className={`shrink-0 px-3 py-1.5 text-white text-xs font-semibold rounded-lg transition-colors cursor-pointer shadow-sm ${
              failedFindings > 0 ? 'bg-red-600 hover:bg-red-700' : 'bg-amber-600 hover:bg-amber-700'
            }`}
          >
            Review Findings
          </button>
        </div>
      )}

      {/* Compact Horizontal Stepper */}
      <div className="bg-slate-50/50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-xl p-3 flex flex-wrap items-center justify-between gap-2 text-xs font-medium text-slate-600 dark:text-slate-400 overflow-x-auto">
        <div className="flex items-center gap-1.5 shrink-0"><ScanSearch className="w-3.5 h-3.5 text-indigo-500" /> Capture</div>
        <ArrowRight className="w-3 h-3 text-slate-300 dark:text-slate-600 shrink-0" />
        <div className="flex items-center gap-1.5 shrink-0"><Cpu className="w-3.5 h-3.5 text-indigo-500" /> Extract</div>
        <ArrowRight className="w-3 h-3 text-slate-300 dark:text-slate-600 shrink-0" />
        <div className="flex items-center gap-1.5 shrink-0"><ShieldCheck className="w-3.5 h-3.5 text-indigo-500" /> Screen</div>
        <ArrowRight className="w-3 h-3 text-slate-300 dark:text-slate-600 shrink-0" />
        <div className="flex items-center gap-1.5 shrink-0"><Search className="w-3.5 h-3.5 text-indigo-500" /> Verify</div>
        <ArrowRight className="w-3 h-3 text-slate-300 dark:text-slate-600 shrink-0" />
        <div className="flex items-center gap-1.5 shrink-0"><FileText className="w-3.5 h-3.5 text-indigo-500" /> Report</div>
      </div>

      {/* Recent Screenings Compact Table */}
      <div className="space-y-3">
        <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 tracking-tight">Recent Screenings</h3>
        
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm">
          {dashboardData.recent.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm border-collapse">
                <thead>
                  <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    <th className="py-2.5 px-4 font-semibold">Product</th>
                    <th className="py-2.5 px-4 font-semibold">Score</th>
                    <th className="py-2.5 px-4 font-semibold">Status</th>
                    <th className="py-2.5 px-4 font-semibold">Date</th>
                    <th className="py-2.5 px-4 text-right font-semibold">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                  {dashboardData.recent.slice(0, 5).map((item) => (
                    <tr 
                      key={item.id} 
                      className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors group"
                    >
                      <td className="py-2 px-4">
                        <div className="font-semibold text-slate-900 dark:text-slate-100 truncate max-w-[200px] sm:max-w-xs">
                          {item.product_name || 'Unknown Product'}
                        </div>
                      </td>
                      <td className="py-2 px-4">
                        <span className={`font-mono font-medium ${typeof item.score === 'number' && item.score >= 90 ? 'text-emerald-600 dark:text-emerald-400' : typeof item.score === 'number' && item.score >= 70 ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400'}`}>
                          {typeof item.score === 'number' ? item.score.toFixed(1) : item.score}
                        </span>
                      </td>
                      <td className="py-2 px-4">
                        <StatusBadge status={item.status} size="xs" />
                      </td>
                      <td className="py-2 px-4 text-xs text-slate-500 dark:text-slate-400 whitespace-nowrap">
                        {formatAnalysisDateTime(item.created_at)}
                      </td>
                      <td className="py-2 px-4 text-right">
                        <button
                          onClick={() => navigate(`/results/${item.id}`)}
                          className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 cursor-pointer"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-8">
              <EmptyState 
                icon={ScanSearch}
                title="No Screenings Yet"
                description="Start by analyzing a package artwork."
                actionLabel="Analyze Package"
                onAction={() => navigate('/analyze')}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
