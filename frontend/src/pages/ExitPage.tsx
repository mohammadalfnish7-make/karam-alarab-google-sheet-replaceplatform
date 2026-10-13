import { FormEvent, useCallback, useEffect, useState } from "react"
import { api, readError } from "../api"
import { useAuth } from "../auth"
import type { Enums, ExitRow, Page, SaveResult, Warning } from "../types"
import {
  ConfirmNew,
  Drawer,
  Field,
  Flags,
  History,
  IssueList,
  Pager,
  Suggest,
  WarningList,
  lookupNames,
  withCurrent,
} from "../ui"

type FormState = {
  mark: string
  supplier: string
  invoice_no: string
  cartons: string
  date_of_submission: string
  status: string
}

const emptyForm = (): FormState => ({
  mark: "",
  supplier: "",
  invoice_no: "",
  cartons: "",
  date_of_submission: "",
  status: "",
})

function fromRow(row: ExitRow): FormState {
  return {
    mark: row.mark ?? "",
    supplier: row.supplier ?? "",
    invoice_no: row.invoice_no ?? "",
    cartons: row.cartons == null ? "" : String(row.cartons),
    date_of_submission: row.date_of_submission ?? "",
    status: row.status ?? "",
  }
}

export function ExitPage() {
  const { user } = useAuth()
  const [rows, setRows] = useState<ExitRow[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [draftQ, setDraftQ] = useState("")
  const [q, setQ] = useState("")
  const [status, setStatus] = useState("")
  const [review, setReview] = useState("")
  const [includeDeleted, setIncludeDeleted] = useState(false)
  const [enums, setEnums] = useState<Enums | null>(null)
  const [editing, setEditing] = useState<ExitRow | null>(null)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState("")
  const limit = 50
  const loadCustomers = useCallback((query: string) => lookupNames("/api/lookups/customers", "code", query), [])
  const loadSuppliers = useCallback((query: string) => lookupNames("/api/lookups/suppliers", "name", query), [])

  const load = useCallback(async () => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (q) params.set("q", q)
    if (status) params.set("status", status)
    if (review) params.set("needs_review", review)
    if (includeDeleted) params.set("include_deleted", "true")
    const response = await api(`/api/exit?${params}`)
    if (!response.ok) {
      setError("Could not load rows")
      return
    }
    const body = (await response.json()) as Page<ExitRow>
    setRows(body.items)
    setTotal(body.total)
    setError("")
  }, [q, status, review, includeDeleted, offset])

  useEffect(() => {
    api("/api/lookups/enums").then(async (response) => {
      if (response.ok) setEnums((await response.json()) as Enums)
    })
  }, [])

  useEffect(() => { setOffset(0) }, [q, status, review, includeDeleted])
  useEffect(() => { load() }, [load])

  return (
    <main className="page">
      <div className="page-head">
        <h1>Exit tracker</h1>
        <button className="btn" type="button" onClick={() => { setEditing(null); setCreating(true) }}>Add</button>
      </div>
      <form className="toolbar" onSubmit={(event) => { event.preventDefault(); setQ(draftQ.trim()) }}>
        <input type="search" placeholder="Search supplier, invoice, mark, no…" value={draftQ} onChange={(event) => setDraftQ(event.target.value)} />
        <button className="btn-quiet" type="submit">Search</button>
        <select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">All statuses</option>
          {(enums?.exit_statuses ?? []).map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
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
              <th>No</th><th>Mark</th><th>Supplier</th><th>Invoice</th><th>Cartons</th><th>Submitted</th><th>Status</th><th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className={row.deleted_at ? "clickable deleted" : "clickable"} onClick={() => { setCreating(false); setEditing(row) }}>
                <td>{row.no}</td>
                <td>{row.mark ?? ""}</td>
                <td className="clip">{row.supplier ?? ""}</td>
                <td>{row.invoice_no ?? ""}</td>
                <td>{row.cartons ?? ""}</td>
                <td>{row.date_of_submission ?? ""}</td>
                <td>{row.status ?? ""}</td>
                <td><Flags legacy={row.legacy} review={row.needs_review} deleted={Boolean(row.deleted_at)} /></td>
              </tr>
            ))}
            {!rows.length ? <tr><td colSpan={8} className="muted">No rows</td></tr> : null}
          </tbody>
        </table>
      </div>
      <Pager offset={offset} limit={limit} total={total} onPage={setOffset} />
      {creating || editing ? (
        <ExitDrawer
          row={editing}
          enums={enums}
          canRestore={user?.role === "admin"}
          loadCustomers={loadCustomers}
          loadSuppliers={loadSuppliers}
          onClose={() => { setCreating(false); setEditing(null) }}
          onKeep={async (item) => { setCreating(false); setEditing(item); await load() }}
          onDone={async () => { setCreating(false); setEditing(null); await load() }}
        />
      ) : null}
    </main>
  )
}

