import { useEffect, useState, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Users as UsersIcon,
  UserPlus,
  ShieldCheck,
  Store,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  KeyRound,
  Trash2,
  X,
  SearchCheck,
  Mail,
  Send,
  UserX,
  ShieldAlert,
  History,
  Copy,
  Search,
  Filter,
} from 'lucide-react';
import { api } from '../services/api';
import type { AuthUser, AccountAuditLog, BackendRole } from '../types';
import { useAuth } from '../context/AuthContext';

const ROLE_STYLES: Record<string, { label: string; cls: string; icon: React.ComponentType<{ className?: string }> }> = {
  ADMIN: { label: 'Administrator', cls: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30', icon: ShieldCheck },
  ENFORCEMENT_OFFICER: { label: 'Enforcement Officer', cls: 'bg-amber-500/15 text-amber-300 border-amber-500/30', icon: ShieldAlert },
  AUDIT_OFFICER: { label: 'Audit Officer', cls: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30', icon: SearchCheck },
  MERCHANT_PUBLIC: { label: 'Merchant / Public', cls: 'bg-sky-500/15 text-sky-300 border-sky-500/30', icon: Store },
};

const STATUS_STYLES: Record<string, { label: string; cls: string }> = {
  ACTIVE: { label: 'Active', cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' },
  INVITED: { label: 'Invited (Pending)', cls: 'bg-amber-500/15 text-amber-300 border-amber-500/30' },
  SUSPENDED: { label: 'Suspended', cls: 'bg-rose-500/15 text-rose-300 border-rose-500/30' },
};

const EMPTY_PROVISION_FORM = {
  username: '',
  email: '',
  full_name: '',
  jurisdiction: '',
  role: 'AUDIT_OFFICER' as BackendRole,
};

interface AdminUsersProps {
  defaultTab?: 'users' | 'audit';
}

export default function AdminUsers({ defaultTab }: AdminUsersProps) {
  const { user: currentUser } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  // Tab State: determine from URL or prop
  const currentTabFromUrl = location.pathname.includes('audit-logs') ? 'audit' : 'users';
  const [activeTab, setActiveTab] = useState<'users' | 'audit'>(defaultTab || currentTabFromUrl);

  useEffect(() => {
    if (location.pathname.includes('audit-logs')) {
      setActiveTab('audit');
    } else if (location.pathname.includes('users')) {
      setActiveTab('users');
    }
  }, [location.pathname]);

  const [users, setUsers] = useState<AuthUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Search & Filter
  const [userSearchQuery, setUserSearchQuery] = useState('');
  const [auditSearchQuery, setAuditSearchQuery] = useState('');
  const [auditFilterEventType, setAuditFilterEventType] = useState('ALL');

  // Provisioning Modal State
  const [showProvisionModal, setShowProvisionModal] = useState(false);
  const [provisionForm, setProvisionForm] = useState({ ...EMPTY_PROVISION_FORM });
  const [provisioning, setProvisioning] = useState(false);
  const [lastProvisionResult, setLastProvisionResult] = useState<{
    username: string;
    email: string;
    role: string;
    invitation_url: string;
    delivery_status: string;
  } | null>(null);

  // Change Role Modal State
  const [changingRoleUser, setChangingRoleUser] = useState<AuthUser | null>(null);
  const [selectedNewRole, setSelectedNewRole] = useState<BackendRole>('AUDIT_OFFICER');
  const [savingRole, setSavingRole] = useState(false);

  // Audit Logs State
  const [auditLogs, setAuditLogs] = useState<AccountAuditLog[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(false);

  // Action in flight trackers
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);

  const loadUsers = async () => {
    setLoading(true);
    setError('');
    try {
      setUsers(await api.adminGetUsers());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not load user list.');
    } finally {
      setLoading(false);
    }
  };

  const loadAuditLogs = async () => {
    setLoadingLogs(true);
    try {
      setAuditLogs(await api.adminGetAuditLogs(100));
    } catch (e: unknown) {
      console.error('Failed to load audit logs', e);
    } finally {
      setLoadingLogs(false);
    }
  };

  useEffect(() => {
    loadUsers();
    loadAuditLogs();
  }, []);

  const handleTabSwitch = (tab: 'users' | 'audit') => {
    setActiveTab(tab);
    if (tab === 'users') {
      navigate('/admin/users');
      loadUsers();
    } else {
      navigate('/admin/audit-logs');
      loadAuditLogs();
    }
  };

  const handleOpenProvisionModal = () => {
    setProvisionForm({ ...EMPTY_PROVISION_FORM });
    setLastProvisionResult(null);
    setShowProvisionModal(true);
    setError('');
    setSuccess('');
  };

  const handleProvisionSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!provisionForm.username.trim() || !provisionForm.email.trim()) {
      setError('Username and email are required.');
      return;
    }
    setProvisioning(true);
    setError('');
    setSuccess('');
    try {
      const res = await api.adminProvisionUser({
        username: provisionForm.username.trim(),
        email: provisionForm.email.trim(),
        role: provisionForm.role,
        full_name: provisionForm.full_name.trim() || undefined,
        jurisdiction: provisionForm.jurisdiction.trim() || undefined,
      });

      const directUrl = res.dev_invitation_token
        ? `${window.location.origin}/activate?token=${res.dev_invitation_token}`
        : `${window.location.origin}/activate`;

      setLastProvisionResult({
        username: res.user.username,
        email: res.user.email || provisionForm.email,
        role: res.user.role,
        invitation_url: directUrl,
        delivery_status: res.message,
      });
      setSuccess(`Invitation dispatched to ${res.user.email || provisionForm.email} for account @${res.user.username}`);
      await loadUsers();
      await loadAuditLogs();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to provision account.');
    } finally {
      setProvisioning(false);
    }
  };

  const handleResendInvitation = async (username: string) => {
    setActionInProgress(`resend-${username}`);
    setError('');
    setSuccess('');
    try {
      const res = await api.adminResendInvitation(username);
      setSuccess(res.message || `New invitation token generated and dispatched for @${username}`);
      await loadUsers();
      await loadAuditLogs();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to resend invitation.');
    } finally {
      setActionInProgress(null);
    }
  };

  const handleSuspend = async (username: string) => {
    if (!window.confirm(`Suspend account @${username}? The user will immediately be logged out and unable to access the system.`)) {
      return;
    }
    setActionInProgress(`suspend-${username}`);
    setError('');
    setSuccess('');
    try {
      await api.adminSuspendUser(username);
      setSuccess(`Account @${username} has been suspended. Active sessions invalidated.`);
      await loadUsers();
      await loadAuditLogs();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to suspend user.');
    } finally {
      setActionInProgress(null);
    }
  };

  const handleReactivate = async (username: string) => {
    setActionInProgress(`reactivate-${username}`);
    setError('');
    setSuccess('');
    try {
      await api.adminReactivateUser(username);
      setSuccess(`Account @${username} has been reactivated.`);
      await loadUsers();
      await loadAuditLogs();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to reactivate user.');
    } finally {
      setActionInProgress(null);
    }
  };

  const handleStartChangeRole = (u: AuthUser) => {
    setChangingRoleUser(u);
    setSelectedNewRole(u.role);
    setError('');
    setSuccess('');
  };

  const handleSaveRole = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!changingRoleUser) return;
    setSavingRole(true);
    setError('');
    setSuccess('');
    try {
      await api.adminChangeRole(changingRoleUser.username, selectedNewRole);
      setSuccess(`Role for @${changingRoleUser.username} updated to ${selectedNewRole}. Sessions invalidated.`);
      setChangingRoleUser(null);
      await loadUsers();
      await loadAuditLogs();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to change role.');
    } finally {
      setSavingRole(false);
    }
  };

  const handleDelete = async (username: string) => {
    if (!window.confirm(`Permanently delete account @${username}? This action is irreversible.`)) {
      return;
    }
    setActionInProgress(`delete-${username}`);
    setError('');
    setSuccess('');
    try {
      await api.adminDeleteUser(username);
      setSuccess(`Account @${username} deleted.`);
      await loadUsers();
      await loadAuditLogs();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete account.');
    } finally {
      setActionInProgress(null);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setSuccess('Link copied to clipboard.');
  };

  const filteredUsers = useMemo(() => {
    if (!userSearchQuery.trim()) return users;
    const q = userSearchQuery.toLowerCase();
    return users.filter(u => 
      u.username.toLowerCase().includes(q) ||
      (u.email && u.email.toLowerCase().includes(q)) ||
      (u.full_name && u.full_name.toLowerCase().includes(q)) ||
      u.role.toLowerCase().includes(q) ||
      (u.status && u.status.toLowerCase().includes(q))
    );
  }, [users, userSearchQuery]);

  const filteredAuditLogs = useMemo(() => {
    return auditLogs.filter(log => {
      if (auditFilterEventType !== 'ALL') {
        const type = (log.event_type || log.action || '').toUpperCase();
        if (type !== auditFilterEventType) return false;
      }
      if (!auditSearchQuery.trim()) return true;
      const q = auditSearchQuery.toLowerCase();
      return (
        (log.actor_username && log.actor_username.toLowerCase().includes(q)) ||
        (log.target_username && log.target_username.toLowerCase().includes(q)) ||
        (log.event_type && log.event_type.toLowerCase().includes(q)) ||
        (log.details && log.details.toLowerCase().includes(q)) ||
        (log.ip_address && log.ip_address.toLowerCase().includes(q))
      );
    });
  }, [auditLogs, auditSearchQuery, auditFilterEventType]);

  const auditEventTypes = useMemo(() => {
    const set = new Set<string>();
    auditLogs.forEach(l => {
      const type = (l.event_type || l.action || '').toUpperCase();
      if (type) set.add(type);
    });
    return Array.from(set);
  }, [auditLogs]);

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Top Header & Tab Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-bold text-indigo-400 uppercase tracking-wider mb-1">
            <ShieldCheck className="w-4 h-4" />
            <span>Administration Control Center</span>
          </div>
          <h1 className="text-2xl font-extrabold text-white tracking-tight flex items-center gap-2.5">
            {activeTab === 'users' ? (
              <>
                <UsersIcon className="w-6 h-6 text-indigo-400" />
                User Management &amp; Role Provisioning
              </>
            ) : (
              <>
                <History className="w-6 h-6 text-indigo-400" />
                Security Audit Logs &amp; Access Trail
              </>
            )}
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            {activeTab === 'users' 
              ? 'Provision authorized Audit & Enforcement accounts via single-use invitation links, manage roles, and monitor security access.'
              : 'Immutable chronological record of administrative actions, account provisioning events, role modifications, and suspensions.'}
          </p>
        </div>

        {/* Administration Section View Tabs */}
        <div className="flex items-center gap-2.5 flex-wrap">
          <div className="flex items-center p-1 bg-slate-900 border border-slate-800 rounded-xl shadow-inner">
            <button
              type="button"
              onClick={() => handleTabSwitch('users')}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeTab === 'users'
                  ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-950/40'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              <UsersIcon className="w-3.5 h-3.5" />
              <span>Users ({users.length})</span>
            </button>
            <button
              type="button"
              onClick={() => handleTabSwitch('audit')}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                activeTab === 'audit'
                  ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-950/40'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              <History className="w-3.5 h-3.5" />
              <span>Audit Logs ({auditLogs.length})</span>
            </button>
          </div>

          <button
            type="button"
            onClick={activeTab === 'users' ? loadUsers : loadAuditLogs}
            disabled={activeTab === 'users' ? loading : loadingLogs}
            className="flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-700 bg-slate-800/80 text-slate-200 text-xs font-semibold hover:bg-slate-700 transition-colors cursor-pointer disabled:opacity-50"
            title="Refresh Data"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${((activeTab === 'users' ? loading : loadingLogs)) ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>

          {activeTab === 'users' && (
            <button
              type="button"
              onClick={handleOpenProvisionModal}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold shadow-md shadow-indigo-950/50 transition-all cursor-pointer"
            >
              <UserPlus className="w-3.5 h-3.5" />
              <span>+ Provision Account</span>
            </button>
          )}
        </div>
      </div>

      {/* Status Messages */}
      {success && (
        <div className="flex items-center justify-between gap-2.5 px-4 py-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-sm font-medium animate-in fade-in">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 shrink-0" />
            <span>{success}</span>
          </div>
          <button type="button" onClick={() => setSuccess('')} className="p-1 hover:text-white cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {error && (
        <div className="flex items-center justify-between gap-2.5 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 text-sm font-medium animate-in fade-in">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 shrink-0" />
            <span>{error}</span>
          </div>
          <button type="button" onClick={() => setError('')} className="p-1 hover:text-white cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 1: USER MANAGEMENT                                               */}
      {/* ==================================================================== */}
      {activeTab === 'users' && (
        <div className="space-y-6">
          {/* Role Architecture Explainer Banner */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-2xl bg-slate-900/80 border border-sky-500/20 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-sky-400 flex items-center gap-1.5">
                  <Store className="w-4 h-4" /> Merchant Workspace
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-500/20">PREVENT</span>
              </div>
              <p className="text-xs text-slate-400">Open registration for manufacturers &amp; merchants. Self-service packaging compliance.</p>
            </div>

            <div className="p-4 rounded-2xl bg-slate-900/80 border border-indigo-500/20 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-indigo-400 flex items-center gap-1.5">
                  <SearchCheck className="w-4 h-4" /> Audit Workspace
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">VERIFY</span>
              </div>
              <p className="text-xs text-slate-400">Restricted to Quality Auditors. Provisioned by Admin with single-use activation email.</p>
            </div>

            <div className="p-4 rounded-2xl bg-slate-900/80 border border-amber-500/20 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-amber-400 flex items-center gap-1.5">
                  <ShieldAlert className="w-4 h-4" /> Enforcement Workspace
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">INVESTIGATE</span>
              </div>
              <p className="text-xs text-slate-400">Restricted to Legal Metrology Officers. Has full jurisdiction across all 3 workspaces.</p>
            </div>
          </div>

          {/* Search & Filter Bar */}
          <div className="flex items-center justify-between gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                value={userSearchQuery}
                onChange={(e) => setUserSearchQuery(e.target.value)}
                placeholder="Search by username, email, full name, or role…"
                className="w-full pl-9 pr-4 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
              />
            </div>
            <span className="text-xs text-slate-400">
              Showing <strong>{filteredUsers.length}</strong> of <strong>{users.length}</strong> accounts
            </span>
          </div>

          {/* Users Table */}
          <div className="rounded-2xl bg-slate-900 border border-slate-800 shadow-xl overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <ShieldCheck className="w-4.5 h-4.5 text-indigo-400" />
                Accounts Directory ({users.length})
              </h2>
              <span className="text-xs text-slate-400">Real-time session versioning &amp; revocation active</span>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-20 text-slate-500 text-sm">
                <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Loading accounts…
              </div>
            ) : filteredUsers.length === 0 ? (
              <div className="py-20 text-center text-slate-500 text-sm">No accounts matching criteria.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800 bg-slate-950/40 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                      <th className="py-3 px-4">User</th>
                      <th className="py-3 px-4">Role</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Jurisdiction</th>
                      <th className="py-3 px-4">Activity / Created</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-xs text-slate-300">
                    {filteredUsers.map((u) => {
                      const roleStyle = ROLE_STYLES[u.role] || ROLE_STYLES.MERCHANT_PUBLIC;
                      const statusStyle = STATUS_STYLES[u.status || 'ACTIVE'] || STATUS_STYLES.ACTIVE;
                      const RoleIcon = roleStyle.icon;
                      const isSelf = currentUser?.username === u.username;
                      const isAdmin = u.role === 'ADMIN' || u.is_admin;
                      const isInvited = u.status === 'INVITED';
                      const isSuspended = u.status === 'SUSPENDED';

                      return (
                        <tr key={u.username} className="hover:bg-slate-800/30 transition-colors">
                          {/* User Column */}
                          <td className="py-3.5 px-4">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0">
                                <RoleIcon className="w-4 h-4 text-slate-300" />
                              </div>
                              <div className="min-w-0">
                                <div className="flex items-center gap-1.5">
                                  <span className="font-bold text-white">{u.full_name || u.username}</span>
                                  {isSelf && (
                                    <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                                      You
                                    </span>
                                  )}
                                </div>
                                <span className="text-[11px] text-slate-400 block font-mono">@{u.username}</span>
                                {u.email && (
                                  <span className="text-[11px] text-slate-500 flex items-center gap-1 mt-0.5 truncate">
                                    <Mail className="w-3 h-3 shrink-0" />
                                    {u.email}
                                  </span>
                                )}
                              </div>
                            </div>
                          </td>

                          {/* Role Column */}
                          <td className="py-3.5 px-4">
                            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-bold border ${roleStyle.cls}`}>
                              <RoleIcon className="w-3.5 h-3.5" />
                              <span>{roleStyle.label}</span>
                            </span>
                          </td>

                          {/* Status Column */}
                          <td className="py-3.5 px-4">
                            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-bold border ${statusStyle.cls}`}>
                              <span className={`w-1.5 h-1.5 rounded-full ${
                                u.status === 'ACTIVE' ? 'bg-emerald-400' :
                                u.status === 'INVITED' ? 'bg-amber-400' : 'bg-rose-400'
                              }`} />
                              <span>{statusStyle.label}</span>
                            </span>
                          </td>

                          {/* Jurisdiction Column */}
                          <td className="py-3.5 px-4">
                            <span className="text-slate-300">{u.jurisdiction || 'General Jurisdiction'}</span>
                          </td>

                          {/* Timestamps Column */}
                          <td className="py-3.5 px-4 text-[11px] text-slate-400">
                            {isInvited ? (
                              <div>
                                <span className="text-amber-400 block font-semibold">Invited (Activation Pending)</span>
                                <span>{u.invited_at ? new Date(u.invited_at).toLocaleDateString() : 'Pending'}</span>
                              </div>
                            ) : u.activated_at ? (
                              <div>
                                <span className="text-emerald-400 block font-semibold">Activated</span>
                                <span>{new Date(u.activated_at).toLocaleDateString()}</span>
                              </div>
                            ) : (
                              <span>{u.created_at ? new Date(u.created_at).toLocaleDateString() : 'Active'}</span>
                            )}
                          </td>

                          {/* Actions Column */}
                          <td className="py-3.5 px-4 text-right">
                            {isAdmin || isSelf ? (
                              <span className="text-[11px] text-slate-500 italic">Protected</span>
                            ) : (
                              <div className="flex items-center justify-end gap-1.5">
                                {/* If Invited -> Resend Invite */}
                                {isInvited && (
                                  <button
                                    type="button"
                                    onClick={() => handleResendInvitation(u.username)}
                                    disabled={actionInProgress === `resend-${u.username}`}
                                    className="px-2.5 py-1 rounded-lg border border-indigo-500/30 bg-indigo-500/10 text-indigo-300 hover:bg-indigo-500/20 text-[11px] font-bold transition-colors cursor-pointer disabled:opacity-50 flex items-center gap-1"
                                    title="Resend 24-hour invitation link"
                                  >
                                    <Send className="w-3 h-3" />
                                    <span>{actionInProgress === `resend-${u.username}` ? 'Resending…' : 'Resend Link'}</span>
                                  </button>
                                )}

                                {/* If Active -> Suspend */}
                                {!isInvited && !isSuspended && (
                                  <button
                                    type="button"
                                    onClick={() => handleSuspend(u.username)}
                                    disabled={actionInProgress === `suspend-${u.username}`}
                                    className="px-2.5 py-1 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-300 hover:bg-amber-500/20 text-[11px] font-bold transition-colors cursor-pointer disabled:opacity-50 flex items-center gap-1"
                                    title="Suspend account and invalidate sessions"
                                  >
                                    <UserX className="w-3 h-3" />
                                    <span>{actionInProgress === `suspend-${u.username}` ? 'Suspending…' : 'Suspend'}</span>
                                  </button>
                                )}

                                {/* If Suspended -> Reactivate */}
                                {isSuspended && (
                                  <button
                                    type="button"
                                    onClick={() => handleReactivate(u.username)}
                                    disabled={actionInProgress === `reactivate-${u.username}`}
                                    className="px-2.5 py-1 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20 text-[11px] font-bold transition-colors cursor-pointer disabled:opacity-50 flex items-center gap-1"
                                    title="Reactivate suspended user account"
                                  >
                                    <CheckCircle2 className="w-3 h-3" />
                                    <span>{actionInProgress === `reactivate-${u.username}` ? 'Reactivating…' : 'Reactivate'}</span>
                                  </button>
                                )}

                                {/* Change Role Button */}
                                <button
                                  type="button"
                                  onClick={() => handleStartChangeRole(u)}
                                  className="px-2.5 py-1 rounded-lg border border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white text-[11px] font-bold transition-colors cursor-pointer"
                                  title="Change user's authorization role"
                                >
                                  Role
                                </button>

                                {/* Delete Button */}
                                <button
                                  type="button"
                                  onClick={() => handleDelete(u.username)}
                                  disabled={actionInProgress === `delete-${u.username}`}
                                  className="p-1.5 rounded-lg border border-slate-800 bg-slate-900 text-slate-400 hover:text-rose-400 hover:border-rose-500/40 hover:bg-rose-500/10 transition-colors cursor-pointer disabled:opacity-50"
                                  title="Delete account"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 2: SECURITY AUDIT LOGS                                           */}
      {/* ==================================================================== */}
      {activeTab === 'audit' && (
        <div className="space-y-6">
          {/* Search & Event Filter Bar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
            <div className="relative flex-1 max-w-md">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                value={auditSearchQuery}
                onChange={(e) => setAuditSearchQuery(e.target.value)}
                placeholder="Search audit trail by actor, target, event or details…"
                className="w-full pl-9 pr-4 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
              />
            </div>

            <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
              <span className="text-xs text-slate-400 font-semibold shrink-0 flex items-center gap-1">
                <Filter className="w-3 h-3" /> Event:
              </span>
              <button
                type="button"
                onClick={() => setAuditFilterEventType('ALL')}
                className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all shrink-0 cursor-pointer ${
                  auditFilterEventType === 'ALL'
                    ? 'bg-indigo-600 text-white shadow-xs'
                    : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white'
                }`}
              >
                ALL
              </button>
              {auditEventTypes.map(type => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setAuditFilterEventType(type)}
                  className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all shrink-0 cursor-pointer ${
                    auditFilterEventType === type
                      ? 'bg-indigo-600 text-white shadow-xs'
                      : 'bg-slate-900 border border-slate-800 text-slate-400 hover:text-white'
                  }`}
                >
                  {type}
                </button>
              ))}
            </div>
          </div>

          {/* Audit Logs Table */}
          <div className="rounded-2xl bg-slate-900 border border-slate-800 shadow-xl overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <History className="w-4.5 h-4.5 text-indigo-400" />
                Security Audit Log Entries ({filteredAuditLogs.length})
              </h2>
              <span className="text-xs text-slate-400">Append-only immutable audit trail</span>
            </div>

            {loadingLogs ? (
              <div className="flex items-center justify-center py-20 text-slate-500 text-sm">
                <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Loading audit trail…
              </div>
            ) : filteredAuditLogs.length === 0 ? (
              <div className="py-20 text-center text-slate-500 text-sm">No audit logs matching search criteria.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800 bg-slate-950/40 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                      <th className="py-3 px-4">Event Type</th>
                      <th className="py-3 px-4">Actor</th>
                      <th className="py-3 px-4">Target Account</th>
                      <th className="py-3 px-4">IP Address</th>
                      <th className="py-3 px-4">Timestamp</th>
                      <th className="py-3 px-4">Details / Metadata</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-xs text-slate-300">
                    {filteredAuditLogs.map((log) => {
                      const eventType = log.event_type || log.action || 'EVENT';
                      const isDanger = eventType.includes('SUSPEND') || eventType.includes('DELETE');
                      const isSuccess = eventType.includes('ACTIVATED') || eventType.includes('REACTIVATED');
                      const isWarning = eventType.includes('RESET') || eventType.includes('ROLE');

                      return (
                        <tr key={log.id} className="hover:bg-slate-800/30 transition-colors">
                          <td className="py-3 px-4">
                            <span className={`inline-flex items-center font-mono font-bold px-2 py-0.5 rounded text-[11px] border ${
                              isDanger 
                                ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                                : isSuccess
                                ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                                : isWarning
                                ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                                : 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30'
                            }`}>
                              {eventType}
                            </span>
                          </td>
                          <td className="py-3 px-4 font-mono font-semibold text-white">
                            @{log.actor_username || 'system'}
                          </td>
                          <td className="py-3 px-4 font-mono text-slate-300">
                            {log.target_username ? `@${log.target_username}` : '—'}
                          </td>
                          <td className="py-3 px-4 font-mono text-slate-400 text-[11px]">
                            {log.ip_address || '127.0.0.1'}
                          </td>
                          <td className="py-3 px-4 text-slate-400 text-[11px] whitespace-nowrap">
                            {log.created_at ? new Date(log.created_at).toLocaleString() : '—'}
                          </td>
                          <td className="py-3 px-4 text-slate-300 text-[11px]">
                            {log.details ? (
                              <span className="font-mono bg-slate-950/60 px-2 py-1 rounded border border-slate-800 block max-w-md truncate">
                                {log.details}
                              </span>
                            ) : (
                              <span className="text-slate-500">—</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* PROVISION ACCOUNT MODAL                                              */}
      {/* ==================================================================== */}
      {showProvisionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl max-w-lg w-full p-6 space-y-5">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-indigo-500/15 border border-indigo-500/30 text-indigo-400">
                  <UserPlus className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Provision Authorized Account</h3>
                  <p className="text-xs text-slate-400">Issues a secure, single-use 24-hour activation link</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowProvisionModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {lastProvisionResult ? (
              <div className="space-y-4">
                <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 space-y-2">
                  <div className="flex items-center gap-2 font-bold text-sm">
                    <CheckCircle2 className="w-5 h-5 shrink-0" />
                    <span>Account Provisioned Successfully!</span>
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    An activation email has been dispatched to <strong className="text-white font-mono">{lastProvisionResult.email}</strong> for role <strong className="text-white">{lastProvisionResult.role}</strong>.
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 space-y-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                    Direct Activation Link (24-Hour Expiry)
                  </span>
                  <div className="flex items-center gap-2">
                    <input
                      readOnly
                      value={lastProvisionResult.invitation_url}
                      className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-indigo-300 font-mono select-all outline-none"
                    />
                    <button
                      type="button"
                      onClick={() => copyToClipboard(lastProvisionResult.invitation_url)}
                      className="p-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors cursor-pointer shrink-0"
                      title="Copy invitation URL"
                    >
                      <Copy className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => {
                      setLastProvisionResult(null);
                      setProvisionForm({ ...EMPTY_PROVISION_FORM });
                    }}
                    className="px-4 py-2 rounded-xl border border-slate-700 bg-slate-800 text-slate-300 text-xs font-bold hover:bg-slate-700 transition-colors cursor-pointer"
                  >
                    Provision Another
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowProvisionModal(false)}
                    className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-colors cursor-pointer"
                  >
                    Done
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleProvisionSubmit} className="space-y-4">
                <div>
                  <label className="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">
                    Target Role *
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setProvisionForm({ ...provisionForm, role: 'AUDIT_OFFICER' })}
                      className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                        provisionForm.role === 'AUDIT_OFFICER'
                          ? 'bg-indigo-500/15 border-indigo-500/50 text-white ring-2 ring-indigo-500/20'
                          : 'bg-slate-950/50 border-slate-800 text-slate-400 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center gap-1.5 font-bold text-xs">
                        <SearchCheck className="w-4 h-4 text-indigo-400" />
                        <span>Audit Officer</span>
                      </div>
                      <p className="text-[10px] text-slate-400 mt-1">Audit Workspace (VERIFY) only</p>
                    </button>

                    <button
                      type="button"
                      onClick={() => setProvisionForm({ ...provisionForm, role: 'ENFORCEMENT_OFFICER' })}
                      className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                        provisionForm.role === 'ENFORCEMENT_OFFICER'
                          ? 'bg-amber-500/15 border-amber-500/50 text-white ring-2 ring-amber-500/20'
                          : 'bg-slate-950/50 border-slate-800 text-slate-400 hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-center gap-1.5 font-bold text-xs">
                        <ShieldAlert className="w-4 h-4 text-amber-400" />
                        <span>Enforcement Officer</span>
                      </div>
                      <p className="text-[10px] text-slate-400 mt-1">Merchant, Audit &amp; Enforcement</p>
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">
                    Username *
                  </label>
                  <input
                    required
                    value={provisionForm.username}
                    onChange={(e) => setProvisionForm({ ...provisionForm, username: e.target.value })}
                    placeholder="e.g. officer_north"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950/70 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">
                    Authorized Recovery Email *
                  </label>
                  <input
                    type="email"
                    required
                    value={provisionForm.email}
                    onChange={(e) => setProvisionForm({ ...provisionForm, email: e.target.value })}
                    placeholder="e.g. officer@doca.gov.in"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950/70 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">
                      Full Name
                    </label>
                    <input
                      value={provisionForm.full_name}
                      onChange={(e) => setProvisionForm({ ...provisionForm, full_name: e.target.value })}
                      placeholder="e.g. Dr. A. Verma"
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950/70 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">
                      Jurisdiction / Dept
                    </label>
                    <input
                      value={provisionForm.jurisdiction}
                      onChange={(e) => setProvisionForm({ ...provisionForm, jurisdiction: e.target.value })}
                      placeholder="e.g. North Zone / QA"
                      className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950/70 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/60"
                    />
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-slate-950/50 border border-slate-800 text-[11px] text-slate-400 space-y-1">
                  <div className="font-semibold text-slate-300 flex items-center gap-1.5">
                    <KeyRound className="w-3.5 h-3.5 text-indigo-400" />
                    <span>How activation works:</span>
                  </div>
                  <p>
                    The invitee receives a secure single-use activation link. They choose their own password (min 8 characters) to activate their account.
                  </p>
                </div>

                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowProvisionModal(false)}
                    className="px-4 py-2.5 rounded-xl border border-slate-700 bg-slate-800 text-slate-300 text-xs font-semibold hover:bg-slate-700 transition-colors cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={provisioning}
                    className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all shadow-md cursor-pointer disabled:opacity-50 flex items-center gap-2"
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>{provisioning ? 'Dispatching…' : 'Send Invitation Link'}</span>
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* CHANGE ROLE MODAL                                                    */}
      {/* ==================================================================== */}
      {changingRoleUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <form onSubmit={handleSaveRole} className="bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-indigo-500/15 border border-indigo-500/30 text-indigo-400">
                  <KeyRound className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Change Role</h3>
                  <p className="text-xs text-slate-400">Update permissions for @{changingRoleUser.username}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setChangingRoleUser(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-2">
              <label className="block text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                Select New Role
              </label>

              {(['AUDIT_OFFICER', 'ENFORCEMENT_OFFICER', 'MERCHANT_PUBLIC'] as BackendRole[]).map((r) => {
                const style = ROLE_STYLES[r];
                const Icon = style.icon;
                const isSelected = selectedNewRole === r;

                return (
                  <div
                    key={r}
                    onClick={() => setSelectedNewRole(r)}
                    className={`p-3 rounded-xl border flex items-center justify-between cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-indigo-500/15 border-indigo-500/50 text-white ring-2 ring-indigo-500/20'
                        : 'bg-slate-950/50 border-slate-800 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <Icon className="w-4 h-4 text-slate-300" />
                      <div>
                        <span className="text-xs font-bold text-white block">{style.label}</span>
                        <span className="text-[10px] text-slate-400">
                          {r === 'AUDIT_OFFICER' ? 'Access: Audit Workspace only' :
                           r === 'ENFORCEMENT_OFFICER' ? 'Access: Merchant, Audit & Enforcement' :
                           'Access: Merchant Workspace only'}
                        </span>
                      </div>
                    </div>
                    {isSelected && <CheckCircle2 className="w-4 h-4 text-indigo-400 shrink-0" />}
                  </div>
                );
              })}
            </div>

            <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300">
              <strong className="block font-bold">Immediate Session Invalidation:</strong>
              Changing a user's role immediately invalidates their active JWT sessions and forces them to re-authenticate with the updated role.
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setChangingRoleUser(null)}
                className="px-4 py-2 rounded-xl border border-slate-700 bg-slate-800 text-slate-300 text-xs font-semibold hover:bg-slate-700 transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={savingRole}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all shadow-md cursor-pointer disabled:opacity-50 flex items-center gap-1.5"
              >
                {savingRole ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                <span>{savingRole ? 'Updating…' : 'Apply Role Change'}</span>
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}