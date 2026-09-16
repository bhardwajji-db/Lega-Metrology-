import { useState, type FormEvent } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { 
  ShieldCheck, 
  Lock, 
  User, 
  Mail,
  Eye, 
  EyeOff, 
  Loader2, 
  ArrowLeft, 
  Store, 
  SearchCheck, 
  ShieldAlert, 
  Sparkles, 
  ArrowRight, 
  KeyRound, 
  CheckCircle2, 
  RotateCcw,
  BadgeCheck,
  Info,
  X,
  Server,
  Wifi,
  WifiOff
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useWorkspace, WORKSPACE_DEFINITIONS, getAllowedWorkspacesForRole } from '../context/WorkspaceContext';
import { type WorkspaceType, type AuthUser } from '../types';
import { getApiHost, setApiHost } from '../services/api';
import { testServerConnection, isServerConfigured, isNativePlatform } from '../config/api';

export default function Login() {
  const { login, register, logout } = useAuth();
  const { setWorkspace } = useWorkspace();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as any)?.from?.pathname || '/';

  // Workspace selection state: null means user is choosing workspace, otherwise holds target workspace
  const [selectedWorkspace, setSelectedWorkspace] = useState<WorkspaceType | null>(null);
  
  // Login form state
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Informational modal state for privileged workspace access requests
  const [infoModal, setInfoModal] = useState<'AUDIT' | 'ENFORCEMENT' | null>(null);

  // Access denied state: set when an authenticated user attempts to enter an unauthorized workspace
  const [accessDeniedUser, setAccessDeniedUser] = useState<AuthUser | null>(null);

  // Server connection configuration modal
  const [showServerModal, setShowServerModal] = useState(false);
  const [serverUrl, setServerUrl] = useState(getApiHost() || '');
  const [serverTestStatus, setServerTestStatus] = useState<'idle' | 'testing' | 'success' | 'failed'>('idle');
  const [serverTestError, setServerTestError] = useState<string | null>(null);

  const handleTestServer = async () => {
    setServerTestStatus('testing');
    setServerTestError(null);
    const result = await testServerConnection(serverUrl);
    if (result.ok) {
      setServerTestStatus('success');
    } else {
      setServerTestStatus('failed');
      setServerTestError(result.error || 'Connection failed.');
    }
  };

  const handleSaveServer = () => {
    setApiHost(serverUrl);
    setShowServerModal(false);
    setError(null);
  };

  const handleSelectWorkspace = (ws: WorkspaceType) => {
    setSelectedWorkspace(ws);
    setMode('login'); // Always default to sign in
    setError(null);
    setAccessDeniedUser(null);
  };

  const handleBackToWorkspaceSelection = () => {
    setSelectedWorkspace(null);
    setMode('login');
    setError(null);
    setAccessDeniedUser(null);
  };

  const handlePopulateCredentials = (u: string, p: string, ws?: WorkspaceType) => {
    setUsername(u);
    setPassword(p);
    if (ws) {
      setSelectedWorkspace(ws);
    }
    setError(null);
  };

  const handleAccessDeniedContinueAllowed = () => {
    if (!accessDeniedUser) return;
    const allowed = getAllowedWorkspacesForRole(accessDeniedUser.role);
    const fallback = allowed[0] || 'MERCHANT';
    setWorkspace(fallback);
    navigate(from, { replace: true });
  };

  const handleAccessDeniedSignOut = () => {
    logout();
    setAccessDeniedUser(null);
    setUsername('');
    setPassword('');
    setError(null);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setAccessDeniedUser(null);

    if (mode === 'register') {
      if (!username.trim() || !email.trim() || password.length < 8) {
        setError('Username, valid recovery email, and a password of at least 8 characters are required.');
        return;
      }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
        setError('Please enter a valid email address for account recovery.');
        return;
      }
    } else {
      if (!username.trim() || !password) {
        setError('Please enter your username and password.');
        return;
      }
    }

    if (isNativePlatform() && !isServerConfigured()) {
      setError('No backend API server configured. Please tap "Server Settings" below to connect to your backend.');
      setShowServerModal(true);
      return;
    }

    setBusy(true);
    try {
      const authenticatedUser = mode === 'login'
        ? await login(username.trim(), password)
        : await register(username.trim(), email.trim(), password, fullName.trim() || undefined);

      const targetWorkspace = selectedWorkspace || 'MERCHANT';
      const allowedWorkspaces = getAllowedWorkspacesForRole(authenticatedUser.role);

      // Verify if authenticated role is authorized for the requested workspace
      if (allowedWorkspaces.includes(targetWorkspace)) {
        setWorkspace(targetWorkspace);
        navigate(from, { replace: true });
      } else {
        // Access Denied: User role does NOT have permission for this workspace
        setAccessDeniedUser(authenticatedUser);
      }
    } catch (err: any) {
      setError(err?.message || (mode === 'login' ? 'Incorrect username or password. Please check your credentials and try again.' : 'Registration failed.'));
    } finally {
      setBusy(false);
    }
  };

  const targetDef = selectedWorkspace ? WORKSPACE_DEFINITIONS[selectedWorkspace] : null;

  return (
    <div className="min-h-screen w-full flex flex-col justify-between py-8 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      {/* Top Brand Nav */}
      <div className="max-w-5xl w-full mx-auto flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-indigo-500/15 border border-indigo-500/30">
            <ShieldCheck className="w-6 h-6 text-indigo-400" />
          </div>
          <div>
            <span className="text-base font-extrabold tracking-tight text-white block">MetrCheck AI</span>
            <span className="text-xs text-slate-400">AI-Assisted Statutory Compliance</span>
          </div>
        </div>

        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-800/80 border border-slate-700/80 text-[11px] font-semibold text-slate-300">
          <Sparkles className="w-3.5 h-3.5 text-amber-300" />
          <span>SIH 2026 National Finalist</span>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="max-w-5xl w-full mx-auto my-8">
        {/* ==================================================================== */}
        {/* STATE 1: ACCESS DENIED SCREEN (Role not authorized for workspace)    */}
        {/* ==================================================================== */}
        {accessDeniedUser && targetDef ? (
          <div className="max-w-lg mx-auto rounded-3xl border border-amber-500/30 bg-slate-900/90 backdrop-blur-md shadow-2xl p-6 sm:p-8 space-y-6 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-amber-500/15 text-amber-400 rounded-2xl border border-amber-500/30 shrink-0">
                <ShieldAlert className="w-8 h-8" />
              </div>
              <div className="space-y-1">
                <span className="text-xs font-bold uppercase tracking-wider text-amber-400">Access Control Boundary</span>
                <h2 className="text-xl font-black text-white tracking-tight">Workspace Access Restricted</h2>
              </div>
            </div>

            <p className="text-sm text-slate-300 leading-relaxed">
              The <strong className="text-white">{targetDef.label}</strong> is restricted to authorized {targetDef.id === 'ENFORCEMENT' ? 'Enforcement Officers and System Administrators' : 'Quality Auditors and Officers'}. Your authenticated account does not have permission to access this workspace.
            </p>

            {/* Account & Permission Summary Card */}
            <div className="p-4 rounded-2xl bg-slate-950/60 border border-slate-800 space-y-2.5 text-xs font-mono">
              <div className="flex justify-between items-center text-slate-400 border-b border-slate-800/80 pb-2">
                <span>Authenticated Account:</span>
                <span className="font-bold text-slate-200">{accessDeniedUser.username}</span>
              </div>
              <div className="flex justify-between items-center text-slate-400 border-b border-slate-800/80 pb-2">
                <span>Backend Role:</span>
                <span className="font-bold text-sky-400 bg-sky-500/10 px-2 py-0.5 rounded border border-sky-500/20">
                  {accessDeniedUser.role_label || accessDeniedUser.role}
                </span>
              </div>
              <div className="flex justify-between items-center text-slate-400 border-b border-slate-800/80 pb-2">
                <span>Requested Workspace:</span>
                <span className="font-bold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                  {targetDef.label} ({targetDef.coreAction})
                </span>
              </div>
              <div className="flex justify-between items-center text-slate-400 pt-0.5">
                <span>Authorized Workspace:</span>
                <span className="font-bold text-emerald-400">Merchant Workspace (PREVENT)</span>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="space-y-3 pt-2">
              <button
                type="button"
                onClick={handleAccessDeniedContinueAllowed}
                className="w-full py-3 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs sm:text-sm font-bold shadow-lg shadow-indigo-600/30 transition-all flex items-center justify-center gap-2 cursor-pointer active:scale-98"
              >
                <span>Continue to Merchant Workspace</span>
                <ArrowRight className="w-4 h-4" />
              </button>

              <button
                type="button"
                onClick={handleAccessDeniedSignOut}
                className="w-full py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-semibold transition-all flex items-center justify-center gap-2 cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Sign In With Another Account</span>
              </button>
            </div>
          </div>
        ) : selectedWorkspace === null ? (
          /* ==================================================================== */
          /* STATE 2: WORKSPACE SELECTION PORTAL (Choose your workspace)         */
          /* ==================================================================== */
          <div className="space-y-8 animate-in fade-in duration-300">
            {/* Title & Introduction */}
            <div className="text-center space-y-3 max-w-2xl mx-auto">
              <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-white">
                Choose your workspace
              </h1>
              <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                MetrCheck AI provides three specialized operating environments over a unified statutory compliance analysis pipeline. Select your destination workspace to sign in.
              </p>
            </div>

            {/* 3-Column Workspace Selection Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              {/* 1. Merchant Workspace Card */}
              <div 
                onClick={() => handleSelectWorkspace('MERCHANT')}
                className="rounded-3xl border border-slate-800 bg-slate-900/70 hover:border-sky-500/60 hover:bg-slate-900/90 transition-all duration-200 p-6 flex flex-col justify-between group cursor-pointer shadow-xl relative overflow-hidden"
              >
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="w-12 h-12 rounded-2xl bg-sky-500/10 border border-sky-500/30 text-sky-400 flex items-center justify-center group-hover:scale-105 transition-transform">
                      <Store className="w-6 h-6" />
                    </div>
                    <span className="px-2.5 py-1 rounded-full text-[10px] font-black tracking-wider bg-sky-500/20 text-sky-300 border border-sky-400/30 uppercase">
                      PREVENT
                    </span>
                  </div>

                  <div>
                    <h3 className="text-lg font-bold text-white group-hover:text-sky-300 transition-colors">
                      Merchant Workspace
                    </h3>
                    <p className="text-xs text-sky-400/90 font-medium mt-0.5">
                      For manufacturers, brands and merchants
                    </p>
                  </div>

                  <p className="text-xs text-slate-400 leading-relaxed">
                    Check packaging before printing, manufacturing and retail distribution.
                  </p>

                  <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Primary Goal:</span>
                    <p className="text-xs text-slate-200 font-medium">Find issues and fix them before release.</p>
                  </div>
                </div>

                <div className="pt-5 mt-4 border-t border-slate-800/80 flex items-center justify-between">
                  <span className="text-[11px] text-emerald-400 font-semibold flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Open Access</span>
                  </span>
                  <button
                    type="button"
                    className="px-3.5 py-1.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold shadow-md shadow-sky-600/30 transition-all flex items-center gap-1.5"
                  >
                    <span>Continue as Merchant</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* 2. Audit Workspace Card */}
              <div 
                onClick={() => handleSelectWorkspace('AUDIT')}
                className="rounded-3xl border border-slate-800 bg-slate-900/70 hover:border-indigo-500/60 hover:bg-slate-900/90 transition-all duration-200 p-6 flex flex-col justify-between group cursor-pointer shadow-xl relative overflow-hidden"
              >
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 flex items-center justify-center group-hover:scale-105 transition-transform">
                      <SearchCheck className="w-6 h-6" />
                    </div>
                    <span className="px-2.5 py-1 rounded-full text-[10px] font-black tracking-wider bg-indigo-500/20 text-indigo-300 border border-indigo-400/30 uppercase">
                      VERIFY
                    </span>
                  </div>

                  <div>
                    <h3 className="text-lg font-bold text-white group-hover:text-indigo-300 transition-colors">
                      Audit Workspace
                    </h3>
                    <p className="text-xs text-indigo-400/90 font-medium mt-0.5">
                      For quality, compliance and audit users
                    </p>
                  </div>

                  <p className="text-xs text-slate-400 leading-relaxed">
                    Perform detailed rule-by-rule verification with evidence and audit records.
                  </p>

                  <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Primary Goal:</span>
                    <p className="text-xs text-slate-200 font-medium">Verify what was detected and why.</p>
                  </div>
                </div>

                <div className="pt-5 mt-4 border-t border-slate-800/80 flex items-center justify-between">
                  <span className="text-[11px] text-indigo-400 font-semibold flex items-center gap-1">
                    <BadgeCheck className="w-3.5 h-3.5" />
                    <span>Officer / QA Auth</span>
                  </span>
                  <button
                    type="button"
                    className="px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold shadow-md shadow-indigo-600/30 transition-all flex items-center gap-1.5"
                  >
                    <span>Continue to Audit</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* 3. Enforcement Workspace Card */}
              <div 
                onClick={() => handleSelectWorkspace('ENFORCEMENT')}
                className="rounded-3xl border border-amber-900/40 bg-slate-900/70 hover:border-amber-500/60 hover:bg-slate-900/90 transition-all duration-200 p-6 flex flex-col justify-between group cursor-pointer shadow-xl relative overflow-hidden"
              >
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-400 flex items-center justify-center group-hover:scale-105 transition-transform">
                      <ShieldAlert className="w-6 h-6" />
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="px-2.5 py-1 rounded-full text-[10px] font-black tracking-wider bg-amber-500/20 text-amber-300 border border-amber-400/30 uppercase">
                        INVESTIGATE
                      </span>
                      <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-red-950/80 text-red-300 border border-red-800/60 uppercase flex items-center gap-0.5">
                        <Lock className="w-2.5 h-2.5" />
                        <span>Restricted</span>
                      </span>
                    </div>
                  </div>

                  <div>
                    <h3 className="text-lg font-bold text-white group-hover:text-amber-300 transition-colors">
                      Enforcement Workspace
                    </h3>
                    <p className="text-xs text-amber-400/90 font-medium mt-0.5">
                      For authorized Legal Metrology enforcement officials
                    </p>
                  </div>

                  <p className="text-xs text-slate-400 leading-relaxed">
                    Investigate potential violations using statutory references and evidence.
                  </p>

                  <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Primary Goal:</span>
                    <p className="text-xs text-slate-200 font-medium">Review findings and support regulatory action.</p>
                  </div>
                </div>

                <div className="pt-5 mt-4 border-t border-slate-800/80 flex items-center justify-between">
                  <span className="text-[11px] text-amber-400 font-semibold flex items-center gap-1">
                    <Lock className="w-3.5 h-3.5" />
                    <span>Official Auth</span>
                  </span>
                  <button
                    type="button"
                    className="px-3.5 py-1.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold shadow-md shadow-amber-600/30 transition-all flex items-center gap-1.5"
                  >
                    <span>Continue to Enforcement</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* ==================================================================== */
          /* STATE 3: AUTHENTICATION FORM FOR SELECTED WORKSPACE                  */
          /* ==================================================================== */
          <div className="max-w-md mx-auto space-y-4 animate-in fade-in zoom-in-95 duration-200">
            {/* Top Workspace Context Banner */}
            <div className="flex items-center justify-between p-3.5 rounded-2xl bg-slate-900 border border-slate-800 shadow-md">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className={`p-2 rounded-xl shrink-0 ${
                  targetDef?.id === 'MERCHANT' ? 'bg-sky-500/15 text-sky-400 border border-sky-500/30' :
                  targetDef?.id === 'AUDIT' ? 'bg-indigo-500/15 text-indigo-400 border border-indigo-500/30' :
                  'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                }`}>
                  {targetDef?.id === 'MERCHANT' ? <Store className="w-4 h-4" /> :
                   targetDef?.id === 'AUDIT' ? <SearchCheck className="w-4 h-4" /> :
                   <ShieldAlert className="w-4 h-4" />}
                </div>
                <div className="min-w-0">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block tracking-wider">
                    Signing in to
                  </span>
                  <p className="text-xs font-bold text-white truncate">
                    {targetDef?.label} • <span className="font-mono text-indigo-300">{targetDef?.coreAction}</span>
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={handleBackToWorkspaceSelection}
                className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 hover:underline px-2.5 py-1 rounded-lg hover:bg-slate-800 transition-colors shrink-0 cursor-pointer"
              >
                Change workspace
              </button>
            </div>

            {/* Login Card */}
            <div className="rounded-3xl border border-slate-800 bg-slate-900/80 backdrop-blur-md shadow-2xl overflow-hidden">
              {/* Mode Header / Tabs: Merchant gets Sign In + Register tabs; Audit/Enforcement get dedicated Sign In banner */}
              {targetDef?.id === 'MERCHANT' ? (
                <div className="p-2 border-b border-slate-800 bg-slate-950/40">
                  <div className="grid grid-cols-2 gap-1 p-1 rounded-xl bg-slate-800/60 border border-slate-700/60">
                    {(['login', 'register'] as const).map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => { setMode(m); setError(null); }}
                        className={`py-2 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                          mode === m
                            ? 'bg-sky-600 text-white shadow-sm'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {m === 'login' ? 'Sign In' : 'Register Merchant'}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="p-3.5 border-b border-slate-800 bg-slate-950/40 flex items-center justify-between">
                  <span className="text-xs font-bold text-white flex items-center gap-2">
                    <Lock className={`w-3.5 h-3.5 ${targetDef?.id === 'AUDIT' ? 'text-indigo-400' : 'text-amber-400'}`} />
                    <span>{targetDef?.id === 'AUDIT' ? 'Audit Workspace Sign In' : 'Enforcement Workspace Sign In'}</span>
                  </span>
                  <span className={`text-[10px] font-black tracking-wider px-2 py-0.5 rounded border uppercase ${
                    targetDef?.id === 'AUDIT'
                      ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30'
                      : 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                  }`}>
                    {targetDef?.coreAction}
                  </span>
                </div>
              )}

              {/* Form Body */}
              <form onSubmit={handleSubmit} className="p-6 space-y-4">
                {!isServerConfigured() && (
                  <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-between gap-2 text-xs text-amber-300">
                    <div className="flex items-center gap-2">
                      <WifiOff className="w-4 h-4 shrink-0 text-amber-400" />
                      <span>Server address not configured</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setShowServerModal(true)}
                      className="px-2.5 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 font-bold text-[11px] transition-colors cursor-pointer shrink-0"
                    >
                      Configure Server
                    </button>
                  </div>
                )}

                {targetDef?.id === 'MERCHANT' && mode === 'register' && (
                  <div className="p-3 rounded-xl bg-sky-500/10 border border-sky-500/20 text-xs text-sky-300 leading-relaxed">
                    New merchants can create a Merchant/Public account for pre-flight packaging compliance.
                  </div>
                )}

                {targetDef?.id === 'MERCHANT' && mode === 'register' && (
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1.5">Brand / Company Name (Optional)</label>
                    <div className="relative">
                      <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                      <input
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        placeholder="e.g. Acme Organic Foods Ltd"
                        className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-indigo-500 outline-none text-sm text-white placeholder:text-slate-500"
                      />
                    </div>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">Username</label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <input
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="Enter username"
                      autoComplete="username"
                      required
                      className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-indigo-500 outline-none text-sm text-white placeholder:text-slate-500"
                    />
                  </div>
                </div>

                {targetDef?.id === 'MERCHANT' && mode === 'register' && (
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1.5">
                      Recovery Email <span className="text-rose-400">*</span>
                    </label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="merchant@example.com"
                        autoComplete="email"
                        required
                        className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-indigo-500 outline-none text-sm text-white placeholder:text-slate-500"
                      />
                    </div>
                    <p className="text-[11px] text-slate-400 mt-1">Used for statutory notifications and secure password recovery.</p>
                  </div>
                )}

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="block text-xs font-medium text-slate-400">Password</label>
                    {mode === 'login' && (
                      <Link
                        to="/forgot-password"
                        className="text-[11px] font-semibold text-indigo-400 hover:text-indigo-300 transition-colors"
                      >
                        Forgot password?
                      </Link>
                    )}
                  </div>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <input
                      type={showPw ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
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

                {error && (
                  <div className="px-4 py-2.5 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-400">
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={busy}
                  className={`w-full py-3 rounded-xl disabled:opacity-60 text-white text-xs sm:text-sm font-bold flex items-center justify-center gap-2 transition-all shadow-lg cursor-pointer active:scale-98 ${
                    targetDef?.id === 'ENFORCEMENT'
                      ? 'bg-amber-600 hover:bg-amber-500 shadow-amber-900/40'
                      : targetDef?.id === 'AUDIT'
                      ? 'bg-indigo-600 hover:bg-indigo-500 shadow-indigo-900/40'
                      : 'bg-sky-600 hover:bg-sky-500 shadow-sky-900/40'
                  }`}
                >
                  {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
                  <span>
                    {busy ? 'Verifying credentials…' : mode === 'login' ? `Sign In to ${targetDef?.shortLabel} Workspace` : 'Create Merchant Account'}
                  </span>
                </button>
              </form>

              {/* Informational Panel for Privileged Workspaces (Audit & Enforcement) */}
              {targetDef?.id === 'AUDIT' && (
                <div className="px-6 pb-4">
                  <div className="p-3.5 rounded-2xl bg-indigo-950/40 border border-indigo-500/30 text-xs space-y-1.5">
                    <div className="flex items-center gap-2 font-bold text-indigo-300">
                      <SearchCheck className="w-4 h-4 text-indigo-400 shrink-0" />
                      <span>Authorized audit accounts only.</span>
                    </div>
                    <p className="text-slate-300 text-[11px] leading-relaxed">
                      Audit Workspace access is provided to authorized users by an administrator.
                    </p>
                    <div className="pt-0.5">
                      <button
                        type="button"
                        onClick={() => setInfoModal('AUDIT')}
                        className="text-[11px] font-semibold text-indigo-400 hover:text-indigo-300 underline cursor-pointer inline-flex items-center gap-1"
                      >
                        <span>Request Audit Access</span>
                        <Info className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {targetDef?.id === 'ENFORCEMENT' && (
                <div className="px-6 pb-4">
                  <div className="p-3.5 rounded-2xl bg-amber-950/40 border border-amber-500/30 text-xs space-y-1.5">
                    <div className="flex items-center gap-2 font-bold text-amber-300">
                      <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
                      <span>Authorized enforcement officers only.</span>
                    </div>
                    <p className="text-slate-300 text-[11px] leading-relaxed">
                      Enforcement Workspace access is provisioned for authorized enforcement officers.
                    </p>
                    <div className="pt-0.5">
                      <button
                        type="button"
                        onClick={() => setInfoModal('ENFORCEMENT')}
                        className="text-[11px] font-semibold text-amber-400 hover:text-amber-300 underline cursor-pointer inline-flex items-center gap-1"
                      >
                        <span>Contact Administrator</span>
                        <Info className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* SIH Demo Accounts Section — Strictly opt-in only when VITE_METRCHECK_DEMO_MODE is explicitly 'true' */}
              {import.meta.env.VITE_METRCHECK_DEMO_MODE === 'true' && (
                <div className="px-6 pb-6 pt-1">
                  <div className="rounded-2xl bg-slate-950/60 border border-slate-800/90 p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5 text-amber-300" /> SIH Demo Accounts
                      </span>
                      <span className="text-[9px] text-slate-500 font-mono">Fill &amp; Authenticate</span>
                    </div>

                  <div className="space-y-2 text-xs">
                    {/* Enforcement Officer */}
                    <div className="flex items-center justify-between p-2 rounded-xl bg-slate-900/80 border border-slate-800">
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-slate-200">ENFORCEMENT OFFICER</span>
                          <span className="text-[10px] text-emerald-400 font-mono">officer / officer123</span>
                        </div>
                        <p className="text-[10px] text-slate-500">Enforcement, Audit &amp; Merchant access</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handlePopulateCredentials('officer', 'officer123', 'ENFORCEMENT')}
                        className="px-2.5 py-1 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 text-[10px] font-bold transition-colors cursor-pointer"
                      >
                        Use Account
                      </button>
                    </div>

                    {/* Audit Officer */}
                    <div className="flex items-center justify-between p-2 rounded-xl bg-slate-900/80 border border-slate-800">
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-slate-200">AUDIT OFFICER</span>
                          <span className="text-[10px] text-indigo-400 font-mono">audit / audit123</span>
                        </div>
                        <p className="text-[10px] text-slate-500">Audit &amp; Compliance verification workspace access</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handlePopulateCredentials('audit', 'audit123', 'AUDIT')}
                        className="px-2.5 py-1 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 text-[10px] font-bold transition-colors cursor-pointer"
                      >
                        Use Account
                      </button>
                    </div>

                    {/* Demo Merchant */}
                    <div className="flex items-center justify-between p-2 rounded-xl bg-slate-900/80 border border-slate-800">
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-slate-200">DEMO MERCHANT</span>
                          <span className="text-[10px] text-sky-400 font-mono">merchant / merchant123</span>
                        </div>
                        <p className="text-[10px] text-slate-500">Merchant Pre-Flight workspace access</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handlePopulateCredentials('merchant', 'merchant123', 'MERCHANT')}
                        className="px-2.5 py-1 rounded-lg bg-sky-600/20 hover:bg-sky-600/30 text-sky-300 border border-sky-500/30 text-[10px] font-bold transition-colors cursor-pointer"
                      >
                        Use Account
                      </button>
                    </div>
                  </div>
                </div>
              </div>
              )}
            </div>

            <div className="text-center">
              <button
                type="button"
                onClick={handleBackToWorkspaceSelection}
                className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Return to Workspace Selection</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Informational Request / Contact Modal */}
      {infoModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className={`p-2.5 rounded-xl border ${
                  infoModal === 'AUDIT'
                    ? 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30'
                    : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                }`}>
                  {infoModal === 'AUDIT' ? <SearchCheck className="w-5 h-5" /> : <ShieldAlert className="w-5 h-5" />}
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">
                    {infoModal === 'AUDIT' ? 'Request Audit Access' : 'Contact Administrator'}
                  </h3>
                  <p className="text-xs text-slate-400">
                    {infoModal === 'AUDIT' ? 'Quality & Compliance Verification' : 'Statutory Enforcement Access'}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setInfoModal(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-3.5 rounded-2xl bg-slate-950/60 border border-slate-800/80 text-xs text-slate-300 space-y-2 leading-relaxed">
              {infoModal === 'AUDIT' ? (
                <>
                  <p>
                    The <strong className="text-white">Audit Workspace</strong> is intended for internal quality inspectors, auditors, and technical compliance teams.
                  </p>
                  <p>
                    Audit accounts are provisioned and managed by system administrators. Public self-registration is disabled to ensure audit chain-of-custody.
                  </p>
                  <p className="text-slate-400 text-[11px]">
                    To request access, contact your organization's compliance administrator or DoCA coordinator.
                  </p>
                </>
              ) : (
                <>
                  <p>
                    The <strong className="text-white">Enforcement Workspace</strong> is restricted exclusively to gazetted Legal Metrology Inspectors and authorized enforcement officers.
                  </p>
                  <p>
                    Official credentials and statutory jurisdiction assignments are provisioned directly by the Directorate of Legal Metrology.
                  </p>
                  <p className="text-slate-400 text-[11px]">
                    For authorization inquiries or officer onboarding, please coordinate with your departmental administrator.
                  </p>
                </>
              )}
            </div>

            <div className="pt-2">
              <button
                type="button"
                onClick={() => setInfoModal(null)}
                className="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold transition-all cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Server Connection Configuration Modal */}
      {showServerModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-200">
          <div className="w-full max-w-md bg-slate-900 border border-slate-700/80 rounded-3xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                  <Server className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Backend Server Setup</h3>
                  <p className="text-xs text-slate-400">Configure your AI engine connection URL</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowServerModal(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-2 text-xs text-slate-300">
              <p className="leading-relaxed">
                Enter your MetrCheck server URL. Use your Cloudflare Tunnel HTTPS URL for remote access, or local network IP (e.g. <code className="text-indigo-300">http://192.168.x.x:8000</code>) on the same Wi-Fi.
              </p>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Backend Server URL</label>
                <div className="relative">
                  <input
                    type="text"
                    value={serverUrl}
                    onChange={(e) => {
                      setServerUrl(e.target.value);
                      setServerTestStatus('idle');
                    }}
                    placeholder="https://your-server.trycloudflare.com"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/80 border border-slate-700 focus:border-indigo-500 outline-none text-xs text-white placeholder:text-slate-500"
                  />
                </div>
              </div>

              {serverTestStatus === 'success' && (
                <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span>Successfully connected to MetrCheck AI Backend!</span>
                </div>
              )}

              {serverTestStatus === 'failed' && (
                <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-start gap-2">
                  <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold block">Connection failed</span>
                    <span className="text-[11px] text-rose-300/90 leading-relaxed block">{serverTestError || 'Could not reach backend at this URL. Make sure run.bat is running on your laptop!'}</span>
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center gap-2 pt-2">
              <button
                type="button"
                onClick={handleTestServer}
                disabled={serverTestStatus === 'testing'}
                className="flex-1 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                {serverTestStatus === 'testing' ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wifi className="w-4 h-4 text-indigo-400" />}
                <span>Test Connection</span>
              </button>
              <button
                type="button"
                onClick={handleSaveServer}
                className="flex-1 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all shadow-lg shadow-indigo-900/40 cursor-pointer"
              >
                Save & Connect
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="max-w-5xl w-full mx-auto flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-slate-600">
        <span>SIH 2026 · Problem Statement 26034 · Directorate of Legal Metrology Compliance Support</span>
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => setShowServerModal(true)}
            className="text-slate-500 hover:text-indigo-400 transition-colors text-[11px] flex items-center gap-1 cursor-pointer"
          >
            <Server className="w-3 h-3" />
            <span>Server: {getApiHost() || 'Not configured'}</span>
          </button>
          <Link to="/admin/login" className="text-slate-500 hover:text-slate-400 transition-colors text-[11px] flex items-center gap-1">
            <Lock className="w-3 h-3" />
            <span>Administrator Portal</span>
          </Link>
        </div>
      </div>
    </div>
  );
}