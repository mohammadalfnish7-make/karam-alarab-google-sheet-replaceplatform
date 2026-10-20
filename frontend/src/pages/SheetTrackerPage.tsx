import { FormEvent, useCallback, useEffect, useState } from "react"
import { api, readError } from "../api"
import { useAuth } from "../auth"
import type { Enums, Page, Warning } from "../types"
import { Drawer, Field, Flags, History, IssueList, Pager, WarningList, withCurrent } from "../ui"

export type SheetField = {
  key: string
  label: string
  kind?: "text" | "date" | "number" | "textarea" | "select"
  optionsKey?: keyof Enums
  table?: boolean
  wide?: boolean
}

export type SheetConfig = {
  title: string
  api: string
  searchPlaceholder: string
  fields: SheetField[]
}

type SheetRow = {
  id: number
  legacy: boolean
  needs_review: boolean
  issues: { field: string; message: string; raw?: string }[]
  deleted_at?: string | null
  [key: string]: unknown
}

function emptyForm(fields: SheetField[]): Record<string, string> {
  return Object.fromEntries(fields.map((field) => [field.key, ""]))
}

function fromRow(fields: SheetField[], row: SheetRow): Record<string, string> {
  const form = emptyForm(fields)
  for (const field of fields) {
    const value = row[field.key]
    form[field.key] = value == null ? "" : String(value)
  }
  return form
}

function toPayload(fields: SheetField[], form: Record<string, string>) {
  const payload: Record<string, string | number | null> = {}
  for (const field of fields) {
    const raw = form[field.key].trim()
    if (!raw) {
      payload[field.key] = null
      continue
    }
    if (field.kind === "number") {
      const number = Number(raw)
      payload[field.key] = Number.isFinite(number) ? number : raw
    } else {
      payload[field.key] = raw
    }
  }
  return payload
}

export function SheetTrackerPage({ config }: { config: SheetConfig }) {
  const { user } = useAuth()
  const [rows, setRows] = useState<SheetRow[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [draftQ, setDraftQ] = useState("")
  const [q, setQ] = useState("")
  const [review, setReview] = useState("")
  const [includeDeleted, setIncludeDeleted] = useState(false)
  const [editing, setEditing] = useState<SheetRow | null>(null)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState("")
  const [enums, setEnums] = useState<Enums | null>(null)
  const limit = 50
  const tableFields = config.fields.filter((field) => field.table !== false)

  useEffect(() => {
    api("/api/lookups/enums").then(async (response) => {
      if (response.ok) setEnums((await response.json()) as Enums)
    })
  }, [])

  const load = useCallback(async () => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (q) params.set("q", q)
    if (review) params.set("needs_review", review)
    if (includeDeleted) params.set("include_deleted", "true")
    const response = await api(`${config.api}?${params}`)
    if (!response.ok) {
      setError("Could not load rows")
      return
    }
    const body = (await response.json()) as Page<SheetRow>
    setRows(body.items)
    setTotal(body.total)
    setError("")
  }, [config.api, q, review, includeDeleted, offset])

  useEffect(() => { setOffset(0) }, [q, review, includeDeleted, config.api])
  useEffect(() => { load() }, [load])

  return (
    <main className="page">
      <div className="page-head">
        <h1>{config.title}</h1>
        <button className="btn" type="button" onClick={() => { setEditing(null); setCreating(true) }}>Add</button>
      </div>
      <form className="toolbar" onSubmit={(event) => { event.preventDefault(); setQ(draftQ.trim()) }}>
        <input type="search" placeholder={config.searchPlaceholder} value={draftQ} onChange={(event) => setDraftQ(event.target.value)} />
        <button className="btn-quiet" type="submit">Search</button>
        <select value={review} onChange={(event) => setReview(event.target.value)}>
          <option value="">All rows</option>
          <option value="true">Needs review</option>
          <option value="false">No review flag</option>
        </select>
        {user?.role === "admin" ? (
          <label className="check">
            <input type="checkbox" checked={includeDeleted} onChange={(event) => setIncludeDeleted(event.target.checked)} />
            Show deleted
          </label>
        ) : null}
      </form>
      {error ? <div className="banner err">{error}</div> : null}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {tableFields.map((field) => <th key={field.key}>{field.label}</th>)}
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.id}
                className={row.deleted_at ? "clickable deleted" : "clickable"}
                onClick={() => { setCreating(false); setEditing(row) }}
              >
                {tableFields.map((field) => (
                  <td
                    key={field.key}
                    className={
                      ["status", "notes", "comment", "qr", "info", "stage"].includes(field.key) ? "clip" : undefined
                    }
                  >
                    {row[field.key] == null ? "" : String(row[field.key])}
                  </td>
                ))}
                <td><Flags legacy={row.legacy} review={row.needs_review} deleted={Boolean(row.deleted_at)} /></td>
              </tr>
            ))}
            {!rows.length ? <tr><td colSpan={tableFields.length + 1} className="muted">No rows</td></tr> : null}
          </tbody>
        </table>
      </div>
      <Pager offset={offset} limit={limit} total={total} onPage={setOffset} />
      {creating || editing ? (
        <SheetDrawer
          config={config}
          row={editing}
          canRestore={user?.role === "admin"}
          enums={enums}
          onClose={() => { setCreating(false); setEditing(null) }}
          onKeep={async (item) => { setCreating(false); setEditing(item); await load() }}
          onDone={async () => { setCreating(false); setEditing(null); await load() }}
        />
      ) : null}
    </main>
  )
}

