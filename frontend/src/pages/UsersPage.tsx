import { FormEvent, useEffect, useState } from "react"
import { Navigate } from "react-router-dom"
import { api, readError } from "../api"
import { useAuth } from "../auth"
import type { User } from "../types"

export function UsersPage() {
  const { user } = useAuth()
  const [rows, setRows] = useState<User[]>([])
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [role, setRole] = useState("operator")
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")

  async function load() {
    const response = await api("/api/users")
    if (response.ok) setRows(await response.json())
  }

  useEffect(() => { load() }, [])

  if (user && user.role !== "admin") return <Navigate to="/sea" replace />

  async function create(event: FormEvent) {
    event.preventDefault()
    setError("")
    setMessage("")
    const response = await api("/api/users", {
      method: "POST",
      body: JSON.stringify({ email, password, role }),
    })
    if (!response.ok) {
      const body = await readError(response)
      const field = body.field_errors ? Object.values(body.field_errors)[0] : ""
      setError(field || body.message || "Could not create the user")
      return
    }
    setEmail("")
    setPassword("")
    setMessage("User created")
    await load()
  }

  async function disable(target: User) {
    if (!window.confirm(`Disable ${target.email}?`)) return
    const response = await api(`/api/users/${target.id}`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: false }),
    })
    if (!response.ok) {
      const body = await readError(response)
      setError(body.message || "Could not disable the user")
      return
    }
    await load()
  }

  return (
    <main className="page">
      <div className="page-head"><h1>Users</h1></div>
      {error ? <div className="banner err">{error}</div> : null}
      {message ? <div className="banner ok">{message}</div> : null}
      <form className="toolbar" onSubmit={create}>
        <input type="email" placeholder="Email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        <input type="password" placeholder="Password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        <select value={role} onChange={(event) => setRole(event.target.value)}>
          <option value="operator">operator</option>
          <option value="admin">admin</option>
        </select>
        <button className="btn" type="submit">Create user</button>
      </form>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Email</th><th>Role</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.email}</td>
                <td>{row.role}</td>
                <td>{row.is_active ? "Active" : "Disabled"}</td>
                <td>
                  {row.is_active && row.id !== user?.id ? (
                    <button className="btn-danger" type="button" onClick={() => disable(row)}>Disable</button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  )
}
