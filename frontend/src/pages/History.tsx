import { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  History as HistoryIcon, 
  Search,
  Trash2, 
  Loader2,
  FileSpreadsheet,
  ScanSearch,
  ChevronUp,
  ChevronDown,
  Image as ImageIcon,
  FileText,
  Lock
} from 'lucide-react';
import { api } from '../services/api';
import { type HistoryItem } from '../types';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import StatusBadge from '../components/ui/StatusBadge';
import EmptyState from '../components/ui/EmptyState';
import LoadingSkeleton from '../components/ui/LoadingSkeleton';
import { formatAnalysisDateTime } from '../utils/datetime';

export default function History() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { t } = useLanguage();
  const isAdmin = user?.role === 'ADMIN';
  const isOfficer = user?.role === 'ENFORCEMENT_OFFICER';
  const isMerchant = user?.role === 'MERCHANT_PUBLIC';

  const canDeleteItem = (item: HistoryItem) => {
    if (isAdmin || isOfficer) return true;
    if (isMerchant) {
      if (!item.owner_user_id || !user?.username) return false;
      return item.owner_user_id.toLowerCase() === user.username.toLowerCase();
    }
    return false;
  };

  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Search, Filter, Sort state
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'COMPLIANT' | 'REVIEW_REQUIRED' | 'NON_COMPLIANT'>('ALL');
  const [sortConfig, setSortConfig] = useState<{ key: keyof HistoryItem | null, direction: 'asc' | 'desc' }>({ key: 'created_at', direction: 'desc' });

  // Deletion state
  const [itemToDelete, setItemToDelete] = useState<HistoryItem | null>(null);
  const [showClearModal, setShowClearModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const fetchHistory = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getHistory();
      setHistory(data || []);
    } catch (err: any) {
      setError(err?.message || 'Unable to load analysis history.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const exportHistoryToCSV = () => {
    if (history.length === 0) return;
    const headers = ["Inspection ID", "Product Name", "Compliance Score", "Status", "Date & Time"];
    const rows = history.map(item => [
      `"${item.id}"`,
      `"${(item.product_name || 'Unknown').replace(/"/g, '""')}"`,
      item.score,
      `"${item.status}"`,
      `"${formatAnalysisDateTime(item.created_at)}"`
    ]);
    const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `metrcheck-history-export-${new Date().toISOString().substring(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleDeleteSingle = async () => {
    if (!itemToDelete) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await api.deleteAnalysis(itemToDelete.id);
      setHistory(prev => prev.filter(item => item.id !== itemToDelete.id));
      setItemToDelete(null);
    } catch (err: any) {
      setDeleteError(err?.message || 'Failed to delete record.');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleClearAll = async () => {
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await api.clearHistory();
      setHistory([]);
      setShowClearModal(false);
    } catch (err: any) {
      setDeleteError(err?.message || 'Failed to clear history.');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleSort = (key: keyof HistoryItem) => {
    let direction: 'asc' | 'desc' = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  const filteredAndSortedHistory = useMemo(() => {
    let result = history.filter(item => {
      const q = searchQuery.toLowerCase().trim();
      if (q) {
        const matchesName = (item.product_name || '').toLowerCase().includes(q);
        const matchesId = (item.id || '').toLowerCase().includes(q);
        const matchesStatus = (item.status || '').toLowerCase().includes(q);
        if (!matchesName && !matchesId && !matchesStatus) return false;
      }

      if (statusFilter !== 'ALL') {
        const s = (item.status || '').toUpperCase();
        if (statusFilter === 'COMPLIANT' && s !== 'COMPLIANT') return false;
        if (statusFilter === 'REVIEW_REQUIRED' && !s.includes('REVIEW')) return false;
        if (statusFilter === 'NON_COMPLIANT' && !s.includes('FAIL') && !s.includes('NON_COMPLIANT') && !s.includes('POTENTIAL')) return false;
      }
      return true;
    });

    if (sortConfig.key) {
      result.sort((a, b) => {
        let aVal = a[sortConfig.key as keyof HistoryItem] ?? '';
        let bVal = b[sortConfig.key as keyof HistoryItem] ?? '';

        if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
        if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
        return 0;
      });
    }

    return result;
  }, [history, searchQuery, statusFilter, sortConfig]);

  if (loading) {
    return <div className="p-8"><LoadingSkeleton variant="page" /></div>;
  }

  if (error) {
    return (
      <div className="max-w-xl mx-auto my-12 p-8 bg-white dark:bg-slate-900 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800 text-center space-y-4">
        <p className="text-red-600 dark:text-red-400 text-sm">{error}</p>
        <button onClick={fetchHistory} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-semibold cursor-pointer">
          {t('common.retry')}
        </button>
      </div>
    );
  }

  if (history.length === 0) {
    return (
      <EmptyState 
        icon={HistoryIcon}
        title={t('dashboard.no_screenings')}
        description="Your completed package screenings will appear here."
        actionLabel={t('navigation.analyze_package')}
        onAction={() => navigate('/analyze')}
      />
    );
  }

  return (
    <div className="space-y-6 pb-12 animate-in fade-in duration-300">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">{t('navigation.screening_history')}</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Review previously screened package analyses.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {isAdmin && (
            <button
              onClick={() => setShowClearModal(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 hover:bg-red-50 hover:text-red-600 hover:border-red-300 text-slate-700 dark:text-slate-200 rounded-lg font-semibold text-xs transition-colors cursor-pointer"
            >
              <Trash2 className="w-3.5 h-3.5" />
              {t('common.delete')}
            </button>
          )}
          <button
            onClick={exportHistoryToCSV}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 rounded-lg font-semibold text-xs transition-colors cursor-pointer"
          >
            <FileSpreadsheet className="w-3.5 h-3.5" />
            {t('common.export')} CSV
          </button>
          <button
            onClick={() => navigate('/analyze')}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-semibold text-xs shadow-sm transition-colors cursor-pointer"
          >
            <ScanSearch className="w-3.5 h-3.5" />
            {t('navigation.analyze_package')}
          </button>
        </div>
      </div>

      {/* Toolbar: Search & Filter */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white dark:bg-slate-900 p-3 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="relative flex-1 max-w-sm">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input 
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={`${t('common.search')}...`}
            className="w-full pl-9 pr-3 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>
        <div className="flex items-center gap-1.5 overflow-x-auto">
          {['ALL', 'COMPLIANT', 'REVIEW_REQUIRED', 'NON_COMPLIANT'].map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status as any)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer ${
                statusFilter === status 
                  ? 'bg-indigo-600 text-white' 
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
              }`}
            >
              {status === 'ALL' ? t('common.all') : status === 'REVIEW_REQUIRED' ? t('status.needs_review') : status === 'NON_COMPLIANT' ? t('status.fail') : t('status.compliant')}
            </button>
          ))}
        </div>
      </div>

      {/* Investigation Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm border-collapse">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                <th className="py-2.5 px-4 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-700/50" onClick={() => handleSort('product_name')}>
                  <div className="flex items-center gap-1.5">
                    <span>{t('dashboard.table.product')}</span>
                    {sortConfig.key === 'product_name' && (sortConfig.direction === 'asc' ? <ChevronUp className="w-3 h-3 inline" /> : <ChevronDown className="w-3 h-3 inline" />)}
                  </div>
                </th>
                <th className="py-2.5 px-4 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-700/50" onClick={() => handleSort('score')}>
                  <div className="flex items-center gap-1.5">
                    <span>{t('dashboard.table.score')}</span>
                    {sortConfig.key === 'score' && (sortConfig.direction === 'asc' ? <ChevronUp className="w-3 h-3 inline" /> : <ChevronDown className="w-3 h-3 inline" />)}
                  </div>
                </th>
                <th className="py-2.5 px-4 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-700/50" onClick={() => handleSort('status')}>
                  <div className="flex items-center gap-1.5">
                    <span>{t('dashboard.table.status')}</span>
                    {sortConfig.key === 'status' && (sortConfig.direction === 'asc' ? <ChevronUp className="w-3 h-3 inline" /> : <ChevronDown className="w-3 h-3 inline" />)}
                  </div>
                </th>
                <th className="py-2.5 px-4 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-700/50" onClick={() => handleSort('created_at')}>
                  <div className="flex items-center gap-1.5">
                    <span>{t('dashboard.table.date')}</span>
                    {sortConfig.key === 'created_at' && (sortConfig.direction === 'asc' ? <ChevronUp className="w-3 h-3 inline" /> : <ChevronDown className="w-3 h-3 inline" />)}
                  </div>
                </th>
                <th className="py-2.5 px-4 text-right">{t('dashboard.table.action')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
              {filteredAndSortedHistory.length > 0 ? (
                filteredAndSortedHistory.map((item) => (
                  <tr 
                    key={item.id}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors group cursor-pointer"
                    onClick={() => navigate(`/results/${item.id}`)}
                  >
                    <td className="py-2.5 px-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-12 bg-slate-100 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700/80 overflow-hidden flex items-center justify-center shrink-0 shadow-2xs">
                          {item.image_url && item.image_url !== '/placeholder.png' ? (
                            <img
                              src={item.image_url}
                              alt={item.product_name || 'Product'}
                              className="w-full h-full object-contain p-0.5"
                              loading="lazy"
                              onError={(e) => {
                                const target = e.currentTarget;
                                target.style.display = 'none';
                                const fallback = target.parentElement?.querySelector('.img-fallback') as HTMLElement | null;
                                if (fallback) fallback.style.display = 'flex';
                              }}
                            />
                          ) : null}
                          <div className={`img-fallback w-full h-full items-center justify-center ${item.image_url && item.image_url !== '/placeholder.png' ? 'hidden' : 'flex'}`}>
                            {item.image_url && item.image_url !== '/placeholder.png' ? (
                              <ImageIcon className="w-4 h-4 text-slate-400 dark:text-slate-500" />
                            ) : (
                              <FileText className="w-4 h-4 text-indigo-500/70 dark:text-indigo-400/70" />
                            )}
                          </div>
                        </div>
                        <div className="min-w-0">
                          <div className="font-semibold text-slate-900 dark:text-slate-100 truncate max-w-[180px] sm:max-w-xs" title={item.product_name || 'Unknown Product'}>
                            {item.product_name || 'Unknown Product'}
                          </div>
                          <div className="text-[10px] text-slate-400 font-mono mt-0.5">{item.id.slice(0, 8)}...</div>
                        </div>
                      </div>
                    </td>
                    <td className="py-2.5 px-4">
                      <span className={`font-mono font-medium ${typeof item.score === 'number' && item.score >= 90 ? 'text-emerald-600 dark:text-emerald-400' : typeof item.score === 'number' && item.score >= 70 ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400'}`}>
                        {typeof item.score === 'number' ? item.score.toFixed(1) : item.score}
                      </span>
                    </td>
                    <td className="py-2.5 px-4">
                      <StatusBadge status={item.status} size="xs" />
                    </td>
                    <td className="py-2.5 px-4 text-xs text-slate-500 dark:text-slate-400 whitespace-nowrap">
                      {formatAnalysisDateTime(item.created_at)}
                    </td>
                    <td className="py-2.5 px-4 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={(e) => { e.stopPropagation(); navigate(`/results/${item.id}`); }}
                          className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300"
                        >
                          Open
                        </button>
                        {canDeleteItem(item) ? (
                          <button
                            onClick={(e) => { e.stopPropagation(); setDeleteError(null); setItemToDelete(item); }}
                            className="p-1 text-slate-400 hover:text-red-600 dark:hover:text-red-400 rounded transition-colors"
                            title="Delete screening record"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        ) : isMerchant ? (
                          <span 
                            className="p-1 text-slate-300 dark:text-slate-600 cursor-not-allowed inline-flex items-center" 
                            title="Deletion unavailable — ownership could not be verified."
                          >
                            <Lock className="w-3.5 h-3.5" />
                          </span>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-400 dark:text-slate-500 text-sm">
                    No results found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Delete Modal */}
      {itemToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <div className="bg-white dark:bg-slate-900 rounded-xl max-w-sm w-full p-5 space-y-4 border border-slate-200 dark:border-slate-800 shadow-2xl">
            <h3 className="font-bold text-slate-900 dark:text-slate-100 text-sm">Delete Screening Record?</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Are you sure you want to delete <span className="font-semibold text-slate-700 dark:text-slate-200">"{itemToDelete.product_name || 'this product'}"</span>? This action cannot be undone.
            </p>
            {deleteError && (
              <div className="p-2.5 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800/60 rounded-lg text-xs text-red-600 dark:text-red-400">
                {deleteError}
              </div>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <button 
                onClick={() => { setItemToDelete(null); setDeleteError(null); }} 
                disabled={isDeleting} 
                className="px-3 py-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs font-semibold rounded-lg cursor-pointer transition-colors"
              >
                Cancel
              </button>
              <button 
                onClick={handleDeleteSingle} 
                disabled={isDeleting} 
                className="px-3.5 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 cursor-pointer shadow-sm transition-colors disabled:opacity-50"
              >
                {isDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                <span>{isDeleting ? 'Deleting...' : 'Delete'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Clear All Modal */}
      {showClearModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <div className="bg-white dark:bg-slate-900 rounded-xl max-w-sm w-full p-5 space-y-4 border border-slate-200 dark:border-slate-800">
            <h3 className="font-bold text-slate-900 dark:text-slate-100">Clear All History?</h3>
            <p className="text-xs text-slate-500">This will permanently delete all records.</p>
            {deleteError && <p className="text-xs text-red-500">{deleteError}</p>}
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setShowClearModal(false)} disabled={isDeleting} className="px-3 py-1.5 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 text-xs font-semibold rounded-lg cursor-pointer">Cancel</button>
              <button onClick={handleClearAll} disabled={isDeleting} className="px-3 py-1.5 bg-red-600 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 cursor-pointer">
                {isDeleting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Clear All'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}