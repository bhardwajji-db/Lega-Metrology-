import { useState, useEffect } from 'react';
import { 
  GitCompare, 
  ArrowRight, 
  CheckCircle2, 
  AlertTriangle, 
  TrendingUp, 
  TrendingDown, 
  Clock, 
  FileText, 
  DollarSign, 
  Scale, 
  Building2, 
  Award, 
  Utensils, 
  Activity, 
  RefreshCw, 
  Minus,
  Sparkles
} from 'lucide-react';
import { api } from '../services/api';
import { 
  type VersionComparisonResult, 
  type VersionTimelineEvent
} from '../types';

export default function VersionComparison() {
  const [targets, setTargets] = useState<any[]>([]);
  const [selectedVersionA, setSelectedVersionA] = useState<string>('');
  const [selectedVersionB, setSelectedVersionB] = useState<string>('');
  const [comparison, setComparison] = useState<VersionComparisonResult | null>(null);
  const [timeline, setTimeline] = useState<VersionTimelineEvent[]>([]);
  const [loadingTargets, setLoadingTargets] = useState<boolean>(true);
  const [comparing, setComparing] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'ALL' | 'ADDED' | 'REMOVED' | 'CHANGED' | 'UNCHANGED'>('ALL');
  const [error, setError] = useState<string | null>(null);

  // Load available version targets on mount
  useEffect(() => {
    const fetchTargets = async () => {
      setLoadingTargets(true);
      try {
        const resp = await api.getVersionTargets();
        const items = resp.targets || [];
        setTargets(items);
        if (items.length >= 2) {
          // Default to latest two versions
          setSelectedVersionA(items[1].version_id);
          setSelectedVersionB(items[0].version_id);
        } else if (items.length === 1) {
          setSelectedVersionA(items[0].version_id);
          setSelectedVersionB(items[0].version_id);
        }
      } catch (err: any) {
        setError(err?.message || 'Failed to load comparable versions.');
      } finally {
        setLoadingTargets(false);
      }
    };
    fetchTargets();
  }, []);

  // Run comparison when both versions are selected
  const handleCompare = async (idA?: string, idB?: string) => {
    const verA = idA || selectedVersionA;
    const verB = idB || selectedVersionB;
    if (!verA || !verB) return;

    setComparing(true);
    setError(null);
    try {
      const targetA = targets.find((t) => t.version_id === verA);
      const targetB = targets.find((t) => t.version_id === verB);

      const result = await api.compareVersions({
        version_a_id: verA,
        version_b_id: verB,
        version_type_a: targetA?.version_type || 'ANALYSIS',
        version_type_b: targetB?.version_type || 'ANALYSIS',
      });
      setComparison(result);

      // Fetch timeline for target product
      const timelineEntity = result.version_b.product_name || result.version_b.version_id;
      if (timelineEntity) {
        const tlResp = await api.getVersionTimeline(timelineEntity);
        setTimeline(tlResp.events || []);
      }
    } catch (err: any) {
      setError(err?.message || 'Comparison failed. Please verify that both version records exist.');
    } finally {
      setComparing(false);
    }
  };

  const filteredDiffs = (comparison?.declaration_diffs || []).filter((d) => {
    if (activeTab === 'ALL') return true;
    return d.change_type === activeTab;
  });

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16">
      {/* ── Header ── */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-slate-900/90 border border-slate-800 p-6 rounded-2xl shadow-xl backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-amber-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-950/40">
            <GitCompare className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-black text-white tracking-tight">Version Comparison Studio</h1>
              <span className="px-2 py-0.5 rounded-md text-[10px] font-extrabold uppercase bg-amber-500/20 text-amber-300 border border-amber-500/30">
                Section 9
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Compare packaging revisions, pre-print artwork iterations, and physical package screenings side-by-side.
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-rose-400 hover:text-white text-xs underline cursor-pointer">
            Dismiss
          </button>
        </div>
      )}

      {/* ── Version Selectors Bar ── */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-lg space-y-4">
        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">Select Versions to Compare</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
          {/* Version A Dropdown */}
          <div className="md:col-span-5 space-y-1.5">
            <label className="block text-xs font-bold text-slate-300">
              Version A (Base / Previous)
            </label>
            <select
              value={selectedVersionA}
              onChange={(e) => setSelectedVersionA(e.target.value)}
              disabled={loadingTargets}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-white text-xs font-medium focus:border-indigo-500 focus:outline-none cursor-pointer disabled:opacity-50"
            >
              <option value="">-- Select Version A --</option>
              {targets.map((t) => (
                <option key={`a-${t.version_id}`} value={t.version_id}>
                  {t.version_label} ({t.score}/100 - {t.risk_level})
                </option>
              ))}
            </select>
          </div>

          {/* Comparison Arrow Icon */}
          <div className="md:col-span-2 flex justify-center py-2 md:py-0">
            <div className="w-10 h-10 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300">
              <ArrowRight className="w-4 h-4" />
            </div>
          </div>

          {/* Version B Dropdown */}
          <div className="md:col-span-5 space-y-1.5">
            <label className="block text-xs font-bold text-slate-300">
              Version B (Target / Revised)
            </label>
            <select
              value={selectedVersionB}
              onChange={(e) => setSelectedVersionB(e.target.value)}
              disabled={loadingTargets}
              className="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-white text-xs font-medium focus:border-indigo-500 focus:outline-none cursor-pointer disabled:opacity-50"
            >
              <option value="">-- Select Version B --</option>
              {targets.map((t) => (
                <option key={`b-${t.version_id}`} value={t.version_id}>
                  {t.version_label} ({t.score}/100 - {t.risk_level})
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            onClick={() => handleCompare()}
            disabled={comparing || !selectedVersionA || !selectedVersionB}
            className="px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-bold text-xs shadow-md shadow-indigo-950/40 transition-all cursor-pointer flex items-center gap-2 disabled:opacity-50"
          >
            {comparing ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <GitCompare className="w-4 h-4" />
            )}
            <span>Run Version Comparison</span>
          </button>
        </div>
      </div>

      {/* ── Comparison Results Section ── */}
      {comparison ? (
        <div className="space-y-6">
          {/* Executive Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            
            {/* Score Delta Card */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 space-y-2">
              <div className="flex items-center justify-between text-xs font-bold text-slate-400 uppercase">
                <span>Compliance Score</span>
                {comparison.score_delta > 0 ? (
                  <TrendingUp className="w-4 h-4 text-emerald-400" />
                ) : comparison.score_delta < 0 ? (
                  <TrendingDown className="w-4 h-4 text-rose-400" />
                ) : (
                  <Minus className="w-4 h-4 text-slate-400" />
                )}
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-black text-white">{comparison.score_b}</span>
                <span className="text-xs text-slate-400 font-mono">from {comparison.score_a}</span>
                <span className={`text-xs font-extrabold px-1.5 py-0.5 rounded ${
                  comparison.score_delta > 0
                    ? 'bg-emerald-500/20 text-emerald-300'
                    : comparison.score_delta < 0
                    ? 'bg-rose-500/20 text-rose-300'
                    : 'bg-slate-800 text-slate-300'
                }`}>
                  {comparison.score_delta > 0 ? `+${comparison.score_delta}` : comparison.score_delta} pts
                </span>
              </div>
            </div>

            {/* Risk Tier Migration */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 space-y-2">
              <div className="flex items-center justify-between text-xs font-bold text-slate-400 uppercase">
                <span>Risk Level Shift</span>
                <Activity className="w-4 h-4 text-sky-400" />
              </div>
              <div className="flex items-center gap-2 text-sm font-black">
                <span className="text-slate-400">{comparison.risk_level_a}</span>
                <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
                <span className={
                  comparison.risk_level_b === 'LOW'
                    ? 'text-emerald-400'
                    : comparison.risk_level_b === 'CRITICAL'
                    ? 'text-rose-400'
                    : 'text-amber-400'
                }>
                  {comparison.risk_level_b}
                </span>
                <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 ml-auto">
                  {comparison.risk_shift}
                </span>
              </div>
            </div>

            {/* Issue Resolution Count */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 space-y-2">
              <div className="flex items-center justify-between text-xs font-bold text-slate-400 uppercase">
                <span>Issues Resolved</span>
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-black text-emerald-400">{comparison.resolved_issues_count}</span>
                <span className="text-xs text-slate-400">resolved</span>
                {comparison.new_issues_count > 0 && (
                  <span className="text-xs font-bold text-rose-400 font-mono">
                    (+{comparison.new_issues_count} new)
                  </span>
                )}
              </div>
            </div>

            {/* Missing Declarations Delta */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 space-y-2">
              <div className="flex items-center justify-between text-xs font-bold text-slate-400 uppercase">
                <span>Missing Declarations</span>
                <FileText className="w-4 h-4 text-amber-400" />
              </div>
              <div className="flex items-baseline gap-2 text-sm font-black">
                <span className="text-slate-400">{comparison.missing_declarations_a} in A</span>
                <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
                <span className={comparison.missing_declarations_b === 0 ? 'text-emerald-400' : 'text-amber-400'}>
                  {comparison.missing_declarations_b} in B
                </span>
              </div>
            </div>

          </div>

          {/* Verdict Banner */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 flex items-center gap-3">
            <Sparkles className="w-5 h-5 text-indigo-400 shrink-0" />
            <p className="text-xs text-slate-200 font-semibold">{comparison.summary_verdict}</p>
          </div>

          {/* ── Specialized Field Comparison Cards Grid ── */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            
            {/* 1. MRP Comparison Card */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <DollarSign className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-sm font-bold text-white">MRP Price Shift</h3>
                </div>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                  comparison.mrp_diff?.change_type === 'UNCHANGED'
                    ? 'bg-slate-800 text-slate-300'
                    : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                }`}>
                  {comparison.mrp_diff?.change_type || 'NOT_DECLARED'}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-3 bg-slate-950 p-3 rounded-xl border border-slate-800 text-xs">
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase font-bold">Version A MRP</span>
                  <span className="font-bold text-slate-300">{comparison.mrp_diff?.old_value || 'Not Declared'}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase font-bold">Version B MRP</span>
                  <span className="font-bold text-white">{comparison.mrp_diff?.new_value || 'Not Declared'}</span>
                </div>
              </div>
              <p className="text-xs text-slate-300 italic">{comparison.mrp_diff?.explanation}</p>
            </div>

            {/* 2. Net Quantity Comparison Card */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Scale className="w-4 h-4 text-sky-400" />
                  <h3 className="text-sm font-bold text-white">Net Quantity Shift</h3>
                </div>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                  comparison.quantity_diff?.change_type === 'UNCHANGED'
                    ? 'bg-slate-800 text-slate-300'
                    : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                }`}>
                  {comparison.quantity_diff?.change_type || 'NOT_DECLARED'}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-3 bg-slate-950 p-3 rounded-xl border border-slate-800 text-xs">
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase font-bold">Version A Quantity</span>
                  <span className="font-bold text-slate-300">{comparison.quantity_diff?.old_value || 'Not Declared'}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase font-bold">Version B Quantity</span>
                  <span className="font-bold text-white">{comparison.quantity_diff?.new_value || 'Not Declared'}</span>
                </div>
              </div>
              <p className="text-xs text-slate-300 italic">{comparison.quantity_diff?.explanation}</p>
            </div>

            {/* 3. Manufacturer & Importer Entity Card */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-indigo-400" />
                  <h3 className="text-sm font-bold text-white">Manufacturer & Packer Entity</h3>
                </div>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                  comparison.manufacturer_diff?.change_type === 'UNCHANGED'
                    ? 'bg-slate-800 text-slate-300'
                    : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                }`}>
                  {comparison.manufacturer_diff?.change_type || 'NOT_DECLARED'}
                </span>
              </div>
              <div className="space-y-2 bg-slate-950 p-3 rounded-xl border border-slate-800 text-xs">
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase font-bold">Version A</span>
                  <span className="text-slate-300">{comparison.manufacturer_diff?.old_value || 'Not Declared'}</span>
                </div>
                <div className="pt-1 border-t border-slate-800">
                  <span className="text-slate-500 block text-[10px] uppercase font-bold">Version B</span>
                  <span className="text-white font-medium">{comparison.manufacturer_diff?.new_value || 'Not Declared'}</span>
                </div>
              </div>
            </div>

            {/* 4. FSSAI License Number Card */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Award className="w-4 h-4 text-amber-400" />
                  <h3 className="text-sm font-bold text-white">FSSAI 14-Digit License</h3>
                </div>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                  comparison.fssai_diff?.change_type === 'UNCHANGED'
                    ? 'bg-slate-800 text-slate-300'
                    : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                }`}>
                  {comparison.fssai_diff?.change_type || 'NOT_DECLARED'}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-3 bg-slate-950 p-3 rounded-xl border border-slate-800 text-xs">
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase font-bold">Version A License</span>
                  <span className="font-mono text-slate-300">{comparison.fssai_diff?.old_value || 'None'}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase font-bold">Version B License</span>
                  <span className="font-mono text-white font-bold">{comparison.fssai_diff?.new_value || 'None'}</span>
                </div>
              </div>
              <p className="text-xs text-slate-300 italic">{comparison.fssai_diff?.explanation}</p>
            </div>

          </div>

          {/* ── Ingredients Set Diff & Nutrition Facts Table Diff ── */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            
            {/* Ingredients Diff */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Utensils className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-sm font-bold text-white">Ingredients Composition Diff</h3>
                </div>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                  {comparison.ingredients_diff?.status}
                </span>
              </div>

              <p className="text-xs text-slate-400">
                {comparison.ingredients_diff?.raw_diff_summary || 'No ingredients changes detected.'}
              </p>

              <div className="space-y-1.5 max-h-[220px] overflow-y-auto pr-1 custom-scrollbar">
                {comparison.ingredients_diff?.items.map((item, idx) => (
                  <div
                    key={idx}
                    className={`flex items-center justify-between p-2 rounded-lg text-xs ${
                      item.status === 'ADDED'
                        ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20'
                        : item.status === 'REMOVED'
                        ? 'bg-rose-500/10 text-rose-300 border border-rose-500/20'
                        : 'bg-slate-950 text-slate-300 border border-slate-800'
                    }`}
                  >
                    <span>{item.name}</span>
                    <span className="text-[9px] font-bold uppercase font-mono">{item.status}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Nutrition Facts Table Diff */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-indigo-400" />
                  <h3 className="text-sm font-bold text-white">Nutrition Values Comparison</h3>
                </div>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                  {comparison.nutrition_diff?.status}
                </span>
              </div>

              <div className="space-y-1.5 max-h-[260px] overflow-y-auto pr-1 custom-scrollbar">
                {comparison.nutrition_diff?.nutrients && comparison.nutrition_diff.nutrients.length > 0 ? (
                  comparison.nutrition_diff.nutrients.map((nutr, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-2 rounded-lg bg-slate-950 border border-slate-800 text-xs"
                    >
                      <span className="font-semibold text-slate-300">{nutr.nutrient_name}</span>
                      <div className="flex items-center gap-2 text-xs font-mono">
                        <span className="text-slate-400">{nutr.old_value || '-'}</span>
                        <ArrowRight className="w-3 h-3 text-slate-600" />
                        <span className="text-white font-bold">{nutr.new_value || '-'}</span>
                        {nutr.amount_delta !== null && nutr.amount_delta !== undefined && (
                          <span className={`text-[10px] px-1 py-0.2 rounded font-bold ${
                            nutr.amount_delta > 0
                              ? 'bg-emerald-500/20 text-emerald-300'
                              : nutr.amount_delta < 0
                              ? 'bg-rose-500/20 text-rose-300'
                              : 'bg-slate-800 text-slate-400'
                          }`}>
                            {nutr.amount_delta > 0 ? `+${nutr.amount_delta}` : nutr.amount_delta}
                          </span>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-6 text-slate-500 text-xs">
                    No nutrient table values detected.
                  </div>
                )}
              </div>
            </div>

          </div>

          {/* ── Declaration Changes Grid ── */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <h3 className="text-sm font-bold text-white">Full Statutory Declaration Diff</h3>
              
              {/* Filter Tabs */}
              <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
                {(['ALL', 'ADDED', 'REMOVED', 'CHANGED', 'UNCHANGED'] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`px-3 py-1 rounded-lg font-bold text-[11px] transition-all cursor-pointer ${
                      activeTab === tab
                        ? 'bg-indigo-600 text-white shadow'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    {tab}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {filteredDiffs.map((diff, idx) => (
                <div
                  key={idx}
                  className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-1.5 text-xs"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-white">{diff.field_label}</span>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                      diff.change_type === 'ADDED'
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        : diff.change_type === 'REMOVED'
                        ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                        : diff.change_type === 'CHANGED'
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                        : 'bg-slate-800 text-slate-400'
                    }`}>
                      {diff.change_type}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">{diff.explanation}</p>
                  {(diff.old_value || diff.new_value) && (
                    <div className="text-[11px] pt-1 border-t border-slate-800/80 flex items-center justify-between text-slate-400 font-mono">
                      <span className="truncate max-w-[180px]">A: {diff.old_value || 'None'}</span>
                      <span className="truncate max-w-[180px] text-white font-medium">B: {diff.new_value || 'None'}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* ── Rule Transitions & Issue-Resolution Matrix ── */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            
            {/* Rule State Transitions */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
              <h3 className="text-sm font-bold text-white">Statutory Rule Transitions</h3>
              <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1 custom-scrollbar">
                {comparison.rule_diffs.map((rd) => (
                  <div
                    key={rd.rule_id}
                    className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs"
                  >
                    <div>
                      <span className="font-bold text-white">{rd.rule_id}: {rd.rule_name}</span>
                      <span className="text-[10px] text-slate-500 block">{rd.explanation}</span>
                    </div>
                    <div className="flex items-center gap-1.5 font-mono text-xs">
                      <span className="text-slate-400">{rd.old_status}</span>
                      <ArrowRight className="w-3 h-3 text-slate-600" />
                      <span className={`font-bold ${
                        rd.new_status === 'PASS' ? 'text-emerald-400' : 'text-rose-400'
                      }`}>
                        {rd.new_status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Issue Resolution Tracking */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
              <h3 className="text-sm font-bold text-white">Issue Resolution Matrix</h3>
              <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1 custom-scrollbar">
                {comparison.issue_resolutions && comparison.issue_resolutions.length > 0 ? (
                  comparison.issue_resolutions.map((iss) => (
                    <div
                      key={iss.issue_id}
                      className={`p-2.5 rounded-xl border text-xs space-y-1 ${
                        iss.resolution_status === 'RESOLVED'
                          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                          : iss.resolution_status === 'NEW_ISSUE'
                          ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                          : 'bg-slate-950 border-slate-800 text-slate-300'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold">{iss.rule_id || iss.field || 'Violation'}</span>
                        <span className="text-[9px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700">
                          {iss.resolution_status}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-300">{iss.explanation}</p>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-slate-500 text-xs">
                    No compliance violations detected between these versions.
                  </div>
                )}
              </div>
            </div>

          </div>

          {/* ── Version Timeline ── */}
          {timeline.length > 0 && (
            <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-4">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-indigo-400" />
                <h3 className="text-sm font-bold text-white">Audit Version Timeline</h3>
              </div>

              <div className="relative border-l-2 border-slate-800 ml-3 pl-4 space-y-4">
                {timeline.map((evt, idx) => (
                  <div key={idx} className="relative group">
                    <div className="absolute -left-[23px] top-1 w-3.5 h-3.5 rounded-full bg-indigo-600 border-2 border-slate-900 group-hover:scale-125 transition-transform" />
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-white">{evt.title}</span>
                      <span className="text-[10px] text-slate-500 font-mono">
                        {evt.timestamp ? new Date(evt.timestamp).toLocaleString() : ''}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">{evt.description}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      ) : comparing ? (
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-12 text-center space-y-3">
          <RefreshCw className="w-8 h-8 text-indigo-400 animate-spin mx-auto" />
          <p className="text-sm text-slate-300 font-semibold">Running deterministic version comparison...</p>
        </div>
      ) : (
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-16 text-center space-y-4">
          <GitCompare className="w-12 h-12 text-slate-600 mx-auto" />
          <h2 className="text-base font-bold text-slate-300">Select Version A and Version B to Compare</h2>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Choose two packaging screenings or artwork iterations from the dropdowns above to analyze differences, score deltas, and issue resolutions.
          </p>
        </div>
      )}

    </div>
  );
}
