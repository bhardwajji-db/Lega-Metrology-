import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
  ShieldCheck, 
  KeyRound, 
  User, 
  ArrowLeft, 
  ArrowRight, 
  Loader2, 
  Sparkles, 
  CheckCircle2, 
  AlertCircle,
  HelpCircle,
  ExternalLink
} from 'lucide-react';
import { api } from '../services/api';

export default function ForgotPassword() {
  const navigate = useNavigate();
  const [identifier, setIdentifier] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successResponse, setSuccessResponse] = useState<{ message: string; dev_token?: string } | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmed = identifier.trim();
    if (!trimmed) {
      setError('Please enter your username or registered email address.');
      return;
    }

    setBusy(true);
    try {
      const res = await api.forgotPassword(trimmed);
      setSuccessResponse(res);
    } catch (err: any) {
      setError(err?.message || 'Unable to process password recovery request. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex flex-col justify-between py-8 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      {/* Top Brand Nav */}
      <div className="max-w-5xl w-full mx-auto flex items-center justify-between">
        <Link to="/login" className="flex items-center gap-3 group">
          <div className="p-2.5 rounded-xl bg-indigo-500/15 border border-indigo-500/30 group-hover:bg-indigo-500/25 transition-colors">
            <ShieldCheck className="w-6 h-6 text-indigo-400" />
          </div>
          <div>
            <span className="text-base font-extrabold tracking-tight text-white block">MetrCheck AI</span>
            <span className="text-xs text-slate-400">AI-Assisted Statutory Compliance</span>
          </div>
        </Link>

        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700/80 text-[11px] font-semibold text-slate-300">
          <Sparkles className="w-3.5 h-3.5 text-amber-300" />
          <span>SIH 2026 Security Suite</span>
        </div>
      </div>

      {/* Main Container */}
      <div className="max-w-md w-full mx-auto my-8">
        <div className="rounded-3xl border border-slate-800 bg-slate-900/80 backdrop-blur-md shadow-2xl p-6 sm:p-8 space-y-6">
          {/* Header */}
          <div className="text-center space-y-2">
            <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 flex items-center justify-center mx-auto mb-3">
              <KeyRound className="w-6 h-6" />
            </div>
            <h1 className="text-2xl font-black text-white tracking-tight">
              Password Recovery
            </h1>
            <p className="text-xs text-slate-400 leading-relaxed">
              Enter your registered username or email address to receive secure password reset instructions.
            </p>
          </div>

          {/* Success or Form State */}
          {successResponse ? (
            <div className="space-y-5 animate-in fade-in zoom-in-95 duration-200">
              <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 space-y-2">
                <div className="flex items-center gap-2 font-bold text-sm text-emerald-200">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                  <span>Request Processed</span>
                </div>
                <p className="text-xs leading-relaxed text-slate-300">
                  {successResponse.message}
                </p>
              </div>

              {/* Dev / Test Mode token helper for automated & manual testing verification */}
              {successResponse.dev_token && (
                <div className="p-4 rounded-2xl bg-indigo-950/60 border border-indigo-500/30 space-y-2.5">
                  <div className="flex items-center justify-between text-[11px] font-bold text-indigo-300 uppercase tracking-wider">
                    <span className="flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                      Dev / Test Environment Helper
                    </span>
                    <span className="text-[10px] text-indigo-400 font-mono">15m Expiry</span>
                  </div>
                  <p className="text-xs text-slate-300">
                    A single-use token was issued. You can immediately open the reset interface:
                  </p>
                  <button
                    type="button"
                    onClick={() => navigate(`/reset-password?token=${encodeURIComponent(successResponse.dev_token!)}`)}
                    className="w-full py-2.5 px-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-colors flex items-center justify-center gap-2 cursor-pointer shadow-md shadow-indigo-600/30"
                  >
                    <span>Open Reset Password Interface</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}

              <div className="pt-2">
                <Link
                  to="/login"
                  className="w-full py-3 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs sm:text-sm font-bold transition-all flex items-center justify-center gap-2"
                >
                  <ArrowLeft className="w-4 h-4" />
                  <span>Back to Sign In</span>
                </Link>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">
                  Username or Registered Email
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                  <input
                    type="text"
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    placeholder="Enter username or recovery email (e.g. merchant, user@domain.com)"
                    autoComplete="username"
                    required
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-indigo-500 outline-none text-sm text-white placeholder:text-slate-500"
                  />
                </div>
              </div>

              {error && (
                <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-400 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 text-[11px] text-slate-400 leading-relaxed space-y-1">
                <div className="flex items-center gap-1 font-semibold text-slate-300">
                  <HelpCircle className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Security &amp; Privacy Notice</span>
                </div>
                <p>
                  To prevent account enumeration, instructions are dispatched silently without revealing account existence. Reset links remain active for 15 minutes.
                </p>
              </div>

              <button
                type="submit"
                disabled={busy}
                className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white text-xs sm:text-sm font-bold flex items-center justify-center gap-2 transition-all shadow-lg shadow-indigo-900/40 cursor-pointer active:scale-98"
              >
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                <span>{busy ? 'Sending recovery link…' : 'Send Recovery Instructions'}</span>
              </button>

              <div className="text-center pt-2">
                <Link
                  to="/login"
                  className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>Return to Sign In</span>
                </Link>
              </div>
            </form>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="max-w-5xl w-full mx-auto text-center text-xs text-slate-600">
        SIH 2026 · Problem Statement 26034 · Directorate of Legal Metrology Compliance Support
      </div>
    </div>
  );
}
