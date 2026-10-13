import { useEffect, useState } from "react"
import { api, showValue } from "../api"
import type { AuditEntry, Page } from "../types"

const ACTIONS = ["login", "logout", "login_failed", "create", "update", "delete", "restore", "pdf_upload", "pdf_extract", "pdf_confirm"]
const ENTITIES = ["sea_cargo", "air_cargo", "exit_record", "pdf_document", "session", "user"]

export function AuditPage() {
  const [rows, setRows] = useState<AuditEntry[]>([])
  const [total, setTotal] = useState(0)
  const [users, setUsers] = useState<{ id: number; email: string }[]>([])
  const [userId, setUserId] = useState("")
  const [entityType, setEntityType] = useState("")
  const [action, setAction] = useState("")
  const [from, setFrom] = useState("")
  const [to, setTo] = useState("")
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState("")
  const limit = 50

  useEffect(() => {
    api("/api/lookups/users").then(async (response) => {
      if (response.ok) setUsers(await response.json())
    })
  }, [])

  useEffect(() => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (userId) params.set("user_id", userId)
    if (entityType) params.set("entity_type", entityType)
    if (action) params.set("action", action)
    if (from) params.set("from", from)
    if (to) params.set("to", to)
    api(`/api/audit?${params}`).then(async (response) => {
      if (!response.ok) {
        setError("Could not load the audit log")
        return
      }
      const body = (await response.json()) as Page<AuditEntry>
      setRows(body.items)
      setTotal(body.total)
      setError("")
    })
  }, [userId, entityType, action, from, to, offset])

  return (
    <main className="page">
      <div className="page-head"><h1>Audit</h1></div>
      <div className="toolbar">
        <select value={userId} onChange={(event) => { setOffset(0); setUserId(event.target.value) }}>
          <option value="">All users</option>
          {users.map((user) => <option key={user.id} value={user.id}>{user.email}</option>)}
        </select>
        <select value={entityType} onChange={(event) => { setOffset(0); setEntityType(event.target.value) }}>
          <option value="">All records</option>
          {ENTITIES.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <select value={action} onChange={(event) => { setOffset(0); setAction(event.target.value) }}>
          <option value="">All actions</option>
          {ACTIONS.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <input type="date" value={from} onChange={(event) => { setOffset(0); setFrom(event.target.value) }} />
        <input type="date" value={to} onChange={(event) => { setOffset(0); setTo(event.target.value) }} />
      </div>
      {error ? <div className="banner err">{error}</div> : null}
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>When</th><th>User</th><th>Action</th><th>Record</th><th>Changes</th></tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{new Date(row.created_at).toLocaleString()}</td>
                <td>{row.actor_email || "—"}</td>
                <td>{row.action}</td>
                <td>{row.entity_type || ""} {row.entity_id || ""}</td>
                <td>
                  <details>
                    <summary>{(row.changed_fields || []).length} fields</summary>
                    <ul>
                      {(row.changed_fields || []).map((change) => (
                        <li key={change.field}>{change.field}: {showValue(change.old)} → {showValue(change.new)}</li>
                      ))}
                    </ul>
                  </details>
                </td>
              </tr>
            ))}
            {!rows.length ? <tr><td colSpan={5} className="muted">No audit rows</td></tr> : null}
          </tbody>
        </table>
      </div>
      <div className="pager">
        <span>{total} events</span>
        <span>
          <button className="btn-quiet" type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>Previous</button>{" "}
          <button className="btn-quiet" type="button" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}>Next</button>
        </span>
      </div>
    </main>
  )
}
