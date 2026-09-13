import { useState, useEffect, type FormEvent } from 'react';
import { 
  UserCircle2, 
  Mail, 
  CheckCircle2, 
  AlertCircle, 
  Loader2, 
  Info
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';

export default function AccountSettings() {
  const { user } = useAuth();
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user?.email) {
      setEmail(user.email);
    }
  }, [user]);

  const handleUpdateEmail = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    const trimmed = email.trim();
    if (!trimmed) {
      setError('Please enter a valid recovery email address.');
      return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      setError('Please enter a valid email address format (e.g. user@example.com).');
      return;
    }

    setBusy(true);
    try {
      const updated = await api.updateMyEmail(trimmed);
      setEmail(updated.email || trimmed);
      setSuccess('Recovery email updated successfully! Password recovery instructions will now be delivered to this address.');
    } catch (err: any) {
      setError(err?.message || 'Could not update recovery email. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const roleLabel = user?.role === 'ADMIN' ? 'System Administrator'
    : user?.role === 'ENFORCEMENT_OFFICER' ? 'Enforcement Officer'
    : user?.role === 'AUDIT_OFFICER' ? 'Audit Officer'
    : 'Merchant / Public';

  const roleBadgeColor = user?.role === 'ADMIN' ? 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30'
    : user?.role === 'ENFORCEMENT_OFFICER' ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
    : user?.role === 'AUDIT_OFFICER' ? 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30'
    : 'bg-amber-500/15 text-amber-300 border-amber-500/30';

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
          <UserCircle2 className="w-6 h-6 text-indigo-400" />
          Account &amp; Security Settings
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Manage your account profile, credentials, and registered recovery email address.
        </p>
      </div>

      {/* Account Overview Card */}
      <div className="rounded-3xl border border-slate-800 bg-slate-900/80 backdrop-blur-md p-6 sm:p-8 space-y-6 shadow-xl">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-300 shrink-0">
              <UserCircle2 className="w-8 h-8" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">
                {user?.full_name || user?.username}
              </h2>
              <p className="text-xs text-slate-400 font-mono">@{user?.username}</p>
            </div>
          </div>

          <span className={`px-3 py-1.5 rounded-full text-xs font-bold border ${roleBadgeColor}`}>
            {roleLabel}
          </span>
        </div>

        {/* Profile Details Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono">
          <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1">
            <span className="text-slate-500 font-bold uppercase tracking-wider block">Username</span>
            <span className="text-slate-200 text-sm font-semibold">{user?.username}</span>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1">
            <span className="text-slate-500 font-bold uppercase tracking-wider block">Jurisdiction / Office</span>
            <span className="text-slate-200 text-sm font-semibold">{user?.jurisdiction || 'Default National Jurisdiction'}</span>
          </div>
        </div>

        {/* Recovery Email Section */}
        <div className="pt-4 border-t border-slate-800 space-y-4">
          <div className="flex items-start gap-3">
            <div className="p-2.5 rounded-xl bg-sky-500/15 border border-sky-500/30 text-sky-400 shrink-0">
              <Mail className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Registered Recovery Email</h3>
              <p className="text-xs text-slate-400 leading-relaxed mt-0.5">
                Password recovery requests for this account will be sent directly to this email address.
              </p>
            </div>
          </div>

          {/* Feedback messages */}
          {success && (
            <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-start gap-2.5">
              <CheckCircle2 className="w-4.5 h-4.5 text-emerald-400 shrink-0 mt-0.5" />
              <span>{success}</span>
            </div>
          )}

          {error && (
            <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2.5">
              <AlertCircle className="w-4.5 h-4.5 text-rose-400 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleUpdateEmail} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">
                Recovery Email Address
              </label>
              <div className="relative max-w-md">
                <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="e.g. officer@metrcheck.gov.in"
                  autoComplete="email"
                  required
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-950/70 border border-slate-700 focus:border-indigo-500 outline-none text-sm text-white placeholder:text-slate-500"
                />
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-950/40 border border-slate-800/80 text-xs text-slate-400 flex items-start gap-2.5 max-w-xl">
              <Info className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
              <span>
                Setting or updating your recovery email allows you to use the <strong>Forgot Password</strong> self-service flow at any time if you lose access to your account.
              </span>
            </div>

            <button
              type="submit"
              disabled={busy}
              className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white text-xs sm:text-sm font-bold flex items-center gap-2 shadow-lg shadow-indigo-950/40 cursor-pointer transition-all"
            >
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
              <span>{busy ? 'Updating…' : 'Save Recovery Email'}</span>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
