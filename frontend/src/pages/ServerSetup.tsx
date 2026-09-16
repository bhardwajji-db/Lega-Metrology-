import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldCheck, Loader2, CheckCircle2, Server, Wifi, ArrowRight, AlertTriangle } from 'lucide-react';
import { testServerConnection, setApiHost, normalizeServerUrl } from '../config/api';

export default function ServerSetup() {
  const navigate = useNavigate();
  const [serverUrl, setServerUrl] = useState('');
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'failed'>('idle');
  const [testError, setTestError] = useState<string | null>(null);
  const [healthData, setHealthData] = useState<any>(null);

  const handleTest = async () => {
    const normalized = normalizeServerUrl(serverUrl);
    if (!normalized) {
      setTestStatus('failed');
      setTestError('Please enter a valid URL starting with http:// or https://');
      return;
    }
    setTestStatus('testing');
    setTestError(null);
    setHealthData(null);

    const result = await testServerConnection(normalized);
    if (result.ok) {
      setTestStatus('success');
      setHealthData(result.data);
    } else {
      setTestStatus('failed');
      setTestError(result.error || 'Connection failed');
    }
  };

  const handleContinue = () => {
    setApiHost(serverUrl);
    navigate('/login');
  };

  const handleSkip = () => {
    navigate('/login');
  };

  return (
    <div className="min-h-screen w-full flex flex-col items-center justify-center py-8 px-4 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      {/* Branding */}
      <div className="flex items-center gap-3 mb-8">
        <div className="p-2.5 rounded-xl bg-indigo-500/15 border border-indigo-500/30">
          <ShieldCheck className="w-7 h-7 text-indigo-400" />
        </div>
        <div>
          <span className="text-lg font-extrabold tracking-tight text-white block">MetrCheck AI</span>
          <span className="text-xs text-slate-400">AI-Assisted Statutory Compliance</span>
        </div>
      </div>

      {/* Setup Card */}
      <div className="w-full max-w-md rounded-3xl border border-slate-800 bg-slate-900/90 backdrop-blur-md shadow-2xl p-6 sm:p-8 space-y-6">
        <div className="text-center space-y-2">
          <div className="mx-auto w-14 h-14 rounded-2xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center">
            <Server className="w-7 h-7 text-indigo-400" />
          </div>
          <h1 className="text-xl font-bold text-white">Connect to MetrCheck Server</h1>
          <p className="text-sm text-slate-400">Enter your MetrCheck AI backend server URL to get started.</p>
        </div>

        {/* URL Input */}
        <div className="space-y-2">
          <label className="block text-xs font-medium text-slate-400">Server URL</label>
          <div className="relative">
            <Wifi className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="url"
              value={serverUrl}
              onChange={(e) => {
                setServerUrl(e.target.value);
                setTestStatus('idle');
                setTestError(null);
              }}
              placeholder="https://your-server.trycloudflare.com"
              className="w-full pl-10 pr-4 py-3 rounded-xl bg-slate-800/80 border border-slate-700 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50 outline-none text-sm text-white placeholder:text-slate-500 transition-colors"
              onKeyDown={(e) => e.key === 'Enter' && handleTest()}
            />
          </div>
          <p className="text-[11px] text-slate-500">
            Use your Cloudflare Tunnel HTTPS URL or local network address (e.g. http://192.168.x.x:8000)
          </p>
        </div>

        {/* Test Button */}
        <button
          type="button"
          onClick={handleTest}
          disabled={testStatus === 'testing' || !serverUrl.trim()}
          className="w-full py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-sm font-bold transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed border border-slate-700"
        >
          {testStatus === 'testing' ? (
            <><Loader2 className="w-4 h-4 animate-spin" /> Checking connection...</>
          ) : (
            <><Wifi className="w-4 h-4 text-indigo-400" /> Test Connection</>
          )}
        </button>

        {/* Status Display */}
        {testStatus === 'success' && healthData && (
          <div className="space-y-2 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
            <div className="flex items-center gap-2 text-emerald-400 text-sm font-semibold">
              <CheckCircle2 className="w-4 h-4" />
              Server Connected
            </div>
            <div className="space-y-1.5 text-xs">
              <div className="flex items-center gap-2 text-emerald-400/80">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>API Available (v{healthData.version || '1.0'})</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-400/80">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>OCR Service: {healthData.ocr_available ? 'Ready' : 'Unavailable'} ({healthData.ocr_engine || 'Unknown'})</span>
              </div>
              <div className="flex items-center gap-2 text-emerald-400/80">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Database: {healthData.database || 'Connected'}</span>
              </div>
            </div>
          </div>
        )}

        {testStatus === 'failed' && testError && (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30">
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400 mt-0.5 shrink-0" />
              <div className="space-y-1">
                <p className="text-sm font-semibold text-rose-400">Connection Failed</p>
                <p className="text-xs text-rose-400/80">{testError}</p>
                <p className="text-[11px] text-slate-500 mt-2">
                  Make sure the server is running and accessible from this device.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Continue Button */}
        {testStatus === 'success' && (
          <button
            type="button"
            onClick={handleContinue}
            className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-bold transition-all flex items-center justify-center gap-2 cursor-pointer shadow-lg shadow-indigo-900/40"
          >
            Continue <ArrowRight className="w-4 h-4" />
          </button>
        )}

        {/* Skip link */}
        <div className="text-center">
          <button
            type="button"
            onClick={handleSkip}
            className="text-xs text-slate-500 hover:text-slate-400 transition-colors cursor-pointer"
          >
            Skip for now →
          </button>
        </div>
      </div>

      {/* Footer */}
      <p className="mt-6 text-xs text-slate-600">
        SIH 2026 · Problem Statement 26034 · Legal Metrology Compliance
      </p>
    </div>
  );
}
