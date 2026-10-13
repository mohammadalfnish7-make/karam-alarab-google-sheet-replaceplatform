import { Navigate, NavLink, Outlet, Route, BrowserRouter, Routes } from "react-router-dom"
import { AuthProvider, useAuth } from "./auth"
import { AuditPage } from "./pages/AuditPage"
import { CargoPage } from "./pages/CargoPage"
import { ExitPage } from "./pages/ExitPage"
import { LoginPage } from "./pages/LoginPage"
import { IntakePage } from "./pages/IntakePage"
import { PdfPage } from "./pages/PdfPage"
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
          <NavLink to="/sea">Sea</NavLink>
          <NavLink to="/air">Air</NavLink>
          <NavLink to="/exit">Exit</NavLink>
          <NavLink to="/audit">Audit</NavLink>
          <NavLink to="/intake">Intake</NavLink>
          <NavLink to="/pdf">PDF</NavLink>
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
              <Route path="/sea" element={<CargoPage kind="sea" />} />
              <Route path="/air" element={<CargoPage kind="air" />} />
              <Route path="/exit" element={<ExitPage />} />
              <Route path="/audit" element={<AuditPage />} />
              <Route path="/intake" element={<IntakePage />} />
              <Route path="/pdf" element={<PdfPage />} />
              <Route path="/users" element={<UsersPage />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
