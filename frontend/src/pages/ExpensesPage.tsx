import { FormEvent, useCallback, useEffect, useRef, useState } from "react"
import { api, readError, showValue } from "../api"
import { useAuth } from "../auth"
import type { Page } from "../types"
import { Drawer, Field, Flags, Pager } from "../ui"

type Budget = { limit: number; spent: number; remaining: number; currency: string }

type ExpenseSummary = {
  vendor?: string | null
  date?: string | null
  amount?: number | null
  currency?: string | null
  receipt_no?: string | null
  category?: string | null
  payment_method?: string | null
  vat_amount?: number | null
  subtotal?: number | null
  total?: number | null
  line_items?: { description?: string | null; qty?: number | null; amount?: number | null }[]
  notes?: string | null
  raw_text?: string | null
}

type ExpenseRow = {
  id: number
  mark: string
  date: string | null
  amount: number | null
  currency: string
  notes: string | null
  summary?: ExpenseSummary | null
  file_count?: number
  deleted_at?: string | null
}

type ReceiptFile = {
  id: number
  kind: string
  label: string
  file_name: string
  mime: string
  is_image: boolean
  is_pdf: boolean
  deleted_at: string | null
}

const API = "/api/expenses"
const CURRENCIES = ["AED", "USD", "EUR"]

export function ExpensesPage() {
  const { user } = useAuth()
  const [rows, setRows] = useState<ExpenseRow[]>([])
  const [budget, setBudget] = useState<Budget | null>(null)
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [draftQ, setDraftQ] = useState("")
  const [q, setQ] = useState("")
  const [includeDeleted, setIncludeDeleted] = useState(false)
  const [error, setError] = useState("")
  const [editing, setEditing] = useState<ExpenseRow | null>(null)
  const [creating, setCreating] = useState(false)
  const limit = 50

  const load = useCallback(async () => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (q) params.set("q", q)
    if (includeDeleted) params.set("include_deleted", "true")
    const response = await api(`${API}?${params}`)
    if (!response.ok) {
      setError("Could not load expenses")
      return
    }
    const body = (await response.json()) as Page<ExpenseRow> & { budget?: Budget }
    setRows(body.items)
    setTotal(body.total)
    if (body.budget) setBudget(body.budget)
    setError("")
  }, [q, offset, includeDeleted])

  useEffect(() => { setOffset(0) }, [q, includeDeleted])
  useEffect(() => { void load() }, [load])

  return (
    <main className="page">
      <div className="page-head">
        <h1>Qusai expenses</h1>
        <button className="btn" type="button" onClick={() => { setEditing(null); setCreating(true) }}>
          Add
        </button>
      </div>
      {budget ? (
        <div className="banner ok">
          Spent {showValue(budget.spent)} / {showValue(budget.limit)} {budget.currency}
          {" · "}
          Remaining {showValue(budget.remaining)} {budget.currency}
        </div>
      ) : null}
      <form className="toolbar" onSubmit={(event) => { event.preventDefault(); setQ(draftQ.trim()) }}>
        <input
          type="search"
          placeholder="Search mark, notes, currency…"
          value={draftQ}
          onChange={(event) => setDraftQ(event.target.value)}
        />
        <button className="btn-quiet" type="submit">Search</button>
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
              <th>Mark</th>
              <th>Date</th>
              <th>Amount</th>
              <th>Currency</th>
              <th>Photos</th>
              <th>Notes</th>
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
                <td>{row.mark}</td>
                <td>{row.date ?? ""}</td>
                <td>{row.amount == null ? "" : showValue(row.amount)}</td>
                <td>{row.currency}</td>
                <td>{row.file_count ?? 0}</td>
                <td className="clip">{row.notes ?? ""}</td>
                <td><Flags legacy={false} review={false} deleted={Boolean(row.deleted_at)} /></td>
              </tr>
            ))}
            {!rows.length ? <tr><td colSpan={7} className="muted">No expenses</td></tr> : null}
          </tbody>
        </table>
      </div>
      <Pager offset={offset} limit={limit} total={total} onPage={setOffset} />
      {creating || editing ? (
        <ExpenseDrawer
          row={editing}
          canRestore={user?.role === "admin"}
          onClose={() => { setCreating(false); setEditing(null) }}
          onDone={async () => { setCreating(false); setEditing(null); await load() }}
          onKeep={async (item) => { setCreating(false); setEditing(item); await load() }}
        />
      ) : null}
    </main>
  )
}