function ExitDrawer({
  row,
  enums,
  canRestore,
  loadCustomers,
  loadSuppliers,
  onClose,
  onKeep,
  onDone,
}: {
  row: ExitRow | null
  enums: Enums | null
  canRestore: boolean
  loadCustomers: (query: string) => Promise<string[]>
  loadSuppliers: (query: string) => Promise<string[]>
  onClose: () => void
  onKeep: (row: ExitRow) => Promise<void>
  onDone: () => Promise<void>
}) {
  const [form, setForm] = useState<FormState>(row ? fromRow(row) : emptyForm())
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [warnings, setWarnings] = useState<Warning[]>([])
  const [proposed, setProposed] = useState<Record<string, string>>({})
  const [tab, setTab] = useState<"edit" | "history">("edit")
  const [message, setMessage] = useState("")
  const statuses = withCurrent(enums?.exit_statuses ?? [], form.status)

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }))
    setErrors((current) => ({ ...current, [key]: "" }))
    setProposed({})
  }

  async function save(forceNew: boolean) {
    const payload = {
      mark: form.mark.trim() || null,
      supplier: form.supplier.trim() || null,
      invoice_no: form.invoice_no.trim() || null,
      cartons: form.cartons.trim() ? Number(form.cartons) : null,
      date_of_submission: form.date_of_submission || null,
      status: form.status || null,
      confirm_new_customer: forceNew && "mark" in proposed,
      confirm_new_supplier: forceNew && "supplier" in proposed,
    }
    const response = await api(row ? `/api/exit/${row.id}` : "/api/exit", {
      method: row ? "PATCH" : "POST",
      body: JSON.stringify(payload),
    })
    if (response.status === 422) {
      const error = await readError(response)
      setErrors(error.field_errors || {})
      setWarnings(error.warnings || [])
      setProposed(error.code === "NEW_VALUE_CONFIRMATION_REQUIRED" ? error.proposed || {} : {})
      return
    }
    if (!response.ok) {
      const error = await readError(response)
      setMessage(error.message || "Save failed")
      return
    }
    const body = (await response.json()) as SaveResult<ExitRow>
    setWarnings(body.warnings || [])
    setErrors({})
    setProposed({})
    setForm(fromRow(body.item))
    if (body.warnings?.length) {
      setMessage("Saved with warnings")
      await onKeep(body.item)
      return
    }
    await onDone()
  }

  async function remove() {
    if (!row || !window.confirm("Soft-delete this row? It will leave the working list.")) return
    const response = await api(`/api/exit/${row.id}`, { method: "DELETE" })
    if (!response.ok) {
      setMessage("Delete failed")
      return
    }
    await onDone()
  }

  async function restore() {
    if (!row) return
    const response = await api(`/api/exit/${row.id}/restore`, { method: "POST" })
    if (!response.ok) {
      setMessage("Restore failed")
      return
    }
    await onDone()
  }

  return (
    <Drawer
      title={row ? `Exit ${row.no}` : "New exit"}
      onClose={onClose}
      footer={
        <>
          <div>
            {row && !row.deleted_at ? <button className="btn-danger" type="button" onClick={remove}>Delete</button> : null}
            {row && row.deleted_at && canRestore ? <button className="btn-quiet" type="button" onClick={restore}>Restore</button> : null}
          </div>
          <button className="btn" type="button" onClick={() => save(false)} disabled={Boolean(row?.deleted_at)}>Save</button>
        </>
      }
    >
      {row ? (
        <div className="tabs">
          <button type="button" className={tab === "edit" ? "on" : ""} onClick={() => setTab("edit")}>Edit</button>
          <button type="button" className={tab === "history" ? "on" : ""} onClick={() => setTab("history")}>History</button>
        </div>
      ) : null}
      {tab === "history" && row ? <History path={`/api/exit/${row.id}/history`} legacy={row.legacy} /> : (
        <form className="form-grid" onSubmit={(event: FormEvent) => { event.preventDefault(); save(false) }}>
          {row ? <p className="muted wide">Number {row.no} is assigned by the server.</p> : <p className="muted wide">The number is assigned when you save.</p>}
          {message ? <div className="banner ok wide">{message}</div> : null}
          <WarningList warnings={warnings} />
          {row ? <IssueList issues={row.issues || []} /> : null}
          <Field label="Mark" error={errors.mark}>
            <Suggest id="exit-mark" value={form.mark} invalid={Boolean(errors.mark)} onChange={(value) => update("mark", value)} loader={loadCustomers} />
          </Field>
          <Field label="Supplier" error={errors.supplier}>
            <Suggest id="exit-supplier" value={form.supplier} invalid={Boolean(errors.supplier)} onChange={(value) => update("supplier", value)} loader={loadSuppliers} />
          </Field>
          <Field label="Invoice" error={errors.invoice_no} wide>
            <input className={errors.invoice_no ? "invalid" : ""} value={form.invoice_no} onChange={(event) => update("invoice_no", event.target.value)} />
          </Field>
          <Field label="Cartons" error={errors.cartons}>
            <input className={errors.cartons ? "invalid" : ""} inputMode="numeric" value={form.cartons} onChange={(event) => update("cartons", event.target.value)} />
          </Field>
          <Field label="Date of submission" error={errors.date_of_submission}>
            <input className={errors.date_of_submission ? "invalid" : ""} type="date" value={form.date_of_submission} onChange={(event) => update("date_of_submission", event.target.value)} />
          </Field>
          <Field label="Status" error={errors.status}>
            <select className={errors.status ? "invalid" : ""} value={form.status} onChange={(event) => update("status", event.target.value)}>
              <option value="">—</option>
              {statuses.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </Field>
          <div className="wide"><ConfirmNew proposed={proposed} onConfirm={() => save(true)} /></div>
        </form>
      )}
    </Drawer>
  )
}
