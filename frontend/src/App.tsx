import { Navigate, NavLink, Outlet, Route, BrowserRouter, Routes } from "react-router-dom"
import { AuthProvider, useAuth } from "./auth"
import { AgentRunsPage } from "./pages/AgentRunsPage"
import { AirShipmentPicturesPage } from "./pages/AirShipmentPicturesPage"
import { AuditPage } from "./pages/AuditPage"
import { CargoPage } from "./pages/CargoPage"
import { ContainerLoadingPage } from "./pages/ContainerLoadingPage"
import { DashboardPage } from "./pages/DashboardPage"
import { ExpensesPage } from "./pages/ExpensesPage"
import { ExitPage } from "./pages/ExitPage"
import { GraphKnowledgePage } from "./pages/GraphKnowledgePage"
import { ImageInvoicesPage } from "./pages/ImageInvoicesPage"
import { InvoicesPage } from "./pages/InvoicesPage"
import { ExpiryPage } from "./pages/ExpiryPage"
import { LoginPage } from "./pages/LoginPage"
import { PdfPage } from "./pages/PdfPage"
import { TrackerPage } from "./pages/TrackerPage"
import { SettingsPage } from "./pages/SettingsPage"
import {
  AIR_TRACKER_CONFIG,
  CONTAINERS_CONFIG,
  COO_CONFIG,
  FLIGHT_SCHEDULE_CONFIG,
  SheetTrackerPage,
} from "./pages/SheetTrackerPage"
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
          <img className="mark-logo" src="/karam-mark.svg" alt="" />
          <div>
            <strong>Karam Al Arab</strong>
            <small>Load plan</small>
          </div>
        </div>
        <nav className="nav">
          {user?.role === "admin" ? <NavLink to="/dashboard">Dashboard</NavLink> : null}
          <NavLink to="/graph-knowledge">Graph knowledge</NavLink>
          <NavLink to="/tracker">Tracker</NavLink>
          <NavLink to="/sea">Sea</NavLink>
          <NavLink to="/air">Air</NavLink>
          <NavLink to="/air-shipment-pictures">Air shipment pictures</NavLink>
          <NavLink to="/exit">Exit</NavLink>
          <NavLink to="/containers">Containers</NavLink>
          <NavLink to="/container-loading">Container loading</NavLink>
          <NavLink to="/invoices">Invoices</NavLink>
          <NavLink to="/image-invoices">Image invoices</NavLink>
          <NavLink to="/expenses">Expenses</NavLink>
          <NavLink to="/air-tracker">Air tracker</NavLink>
          <NavLink to="/coo">COO</NavLink>
          <NavLink to="/flight-schedule">Flight schedule</NavLink>
          <NavLink to="/expiry">Expiry</NavLink>
          <NavLink to="/audit">Audit</NavLink>
          <NavLink to="/pdf">PDF</NavLink>
          {user?.role === "admin" ? <NavLink to="/runs">Tracking</NavLink> : null}
          {user?.role === "admin" ? <NavLink to="/users">Users</NavLink> : null}
          {user?.role === "admin" ? <NavLink to="/settings">Settings</NavLink> : null}
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
              <Route path="/graph-knowledge" element={<GraphKnowledgePage />} />
              <Route path="/tracker" element={<TrackerPage />} />
              <Route path="/sea" element={<CargoPage kind="sea" />} />
              <Route path="/air" element={<CargoPage kind="air" />} />
              <Route path="/air-shipment-pictures" element={<AirShipmentPicturesPage />} />
              <Route path="/exit" element={<ExitPage />} />
              <Route path="/containers" element={<SheetTrackerPage config={CONTAINERS_CONFIG} />} />
              <Route path="/container-loading" element={<ContainerLoadingPage />} />
              <Route path="/invoices" element={<InvoicesPage />} />
              <Route path="/image-invoices" element={<ImageInvoicesPage />} />
              <Route path="/expenses" element={<ExpensesPage />} />
              <Route path="/air-tracker" element={<SheetTrackerPage config={AIR_TRACKER_CONFIG} />} />
              <Route path="/coo" element={<SheetTrackerPage config={COO_CONFIG} />} />
              <Route path="/flight-schedule" element={<SheetTrackerPage config={FLIGHT_SCHEDULE_CONFIG} />} />
              <Route path="/expiry" element={<ExpiryPage />} />
              <Route path="/audit" element={<AuditPage />} />
              <Route path="/intake" element={<Navigate to="/sea" replace />} />
              <Route path="/pdf" element={<PdfPage />} />
              <Route path="/runs" element={<AgentRunsPage />} />
              <Route path="/users" element={<UsersPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
