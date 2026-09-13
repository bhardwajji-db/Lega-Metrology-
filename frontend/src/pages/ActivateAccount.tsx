import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Eye,
  EyeOff,
  Sparkles,
  Lock,
  User,
  Mail,
  RotateCcw,
} from 'lucide-react';
import { api } from '../services/api';
import type { InvitationVerification } from '../types';

export default function ActivateAccount() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') || '';

  const [verifying, setVerifying] = useState(true);
  const [invitation, setInvitation] = useState<InvitationVerification | null>(null);
  const [verifyError, setVerifyError] = useState('');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [activated, setActivated] = useState(false);

  useEffect(() => {
    if (!token.trim()) {
      setVerifying(false);
      setVerifyError('No invitation token was provided. Please use the complete activation link from your invitation email.');
      return;
    }

    let isMounted = true;
    (async () => {
      try {
        const res = await api.verifyInvitation(token.trim());
        if (!isMounted) return;
        if (res.valid) {
          setInvitation(res);
        } else {
          setVerifyError('This invitation link is invalid, has expired (valid for 24 hours), or has already been used.');
        }
      } catch (err: unknown) {
        if (!isMounted) return;
        setVerifyError(err instanceof Error ? err.message : 'Could not verify invitation link.');
      } finally {
        if (isMounted) setVerifying(false);
      }
    })();

    return () => {
      isMounted = false;
    };
  }, [token]);

  const passwordValidLength = password.length >= 8;
  const passwordsMatch = password.length > 0 && password === confirmPassword;
  const canSubmit = passwordValidLength && passwordsMatch && !submitting;

  const handleActivate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;

    setSubmitting(true);
    setSubmitError('');

    try {
      await api.activateAccount(token.trim(), password);
      setActivated(true);
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : 'Could not activate account. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const isAudit = invitation?.role === 'AUDIT_OFFICER';

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-between p-4 sm:p-6 selection:bg-indigo-500 selection:text-white">
      {/* Header Branding */}
      <div className="max-w-5xl w-full mx-auto flex items-center justify-between pt-2">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-2xl bg-gradient-to-br from-indigo-500 via-purple-500 to-sky-500 p-0.5 shadow-lg shadow-indigo-500/20">
            <div className="w-full h-full bg-slate-950 rounded-[14px] flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-indigo-400" />
            </div>
          </div>
          <div>
            <span className="font-black tracking-tight text-white text-base sm:text-lg">MetrCheck</span>
            <span className="text-xs font-bold text-indigo-400 ml-1">AI</span>
          </div>
        </div>

        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700/80 text-[11px] font-semibold text-slate-300">
          <ShieldAlert className="w-3.5 h-3.5 text-amber-300" />
          <span>Statutory Compliance Support</span>
        </div>
      </div>

      {/* Main Content Card */}
      <div className="max-w-md w-full mx-auto my-8">
        {verifying ? (
          <div className="rounded-3xl border border-slate-800 bg-slate-900/90 shadow-2xl p-8 text-center space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center mx-auto animate-pulse">
              <RotateCcw className="w-6 h-6 animate-spin" />
            </div>
            <h2 className="text-lg font-bold text-white">Verifying Invitation Link</h2>
            <p className="text-xs text-slate-400">Please wait while we validate your secure invitation token...</p>
          </div>
        ) : verifyError ? (
          <div className="rounded-3xl border border-rose-500/30 bg-slate-900/90 shadow-2xl p-6 sm:p-8 space-y-5 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-rose-500/15 text-rose-400 rounded-2xl border border-rose-500/30 shrink-0">
                <AlertTriangle className="w-7 h-7" />
              </div>
              <div className="space-y-1">
                <span className="text-[11px] font-bold uppercase tracking-wider text-rose-400">Invitation Invalid</span>
                <h2 className="text-lg font-black text-white tracking-tight">Cannot Activate Account</h2>
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-slate-950/60 border border-slate-800 text-xs text-slate-300 leading-relaxed space-y-2">
              <p>{verifyError}</p>
              <p className="text-slate-400 text-[11px]">
                Account invitation links expire after 24 hours or after their first use. If your link expired, please ask your MetrCheck administrator to resend an invitation.
              </p>
            </div>

            <button
              type="button"
              onClick={() => navigate('/login')}
              className="w-full py-3 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <span>Return to Sign In</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        ) : activated ? (
          <div className="rounded-3xl border border-emerald-500/30 bg-slate-900/90 shadow-2xl p-6 sm:p-8 space-y-5 animate-in fade-in zoom-in-95 duration-200 text-center">
            <div className="w-14 h-14 rounded-2xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-8 h-8" />
            </div>

            <div className="space-y-1">
              <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">Activation Complete</span>
              <h2 className="text-xl font-black text-white">Account Ready</h2>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              Your password has been successfully set and your <strong className="text-white">@{invitation?.username}</strong> account is now active.
            </p>

            <button
              type="button"
              onClick={() => navigate('/login')}
              className="w-full py-3 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs sm:text-sm font-bold shadow-lg shadow-indigo-600/30 transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <span>Proceed to Sign In</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <div className="rounded-3xl border border-slate-800 bg-slate-900/90 shadow-2xl p-6 sm:p-8 space-y-6 animate-in fade-in zoom-in-95 duration-200">
            {/* Header */}
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${
                  isAudit
                    ? 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30'
                    : 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                }`}>
                  {isAudit ? 'Audit Officer' : 'Enforcement Officer'}
                </span>
                <span className="text-[10px] text-slate-400">Account Provisioning</span>
              </div>
              <h2 className="text-xl font-black text-white tracking-tight">Activate Your Account</h2>
              <p className="text-xs text-slate-400">
                Choose a strong password to complete onboarding and activate your workspace access.
              </p>
            </div>

            {/* Account Details Summary */}
            <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800 space-y-2 text-xs">
              <div className="flex items-center justify-between text-slate-400">
                <span className="flex items-center gap-1.5">
                  <User className="w-3.5 h-3.5 text-slate-500" />
                  <span>Account:</span>
                </span>
                <span className="font-bold text-slate-200">@{invitation?.username}</span>
              </div>
              {invitation?.full_name && (
                <div className="flex items-center justify-between text-slate-400">
                  <span>Full Name:</span>
                  <span className="text-slate-300">{invitation.full_name}</span>
                </div>
              )}
              {invitation?.email && (
                <div className="flex items-center justify-between text-slate-400">
                  <span className="flex items-center gap-1.5">
                    <Mail className="w-3.5 h-3.5 text-slate-500" />
                    <span>Email:</span>
                  </span>
                  <span className="text-slate-300 font-mono text-[11px]">{invitation.email}</span>
                </div>
              )}
            </div>

            {/* Error Message */}
            {submitError && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <span>{submitError}</span>
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleActivate} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
                  <span>Create Password</span>
                  <span className={`text-[10px] ${passwordValidLength ? 'text-emerald-400' : 'text-slate-500'}`}>
                    min. 8 characters
                  </span>
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your new password"
                    className="w-full pl-3.5 pr-10 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-100 placeholder:text-slate-600 focus:outline-hidden focus:border-indigo-500 transition-colors"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
                  <span>Confirm Password</span>
                  {confirmPassword.length > 0 && (
                    <span className={`text-[10px] ${passwordsMatch ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {passwordsMatch ? 'Passwords match' : 'Passwords do not match'}
                    </span>
                  )}
                </label>
                <div className="relative">
                  <input
                    type={showConfirmPassword ? 'text' : 'password'}
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Confirm your password"
                    className="w-full pl-3.5 pr-10 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-100 placeholder:text-slate-600 focus:outline-hidden focus:border-indigo-500 transition-colors"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                  >
                    {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={!canSubmit}
                className={`w-full py-3 px-4 rounded-xl text-xs sm:text-sm font-bold shadow-lg transition-all flex items-center justify-center gap-2 cursor-pointer ${
                  canSubmit
                    ? 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/30'
                    : 'bg-slate-800 text-slate-500 cursor-not-allowed opacity-70'
                }`}
              >
                {submitting ? (
                  <>
                    <RotateCcw className="w-4 h-4 animate-spin" />
                    <span>Activating Account...</span>
                  </>
                ) : (
                  <>
                    <Lock className="w-4 h-4" />
                    <span>Activate Account</span>
                  </>
                )}
              </button>
            </form>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="max-w-5xl w-full mx-auto text-center text-xs text-slate-600">
        SIH 2026 · Problem Statement 26034 · Directorate of Legal Metrology Compliance Support
      </div>
    </div>
  );
}
