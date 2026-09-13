import { useState, useEffect, type FormEvent } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { 
  ShieldCheck, 
  Lock, 
  Eye, 
  EyeOff, 
  Loader2, 
  ArrowLeft, 
  CheckCircle2, 
  AlertCircle, 
  Sparkles, 
  KeyRound, 
  ArrowRight,
  ShieldAlert
} from 'lucide-react';
import { api } from '../services/api';

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') || '';

  // Verification state
  const [checkingToken, setCheckingToken] = useState(true);
  const [tokenValid, setTokenValid] = useState<boolean | null>(null);
  const [targetUsername, setTargetUsername] = useState<string | null>(null);

  // Form state
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [showConfirmPw, setShowConfirmPw] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // On mount: check if token is valid
  useEffect(() => {
    if (!token) {
      setCheckingToken(false);
      setTokenValid(false);
      return;
    }

    let isMounted = true;
    api.verifyResetToken(token)
      .then((res) => {
        if (!isMounted) return;
        setTokenValid(res.valid);
        if (res.username) setTargetUsername(res.username);
      })
      .catch(() => {
        if (!isMounted) return;
        setTokenValid(false);
      })
      .finally(() => {
        if (isMounted) setCheckingToken(false);
      });

    return () => {
      isMounted = false;
    };
  }, [token]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!token) {
      setError('Password reset token is missing.');
      return;
    }

    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match. Please re-enter.');
      return;
    }

    setBusy(true);
    try {
      await api.resetPassword(token, newPassword);
      setSuccess(true);
    } catch (err: any) {
      setError(err?.message || 'Failed to reset password. The link may have expired.');
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

      {/* Main Form Container */}
      <div className="max-w-md w-full mx-auto my-8">
        <div className="rounded-3xl border border-slate-800 bg-slate-900/80 backdrop-blur-md shadow-2xl p-6 sm:p-8 space-y-6">
          {/* Header */}
          <div className="text-center space-y-2">
            <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 flex items-center justify-center mx-auto mb-3">
              <KeyRound className="w-6 h-6" />
            </div>
            <h1 className="text-2xl font-black text-white tracking-tight">
              Set New Password
            </h1>
            <p className="text-xs text-slate-400 leading-relaxed">
              {targetUsername
                ? `Create a secure new password for account '${targetUsername}'.`
                : 'Create a secure new password for your MetrCheck AI account.'}
            </p>
          </div>

          {/* Loading verification */}
          {checkingToken ? (
            <div className="py-12 flex flex-col items-center justify-center space-y-3 text-slate-400">
              <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
              <span className="text-xs font-medium">Verifying reset authorization link…</span>
            </div>
          ) : success ? (
            /* Success state */
            <div className="space-y-5 animate-in fade-in zoom-in-95 duration-200">
              <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 space-y-2">
                <div className="flex items-center gap-2 font-bold text-sm text-emerald-200">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                  <span>Password Reset Complete</span>
                </div>
                <p className="text-xs leading-relaxed text-slate-300">
                  Your password has been successfully updated. You can now sign in with your new credentials.
                </p>
              </div>

              <button
                type="button"
                onClick={() => navigate('/login')}
                className="w-full py-3 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs sm:text-sm font-bold shadow-lg shadow-indigo-600/30 transition-all flex items-center justify-center gap-2 cursor-pointer active:scale-98"
              >
                <span>Proceed to Sign In</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          ) : tokenValid === false ? (
            /* Invalid or Expired Token State */
            <div className="space-y-5 animate-in fade-in zoom-in-95 duration-200">
              <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-300 space-y-2">
                <div className="flex items-center gap-2 font-bold text-sm text-amber-200">
                  <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0" />
                  <span>Invalid or Expired Link</span>
                </div>
                <p className="text-xs leading-relaxed text-slate-300">
                  This password reset link is invalid, has already been used, or has expired (15-minute validity window).
                </p>
              </div>

              <div className="space-y-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => navigate('/forgot-password')}
                  className="w-full py-3 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs sm:text-sm font-bold shadow-lg shadow-indigo-600/30 transition-all flex items-center justify-center gap-2 cursor-pointer active:scale-98"
                >
                  <span>Request New Reset Link</span>
                  <ArrowRight className="w-4 h-4" />
                </button>

                <Link
                  to="/login"
                  className="w-full py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-semibold transition-all flex items-center justify-center gap-2"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>Return to Sign In</span>
                </Link>
              </div>
            </div>
          ) : (
            /* Reset Password Form */
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">
                  New Password
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                  <input
                    type={showPw ? 'text' : 'password'}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Enter new password (min. 8 chars)"
                    autoComplete="new-password"
                    required
                    className="w-full pl-10 pr-11 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-indigo-500 outline-none text-sm text-white placeholder:text-slate-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw(!showPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 cursor-pointer"
                  >
                    {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">
                  Confirm New Password
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                  <input
                    type={showConfirmPw ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Re-enter new password"
                    autoComplete="new-password"
                    required
                    className="w-full pl-10 pr-11 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-indigo-500 outline-none text-sm text-white placeholder:text-slate-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPw(!showConfirmPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 cursor-pointer"
                  >
                    {showConfirmPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {error && (
                <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-400 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1 text-[11px] text-slate-400">
                <span className="font-semibold text-slate-300 block">Password Requirements:</span>
                <ul className="list-disc list-inside space-y-0.5 text-[10px]">
                  <li className={newPassword.length >= 8 ? 'text-emerald-400 font-medium' : 'text-slate-500'}>
                    Minimum 8 characters
                  </li>
                  <li className={newPassword && newPassword === confirmPassword ? 'text-emerald-400 font-medium' : 'text-slate-500'}>
                    Passwords match
                  </li>
                </ul>
              </div>

              <button
                type="submit"
                disabled={busy}
                className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white text-xs sm:text-sm font-bold flex items-center justify-center gap-2 transition-all shadow-lg shadow-indigo-900/40 cursor-pointer active:scale-98"
              >
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                <span>{busy ? 'Updating password…' : 'Update Password'}</span>
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
