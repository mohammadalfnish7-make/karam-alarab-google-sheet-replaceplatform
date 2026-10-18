import { useEffect, useState } from "react"
import { Navigate } from "react-router-dom"
import { api } from "../api"
import { useAuth } from "../auth"
import type { AgentRun, Page, RequestLog } from "../types"

const AGENTS = ["intake.delivery_note", "intake.scale", "pdf.sea", "pdf.air", "pdf.exit"]

function pretty(value: unknown) {
  if (value == null) return ""
  return JSON.stringify(value, null, 2)
}

function formatMs(ms: number | null | undefined) {
  if (ms == null) return "—"
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(2)} s`
}

export function AgentRunsPage() {
  const { user } = useAuth()
  const [tab, setTab] = useState<"agents" | "http">("agents")
  const [rows, setRows] = useState<AgentRun[]>([])
  const [httpRows, setHttpRows] = useState<RequestLog[]>([])
  const [total, setTotal] = useState(0)
  const [agentName, setAgentName] = useState("")
  const [status, setStatus] = useState("")
  const [pathFilter, setPathFilter] = useState("")
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState("")
  const [selected, setSelected] = useState<AgentRun | null>(null)
  const limit = 50

  useEffect(() => {
    if (tab !== "agents") return
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (agentName) params.set("agent_name", agentName)
    if (status) params.set("status", status)
    api(`/api/agent-runs?${params}`).then(async (response) => {
      if (!response.ok) {
        setError("Could not load agent runs")
        return
      }
      const body = (await response.json()) as Page<AgentRun>
      setRows(body.items)
      setTotal(body.total)
      setError("")
    })
  }, [tab, agentName, status, offset])

  useEffect(() => {
    if (tab !== "http") return
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (pathFilter.trim()) params.set("path", pathFilter.trim())
    api(`/api/request-logs?${params}`).then(async (response) => {
      if (!response.ok) {
        setError("Could not load request logs")
        return
      }
      const body = (await response.json()) as Page<RequestLog>
      setHttpRows(body.items)
      setTotal(body.total)
      setError("")
    })
  }, [tab, pathFilter, offset])

  async function openRun(id: number) {
    const response = await api(`/api/agent-runs/${id}`)
    if (!response.ok) {
      setError("Could not load this run")
      return
    }
    setSelected((await response.json()) as AgentRun)
    setError("")
  }

  if (user && user.role !== "admin") return <Navigate to="/sea" replace />

  return (
    <main className="page">
      <div className="page-head"><h1>Developer tracking</h1></div>
      <div className="toolbar">
        <button className={tab === "agents" ? "btn" : "btn-quiet"} type="button" onClick={() => { setTab("agents"); setOffset(0); setSelected(null) }}>Agent runs</button>
        <button className={tab === "http" ? "btn" : "btn-quiet"} type="button" onClick={() => { setTab("http"); setOffset(0); setSelected(null) }}>HTTP requests</button>
        {tab === "agents" ? (
          <>
            <select value={agentName} onChange={(event) => { setOffset(0); setAgentName(event.target.value); setSelected(null) }}>
              <option value="">All agents</option>
              {AGENTS.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
            <select value={status} onChange={(event) => { setOffset(0); setStatus(event.target.value); setSelected(null) }}>
              <option value="">All statuses</option>
              <option value="ok">ok</option>
              <option value="error">error</option>
              <option value="running">running</option>
            </select>
          </>
        ) : (
          <input
            placeholder="Filter path"
            value={pathFilter}
            onChange={(event) => { setOffset(0); setPathFilter(event.target.value) }}
          />
        )}
      </div>
      {error ? <div className="banner err">{error}</div> : null}

      {tab === "agents" ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>When</th><th>Agent</th><th>Status</th><th>Provider</th><th>Duration</th><th>User</th><th>Steps</th><th>Error</th></tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className={selected?.id === row.id ? "clickable active" : "clickable"} onClick={() => openRun(row.id)}>
                  <td>{new Date(row.started_at).toLocaleString()}</td>
                  <td>{row.agent_name}</td>
                  <td>{row.status === "error" ? <span className="badge dead">{row.status}</span> : row.status}</td>
                  <td>{row.provider || "—"}{row.model ? ` / ${row.model}` : ""}</td>
                  <td>{formatMs(row.duration_ms)}</td>
                  <td>{row.actor_email || "—"}</td>
                  <td>{row.step_count}</td>
                  <td className="clip">{row.error_message || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>When</th><th>Method</th><th>Path</th><th>Status</th><th>Duration</th><th>User</th><th>IP</th><th>Error</th></tr>
            </thead>
            <tbody>
              {httpRows.map((row) => (
                <tr key={row.id}>
                  <td>{new Date(row.created_at).toLocaleString()}</td>
                  <td>{row.method}</td>
                  <td className="clip" title={row.query ? `${row.path}?${row.query}` : row.path}>{row.path}{row.query ? `?${row.query}` : ""}</td>
                  <td>{row.status_code >= 400 ? <span className="badge dead">{row.status_code}</span> : row.status_code}</td>
                  <td>{formatMs(row.duration_ms)}</td>
                  <td>{row.actor_email || "—"}</td>
                  <td>{row.ip || "—"}</td>
                  <td className="clip">{row.error_message || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="pager">
        <span>{total} {tab === "agents" ? "runs" : "requests"}</span>
        <span>
          <button className="btn-quiet" type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>Previous</button>
          <button className="btn-quiet" type="button" disabled={offset + limit >= total} onClick={() => setOffset(offset + limit)}>Next</button>
        </span>
      </div>

      {selected && tab === "agents" ? (
        <section className="panel">
          <h2>{selected.agent_name}</h2>
          <p className="muted">
            {selected.status}
            {selected.provider ? ` · ${selected.provider}` : ""}
            {selected.model ? ` · ${selected.model}` : ""}
            {` · ${formatMs(selected.duration_ms)}`}
            {selected.actor_email ? ` · ${selected.actor_email}` : ""}
            {selected.entity_type ? ` · ${selected.entity_type} ${selected.entity_id || ""}` : ""}
          </p>
          {selected.error_message ? <div className="banner err">{selected.error_message}</div> : null}
          <h3>Input</h3>
          <pre className="trace-block">{pretty(selected.input_json)}</pre>
          {(selected.steps_json || []).map((step, index) => (
            <article key={`${step.name}-${index}`} className="history-item">
              <strong>{index + 1}. {step.name}</strong>
              <span className="muted"> {step.at} · {formatMs(step.duration_ms)}</span>
              {step.error ? <div className="banner err">{step.error}</div> : null}
              {step.input != null ? <pre className="trace-block">{pretty(step.input)}</pre> : null}
              {step.output != null ? <pre className="trace-block">{pretty(step.output)}</pre> : null}
            </article>
          ))}
          <h3>Output</h3>
          <pre className="trace-block">{pretty(selected.output_json)}</pre>
          {selected.error_stack ? (
            <>
              <h3>Stack</h3>
              <pre className="trace-block">{selected.error_stack}</pre>
            </>
          ) : null}
        </section>
      ) : null}
    </main>
  )
}
