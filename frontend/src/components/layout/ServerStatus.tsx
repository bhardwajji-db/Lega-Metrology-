import { useState, useEffect, useCallback } from 'react';
import { Wifi, WifiOff, Loader2, Server, CheckCircle2, AlertTriangle, X, RefreshCw } from 'lucide-react';
import { getApiHost, setApiHost, testServerConnection, normalizeServerUrl } from '../../config/api';

export default function ServerStatus() {
  const [status, setStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [showSettings, setShowSettings] = useState(false);
  const [editUrl, setEditUrl] = useState(getApiHost());
  const [testResult, setTestResult] = useState<'idle' | 'testing' | 'success' | 'failed'>('idle');
  const [testError, setTestError] = useState<string | null>(null);

  const checkConnection = useCallback(async () => {
    const host = getApiHost();
    if (!host) {
      setStatus('offline');
      return;
    }
    setStatus('checking');
    const result = await testServerConnection(host);
    setStatus(result.ok ? 'online' : 'offline');
  }, []);

  // Check on mount and every 60 seconds
  useEffect(() => {
    checkConnection();
    const interval = setInterval(checkConnection, 60000);
    return () => clearInterval(interval);
  }, [checkConnection]);

  const handleTestAndSave = async () => {
    const normalized = normalizeServerUrl(editUrl);
    if (!normalized) {
      setTestResult('failed');
      setTestError('Invalid URL. Must start with http:// or https://');
      return;
    }
    setTestResult('testing');
    setTestError(null);
    const result = await testServerConnection(normalized);
    if (result.ok) {
      setTestResult('success');
      setApiHost(normalized);
      setStatus('online');
      setTimeout(() => setShowSettings(false), 800);
    } else {
      setTestResult('failed');
      setTestError(result.error || 'Connection failed');
    }
  };

  const handleOpen = () => {
    setEditUrl(getApiHost());
    setTestResult('idle');
    setTestError(null);
    setShowSettings(true);
  };

  return (
    <>
      {/* Status Indicator Button */}
      <button
        type="button"
        onClick={handleOpen}
        className={`inline-flex items-center gap-1.5 px-2 py-1 text-[11px] font-semibold rounded-lg border transition-all cursor-pointer ${
          status === 'online'
            ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-300 dark:border-emerald-700/80'
            : status === 'checking'
            ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-300 dark:border-amber-700/80'
            : 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-300 dark:border-rose-700/80'
        }`}
        title="Server connection status — click to configure"
      >
        {status === 'online' ? (
          <><Wifi className="w-3 h-3" /><span className="hidden sm:inline">Connected</span></>
        ) : status === 'checking' ? (
          <><Loader2 className="w-3 h-3 animate-spin" /><span className="hidden sm:inline">Checking…</span></>
        ) : (
          <><WifiOff className="w-3 h-3" /><span className="hidden sm:inline">Offline</span></>
        )}
      </button>

      {/* Settings Modal */}
      {showSettings && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowSettings(false)} />
          <div className="relative w-full max-w-md rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl p-5 space-y-4 z-10">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Server className="w-5 h-5 text-indigo-500" />
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">Server Settings</h3>
              </div>
              <button type="button" onClick={() => setShowSettings(false)} className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Server URL</label>
              <input
                type="url"
                value={editUrl}
                onChange={(e) => { setEditUrl(e.target.value); setTestResult('idle'); }}
                placeholder="https://your-server.trycloudflare.com"
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 focus:border-indigo-500 outline-none text-xs text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500"
              />
            </div>

            {testResult === 'success' && (
              <div className="p-2.5 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 shrink-0" /> Server connected and saved!
              </div>
            )}

            {testResult === 'failed' && testError && (
              <div className="p-2.5 rounded-xl bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" /> {testError}
              </div>
            )}

            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleTestAndSave}
                disabled={testResult === 'testing' || !editUrl.trim()}
                className="flex-1 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                {testResult === 'testing' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wifi className="w-3.5 h-3.5" />}
                Test & Save
              </button>
              <button
                type="button"
                onClick={() => { checkConnection(); setShowSettings(false); }}
                className="px-3 py-2.5 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Retry
              </button>
            </div>

            <p className="text-[10px] text-slate-400 dark:text-slate-500 text-center">
              Current: {getApiHost() || 'Not configured'}
            </p>
          </div>
        </div>
      )}
    </>
  );
}