function SheetDrawer({
  config,
  row,
  canRestore,
  enums,
  onClose,
  onKeep,
  onDone,
}: {
  config: SheetConfig
  row: SheetRow | null
  canRestore: boolean
  enums: Enums | null
  onClose: () => void
  onKeep: (row: SheetRow) => Promise<void>
  onDone: () => Promise<void>
}) {
  const [form, setForm] = useState(() => row ? fromRow(config.fields, row) : emptyForm(config.fields))
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [warnings, setWarnings] = useState<Warning[]>([])
  const [tab, setTab] = useState<"edit" | "history">("edit")
  const [message, setMessage] = useState("")

  function optionsFor(field: SheetField) {
    if (!field.optionsKey || !enums) return []
    return withCurrent(enums[field.optionsKey] || [], form[field.key])
  }

  function update(key: string, value: string) {
    setForm((current) => ({ ...current, [key]: value }))
    setErrors((current) => ({ ...current, [key]: "" }))
  }

  async function save() {
    const response = await api(row ? `${config.api}/${row.id}` : config.api, {
      method: row ? "PATCH" : "POST",
      body: JSON.stringify(toPayload(config.fields, form)),
    })
    if (response.status === 422) {
      const error = await readError(response)
      setErrors(error.field_errors || {})
      setWarnings(error.warnings || [])
      return
    }
    if (!response.ok) {
      const error = await readError(response)
      setMessage(error.message || "Save failed")
      return
    }
    const body = await response.json() as { item: SheetRow; warnings?: Warning[] }
    setWarnings(body.warnings || [])
    setErrors({})
    setForm(fromRow(config.fields, body.item))
    if (body.warnings?.length) {
      setMessage("Saved with warnings")
      await onKeep(body.item)
      return
    }
    await onDone()
  }

  async function remove() {
    if (!row || !window.confirm("Soft-delete this row? It will leave the working list.")) return
    const response = await api(`${config.api}/${row.id}`, { method: "DELETE" })
    if (!response.ok) {
      setMessage("Delete failed")
      return
    }
    await onDone()
  }

  async function restore() {
    if (!row) return
    const response = await api(`${config.api}/${row.id}/restore`, { method: "POST" })
    if (!response.ok) {
      setMessage("Restore failed")
      return
    }
    await onDone()
  }

  return (
    <Drawer
      title={row ? `${config.title} #${row.id}` : `New ${config.title}`}
      onClose={onClose}
      footer={
        <>
          <div>
            {row && !row.deleted_at ? <button className="btn-danger" type="button" onClick={remove}>Delete</button> : null}
            {row && row.deleted_at && canRestore ? <button className="btn-quiet" type="button" onClick={restore}>Restore</button> : null}
          </div>
          <button className="btn" type="button" onClick={() => save()} disabled={Boolean(row?.deleted_at)}>Save</button>
        </>
      }
    >
      {row ? (
        <div className="tabs">
          <button type="button" className={tab === "edit" ? "on" : ""} onClick={() => setTab("edit")}>Edit</button>
          <button type="button" className={tab === "history" ? "on" : ""} onClick={() => setTab("history")}>History</button>
        </div>
      ) : null}
      {tab === "history" && row ? <History path={`${config.api}/${row.id}/history`} legacy={row.legacy} /> : (
        <form className="form-grid" onSubmit={(event: FormEvent) => { event.preventDefault(); save() }}>
          {message ? <div className="banner ok wide">{message}</div> : null}
          <WarningList warnings={warnings} />
          {row ? <IssueList issues={row.issues || []} /> : null}
          {config.fields.map((field) => (
            <Field key={field.key} label={field.label} error={errors[field.key]} wide={field.wide || field.kind === "textarea"}>
              {field.kind === "textarea" ? (
                <textarea
                  className={errors[field.key] ? "invalid invoice-box" : "invoice-box"}
                  value={form[field.key]}
                  onChange={(event) => update(field.key, event.target.value)}
                />
              ) : field.kind === "select" ? (
                <select
                  className={errors[field.key] ? "invalid" : ""}
                  value={form[field.key]}
                  onChange={(event) => update(field.key, event.target.value)}
                >
                  <option value="">—</option>
                  {optionsFor(field).map((item) => (
                    <option key={item} value={item}>{item}</option>
                  ))}
                </select>
              ) : (
                <input
                  className={errors[field.key] ? "invalid" : ""}
                  type={field.kind === "date" ? "date" : field.kind === "number" ? "text" : "text"}
                  inputMode={field.kind === "number" ? "decimal" : undefined}
                  value={form[field.key]}
                  onChange={(event) => update(field.key, event.target.value)}
                />
              )}
            </Field>
          ))}
        </form>
      )}
    </Drawer>
  )
}

