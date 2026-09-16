import { useState, type FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { 
  ShieldCheck, 
  Lock, 
  User, 
  Eye, 
  EyeOff, 
  Loader2, 
  ArrowLeft, 
  KeyRound, 
  ShieldAlert
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

import { getApiHost } from '../services/api';
import { isServerConfigured, isNativePlatform } from '../config/api';

export default function AdminLogin() {
  const { login, logout } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    const cleanUsername = username.trim();
    if (!cleanUsername || !password) {
      setError('Please enter your administrator username and password.');
      return;
    }

    if (isNativePlatform() && !isServerConfigured()) {
      setError('No backend API server configured. Please return to the public login screen to configure your server address.');
      return;
    }

    setBusy(true);
    try {
      const authenticatedUser = await login(cleanUsername, password);
      
      // Strict role check: Only ADMIN accounts can enter through this portal
      if (authenticatedUser.role === 'ADMIN') {
        navigate('/admin/users', { replace: true });
      } else {
        // Non-admin attempted login on admin portal
        logout();
        setError('Access Restricted: This portal is strictly reserved for System Administrators. Your account does not have administrative authority.');
      }
    } catch (err: any) {
      setError(
        err?.message || 'Authentication failed. Please verify administrator credentials and try again.'
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex flex-col justify-between py-10 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 text-slate-100">
      {/* Top Header */}
      <div className="max-w-md w-full mx-auto flex items-center justify-between">
        <Link to="/" className="flex items-center gap-3 group">
          <div className="p-2.5 rounded-xl bg-indigo-500/15 border border-indigo-500/30 group-hover:border-indigo-500/50 transition-colors">
            <ShieldCheck className="w-6 h-6 text-indigo-400" />
          </div>
          <div>
            <span className="text-base font-extrabold tracking-tight text-white block">MetrCheck AI</span>
            <span className="text-xs text-slate-400">Directorate of Legal Metrology</span>
          </div>
        </Link>

        <span className="px-2.5 py-1 rounded-full text-[10px] font-mono font-bold uppercase tracking-wider bg-red-950/80 text-red-300 border border-red-800/60 flex items-center gap-1">
          <Lock className="w-3 h-3" />
          <span>Admin Portal</span>
        </span>
      </div>

      {/* Main Admin Login Card */}
      <div className="max-w-md w-full mx-auto my-8">
        <div className="rounded-3xl border border-indigo-500/30 bg-slate-900/90 backdrop-blur-md shadow-2xl overflow-hidden p-6 sm:p-8 space-y-6">
          {/* Title and Scope Banner */}
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                <ShieldAlert className="w-4 h-4" />
              </span>
              <h1 className="text-xl font-black text-white tracking-tight">
                System Administrator Sign In
              </h1>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              Authorized personnel only. Access to user provisioning, role assignments, and security audit logs is monitored and recorded.
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Administrator Username
              </label>
              <div className="relative">
                <User className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter admin username"
                  autoComplete="username"
                  required
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-950/80 border border-slate-700 focus:border-indigo-500 outline-none text-sm text-white placeholder:text-slate-500"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-medium text-slate-300">
                  Password
                </label>
                <Link
                  to="/forgot-password"
                  className="text-[11px] font-semibold text-indigo-400 hover:text-indigo-300 transition-colors"
                >
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  required
                  className="w-full pl-10 pr-11 py-2.5 rounded-xl bg-slate-950/80 border border-slate-700 focus:border-indigo-500 outline-none text-sm text-white placeholder:text-slate-500"
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 cursor-pointer"
                  aria-label={showPw ? 'Hide password' : 'Show password'}
                >
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-300 leading-relaxed">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 text-white text-xs sm:text-sm font-bold flex items-center justify-center gap-2 shadow-lg shadow-indigo-950/50 cursor-pointer transition-all active:scale-98"
            >
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
              <span>{busy ? 'Authenticating Administrator…' : 'Authenticate & Enter Admin Area'}</span>
            </button>
          </form>

          {/* Security Notice */}
          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-[11px] text-slate-400 leading-relaxed">
            Administrative actions are cryptographically signed and archived in the immutable security audit trail.
          </div>
        </div>

        {/* Back to Public App */}
        <div className="text-center mt-4">
          <Link
            to="/login"
            className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Return to Public Workspaces</span>
          </Link>
        </div>
      </div>

      {/* Footer */}
      <div className="max-w-md w-full mx-auto text-center text-xs text-slate-600 flex flex-col items-center gap-1">
        <span>MetrCheck AI Security Boundary · Directorate of Legal Metrology</span>
        <span className="text-[10px] text-slate-500">Server: {getApiHost() || 'Not configured'}</span>
      </div>
    </div>
  );
}
