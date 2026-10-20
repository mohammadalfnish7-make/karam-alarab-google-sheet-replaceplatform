import { useEffect, useState } from "react"
import type { ReactNode } from "react"
import { api, friendlyAction, normalizeAuditChanges, showValue } from "./api"
import type { AuditEntry, Issue, Warning } from "./types"

export function Field({
  label,
  error,
  wide,
  children,
}: {
  label: string
  error?: string
  wide?: boolean
  children: ReactNode
}) {
  return (
    <label className={wide ? "field wide" : "field"}>
      <span>{label}</span>
      {children}
      {error ? <em>{error}</em> : null}
    </label>
  )
}

export function Drawer({
  title,
  onClose,
  children,
  footer,
}: {
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
}) {
  return (
    <div className="drawer-back" onClick={onClose}>
      <aside className="drawer" onClick={(event) => event.stopPropagation()}>
        <header>
          <h2>{title}</h2>
          <button className="btn-quiet" type="button" onClick={onClose}>Close</button>
        </header>
        <div className="body">{children}</div>
        {footer ? <footer>{footer}</footer> : null}
      </aside>
    </div>
  )
}

export function Flags({ legacy, review, deleted }: { legacy?: boolean; review?: boolean; deleted?: boolean }) {
  return (
    <>
      {legacy ? <span className="badge">Legacy</span> : null}
      {review ? <span className="badge warn">Review</span> : null}
      {deleted ? <span className="badge dead">Deleted</span> : null}
    </>
  )
}

export function IssueList({ issues }: { issues: Issue[] }) {
  if (!issues.length) return null
  return (
    <ul className="issues">
      {issues.map((issue, index) => (
        <li key={`${issue.field}-${index}`}>{issue.field}: {issue.message}</li>
      ))}
    </ul>
  )
}

export function WarningList({ warnings }: { warnings: Warning[] }) {
  if (!warnings.length) return null
  return (
    <ul className="warn-list">
      {warnings.map((item) => (
        <li key={item.code + item.field}>{item.message}</li>
      ))}
    </ul>
  )
}

export function ConfirmNew({
  proposed,
  onConfirm,
}: {
  proposed: Record<string, string>
  onConfirm: () => void
}) {
  const entries = Object.entries(proposed)
  if (!entries.length) return null
  return (
    <div className="confirm-box">
      <strong>These values are not in the lists yet.</strong>
      <ul>
        {entries.map(([key, value]) => (
          <li key={key}>{key.replaceAll("_", " ")}: {value}</li>
        ))}
      </ul>
      <button className="btn" type="button" onClick={onConfirm}>Add them and save</button>
    </div>
  )
}

export function History({ path, legacy }: { path: string; legacy?: boolean }) {
  const [rows, setRows] = useState<AuditEntry[]>([])
  const [error, setError] = useState("")
  useEffect(() => {
    let cancelled = false
    api(path).then(async (response) => {
      if (!response.ok) {
        if (!cancelled) setError("Could not load history")
        return
      }
      const body = (await response.json()) as AuditEntry[]
      if (!cancelled) setRows(body)
    })
    return () => {
      cancelled = true
    }
  }, [path])
  if (error) return <p className="err">{error}</p>
  if (!rows.length) {
    return <p className="muted">{legacy ? "Imported from the workbook. No edits yet." : "No history yet."}</p>
  }
  return (
    <div>
      {rows.map((row) => {
        const changes = normalizeAuditChanges(row.changed_fields, row.after_json, row.before_json)
        return (
          <article className="history-item" key={row.id}>
            <div>
              <strong>{friendlyAction(row.action)}</strong>
              {" · "}
              {row.actor_email || "system"}
              {" · "}
              {new Date(row.created_at).toLocaleString()}
            </div>
            <ul className="change-list">
              {changes.map((change, index) => (
                <li key={`${change.field}-${index}`}>
                  <span className="change-field">{change.field}</span>
                  <span className="change-old">{showValue(change.old)}</span>
                  <span className="change-arrow" aria-hidden="true">→</span>
                  <span className="change-new">{showValue(change.new)}</span>
                </li>
              ))}
            </ul>
          </article>
        )
      })}
    </div>
  )
}

export function Suggest({
  id,
  value,
  onChange,
  invalid,
  loader,
}: {
  id: string
  value: string
  onChange: (value: string) => void
  invalid?: boolean
  loader: (query: string) => Promise<string[]>
}) {
  const [options, setOptions] = useState<string[]>([])
  useEffect(() => {
    const timer = window.setTimeout(() => {
      loader(value).then(setOptions).catch(() => setOptions([]))
    }, 200)
    return () => window.clearTimeout(timer)
  }, [value, loader])
  return (
    <>
      <input className={invalid ? "invalid" : ""} list={id} value={value} onChange={(event) => onChange(event.target.value)} />
      <datalist id={id}>
        {options.map((option) => <option key={option} value={option} />)}
      </datalist>
    </>
  )
}

export function Pager({
  offset,
  limit,
  total,
  onPage,
}: {
  offset: number
  limit: number
  total: number
  onPage: (offset: number) => void
}) {
  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(offset + limit, total)
  return (
    <div className="pager">
      <span>Showing {from}–{to} of {total}</span>
      <span>
        <button className="btn-quiet" type="button" disabled={offset === 0} onClick={() => onPage(Math.max(0, offset - limit))}>Previous</button>{" "}
        <button className="btn-quiet" type="button" disabled={offset + limit >= total} onClick={() => onPage(offset + limit)}>Next</button>
      </span>
    </div>
  )
}

export async function lookupNames(path: string, key: "code" | "name", query: string) {
  const response = await api(`${path}?q=${encodeURIComponent(query)}`)
  if (!response.ok) return []
  const rows = (await response.json()) as Record<string, string>[]
  return rows.map((row) => row[key]).filter(Boolean)
}

export function withCurrent(options: string[], current: string) {
  if (current && !options.includes(current)) return [current, ...options]
  return options
}

export function grossText(row: { gross_is_no_pallet: boolean; gross_weight_kg: number | null }) {
  if (row.gross_is_no_pallet) return "NO PALLET"
  if (row.gross_weight_kg == null) return ""
  return String(row.gross_weight_kg)
}