export const CONTAINERS_CONFIG: SheetConfig = {
  title: "Containers",
  api: "/api/containers",
  searchPlaceholder: "Search INV NO, container, QR, info, stage, status…",
  fields: [
    { key: "date", label: "DATE", kind: "date" },
    { key: "inv_no", label: "INV NO" },
    { key: "qr", label: "Q R", kind: "textarea", wide: true },
    { key: "previous_cont", label: "Previous Cont" },
    { key: "container_no", label: "№ Container" },
    { key: "kgs", label: "KGs", kind: "number" },
    { key: "carton", label: "Carton", kind: "number" },
    { key: "driver_name", label: "Driver's Name" },
    { key: "driver_contact", label: "Driver's Contact" },
    { key: "info", label: "Info / Инфо", kind: "textarea", wide: true },
    { key: "notes", label: "NOTES", kind: "textarea", wide: true },
    { key: "foreign_invoice", label: "Foreign Invoice" },
    { key: "russian_instrct", label: "Russian Instrct." },
    { key: "supplier_buyer", label: "Supplier/Buyer" },
    { key: "status", label: "Status", kind: "textarea", wide: true },
    { key: "stage", label: "Stage", kind: "select", optionsKey: "container_stages" },
  ],
}

export const AIR_TRACKER_CONFIG: SheetConfig = {
  title: "Air tracker",
  api: "/api/air-tracker",
  searchPlaceholder: "Search Ref No, vendor, AWB, status…",
  fields: [
    { key: "ref_no", label: "Ref No" },
    { key: "vendor", label: "Vendor" },
    { key: "airline", label: "Airline" },
    { key: "date", label: "Date", kind: "date" },
    { key: "item", label: "Item" },
    { key: "cartons", label: "Crtn", kind: "number" },
    { key: "weight_kg", label: "Wt(Kg)", kind: "number" },
    { key: "awb", label: "Awb" },
    { key: "status", label: "Status", kind: "textarea", wide: true },
    { key: "comment", label: "Comment", kind: "textarea", wide: true },
  ],
}

export const COO_CONFIG: SheetConfig = {
  title: "COO",
  api: "/api/coo",
  searchPlaceholder: "Search Inv Number, container…",
  fields: [
    { key: "sr", label: "SR", kind: "number" },
    { key: "inv_number", label: "Inv Number" },
    { key: "container_no", label: "Container No" },
    { key: "kjs", label: "KJS" },
    { key: "grg", label: "GRG" },
    { key: "k_exit", label: "K-EXIT" },
  ],
}

export const FLIGHT_SCHEDULE_CONFIG: SheetConfig = {
  title: "Flight schedule",
  api: "/api/flight-schedule",
  searchPlaceholder: "Search airline, status…",
  fields: [
    { key: "sr", label: "Sr", kind: "number" },
    { key: "airline", label: "Airline" },
    { key: "date", label: "Date", kind: "date" },
    { key: "day", label: "Day" },
    { key: "narrow", label: "Narrow" },
    { key: "wide", label: "Wide" },
    { key: "status", label: "Status" },
    { key: "column_1", label: "Column 1" },
  ],
}