function ExpenseDrawer({
  row,
  canRestore,
  onClose,
  onDone,
  onKeep,
}: {
  row: ExpenseRow | null
  canRestore: boolean
  onClose: () => void
  onDone: () => Promise<void>
  onKeep: (row: ExpenseRow) => Promise<void>
}) {
  const [mark, setMark] = useState(row?.mark || "")
  const [dateValue, setDateValue] = useState(row?.date || new Date().toISOString().slice(0, 10))
  const [amount, setAmount] = useState(row?.amount == null ? "" : String(row.amount))
  const [currency, setCurrency] = useState(row?.currency || "AED")
  const [notes, setNotes] = useState(row?.notes || "")
  const [summary, setSummary] = useState<ExpenseSummary | null>(row?.summary || null)
  const [tab, setTab] = useState<"edit" | "receipts">(row ? "receipts" : "edit")
  const [message, setMessage] = useState("")
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [summarizing, setSummarizing] = useState(false)

  useEffect(() => {
    if (row) return
    void api(`${API}/next-mark`).then(async (response) => {
      if (!response.ok) return
      const body = (await response.json()) as { mark: string }
      setMark(body.mark)
    })
  }, [row])

  async function save() {
    const payload = {
      mark: mark.trim(),
      date: dateValue,
      amount: amount.trim() === "" ? null : amount.trim(),
      currency,
      notes: notes.trim() || null,
    }
    const response = await api(row ? `${API}/${row.id}` : API, {
      method: row ? "PATCH" : "POST",
      body: JSON.stringify(payload),
    })
    if (response.status === 422) {
      const error = await readError(response)
      setErrors(error.field_errors || {})
      setMessage(error.message || "Save failed")
      return
    }
    if (!response.ok) {
      const error = await readError(response)
      setMessage(error.message || "Save failed")
      return
    }
    const body = (await response.json()) as { item: ExpenseRow }
    setErrors({})
    setMark(body.item.mark)
    setDateValue(body.item.date || "")
    setAmount(body.item.amount == null ? "" : String(body.item.amount))
    setCurrency(body.item.currency)
    setNotes(body.item.notes || "")
    setSummary(body.item.summary || null)
    if (!row) {
      setMessage("Saved")
      await onKeep(body.item)
      setTab("receipts")
      return
    }
    await onDone()
  }

  async function remove() {
    if (!row || !window.confirm("Soft-delete this expense?")) return
    const response = await api(`${API}/${row.id}`, { method: "DELETE" })
    if (!response.ok) {
      setMessage("Delete failed")
      return
    }
    await onDone()
  }

  async function restore() {
    if (!row) return
    const response = await api(`${API}/${row.id}/restore`, { method: "POST" })
    if (!response.ok) {
      const error = await readError(response)
      setMessage(error.message || "Restore failed")
      return
    }
    await onDone()
  }

  async function summarize() {
    if (!row) return
    setSummarizing(true)
    setMessage("")
    const response = await api(`${API}/${row.id}/summarize`, { method: "POST" })
    setSummarizing(false)
    if (!response.ok) {
      const error = await readError(response)
      setMessage(error.message || "Summarize failed")
      return
    }
    const body = (await response.json()) as { item: ExpenseRow; summary: ExpenseSummary }
    setSummary(body.summary)
    setAmount(body.item.amount == null ? "" : String(body.item.amount))
    setCurrency(body.item.currency)
    setNotes(body.item.notes || "")
    setMessage("Summary ready")
    await onKeep(body.item)
  }

  return (
    <Drawer
      title={row ? `Expense ${row.mark}` : "New expense"}
      onClose={onClose}
      footer={
        tab === "receipts" ? (
          <div className="container-loading-actions">
            {row && !row.deleted_at ? (
              <button className="btn" type="button" disabled={summarizing} onClick={() => void summarize()}>
                {summarizing ? "Summarizing…" : "Summarize receipts"}
              </button>
            ) : null}
            <button className="btn-quiet" type="button" onClick={onClose}>Close</button>
          </div>
        ) : (
          <>
            <div>
              {row && !row.deleted_at ? <button className="btn-danger" type="button" onClick={() => void remove()}>Delete</button> : null}
              {row && row.deleted_at && canRestore ? <button className="btn-quiet" type="button" onClick={() => void restore()}>Restore</button> : null}
            </div>
            <button className="btn" type="button" onClick={() => void save()} disabled={Boolean(row?.deleted_at)}>Save</button>
          </>
        )
      }
    >
      {row ? (
        <div className="tabs">
          <button type="button" className={tab === "edit" ? "on" : ""} onClick={() => setTab("edit")}>Edit</button>
          <button type="button" className={tab === "receipts" ? "on" : ""} onClick={() => setTab("receipts")}>Receipts</button>
        </div>
      ) : null}
      {tab === "receipts" && row ? (
        <>
          <ReceiptsPanel itemId={row.id} canRestore={canRestore} disabled={Boolean(row.deleted_at)} />
          {summary ? <SummaryCard summary={summary} /> : <p className="muted">Run Summarize receipts to fill dashboard fields from the photos.</p>}
          {message ? <div className="banner ok">{message}</div> : null}
        </>
      ) : (
        <form className="form-grid" onSubmit={(event: FormEvent) => { event.preventDefault(); void save() }}>
          {message ? <div className="banner ok wide">{message}</div> : null}
          <Field label="Mark (auto)" error={errors.mark}>
            <input className={errors.mark ? "invalid" : ""} value={mark} onChange={(event) => setMark(event.target.value)} />
          </Field>
          <Field label="Date (auto)" error={errors.date}>
            <input type="date" className={errors.date ? "invalid" : ""} value={dateValue} onChange={(event) => setDateValue(event.target.value)} />
          </Field>
          <Field label="Amount" error={errors.amount}>
            <input
              className={errors.amount ? "invalid" : ""}
              inputMode="decimal"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              placeholder="0.00"
            />
          </Field>
          <Field label="Currency" error={errors.currency}>
            <select className={errors.currency ? "invalid" : ""} value={currency} onChange={(event) => setCurrency(event.target.value)}>
              {CURRENCIES.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </Field>
          <Field label="Notes" error={errors.notes} wide>
            <textarea className="invoice-box" value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Any additional information" />
          </Field>
        </form>
      )}
    </Drawer>
  )
}

function SummaryCard({ summary }: { summary: ExpenseSummary }) {
  return (
    <div className="expense-summary">
      <h3>Receipt summary</h3>
      <dl className="expense-summary-grid">
        <div><dt>Vendor</dt><dd>{showValue(summary.vendor)}</dd></div>
        <div><dt>Date</dt><dd>{showValue(summary.date)}</dd></div>
        <div><dt>Amount</dt><dd>{showValue(summary.amount)}</dd></div>
        <div><dt>Currency</dt><dd>{showValue(summary.currency)}</dd></div>
        <div><dt>Receipt no</dt><dd>{showValue(summary.receipt_no)}</dd></div>
        <div><dt>Category</dt><dd>{showValue(summary.category)}</dd></div>
        <div><dt>Payment</dt><dd>{showValue(summary.payment_method)}</dd></div>
        <div><dt>VAT</dt><dd>{showValue(summary.vat_amount)}</dd></div>
        <div><dt>Subtotal</dt><dd>{showValue(summary.subtotal)}</dd></div>
        <div><dt>Total</dt><dd>{showValue(summary.total)}</dd></div>
        <div className="wide"><dt>Notes</dt><dd>{showValue(summary.notes)}</dd></div>
        <div className="wide"><dt>Raw text</dt><dd>{showValue(summary.raw_text)}</dd></div>
      </dl>
      {summary.line_items?.length ? (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Description</th><th>Qty</th><th>Amount</th></tr></thead>
            <tbody>
              {summary.line_items.map((item, index) => (
                <tr key={index}>
                  <td>{showValue(item.description)}</td>
                  <td>{showValue(item.qty)}</td>
                  <td>{showValue(item.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  )
}

function ReceiptsPanel({
  itemId,
  canRestore,
  disabled,
}: {
  itemId: number
  canRestore: boolean
  disabled: boolean
}) {
  const [files, setFiles] = useState<ReceiptFile[]>([])
  const [previews, setPreviews] = useState<Record<number, string>>({})
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [viewing, setViewing] = useState<ReceiptFile | null>(null)
  const [viewUrl, setViewUrl] = useState("")
  const uploadRef = useRef<HTMLInputElement>(null)
  const cameraRef = useRef<HTMLInputElement>(null)
  const previewUrls = useRef<Record<number, string>>({})
  const viewUrlRef = useRef("")

  const load = useCallback(async () => {
    const params = canRestore ? "?include_deleted=true" : ""
    const response = await api(`${API}/${itemId}/files${params}`)
    if (!response.ok) {
      setError("Could not load receipts")
      return
    }
    const body = (await response.json()) as { items: ReceiptFile[] }
    setFiles(body.items)
    setError("")
  }, [itemId, canRestore])

  useEffect(() => { void load() }, [load])

  useEffect(() => {
    if (!viewing) {
      if (viewUrlRef.current && !Object.values(previewUrls.current).includes(viewUrlRef.current)) {
        URL.revokeObjectURL(viewUrlRef.current)
      }
      viewUrlRef.current = ""
      setViewUrl("")
      return
    }
    const existing = previews[viewing.id]
    if (existing) {
      setViewUrl(existing)
      return
    }
    let cancelled = false
    void api(`${API}/${itemId}/files/${viewing.id}`).then(async (response) => {
      if (!response.ok || cancelled) return
      const blob = await response.blob()
      if (cancelled) return
      const url = URL.createObjectURL(blob)
      viewUrlRef.current = url
      setViewUrl(url)
    })
    return () => { cancelled = true }
  }, [viewing, previews, itemId])

  useEffect(() => {
    let cancelled = false
    const next: Record<number, string> = {}
    const tasks = files
      .filter((file) => file.is_image && (!file.deleted_at || canRestore))
      .map(async (file) => {
        const response = await api(`${API}/${itemId}/files/${file.id}`)
        if (!response.ok) return
        const blob = await response.blob()
        if (cancelled) return
        next[file.id] = URL.createObjectURL(blob)
      })
    void Promise.all(tasks).then(() => {
      if (cancelled) {
        Object.values(next).forEach((url) => URL.revokeObjectURL(url))
        return
      }
      Object.values(previewUrls.current).forEach((url) => URL.revokeObjectURL(url))
      previewUrls.current = next
      setPreviews(next)
    })
    return () => { cancelled = true }
  }, [files, itemId, canRestore])

  useEffect(() => () => {
    Object.values(previewUrls.current).forEach((url) => URL.revokeObjectURL(url))
  }, [])

  async function uploadList(list: FileList | null) {
    if (!list?.length || disabled) return
    setBusy(true)
    setError("")
    const form = new FormData()
    Array.from(list).forEach((file, index) => {
      form.append("files", file)
      form.append("labels", `Receipt ${files.filter((item) => !item.deleted_at).length + index + 1}`)
    })
    const response = await api(`${API}/${itemId}/files`, { method: "POST", body: form })
    setBusy(false)
    if (!response.ok) {
      const body = await readError(response)
      setError(body.message || "Upload failed")
      return
    }
    await load()
  }

  async function removeFile(file: ReceiptFile) {
    if (!window.confirm("Remove this receipt photo?")) return
    setBusy(true)
    const response = await api(`${API}/${itemId}/files/${file.id}`, { method: "DELETE" })
    setBusy(false)
    if (!response.ok) {
      setError("Delete failed")
      return
    }
    await load()
  }

  async function restoreFile(file: ReceiptFile) {
    setBusy(true)
    const response = await api(`${API}/${itemId}/files/${file.id}/restore`, { method: "POST" })
    setBusy(false)
    if (!response.ok) {
      setError("Restore failed")
      return
    }
    await load()
  }

  const active = files.filter((file) => !file.deleted_at)
  const deleted = files.filter((file) => file.deleted_at)

  return (
    <div className="container-loading">
      <p className="muted">Upload or take multiple receipt photos.</p>
      {error ? <div className="banner err">{error}</div> : null}
      <div className="container-loading-actions">
        <button className="btn" type="button" disabled={disabled || busy} onClick={() => uploadRef.current?.click()}>Upload</button>
        <button className="btn-quiet" type="button" disabled={disabled || busy} onClick={() => cameraRef.current?.click()}>Take photo</button>
        <input ref={uploadRef} type="file" accept="image/*,application/pdf,.pdf" multiple hidden onChange={(event) => { void uploadList(event.target.files); event.target.value = "" }} />
        <input ref={cameraRef} type="file" accept="image/*" capture="environment" hidden onChange={(event) => { void uploadList(event.target.files); event.target.value = "" }} />
      </div>
      {!active.length ? <p className="muted">No receipts yet.</p> : null}
      <div className="thumbs">
        {active.map((file) => (
          <figure key={file.id} className="thumb">
            {file.is_image && previews[file.id] ? <img src={previews[file.id]} alt={file.label} /> : <div className="pdf-chip">{file.is_pdf ? "PDF" : "File"}</div>}
            <figcaption>{file.label || file.file_name}</figcaption>
            <div className="container-loading-thumb-actions">
              <button className="btn-quiet" type="button" onClick={() => setViewing(file)}>View</button>
              {!disabled ? <button className="btn-danger" type="button" disabled={busy} onClick={() => void removeFile(file)}>Delete</button> : null}
            </div>
          </figure>
        ))}
      </div>
      {canRestore && deleted.length ? (
        <div className="container-loading-deleted">
          <h3>Deleted</h3>
          <div className="thumbs">
            {deleted.map((file) => (
              <figure key={file.id} className="thumb deleted">
                {file.is_image && previews[file.id] ? <img src={previews[file.id]} alt={file.label} /> : <div className="pdf-chip">{file.is_pdf ? "PDF" : "File"}</div>}
                <figcaption>{file.label || file.file_name}</figcaption>
                <div className="container-loading-thumb-actions">
                  <button className="btn-quiet" type="button" onClick={() => setViewing(file)}>View</button>
                  <button className="btn-quiet" type="button" disabled={busy} onClick={() => void restoreFile(file)}>Restore</button>
                </div>
              </figure>
            ))}
          </div>
        </div>
      ) : null}
      {viewing ? (
        <div className="container-loading-viewer" role="dialog" aria-modal="true" onClick={() => setViewing(null)}>
          <div className="container-loading-viewer-panel" onClick={(event) => event.stopPropagation()}>
            <div className="container-loading-viewer-head">
              <strong>{viewing.label || viewing.file_name}</strong>
              <button className="btn-quiet" type="button" onClick={() => setViewing(null)}>Close</button>
            </div>
            <div className="container-loading-viewer-body">
              {!viewUrl ? <p className="muted">Loading…</p> : viewing.is_image ? (
                <img src={viewUrl} alt={viewing.label || viewing.file_name} />
              ) : viewing.is_pdf ? (
                <iframe className="container-loading-viewer-pdf" title={viewing.label || viewing.file_name} src={viewUrl} />
              ) : (
                <p className="muted">Preview not available.</p>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
