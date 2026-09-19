import { useState, useEffect } from 'react';
import { Outlet, useLocation, Link } from 'react-router-dom';
import Sidebar from './Sidebar';
import { useWorkspace, WORKSPACE_DEFINITIONS } from '../../context/WorkspaceContext';
import { useAuth } from '../../context/AuthContext';
import { useLanguage } from '../../context/LanguageContext';
import { type WorkspaceType } from '../../types';
import { Menu, ChevronRight, Sparkles, SearchCheck, ShieldAlert, Store, Lock, Check } from 'lucide-react';
import ThemeToggle from '../ui/ThemeToggle';
import LanguageSelector from '../ui/LanguageSelector';
import ServerStatus from './ServerStatus';

export default function Layout() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user } = useAuth();
  const { currentWorkspace, setWorkspace, workspaceInfo, isWorkspaceAllowed } = useWorkspace();
  const { t } = useLanguage();
  const [workspaceDropdownOpen, setWorkspaceDropdownOpen] = useState(false);

  // Close workspace dropdown on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setWorkspaceDropdownOpen(false);
      }
    };
    if (workspaceDropdownOpen) {
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [workspaceDropdownOpen]);
  
  const getPageInfo = () => {
    const path = location.pathname;
    if (path === '/') {
      return { 
        title: `${workspaceInfo.shortLabel} ${t('navigation.dashboard')}`, 
        subtitle: `${workspaceInfo.tagline} • Legal Metrology & FSSAI Compliance Overview`,
        breadcrumb: t('navigation.dashboard')
      };
    }
    if (path.startsWith('/demo')) {
      return { 
        title: t('navigation.demo_mode'), 
        subtitle: 'Benchmark Packaging Scenarios for Evaluation',
        breadcrumb: t('navigation.demo_mode')
      };
    }
    if (path.startsWith('/analyze')) {
      return { 
        title: currentWorkspace === 'MERCHANT' ? t('navigation.analyze_package') : currentWorkspace === 'AUDIT' ? 'Technical Packaging Verification' : 'Statutory Compliance Inspection', 
        subtitle: 'Upload multi-angle packaging artwork for AI statutory verification',
        breadcrumb: t('navigation.screening')
      };
    }
    if (path.startsWith('/results')) {
      return { 
        title: t('results.title'), 
        subtitle: 'Statutory rule findings, OCR evidence localization & corrective actions',
        breadcrumb: t('results.title')
      };
    }
    if (path.startsWith('/history')) {
      return { 
        title: currentWorkspace === 'ENFORCEMENT' ? 'Inspection Case Records' : currentWorkspace === 'AUDIT' ? 'Audited Compliance Logs' : t('navigation.screening_history'), 
        subtitle: 'Audited commodity screenings and historical compliance reports',
        breadcrumb: t('navigation.screening_history')
      };
    }
    if (path.startsWith('/rules')) {
      return { 
        title: t('navigation.compliance_rules'), 
        subtitle: 'Legal Metrology (Packaged Commodities) Rules 2011 & FSSAI Regulations',
        breadcrumb: t('navigation.compliance_rules')
      };
    }
    if (path.startsWith('/admin/users')) {
      return { 
        title: t('navigation.user_management'), 
        subtitle: 'Provision authorized officers, manage roles, and enforce workspace access',
        breadcrumb: `${t('navigation.administration')} / ${t('navigation.user_management')}`
      };
    }
    if (path.startsWith('/admin/audit-logs')) {
      return { 
        title: t('navigation.security_audit_logs'), 
        subtitle: 'Immutable chronological record of administrative actions and security events',
        breadcrumb: `${t('navigation.administration')} / ${t('navigation.security_audit_logs')}`
      };
    }
    if (path.startsWith('/settings')) {
      return { 
        title: t('navigation.settings'), 
        subtitle: 'Manage recovery email, password, and session preferences',
        breadcrumb: t('navigation.settings')
      };
    }
    return { title: 'MetrCheck AI', subtitle: '', breadcrumb: '' };
  };

  const pageInfo = getPageInfo();

  return (
    <div className="flex h-screen bg-slate-50/70 dark:bg-slate-950 overflow-hidden font-sans text-slate-900 dark:text-slate-100 antialiased transition-colors duration-200">
      {/* Skip to Main Content Link for Keyboard / Screen Reader Accessibility */}
      <a href="#main-content" className="skip-to-content">
        Skip to main content
      </a>

      {/* Sidebar Navigation */}
      <Sidebar 
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed(!collapsed)}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top App Header */}
        <header className="bg-white dark:bg-slate-900 border-b border-slate-200/80 dark:border-slate-800 h-16 flex items-center justify-between px-4 sm:px-6 lg:px-8 shrink-0 relative z-30 transition-colors duration-200">
          <div className="flex items-center gap-3 min-w-0">
            {/* Mobile Hamburger */}
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="p-2 -ml-1 text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg md:hidden transition-colors cursor-pointer"
              aria-label="Open navigation drawer"
            >
              <Menu className="w-5 h-5" />
            </button>

            {/* Breadcrumb & Title */}
            <div className="flex flex-col min-w-0">
              <div className="flex items-center gap-1.5 text-xs text-slate-400 dark:text-slate-500 font-medium">
                <Link to="/" className="hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors">MetrCheck</Link>
                {pageInfo.breadcrumb && (
                  <>
                    <ChevronRight className="w-3 h-3 text-slate-300 dark:text-slate-600" />
                    <span className="text-slate-600 dark:text-slate-400 truncate">{pageInfo.breadcrumb}</span>
                  </>
                )}
              </div>
              <h1 className="text-base sm:text-lg font-bold text-slate-900 dark:text-slate-100 truncate tracking-tight">
                {pageInfo.title}
              </h1>
            </div>
          </div>

          {/* Right Header: Workspace Switcher, Badges & Theme Toggle */}
          <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
            {/* Workspace Switcher Dropdown */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setWorkspaceDropdownOpen(prev => !prev)}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-lg border transition-all cursor-pointer ${
                  currentWorkspace === 'ENFORCEMENT'
                    ? 'bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-700/80 shadow-2xs'
                    : currentWorkspace === 'AUDIT'
                    ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border-indigo-200/80 dark:border-indigo-800'
                    : 'bg-sky-50 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-800'
                }`}
                title="Switch Active Workspace"
              >
                {currentWorkspace === 'ENFORCEMENT' ? (
                  <ShieldAlert className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                ) : currentWorkspace === 'AUDIT' ? (
                  <SearchCheck className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                ) : (
                  <Store className="w-3.5 h-3.5 text-sky-600 dark:text-sky-400" />
                )}
                <span className="hidden sm:inline font-bold">{workspaceInfo.label}</span>
                <span className="sm:hidden font-bold">{workspaceInfo.shortLabel}</span>
              </button>

              {workspaceDropdownOpen && (
                <>
                  {/* Backdrop overlay */}
                  <div 
                    className="fixed inset-0 z-40 bg-black/10 dark:bg-black/30 backdrop-blur-[0.5px]" 
                    onClick={() => setWorkspaceDropdownOpen(false)} 
                  />
                  <div className="absolute right-0 mt-2 w-80 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/90 dark:border-slate-800 shadow-2xl p-2.5 z-50 space-y-1.5 ring-1 ring-black/5 animate-in fade-in duration-150">
                    <div className="px-3 py-1.5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
                      <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider block">Active Workspace</span>
                      <span className="text-[10px] text-slate-400 font-mono font-semibold">
                        Role: {user?.role === 'ADMIN' ? 'Admin' : user?.role === 'ENFORCEMENT_OFFICER' ? 'Officer' : user?.role === 'AUDIT_OFFICER' ? 'Audit Officer' : 'Merchant'}
                      </span>
                    </div>

                    {(['MERCHANT', 'AUDIT', 'ENFORCEMENT'] as WorkspaceType[]).map(wsKey => {
                      const info = WORKSPACE_DEFINITIONS[wsKey];
                      const isSelected = currentWorkspace === wsKey;
                      const isAllowed = isWorkspaceAllowed(wsKey);

                      const getIcon = () => {
                        if (wsKey === 'ENFORCEMENT') return <ShieldAlert className="w-4 h-4 text-amber-500" />;
                        if (wsKey === 'AUDIT') return <SearchCheck className="w-4 h-4 text-indigo-500" />;
                        return <Store className="w-4 h-4 text-sky-500" />;
                      };

                      if (!isAllowed) {
                        return (
                          <div
                            key={wsKey}
                            className="w-full p-2.5 rounded-xl text-xs bg-slate-50/60 dark:bg-slate-800/30 border border-slate-200/40 dark:border-slate-800/40 opacity-60 flex flex-col gap-0.5 cursor-not-allowed select-none"
                            title="Requires Administrator or Enforcement Official login"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-bold flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
                                {getIcon()}
                                {info.label}
                              </span>
                              <span className="text-[10px] font-semibold text-slate-400 flex items-center gap-1">
                                <Lock className="w-3 h-3" /> Locked
                              </span>
                            </div>
                            <span className="text-[11px] text-slate-400 dark:text-slate-500 leading-tight">
                              Requires Enforcement Official or Administrator credentials.
                            </span>
                          </div>
                        );
                      }

                      return (
                        <button
                          key={wsKey}
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setWorkspace(wsKey);
                            setWorkspaceDropdownOpen(false);
                          }}
                          className={`w-full text-left p-2.5 rounded-xl text-xs transition flex flex-col gap-1 cursor-pointer relative z-50 ${
                            isSelected 
                              ? 'bg-indigo-50 dark:bg-indigo-950/70 border border-indigo-200 dark:border-indigo-800 text-indigo-950 dark:text-indigo-200 font-medium' 
                              : 'hover:bg-slate-100 dark:hover:bg-slate-800/80 text-slate-700 dark:text-slate-300'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-bold flex items-center gap-1.5">
                              {getIcon()}
                              {info.label}
                            </span>
                            <div className="flex items-center gap-1.5">
                              <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded tracking-wider ${
                                info.coreAction === 'PREVENT'
                                  ? 'bg-sky-100 dark:bg-sky-950 text-sky-700 dark:text-sky-300'
                                  : info.coreAction === 'VERIFY'
                                  ? 'bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300'
                                  : 'bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300'
                              }`}>
                                {info.coreAction}
                              </span>
                              {isSelected && (
                                <span className="text-[10px] font-bold text-indigo-600 dark:text-indigo-400 px-1.5 py-0.5 rounded bg-indigo-100/60 dark:bg-indigo-900/40 flex items-center gap-0.5">
                                  <Check className="w-3 h-3" /> ACTIVE
                                </span>
                              )}
                            </div>
                          </div>
                          <span className="text-[11px] text-slate-500 dark:text-slate-400 leading-tight">
                            {info.tagline}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </>
              )}
            </div>

            <Link
              to="/demo"
              className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200/80 dark:border-indigo-800/80 hover:bg-indigo-100/70 dark:hover:bg-indigo-900/60 transition-colors"
            >
              <Sparkles className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
              <span>SIH Demo</span>
            </Link>

            {/* Server Status Indicator */}
            <ServerStatus />

            {/* Language Selector */}
            <LanguageSelector />

            {/* Theme Toggle Button */}
            <ThemeToggle />
          </div>
        </header>

        {/* Scrollable Page Body */}
        <main id="main-content" tabIndex={-1} className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 focus:outline-none">
          <div className="max-w-7xl mx-auto space-y-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
