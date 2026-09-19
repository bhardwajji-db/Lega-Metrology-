import { useState, useEffect, useCallback } from 'react';
import { 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  Loader2, 
  Server, 
  X, 
  RefreshCw, 
  Database, 
  Cpu, 
  Globe, 
  RotateCcw
} from 'lucide-react';
import { 
  getApiHost, 
  setApiHost, 
  checkSystemHealth, 
  testServerConnection, 
  normalizeServerUrl, 
  isNativePlatform 
} from '../../config/api';

interface ServiceStates {
  backend: string;
  database: string;
  ocr: string;
}

export default function ServerStatus() {
  const [status, setStatus] = useState<'checking' | 'operational' | 'degraded' | 'offline'>('checking');
  const [services, setServices] = useState<ServiceStates>({
    backend: 'operational',
    database: 'operational',
    ocr: 'operational',
  });
  const [lastChecked, setLastChecked] = useState<string>('');
  const [showModal, setShowModal] = useState(false);
  const [editUrl, setEditUrl] = useState(getApiHost());
  const [testing, setTesting] = useState(false);
  const [testSuccess, setTestSuccess] = useState<string | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  const performHealthCheck = useCallback(async () => {
    setStatus('checking');
    const result = await checkSystemHealth();
    setLastChecked(new Date().toLocaleTimeString());

    if (result.ok) {
      setStatus(result.status || 'operational');
      if (result.services) {
        setServices(result.services);
      }
    } else {
      setStatus('offline');
      setServices({
        backend: 'unavailable',
        database: 'unavailable',
        ocr: 'unavailable',
      });
    }
  }, []);

  // Poll health every 30 seconds, and on mount
  useEffect(() => {
    performHealthCheck();
    const interval = setInterval(performHealthCheck, 30000);
    return () => clearInterval(interval);
  }, [performHealthCheck]);

  const handleOpen = () => {
    setEditUrl(getApiHost());
    setTestSuccess(null);
    setTestError(null);
    setShowModal(true);
    performHealthCheck();
  };

  const handleTestAndSave = async () => {
    setTesting(true);
    setTestSuccess(null);
    setTestError(null);

    const isWeb = typeof window !== 'undefined' && !isNativePlatform();
    const trimmed = (editUrl || '').trim();

    if (!trimmed && isWeb) {
      // User cleared override to restore default auto-proxy
      setApiHost('');
      const res = await checkSystemHealth();
      setTesting(false);
      if (res.ok) {
        setTestSuccess('Restored default auto-proxy connection successfully!');
        setStatus(res.status || 'operational');
        if (res.services) setServices(res.services);
        setTimeout(() => setShowModal(false), 1200);
      } else {
        setTestError(res.error || 'Unable to connect via default local server.');
      }
      return;
    }

    const normalized = normalizeServerUrl(trimmed);
    if (!normalized) {
      setTesting(false);
      setTestError('Please enter a valid server URL starting with http:// or https://');
      return;
    }

    const res = await testServerConnection(normalized);
    setTesting(false);

    if (res.ok) {
      setApiHost(normalized);
      setTestSuccess('Connected and saved server URL successfully!');
      setStatus(res.status || 'operational');
      if (res.services) setServices(res.services);
      setTimeout(() => setShowModal(false), 1200);
    } else {
      setTestError(res.error || 'Unable to connect to the MetrCheck server.');
    }
  };

  const handleResetDefault = async () => {
    setApiHost('');
    setEditUrl('');
    setTesting(true);
    setTestSuccess(null);
    setTestError(null);
    const res = await checkSystemHealth();
    setTesting(false);
    if (res.ok) {
      setTestSuccess('Restored default server connection!');
      setStatus(res.status || 'operational');
      if (res.services) setServices(res.services);
      setTimeout(() => setShowModal(false), 1200);
    } else {
      setTestError(res.error || 'Unable to connect to local default server.');
    }
  };

  return (
    <>
      {/* ── Status Indicator Button in Top Navigation ── */}
      <button
        type="button"
        onClick={handleOpen}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-semibold rounded-lg border transition-all cursor-pointer shadow-xs ${
          status === 'operational'
            ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-300 dark:border-emerald-700/80 hover:bg-emerald-500/20'
            : status === 'degraded'
            ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-300 dark:border-amber-700/80 hover:bg-amber-500/20'
            : status === 'checking'
            ? 'bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-300 dark:border-slate-700 hover:bg-slate-500/20'
            : 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-300 dark:border-rose-700/80 hover:bg-rose-500/20'
        }`}
        title="System Operational status and backend configuration — click to inspect"
      >
        {status === 'operational' ? (
          <>
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
            <span className="hidden sm:inline">System Operational</span>
          </>
        ) : status === 'degraded' ? (
          <>
            <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
            <span className="hidden sm:inline">System Degraded</span>
          </>
        ) : status === 'checking' ? (
          <>
            <Loader2 className="w-3.5 h-3.5 animate-spin text-slate-400" />
            <span className="hidden sm:inline">Checking…</span>
          </>
        ) : (
          <>
            <XCircle className="w-3.5 h-3.5 text-rose-500" />
            <span className="hidden sm:inline">System Offline</span>
          </>
        )}
      </button>

      {/* ── System Operational & Server Settings Modal ── */}
      {showModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowModal(false)} />
          <div className="relative w-full max-w-lg rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl p-6 space-y-6 z-10 animate-in fade-in zoom-in-95 duration-200">
            
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-4">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
                  <Server className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                    System Operational Status & Connection
                  </h3>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400">
                    Live infrastructure health & backend server routing
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* ── SECTION 1: System Health ── */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Infrastructure Health
                </span>
                <div className="flex items-center gap-2">
                  {lastChecked && (
                    <span className="text-[10px] text-slate-400">
                      Checked: {lastChecked}
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={performHealthCheck}
                    disabled={status === 'checking'}
                    className="p-1 rounded-md text-slate-500 hover:text-indigo-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer disabled:opacity-50"
                    title="Refresh health check"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${status === 'checking' ? 'animate-spin' : ''}`} />
                  </button>
                </div>
              </div>

              {/* Status Banner */}
              <div className={`p-3.5 rounded-xl border flex items-center justify-between ${
                status === 'operational'
                  ? 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200'
                  : status === 'degraded'
                  ? 'bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-200'
                  : status === 'checking'
                  ? 'bg-slate-50 dark:bg-slate-800/60 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300'
                  : 'bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200'
              }`}>
                <div className="flex items-center gap-2.5">
                  {status === 'operational' ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />
                  ) : status === 'degraded' ? (
                    <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0" />
                  ) : status === 'checking' ? (
                    <Loader2 className="w-5 h-5 animate-spin text-slate-400 shrink-0" />
                  ) : (
                    <XCircle className="w-5 h-5 text-rose-500 shrink-0" />
                  )}
                  <div>
                    <p className="text-xs font-bold">
                      {status === 'operational' ? 'All Systems Operational' : status === 'degraded' ? 'System Degraded' : status === 'checking' ? 'Inspecting Services…' : 'System Offline'}
                    </p>
                    <p className="text-[11px] opacity-80">
                      {status === 'operational' 
                        ? 'Backend API, SQLite database, and OCR engines are active and verified.' 
                        : status === 'degraded'
                        ? 'Application is reachable but one or more background services reported warnings.'
                        : 'Unable to connect to the MetrCheck backend. Please ensure the server is running.'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Subsystems Health Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                {/* Frontend */}
                <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-800 flex flex-col justify-between">
                  <div className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400 mb-1">
                    <Globe className="w-3.5 h-3.5" />
                    <span className="font-semibold text-[11px]">Frontend</span>
                  </div>
                  <span className="font-bold text-emerald-600 dark:text-emerald-400 text-[11px]">
                    Operational
                  </span>
                </div>

                {/* Backend API */}
                <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-800 flex flex-col justify-between">
                  <div className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400 mb-1">
                    <Server className="w-3.5 h-3.5" />
                    <span className="font-semibold text-[11px]">Backend API</span>
                  </div>
                  <span className={`font-bold text-[11px] ${
                    services.backend === 'operational' ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'
                  }`}>
                    {services.backend === 'operational' ? 'Operational' : 'Unavailable'}
                  </span>
                </div>

                {/* Database */}
                <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-800 flex flex-col justify-between">
                  <div className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400 mb-1">
                    <Database className="w-3.5 h-3.5" />
                    <span className="font-semibold text-[11px]">Database</span>
                  </div>
                  <span className={`font-bold text-[11px] ${
                    services.database === 'operational' ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'
                  }`}>
                    {services.database === 'operational' ? 'Operational' : 'Unavailable'}
                  </span>
                </div>

                {/* OCR Engine */}
                <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-800 flex flex-col justify-between">
                  <div className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400 mb-1">
                    <Cpu className="w-3.5 h-3.5" />
                    <span className="font-semibold text-[11px]">OCR Engine</span>
                  </div>
                  <span className={`font-bold text-[11px] ${
                    services.ocr === 'operational' ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'
                  }`}>
                    {services.ocr === 'operational' ? 'Operational' : 'Degraded'}
                  </span>
                </div>
              </div>
            </div>

            {/* ── SECTION 2: Backend Connection / Server URL ── */}
            <div className="space-y-3 pt-2 border-t border-slate-100 dark:border-slate-800">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Backend Server Routing
                </label>
                {getApiHost() && (
                  <button
                    type="button"
                    onClick={handleResetDefault}
                    className="text-[11px] text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1 cursor-pointer"
                  >
                    <RotateCcw className="w-3 h-3" /> Reset to Auto
                  </button>
                )}
              </div>

              <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                By default, web clients connect to FastAPI via local same-origin proxy. For mobile APK testing on local Wi-Fi, enter your laptop's LAN IP (e.g. <code className="font-mono text-slate-700 dark:text-slate-300">http://192.168.1.5:8000</code>) or tunnel URL.
              </p>

              <div className="space-y-1.5">
                <input
                  type="url"
                  value={editUrl}
                  onChange={(e) => { 
                    setEditUrl(e.target.value); 
                    setTestSuccess(null); 
                    setTestError(null); 
                  }}
                  placeholder={isNativePlatform() ? "http://192.168.1.5:8000" : "Auto / Same-Origin (or enter custom http://...)"}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 focus:border-indigo-500 outline-none text-xs text-slate-900 dark:text-white placeholder:text-slate-400 font-mono"
                />
              </div>

              {testSuccess && (
                <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800/60 text-emerald-700 dark:text-emerald-300 text-xs flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-500" />
                  <span>{testSuccess}</span>
                </div>
              )}

              {testError && (
                <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800/60 text-rose-700 dark:text-rose-300 text-xs flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0 text-rose-500" />
                  <span>{testError}</span>
                </div>
              )}

              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={handleTestAndSave}
                  disabled={testing}
                  className="flex-1 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 shadow-sm"
                >
                  {testing ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Testing Connection…</span>
                    </>
                  ) : (
                    <>
                      <Server className="w-3.5 h-3.5" />
                      <span>Test & Save Server</span>
                    </>
                  )}
                </button>
              </div>

              <div className="flex items-center justify-between text-[10px] text-slate-400 dark:text-slate-500 pt-1">
                <span>Active Target: {getApiHost() || 'Auto (/api proxy)'}</span>
                <span>Port: 8000 (API) / 5173 (Web)</span>
              </div>
            </div>

          </div>
        </div>
      )}
    </>
  );
}
