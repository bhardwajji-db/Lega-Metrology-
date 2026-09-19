import { useEffect, useState } from 'react';
import { ShieldCheck, Search, ChevronDown, ChevronUp, Play, FlaskConical, X, AlertTriangle, CheckCircle2, XCircle, HelpCircle } from 'lucide-react';
import { api } from '../services/api';
import { type ComplianceRule, type RuleTestResponse } from '../types';
import { useLanguage } from '../context/LanguageContext';
import SeverityBadge from '../components/ui/SeverityBadge';
import LoadingSkeleton from '../components/ui/LoadingSkeleton';

export default function ComplianceRules() {
  const { t } = useLanguage();
  const [rules, setRules] = useState<ComplianceRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [domainFilter, setDomainFilter] = useState<'ALL' | 'LEGAL_METROLOGY' | 'FSSAI'>('ALL');
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedRule, setExpandedRule] = useState<string | null>(null);

  // Simulation Modal State
  const [isTestModalOpen, setIsTestModalOpen] = useState(false);
  const [selectedTestRule, setSelectedTestRule] = useState<string>('LM-001');
  const [testOcrText, setTestOcrText] = useState('');
  const [testProductInfo, setTestProductInfo] = useState<Record<string, any>>({
    brand_name: 'Britannia',
    manufacturer: 'Britannia Industries Ltd, Bangalore, Karnataka 560001',
    mrp: 'Rs. 40.00 (incl. of all taxes)',
    net_quantity: '200 g',
    unit_sale_price: 'Rs. 0.20 / g',
    manufacturing_date: '01/2025',
    fssai_license: '10014011000123',
    country_of_origin: 'India',
    consumer_care: 'feedback@britannia.com, 1800-425-4449',
    ingredients: 'Wheat Flour, Sugar, Butter, Salt',
  });
  const [testIsFood, setTestIsFood] = useState(true);
  const [testIsImported, setTestIsImported] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [simResult, setSimResult] = useState<RuleTestResponse | null>(null);
  const [simError, setSimError] = useState<string | null>(null);

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

  const openSimModal = (ruleId?: string) => {
    if (ruleId) setSelectedTestRule(ruleId);
    setSimResult(null);
    setSimError(null);
    setIsTestModalOpen(true);
  };

  const runSimulation = async () => {
    setSimulating(true);
    setSimError(null);
    setSimResult(null);
    try {
      const resp = await api.testComplianceRule({
        rule_id: selectedTestRule,
        product_info: testProductInfo,
        ocr_text: testOcrText,
        context_override: {
          is_food: testIsFood,
          is_imported: testIsImported,
        }
      });
      setSimResult(resp);
    } catch (err: any) {
      setSimError(err?.message || 'Simulation execution failed.');
    } finally {
      setSimulating(false);
    }
  };

  if (loading) {
    return <div className="space-y-6"><LoadingSkeleton variant="page" /></div>;
  }

  const filteredRules = rules.filter((rule: any) => {
    const ruleId = (rule.rule_id || rule.id || '').toUpperCase();
    const isFssai = ruleId.startsWith('FS-') || (rule.domain || '').toUpperCase() === 'FSSAI';
    
    if (domainFilter === 'LEGAL_METROLOGY' && isFssai) return false;
    if (domainFilter === 'FSSAI' && !isFssai) return false;

    if (categoryFilter !== 'ALL') {
      const cat = (rule.category_applicability || 'ALL').toUpperCase();
      if (cat !== 'ALL' && cat !== categoryFilter) return false;
    }

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
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">{t('navigation.compliance_rules')}</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">{t('rules.registry_subtitle')}</p>
          </div>
        </div>

        <button
          onClick={() => openSimModal()}
          className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-semibold shadow-sm transition-all cursor-pointer"
        >
          <FlaskConical className="w-4 h-4" />
          <span>Simulate / Test Rule</span>
        </button>
      </div>

      {error ? (
        <div className="text-red-500 text-sm">{error}</div>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-col md:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder={t('rules.search_rules')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
              />
            </div>
            
            <div className="flex flex-wrap items-center gap-2">
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
                    {d === 'ALL' ? t('common.all') : d === 'LEGAL_METROLOGY' ? t('rules.legal_metrology') : t('rules.food_safety')}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-1 p-1 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-x-auto text-xs">
                {['ALL', 'FOOD', 'NON_FOOD', 'COSMETICS', 'MEDICAL_DEVICES', 'EXPORT'].map((c) => (
                  <button
                    key={c}
                    onClick={() => setCategoryFilter(c)}
                    className={`px-2.5 py-1 text-xs font-medium rounded-lg whitespace-nowrap transition-colors cursor-pointer ${
                      categoryFilter === c
                        ? 'bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900 font-semibold'
                        : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                    }`}
                  >
                    {c.replace('_', ' ')}
                  </button>
                ))}
              </div>
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
                      <div className="flex flex-wrap items-center gap-2.5 w-full pr-4">
                        <span className="font-mono text-xs font-bold text-indigo-700 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/50 px-2 py-0.5 rounded border border-indigo-100 dark:border-indigo-800/60 shrink-0">
                          {ruleId}
                        </span>
                        <h3 className="font-semibold text-slate-900 dark:text-slate-100 text-sm truncate max-w-[180px] sm:max-w-xs">{label}</h3>
                        
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border shrink-0 ${
                          isFssai 
                            ? 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-800 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800/60'
                            : 'bg-blue-50 dark:bg-blue-950/50 text-blue-800 dark:text-blue-400 border-blue-200 dark:border-blue-800/60'
                        }`}>
                          {isFssai ? 'FSSAI' : 'Metrology'}
                        </span>

                        {rule.rule_version && (
                          <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                            v{rule.rule_version}
                          </span>
                        )}

                        {rule.category_applicability && (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800/50">
                            {rule.category_applicability}
                          </span>
                        )}

                        <SeverityBadge severity={rule.severity} />
                        
                        <p className="hidden lg:block text-xs text-slate-500 dark:text-slate-400 truncate flex-1 ml-2">
                          {desc}
                        </p>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            openSimModal(ruleId);
                          }}
                          className="px-2.5 py-1 text-xs font-semibold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 rounded-lg border border-indigo-200 dark:border-indigo-800 flex items-center gap-1 transition-colors cursor-pointer"
                        >
                          <Play className="w-3 h-3 fill-current" />
                          <span>Simulate</span>
                        </button>
                        <div className="text-slate-400">
                          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                        </div>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="px-4 pb-4 pt-1 border-t border-slate-100 dark:border-slate-800/60 bg-slate-50/50 dark:bg-slate-900/30">
                        <div className="mt-3 space-y-3 text-sm">
                          <div>
                            <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-1">Requirement Description</span>
                            <p className="text-slate-600 dark:text-slate-400 leading-relaxed">{desc}</p>
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 pt-2">
                            <div>
                              <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-1 text-xs">Source Standard & Gazette</span>
                              <p className="text-xs text-slate-600 dark:text-slate-300 font-mono bg-white dark:bg-slate-800 p-2 rounded border border-slate-200 dark:border-slate-700">
                                {rule.source || `${rule.source_name || ''} — ${rule.source_reference || ''}`.trim() || 'Statutory Rule'}
                              </p>
                            </div>

                            <div>
                              <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-1 text-xs">Effective Dates</span>
                              <p className="text-xs text-slate-600 dark:text-slate-300 bg-white dark:bg-slate-800 p-2 rounded border border-slate-200 dark:border-slate-700">
                                From: <span className="font-mono font-medium">{rule.effective_from || '2011-11-01'}</span>
                                {rule.effective_to ? ` To: ${rule.effective_to}` : ' (Currently Active)'}
                              </p>
                            </div>

                            <div>
                              <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-1 text-xs">Evidence Fields</span>
                              <div className="flex flex-wrap gap-1 bg-white dark:bg-slate-800 p-1.5 rounded border border-slate-200 dark:border-slate-700">
                                {(rule.evidence_fields || []).map((f: string) => (
                                  <span key={f} className="text-[10px] font-mono bg-slate-100 dark:bg-slate-700 px-1.5 py-0.5 rounded text-slate-700 dark:text-slate-300">
                                    {f}
                                  </span>
                                ))}
                              </div>
                            </div>
                          </div>

                          {rule.conditions && rule.conditions.length > 0 && (
                            <div className="pt-1">
                              <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-1 text-xs">Statutory Conditions</span>
                              <ul className="list-disc list-inside text-xs text-slate-600 dark:text-slate-400 space-y-0.5 bg-white dark:bg-slate-800/60 p-2 rounded border border-slate-200 dark:border-slate-700/60">
                                {rule.conditions.map((c: string, idx: number) => (
                                  <li key={idx}>{c}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {rule.exemptions && rule.exemptions.length > 0 && (
                            <div className="pt-1">
                              <span className="font-semibold text-slate-700 dark:text-slate-300 block mb-1 text-xs">Exemptions & Provisos</span>
                              <ul className="list-disc list-inside text-xs text-slate-600 dark:text-slate-400 space-y-0.5 bg-white dark:bg-slate-800/60 p-2 rounded border border-slate-200 dark:border-slate-700/60">
                                {rule.exemptions.map((ex: string, idx: number) => (
                                  <li key={idx}>{ex}</li>
                                ))}
                              </ul>
                            </div>
                          )}
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

      {/* Rule Tester / Simulation Modal */}
      {isTestModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl flex flex-col">
            <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between sticky top-0 bg-white/95 dark:bg-slate-900/95 backdrop-blur z-10">
              <div className="flex items-center gap-2">
                <div className="p-1.5 bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 rounded-lg">
                  <FlaskConical className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-slate-900 dark:text-slate-100 text-base">Rule Simulation & Tester</h3>
                  <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">SIMULATION — DOES NOT MODIFY PRODUCTION DATA (In-Memory)</p>
                </div>
              </div>
              <button
                onClick={() => setIsTestModalOpen(false)}
                className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-4 flex-1">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Target Rule to Test</label>
                <select
                  value={selectedTestRule}
                  onChange={(e) => setSelectedTestRule(e.target.value)}
                  className="w-full px-3 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-sm font-mono text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                >
                  {rules.map((r: any) => (
                    <option key={r.rule_id || r.id} value={r.rule_id || r.id}>
                      {r.rule_id || r.id} — {r.field_label || r.title}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <label className="flex items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-300 p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={testIsFood}
                    onChange={(e) => setTestIsFood(e.target.checked)}
                    className="rounded text-indigo-600"
                  />
                  <span>Is Food Product (FSSAI Scope)</span>
                </label>

                <label className="flex items-center gap-2 text-xs font-medium text-slate-700 dark:text-slate-300 p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={testIsImported}
                    onChange={(e) => setTestIsImported(e.target.checked)}
                    className="rounded text-indigo-600"
                  />
                  <span>Is Imported Product</span>
                </label>
              </div>

              <div className="space-y-2">
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">Simulated Product Fields</label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                  {Object.entries(testProductInfo).map(([key, val]) => (
                    <div key={key} className="space-y-0.5">
                      <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 capitalize">{key.replace(/_/g, ' ')}</span>
                      <input
                        type="text"
                        value={Array.isArray(val) ? val.join(', ') : (val || '')}
                        onChange={(e) => {
                          const v = e.target.value;
                          setTestProductInfo((prev: Record<string, any>) => ({ ...prev, [key]: v }));
                        }}
                        className="w-full px-2.5 py-1.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs"
                      />
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Simulated OCR Text (Optional)</label>
                <textarea
                  rows={2}
                  value={testOcrText}
                  onChange={(e) => setTestOcrText(e.target.value)}
                  placeholder="Raw OCR text lines from packaging..."
                  className="w-full px-3 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl text-xs font-mono"
                />
              </div>

              <button
                onClick={runSimulation}
                disabled={simulating}
                className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-semibold shadow-sm flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {simulating ? (
                  <span>Evaluating In-Memory...</span>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-current" />
                    <span>Run In-Memory Simulation</span>
                  </>
                )}
              </button>

              {simError && (
                <div className="p-3 bg-red-50 dark:bg-red-950/50 border border-red-200 dark:border-red-800 rounded-xl text-xs text-red-600 dark:text-red-400">
                  {simError}
                </div>
              )}

              {simResult && (
                <div className="p-4 bg-slate-50 dark:bg-slate-800/70 border border-slate-200 dark:border-slate-700 rounded-xl space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {simResult.status === 'PASS' && <CheckCircle2 className="w-5 h-5 text-emerald-500" />}
                      {simResult.status === 'FAIL' && <XCircle className="w-5 h-5 text-red-500" />}
                      {(simResult.status === 'NEEDS_REVIEW' || simResult.status === 'WARNING' || simResult.status === 'INSUFFICIENT_EVIDENCE') && <AlertTriangle className="w-5 h-5 text-amber-500" />}
                      {simResult.status === 'NOT_APPLICABLE' && <HelpCircle className="w-5 h-5 text-blue-500" />}
                      <span className="font-bold text-sm text-slate-800 dark:text-slate-100">
                        Result: {simResult.status}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono bg-indigo-100 dark:bg-indigo-900/60 text-indigo-700 dark:text-indigo-300 px-2 py-0.5 rounded">
                      {simResult.execution_trace?.execution_ms}ms
                    </span>
                  </div>

                  <div className="text-xs space-y-1">
                    <p className="text-slate-700 dark:text-slate-300 font-medium">
                      {simResult.pass_reason || simResult.fail_reason || simResult.review_reason || simResult.reason}
                    </p>
                    {simResult.detected_value && (
                      <p className="text-slate-500 dark:text-slate-400">
                        Detected Value: <span className="font-mono text-slate-700 dark:text-slate-200 font-semibold">{simResult.detected_value}</span>
                      </p>
                    )}
                  </div>

                  {simResult.execution_trace && (
                    <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg text-[11px] font-mono space-y-1">
                      <div className="font-bold text-slate-600 dark:text-slate-400 mb-1 font-sans">Execution Trace</div>
                      <p>Rule Version: {simResult.execution_trace.rule_version} | Category: {simResult.execution_trace.category}</p>
                      <p>Effective From: {simResult.execution_trace.effective_from}</p>
                      <p>Prerequisites Met: {String(simResult.execution_trace.prerequisites_met)}</p>
                      {simResult.execution_trace.exemption_applied && (
                        <p className="text-blue-600 dark:text-blue-400">Exemption: {simResult.execution_trace.exemption_applied}</p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}