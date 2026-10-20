import { FormEvent, useEffect, useState } from "react"
import { Navigate } from "react-router-dom"
import { api, readError } from "../api"
import { useAuth } from "../auth"
import type { AppSettings, PromptDetail, PromptSummary } from "../types"

export function SettingsPage() {
  const { user } = useAuth()
  const [prompts, setPrompts] = useState<PromptSummary[]>([])
  const [app, setApp] = useState<AppSettings>({ llm_model: "", llm_timeout_sec: "120" })
  const [selectedKey, setSelectedKey] = useState("intake.note")
  const [detail, setDetail] = useState<PromptDetail | null>(null)
  const [body, setBody] = useState("")
  const [note, setNote] = useState("")
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [busy, setBusy] = useState(false)

  async function loadOverview() {
    const response = await api("/api/settings")
    if (!response.ok) return
    const data = await response.json()
    setPrompts(data.prompts || [])
    setApp(data.app || { llm_model: "", llm_timeout_sec: "120" })
  }

  async function loadPrompt(key: string) {
    const response = await api(`/api/settings/prompts/${encodeURIComponent(key)}`)
    if (!response.ok) {
      const err = await readError(response)
      setError(err.message || "Could not load prompt")
      return
    }
    const data: PromptDetail = await response.json()
    setDetail(data)
    const active = data.versions.find((row) => row.is_active) || data.versions[0]
    setBody(active?.body || "")
    setNote("")
  }

  useEffect(() => {
    loadOverview().then(() => loadPrompt(selectedKey))
  }, [])

  if (user && user.role !== "admin") return <Navigate to="/sea" replace />

  async function selectPrompt(key: string) {
    setSelectedKey(key)
    setError("")
    setMessage("")
    await loadPrompt(key)
  }

  async function savePrompt(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError("")
    setMessage("")
    const response = await api(`/api/settings/prompts/${encodeURIComponent(selectedKey)}`, {
      method: "PUT",
      body: JSON.stringify({ body, note: note || null }),
    })
    setBusy(false)
    if (!response.ok) {
      const err = await readError(response)
      const field = err.field_errors ? Object.values(err.field_errors)[0] : ""
      setError(field || err.message || "Could not save prompt")
      return
    }
    const data: PromptDetail = await response.json()
    setDetail(data)
    setMessage(`Saved as version ${data.active_version}`)
    setNote("")
    await loadOverview()
  }

  async function rollback(version: number) {
    if (!window.confirm(`Roll back to version ${version}? Extraction will use that text immediately.`)) return
    setBusy(true)
    setError("")
    setMessage("")
    const response = await api(`/api/settings/prompts/${encodeURIComponent(selectedKey)}/rollback`, {
      method: "POST",
      body: JSON.stringify({ version }),
    })
    setBusy(false)
    if (!response.ok) {
      const err = await readError(response)
      setError(err.message || "Could not roll back")
      return
    }
    const data: PromptDetail = await response.json()
    setDetail(data)
    const active = data.versions.find((row) => row.is_active)
    setBody(active?.body || "")
    setMessage(`Active prompt is now version ${data.active_version}`)
    await loadOverview()
  }

  async function saveApp(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError("")
    setMessage("")
    const response = await api("/api/settings/app", {
      method: "PUT",
      body: JSON.stringify({
        llm_model: app.llm_model,
        llm_timeout_sec: Number(app.llm_timeout_sec),
      }),
    })
    setBusy(false)
    if (!response.ok) {
      const err = await readError(response)
      const field = err.field_errors ? Object.values(err.field_errors)[0] : ""
      setError(field || err.message || "Could not save settings")
      return
    }
    const data = await response.json()
    setApp(data.app)
    setMessage("LLM settings saved")
  }

  return (
    <main className="page">
      <div className="page-head">
        <h1>Settings</h1>
      </div>
      {error ? <div className="banner err">{error}</div> : null}
      {message ? <div className="banner ok">{message}</div> : null}

      <section className="panel">
        <div className="file-head">
          <h2>Prompts</h2>
          <span className="muted">Versioned — save creates a new version; rollback switches the active one</span>
        </div>
        <div className="settings-prompt-layout">
          <aside className="settings-prompt-list">
            {prompts.map((prompt) => (
              <button
                key={prompt.key}
                type="button"
                className={prompt.key === selectedKey ? "settings-prompt-item active" : "settings-prompt-item"}
                onClick={() => selectPrompt(prompt.key)}
              >
                <strong>{prompt.label}</strong>
                <small>
                  {prompt.key} · v{prompt.active_version}
                </small>
              </button>
            ))}
          </aside>
          <div className="settings-prompt-editor">
            <form onSubmit={savePrompt}>
              <label className="field wide">
                <span>Active body — {detail?.label || selectedKey}</span>
                <textarea
                  className="settings-prompt-body"
                  value={body}
                  onChange={(event) => setBody(event.target.value)}
                  rows={16}
                  required
                />
              </label>
              <div className="toolbar">
                <input
                  type="text"
                  placeholder="Optional note for this version"
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                />
                <button className="btn" type="submit" disabled={busy}>
                  Save as new version
                </button>
              </div>
            </form>

            <h3 className="settings-subhead">Version history</h3>
            <div className="table-wrap settings-versions">
              <table>
                <thead>
                  <tr>
                    <th>Version</th>
                    <th>When</th>
                    <th>By</th>
                    <th>Note</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {(detail?.versions || []).map((row) => (
                    <tr key={row.id} className={row.is_active ? "settings-active-row" : undefined}>
                      <td>
                        v{row.version}
                        {row.is_active ? " · active" : ""}
                      </td>
                      <td>{row.created_at ? new Date(row.created_at).toLocaleString() : "—"}</td>
                      <td>{row.created_by_email || "system"}</td>
                      <td>{row.note || "—"}</td>
                      <td>
                        {!row.is_active ? (
                          <button className="btn-quiet" type="button" disabled={busy} onClick={() => rollback(row.version)}>
                            Rollback
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>

      <section className="panel">
        <h2>LLM</h2>
        <form className="form-grid" onSubmit={saveApp}>
          <label className="field">
            <span>Model</span>
            <input
              value={app.llm_model}
              onChange={(event) => setApp({ ...app, llm_model: event.target.value })}
              required
            />
          </label>
          <label className="field">
            <span>Timeout (seconds)</span>
            <input
              type="number"
              min={10}
              max={600}
              value={app.llm_timeout_sec}
              onChange={(event) => setApp({ ...app, llm_timeout_sec: event.target.value })}
              required
            />
          </label>
          <div className="field wide">
            <button className="btn" type="submit" disabled={busy}>
              Save LLM settings
            </button>
          </div>
        </form>
      </section>
    </main>
  )
}
