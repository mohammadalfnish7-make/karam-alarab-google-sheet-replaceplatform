import { FormEvent, useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "../auth"

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (user) navigate("/sea", { replace: true })
  }, [user, navigate])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError("")
    try {
      await login(email, password)
      navigate("/sea")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-card stack" onSubmit={onSubmit}>
        <div className="brand brand-login">
          <img className="logo" src="/karam-logo.svg" alt="Karam Al Arab" />
          <small>Load plan</small>
        </div>
        <h1>Sign in</h1>
        <p className="muted">Sea, air, and exit records for the warehouse team.</p>
        {error ? <div className="banner err">{error}</div> : null}
        <label className="field">
          <span>Email</span>
          <input type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </label>
        <label className="field">
          <span>Password</span>
          <input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        </label>
        <button className="btn" type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
    </div>
  )
}
