import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { ThemeProvider } from './context/ThemeContext';
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
      <AuthProvider>
        <WorkspaceProvider>
          <RoleProvider>
            <BrowserRouter>
              <Routes>
                {/* Public pages */}
                <Route path="/login" element={<Login />} />
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
                  <Route path="/analyze" element={<RequireAuth><Analyze /></RequireAuth>} />
                  <Route path="/analyze-listing" element={<RequireAuth><AnalyzeListing /></RequireAuth>} />
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
    </ThemeProvider>
  );
}

export default App;