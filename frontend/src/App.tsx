import { Navigate, NavLink, Outlet, Route, BrowserRouter, Routes } from "react-router-dom"
import { AuthProvider, useAuth } from "./auth"
import { IntakeDemoComparePage } from "./demos/intake/ComparePage"
import { IntakeDemoLightboxPage } from "./demos/intake/LightboxPage"
import { IntakeDemoPickerPage } from "./demos/intake/PickerPage"
import { IntakeDemoSideBySidePage } from "./demos/intake/SideBySidePage"
import { TwFixAutoDigitPage } from "./demos/intake/TwFixAutoDigitPage"
import { TwFixConflictPage } from "./demos/intake/TwFixConflictPage"
import { TwFixDualPassPage } from "./demos/intake/TwFixDualPassPage"
import { TwFixEditablePage } from "./demos/intake/TwFixEditablePage"
import { TwFixPickerPage } from "./demos/intake/TwFixPickerPage"
import { TwFixPreferScalePage } from "./demos/intake/TwFixPreferScalePage"
import { TwFixRecheckPage } from "./demos/intake/TwFixRecheckPage"
import { IntakeDemoWizardPage } from "./demos/intake/WizardPage"
import { AgentRunsPage } from "./pages/AgentRunsPage"
import { AuditPage } from "./pages/AuditPage"
import { CargoPage } from "./pages/CargoPage"
import { DashboardPage } from "./pages/DashboardPage"
import { ExitPage } from "./pages/ExitPage"
import { ExpiryPage } from "./pages/ExpiryPage"
import { LoginPage } from "./pages/LoginPage"
import { PdfPage } from "./pages/PdfPage"
import { TrackerPage } from "./pages/TrackerPage"
import { UsersPage } from "./pages/UsersPage"

function RequireAuth() {
  const { user, loading } = useAuth()
  if (loading) return <p className="page-loading">Loading…</p>
  if (!user) return <Navigate to="/login" replace />
  return <Outlet />
}

function Shell() {
  const { user, logout } = useAuth()
  return (
    <>
      <header className="topbar">
        <div className="brand">
          <span className="mark">KA</span>
          <div>
            <strong>Karam Al Arab</strong>
            <small>Load plan</small>
          </div>
        </div>
        <nav className="nav">
          {user?.role === "admin" ? <NavLink to="/dashboard">Dashboard</NavLink> : null}
          <NavLink to="/tracker">Tracker</NavLink>
          <NavLink to="/sea">Sea</NavLink>
          <NavLink to="/air">Air</NavLink>
          <NavLink to="/exit">Exit</NavLink>
          <NavLink to="/expiry">Expiry</NavLink>
          <NavLink to="/audit">Audit</NavLink>
          <NavLink to="/pdf">PDF</NavLink>
          {user?.role === "admin" ? <NavLink to="/runs">Tracking</NavLink> : null}
          {user?.role === "admin" ? <NavLink to="/demo/intake">UI demos</NavLink> : null}
          {user?.role === "admin" ? <NavLink to="/users">Users</NavLink> : null}
        </nav>
        <div className="who">
          <span>{user?.email}</span>
          <button className="btn-quiet" type="button" onClick={() => logout()}>Log out</button>
        </div>
      </header>
      <Outlet />
    </>
  )
}

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<RequireAuth />}>
            <Route element={<Shell />}>
              <Route path="/" element={<Navigate to="/sea" replace />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/tracker" element={<TrackerPage />} />
              <Route path="/sea" element={<CargoPage kind="sea" />} />
              <Route path="/air" element={<CargoPage kind="air" />} />
              <Route path="/exit" element={<ExitPage />} />
              <Route path="/expiry" element={<ExpiryPage />} />
              <Route path="/audit" element={<AuditPage />} />
              <Route path="/intake" element={<Navigate to="/sea" replace />} />
              <Route path="/pdf" element={<PdfPage />} />
              <Route path="/runs" element={<AgentRunsPage />} />
              <Route path="/demo/intake" element={<IntakeDemoPickerPage />} />
              <Route path="/demo/intake/side-by-side" element={<IntakeDemoSideBySidePage />} />
              <Route path="/demo/intake/compare" element={<IntakeDemoComparePage />} />
              <Route path="/demo/intake/wizard" element={<IntakeDemoWizardPage />} />
              <Route path="/demo/intake/lightbox" element={<IntakeDemoLightboxPage />} />
              <Route path="/demo/intake/tw-fix" element={<TwFixPickerPage />} />
              <Route path="/demo/intake/tw-fix/editable" element={<TwFixEditablePage />} />
              <Route path="/demo/intake/tw-fix/recheck" element={<TwFixRecheckPage />} />
              <Route path="/demo/intake/tw-fix/auto-digit" element={<TwFixAutoDigitPage />} />
              <Route path="/demo/intake/tw-fix/prefer-scale" element={<TwFixPreferScalePage />} />
              <Route path="/demo/intake/tw-fix/dual-pass" element={<TwFixDualPassPage />} />
              <Route path="/demo/intake/tw-fix/conflict" element={<TwFixConflictPage />} />
              <Route path="/users" element={<UsersPage />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
