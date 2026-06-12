import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import Layout from './components/Layout'
import ErrorBoundary from './components/ErrorBoundary'
import { ToastProvider } from './components/ToastProvider'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import { useAuth, AuthProvider } from './hooks/useAuth'
import AdminLayout from './components/AdminLayout'
import AdminRoute from './components/AdminRoute'

const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const ExecutePage = lazy(() => import('./pages/ExecutePage'))
const HistoryPage = lazy(() => import('./pages/HistoryPage'))
const BillingPage = lazy(() => import('./pages/BillingPage'))
const BacktestPage = lazy(() => import('./pages/BacktestPage'))
const ReportsPage = lazy(() => import('./pages/ReportsPage'))
const OnboardingPage = lazy(() => import('./pages/OnboardingPage'))
const TermsPage = lazy(() => import('./pages/TermsPage'))
const PrivacyPage = lazy(() => import('./pages/PrivacyPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))
const TeamPage = lazy(() => import('./pages/TeamPage'))
const DataRightsPage = lazy(() => import('./pages/DataRightsPage'))
const OpsPage = lazy(() => import('./pages/OpsPage'))
const MfaPage = lazy(() => import('./pages/MfaPage'))
const MarketPage = lazy(() => import('./pages/MarketPage'))
const ShareCardPage = lazy(() => import('./pages/ShareCardPage'))
const VerifyEmailPage = lazy(() => import('./pages/VerifyEmailPage'))

function PageFallback() {
  return (
    <div className="flex min-h-[55vh] items-center justify-center">
      <div className="glass-control flex items-center gap-3 px-4 py-3 text-sm text-text-secondary">
        <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-accent" />
        正在加载工作台
      </div>
    </div>
  )
}

function ProtectedRoute({ authed, children }: { authed: boolean; children: React.ReactNode }) {
  const location = useLocation()
  if (!authed) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return children
}

function AppContent() {
  const { authed, user, loading, loadUser, clearAuth } = useAuth()

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg">
        <div className="glass-control px-5 py-4 text-sm text-text-secondary">Kenne Index 正在恢复会话</div>
      </div>
    )
  }

  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route path="/" element={<HomePage authed={authed} />} />
        <Route
          path="/login"
          element={authed ? <Navigate to="/app/dashboard" replace /> : <LoginPage onLogin={loadUser} />}
        />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/market" element={<MarketPage />} />
        <Route path="/share-card" element={<ShareCardPage />} />
        <Route
          path="/app"
          element={
            <ProtectedRoute authed={authed}>
              <Layout user={user} onLogout={clearAuth} />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/app/dashboard" replace />} />
          <Route path="onboarding" element={<OnboardingPage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="execute" element={<ExecutePage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="billing" element={<BillingPage />} />
          <Route path="backtest" element={<BacktestPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="data-rights" element={<DataRightsPage />} />
          <Route path="mfa" element={<MfaPage />} />
        </Route>
        <Route
          path="/admin"
          element={
            <ProtectedRoute authed={authed}>
              <AdminRoute>
                <AdminLayout user={user} onLogout={clearAuth} />
              </AdminRoute>
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/admin/ops" replace />} />
          <Route path="ops" element={<OpsPage />} />
          <Route path="team" element={<TeamPage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  )
}

function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <AuthProvider>
          <AppContent />
        </AuthProvider>
      </ToastProvider>
    </ErrorBoundary>
  )
}

export default App
