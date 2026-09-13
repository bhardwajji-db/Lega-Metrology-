import { useEffect, useState } from 'react';
import { ShieldCheck, Search, ChevronDown, ChevronUp } from 'lucide-react';
import { api } from '../services/api';
import { type ComplianceRule } from '../types';
import SeverityBadge from '../components/ui/SeverityBadge';
import LoadingSkeleton from '../components/ui/LoadingSkeleton';

export default function ComplianceRules() {
  const [rules, setRules] = useState<ComplianceRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [domainFilter, setDomainFilter] = useState<'ALL' | 'LEGAL_METROLOGY' | 'FSSAI'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedRule, setExpandedRule] = useState<string | null>(null);

  const fetchRules = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getComplianceRules();
      setRules(data || []);
    } catch (err: any) {
      setError(err?.message || 'Failed to load statutory rules registry.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRules();
  }, []);

  if (loading) {
    return <div className="space-y-6"><LoadingSkeleton variant="page" /></div>;
  }

  const filteredRules = rules.filter((rule: any) => {
    const ruleId = (rule.rule_id || rule.id || '').toUpperCase();
    const isFssai = ruleId.startsWith('FS-') || (rule.domain || '').toUpperCase() === 'FSSAI';
    
    if (domainFilter === 'LEGAL_METROLOGY' && isFssai) return false;
    if (domainFilter === 'FSSAI' && !isFssai) return false;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const label = (rule.field_label || rule.title || '').toLowerCase();
      const desc = (rule.description || rule.requirement || '').toLowerCase();
      const idStr = ruleId.toLowerCase();
      return label.includes(q) || desc.includes(q) || idStr.includes(q);
    }

    return true;
  });

  return (
    <div className="space-y-6 pb-12 animate-in fade-in duration-300">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 rounded-xl">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">Compliance Rules</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">Searchable statutory rules registry</p>
          </div>
        </div>
      </div>

      {error ? (
        <div className="text-red-500 text-sm">{error}</div>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search rules by ID, label, or description..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
            </div>
            <div className="flex items-center gap-1.5 p-1 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-x-auto">
              {['ALL', 'LEGAL_METROLOGY', 'FSSAI'].map((d) => (
                <button
                  key={d}
                  onClick={() => setDomainFilter(d as any)}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-lg whitespace-nowrap transition-colors cursor-pointer ${
                    domainFilter === d 
                      ? 'bg-indigo-50 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300' 
                      : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800'
                  }`}
                >
                  {d === 'ALL' ? 'All' : d === 'LEGAL_METROLOGY' ? 'Legal Metrology' : 'FSSAI'}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3">
            {filteredRules.length > 0 ? (
              filteredRules.map((rule: any) => {
                const ruleId = rule.rule_id || rule.id;
                const label = rule.field_label || rule.title || ruleId;
                const desc = rule.description || rule.requirement || '';
                const isFssai = ruleId.startsWith('FS-') || (rule.domain || '').toUpperCase() === 'FSSAI';
                const isExpanded = expandedRule === ruleId;

                return (
                  <div 
                    key={ruleId}
                    className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm hover:border-indigo-300 dark:hover:border-indigo-700/50 transition-colors"
                  >
                    <div 
                      className="p-3 sm:p-4 flex items-center justify-between cursor-pointer select-none"
                      onClick={() => setExpandedRule(isExpanded ? null : ruleId)}
                    >
                      <div className="flex flex-wrap items-center gap-3 w-full pr-4">
                        <span className="font-mono text-xs font-bold text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/50 px-2 py-0.5 rounded border border-indigo-100 dark:border-indigo-800/60 shrink-0">
                          {ruleId}
                        </span>
                        <h3 className="font-semibold text-slate-900 dark:text-slate-100 text-sm truncate max-w-[200px] sm:max-w-xs">{label}</h3>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border shrink-0 ${
                          isFssai 
                            ? 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-800 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800/60'
                            : 'bg-blue-50 dark:bg-blue-950/50 text-blue-800 dark:text-blue-400 border-blue-200 dark:border-blue-800/60'
                        }`}>
                          {isFssai ? 'FSSAI' : 'Metrology'}
                        </span>
                        <SeverityBadge severity={rule.severity} />
                        <p className="hidden md:block text-xs text-slate-500 dark:text-slate-400 truncate flex-1 ml-2">
                          {desc}
                        </p>
                      </div>
                      <div className="shrink-0 text-slate-400">
                        {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="px-4 pb-4 pt-1 border-t border-slate-100 dark:border-slate-800/60 bg-slate-50/50 dark:bg-slate-900/30">
                        <div className="mt-3 space-y-3 text-sm">
                          <div>
                            <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-1">Requirement Description</span>
                            <p className="text-slate-600 dark:text-slate-400 leading-relaxed">{desc}</p>
                          </div>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                            <div>
                              <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-1">Source Standard</span>
                              <p className="text-xs text-slate-500 font-mono bg-white dark:bg-slate-800 p-2 rounded border border-slate-200 dark:border-slate-700">
                                {rule.source || `${rule.source_name || ''} ${rule.source_reference || ''}`.trim() || 'Statutory Rule'}
                              </p>
                            </div>
                            {rule.recommendation && (
                              <div>
                                <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-1">Corrective Action</span>
                                <p className="text-xs text-slate-500 bg-white dark:bg-slate-800 p-2 rounded border border-slate-200 dark:border-slate-700">
                                  {rule.recommendation}
                                </p>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })
            ) : (
              <div className="text-center py-8 text-slate-500 text-sm border border-slate-200 dark:border-slate-800 rounded-xl">
                No rules found matching search criteria.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}