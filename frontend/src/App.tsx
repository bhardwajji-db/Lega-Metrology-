import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { ThemeProvider } from './context/ThemeContext';
import { LanguageProvider } from './context/LanguageContext';
import { WorkspaceProvider } from './context/WorkspaceContext';
import { RoleProvider } from './context/RoleContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/layout/Layout';
import Dashboard from './pages/Dashboard';
import DemoCases from './pages/DemoCases';
import Analyze from './pages/Analyze';
import AnalyzeListing from './pages/AnalyzeListing';
import Results from './pages/Results';
import History from './pages/History';
import ComplianceRules from './pages/ComplianceRules';
import About from './pages/About';
import Login from './pages/Login';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import ActivateAccount from './pages/ActivateAccount';
import AdminUsers from './pages/AdminUsers';
import AdminLogin from './pages/AdminLogin';
import AccountSettings from './pages/AccountSettings';
import ServerSetup from './pages/ServerSetup';
import { LiveScannerPage } from './pages/LiveScannerPage';
import PrePrintCompliance from './pages/PrePrintCompliance';
import VersionComparison from './pages/VersionComparison';
import OfficerDashboard from './pages/OfficerDashboard';
import ReviewWorkspace from './pages/ReviewWorkspace';
import ErrorBoundary from './components/ui/ErrorBoundary';

function RequireAuth({ children }: { children: ReactNode }) {
  const { token, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950">
        <div className="flex items-center gap-3 text-slate-400">
          <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Restoring session…</span>
        </div>
      </div>
    );
  }

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

function AdminOnly({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();

  if (!user || user.role !== 'ADMIN') {
    return <Navigate to="/" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

function App() {
  return (
    <ThemeProvider>
      <LanguageProvider>
        <AuthProvider>
          <WorkspaceProvider>
            <RoleProvider>
              <BrowserRouter>
                <Routes>
                  {/* Public pages */}
                  <Route path="/login" element={<Login />} />
                  <Route path="/server-setup" element={<ServerSetup />} />
                  <Route path="/admin/login" element={<AdminLogin />} />
                  <Route path="/forgot-password" element={<ForgotPassword />} />
                  <Route path="/reset-password" element={<ResetPassword />} />
                  <Route path="/activate" element={<ActivateAccount />} />
                  <Route path="/activate-account" element={<ActivateAccount />} />
                  <Route element={<Layout />}>
                    <Route path="/demo" element={<DemoCases />} />
                    <Route path="/rules" element={<ComplianceRules />} />
                    <Route path="/about" element={<About />} />

                    {/* Protected pages (role-based access) */}
                    <Route path="/" element={<RequireAuth><Dashboard /></RequireAuth>} />
                    <Route path="/dashboard" element={<Navigate to="/" replace />} />
                    <Route path="/scanner" element={<RequireAuth><LiveScannerPage /></RequireAuth>} />
                    <Route path="/live-scanner" element={<Navigate to="/scanner" replace />} />
                    <Route path="/live" element={<Navigate to="/scanner" replace />} />
                    <Route path="/scan" element={<Navigate to="/scanner" replace />} />
                    <Route path="/barcode-scanner" element={<Navigate to="/scanner" replace />} />
                    <Route path="/barcode" element={<Navigate to="/scanner" replace />} />
                    <Route path="/analyze" element={<RequireAuth><Analyze /></RequireAuth>} />
                    <Route path="/analyze-listing" element={<RequireAuth><AnalyzeListing /></RequireAuth>} />
                    <Route path="/listing" element={<Navigate to="/analyze-listing" replace />} />
                    <Route path="/listings" element={<Navigate to="/analyze-listing" replace />} />
                    <Route path="/preprint" element={<RequireAuth><PrePrintCompliance /></RequireAuth>} />
                    <Route path="/pre-print" element={<Navigate to="/preprint" replace />} />
                    <Route path="/versions" element={<RequireAuth><VersionComparison /></RequireAuth>} />
                    <Route path="/version" element={<Navigate to="/versions" replace />} />
                    <Route path="/version-comparison" element={<Navigate to="/versions" replace />} />
                    <Route path="/reviews" element={<RequireAuth><OfficerDashboard /></RequireAuth>} />
                    <Route path="/review" element={<Navigate to="/reviews" replace />} />
                    <Route path="/officer" element={<Navigate to="/reviews" replace />} />
                    <Route path="/reviews/:reviewId" element={<RequireAuth><ReviewWorkspace /></RequireAuth>} />
                    <Route path="/results/:id" element={<RequireAuth><ErrorBoundary><Results /></ErrorBoundary></RequireAuth>} />
                    <Route path="/history" element={<RequireAuth><History /></RequireAuth>} />
                    <Route path="/settings" element={<RequireAuth><AccountSettings /></RequireAuth>} />
                    <Route path="/admin/users" element={<RequireAuth><AdminOnly><AdminUsers defaultTab="users" /></AdminOnly></RequireAuth>} />
                    <Route path="/admin/audit-logs" element={<RequireAuth><AdminOnly><AdminUsers defaultTab="audit" /></AdminOnly></RequireAuth>} />
                  </Route>

                  <Route path="*" element={<Navigate to="/" />} />
                </Routes>
              </BrowserRouter>
            </RoleProvider>
          </WorkspaceProvider>
        </AuthProvider>
      </LanguageProvider>
    </ThemeProvider>
  );
}

export default App;