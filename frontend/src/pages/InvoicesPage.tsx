import { FormEvent, useCallback, useEffect, useRef, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { api, readError } from "../api"
import { useAuth } from "../auth"
import type { Page } from "../types"
import { Drawer, Field, Flags, Pager } from "../ui"

type LoadingOption = {
  id: number
  mark: string
  container_no: string | null
}

function loadingLabel(row: Pick<LoadingOption, "mark" | "container_no" | "id">): string {
  const cont = row.container_no?.trim()
  return cont ? `${row.mark} · ${cont}` : row.mark || `#${row.id}`
}

type InvoiceLine = {
  no?: number | null
  mark?: string | null
  shop?: string | null
  description?: string | null
  coo?: string | null
  pcs?: number | null
  hs_code?: string | null
  type?: string | null
  cartons?: number | null
  weight?: number | null
}

type InvoiceGroup = {
  mark?: string | null
  shop?: string | null
  cartons?: number | null
  weight?: number | null
  line_count?: number
}

type InvoiceData = {
  ref?: string | null
  title?: string | null
  plate_line?: string | null
  coo_line?: string | null
  container_no?: string | null
  invoice_date?: string | null
  filename?: string | null
  lines?: InvoiceLine[]
  groups?: InvoiceGroup[]
  line_count?: number
  group_count?: number
  total_cartons?: number | null
  total_weight?: number | null
}

type InvoiceRow = {
  id: number
  ref: string
  container_loading_id: number | null
  loading_mark?: string | null
  container_no: string | null
  invoice_date: string | null
  filename: string | null
  line_count?: number
  group_count?: number
  total_cartons?: number | null
  total_weight?: number | null
  groups?: InvoiceGroup[]
  invoice?: InvoiceData
  deleted_at?: string | null
}

const API = "/api/loading-invoices"

function emptyLine(index: number): InvoiceLine {
  return {
    no: index + 1,
    mark: "",
    shop: "",
    description: "",
    coo: "",
    pcs: null,
    hs_code: "",
    type: "",
    cartons: null,
    weight: null,
  }
}

function draftFromInvoice(invoice?: InvoiceData | null): InvoiceLine[] {
  const lines = invoice?.lines
  if (!Array.isArray(lines) || !lines.length) return [emptyLine(0)]
  return lines.map((line, index) => ({
    no: line.no ?? index + 1,
    mark: line.mark ?? "",
    shop: line.shop ?? "",
    description: line.description ?? "",
    coo: line.coo ?? "",
    pcs: line.pcs ?? null,
    hs_code: line.hs_code ?? "",
    type: line.type ?? "",
    cartons: line.cartons ?? null,
    weight: line.weight ?? null,
  }))
}

function numOrNull(raw: string): number | null {
  const trimmed = raw.trim()
  if (!trimmed) return null
  const n = Number(trimmed)
  return Number.isFinite(n) ? n : null
}

function formatWeight(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—"
  return Number.isInteger(value) ? String(value) : value.toFixed(2)
}

export function InvoicesPage() {
  const { user } = useAuth()
  const [searchParams] = useSearchParams()
  const [rows, setRows] = useState<InvoiceRow[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [draftQ, setDraftQ] = useState("")
  const [q, setQ] = useState("")
  const [includeDeleted, setIncludeDeleted] = useState(false)
  const [error, setError] = useState("")
  const [editing, setEditing] = useState<InvoiceRow | null>(null)
  const [creating, setCreating] = useState(false)
  const limit = 50
  const openId = searchParams.get("id")

  const load = useCallback(async () => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (q) params.set("q", q)
    if (includeDeleted) params.set("include_deleted", "true")
    const response = await api(`${API}?${params}`)
    if (!response.ok) {
      setError("Could not load invoices")
      return
    }
    const body = (await response.json()) as Page<InvoiceRow>
    setRows(body.items)
    setTotal(body.total)
    setError("")
    setEditing((current) => {
      if (!current) return current
      return body.items.find((row) => row.id === current.id) || current
    })
  }, [q, offset, includeDeleted])

  useEffect(() => { setOffset(0) }, [q, includeDeleted])
  useEffect(() => { void load() }, [load])

  useEffect(() => {
    if (!openId) return
    const id = Number(openId)
    if (!Number.isFinite(id)) return
    void api(`${API}/${id}`).then(async (response) => {
      if (!response.ok) return
      const body = (await response.json()) as { item: InvoiceRow }
      setCreating(false)
      setEditing(body.item)
    })
  }, [openId])

  return (
    <main className="page">
      <div className="page-head">
        <h1>Invoices</h1>
        <button
          className="btn"
          type="button"
          onClick={() => {
            setEditing(null)
            setCreating(true)
          }}
        >
          Add
        </button>
      </div>
      <form
        className="toolbar"
        onSubmit={(event) => {
          event.preventDefault()
          setQ(draftQ.trim())
        }}
      >
        <input
          type="search"
          placeholder="Search ref, container…"
          value={draftQ}
          onChange={(event) => setDraftQ(event.target.value)}
        />
        <button className="btn-quiet" type="submit">Search</button>
        {user?.role === "admin" ? (
          <label className="check">
            <input
              type="checkbox"
              checked={includeDeleted}
              onChange={(event) => setIncludeDeleted(event.target.checked)}
            />
            Show deleted
          </label>
        ) : null}
      </form>
      {error ? <div className="banner err">{error}</div> : null}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Ref</th>
              <th>Loading</th>
              <th>Container</th>
              <th>Date</th>
              <th>Lines</th>
              <th>Cartons</th>
              <th>Weight</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.id}
                className={row.deleted_at ? "clickable deleted" : "clickable"}
                onClick={() => {
                  setCreating(false)
                  setEditing(row)
                }}
              >
                <td>{row.ref}</td>
                <td>{row.loading_mark ?? (row.container_loading_id ? `#${row.container_loading_id}` : "")}</td>
                <td>{row.container_no ?? ""}</td>
                <td>{row.invoice_date ?? ""}</td>
                <td>{row.line_count ?? 0}</td>
                <td>{row.total_cartons ?? ""}</td>
                <td>{formatWeight(row.total_weight)}</td>
                <td><Flags legacy={false} review={false} deleted={Boolean(row.deleted_at)} /></td>
              </tr>
            ))}
            {!rows.length ? <tr><td colSpan={8} className="muted">No invoices</td></tr> : null}
          </tbody>
        </table>
      </div>
      <Pager offset={offset} limit={limit} total={total} onPage={setOffset} />
      {creating || editing ? (
        <InvoiceDrawer
          row={editing}
          canRestore={user?.role === "admin"}
          onClose={() => {
            setCreating(false)
            setEditing(null)
          }}
          onDone={async () => {
            setCreating(false)
            setEditing(null)
            await load()
          }}
          onKeep={async (item) => {
            setCreating(false)
            setEditing(item)
            await load()
          }}
        />
      ) : null}
    </main>
  )
}

function InvoiceDrawer({
  row,
  canRestore,
  onClose,
  onDone,
  onKeep,
}: {
  row: InvoiceRow | null
  canRestore: boolean
  onClose: () => void
  onDone: () => Promise<void>
  onKeep: (row: InvoiceRow) => Promise<void>
}) {
  const [refValue, setRefValue] = useState(row?.ref || "")
  const [containerNo, setContainerNo] = useState(row?.container_no || "")
  const [invoiceDate, setInvoiceDate] = useState(row?.invoice_date?.slice(0, 10) || "")
  const [loadingId, setLoadingId] = useState(
    row?.container_loading_id == null ? "" : String(row.container_loading_id),
  )
  const [loadingMark, setLoadingMark] = useState(row?.loading_mark || "")
  const [title, setTitle] = useState(row?.invoice?.title || "")
  const [plateLine, setPlateLine] = useState(row?.invoice?.plate_line || "")
  const [cooLine, setCooLine] = useState(row?.invoice?.coo_line || "")
  const [lines, setLines] = useState<InvoiceLine[]>(() => draftFromInvoice(row?.invoice))
  const [groups, setGroups] = useState<InvoiceGroup[]>(row?.invoice?.groups || row?.groups || [])
  const [filename, setFilename] = useState(row?.filename || "")
  const [totals, setTotals] = useState({
    line_count: row?.line_count ?? 0,
    group_count: row?.group_count ?? 0,
    total_cartons: row?.total_cartons ?? null,
    total_weight: row?.total_weight ?? null,
  })
  const [tab, setTab] = useState<"edit" | "lines">(row ? "lines" : "edit")
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const deleted = Boolean(row?.deleted_at)

  useEffect(() => {
    if (!row) return
    void api(`${API}/${row.id}`).then(async (response) => {
      if (!response.ok) return
      const body = (await response.json()) as { item: InvoiceRow }
      applyItem(body.item)
    })
  }, [row?.id])

  function applyItem(item: InvoiceRow) {
    setRefValue(item.ref || "")
    setContainerNo(item.container_no || "")
    setInvoiceDate(item.invoice_date?.slice(0, 10) || "")
    setLoadingId(item.container_loading_id == null ? "" : String(item.container_loading_id))
    setLoadingMark(item.loading_mark || "")
    setTitle(item.invoice?.title || "")
    setPlateLine(item.invoice?.plate_line || "")
    setCooLine(item.invoice?.coo_line || "")
    setLines(draftFromInvoice(item.invoice))
    setGroups(item.invoice?.groups || item.groups || [])
    setFilename(item.filename || "")
    setTotals({
      line_count: item.line_count ?? item.invoice?.line_count ?? 0,
      group_count: item.group_count ?? item.invoice?.group_count ?? 0,
      total_cartons: item.total_cartons ?? item.invoice?.total_cartons ?? null,
      total_weight: item.total_weight ?? item.invoice?.total_weight ?? null,
    })
  }

  const draftCartons = lines.reduce((sum, line) => sum + (typeof line.cartons === "number" ? line.cartons : 0), 0)
  const draftWeight = lines.reduce((sum, line) => sum + (typeof line.weight === "number" ? line.weight : 0), 0)
  const hasDraftWeight = lines.some((line) => typeof line.weight === "number")

  function patchLine(index: number, patch: Partial<InvoiceLine>) {
    setLines((current) => current.map((line, i) => (i === index ? { ...line, ...patch } : line)))
    setErrors((current) => {
      const next = { ...current }
      for (const key of Object.keys(next)) {
        if (key.startsWith(`lines.${index}.`)) delete next[key]
      }
      return next
    })
  }

  function addRow() {
    setLines((current) => [...current, emptyLine(current.length)])
  }

  function removeRow(index: number) {
    setLines((current) => {
      if (current.length <= 1) return [emptyLine(0)]
      return current.filter((_, i) => i !== index).map((line, i) => ({ ...line, no: line.no ?? i + 1 }))
    })
  }

  async function createHeader() {
    setBusy(true)
    setError("")
    setMessage("")
    setErrors({})
    const response = await api(API, {
      method: "POST",
      body: JSON.stringify({
        ref: refValue.trim() || "NEW",
        container_no: containerNo.trim() || null,
        invoice_date: invoiceDate || null,
        container_loading_id: loadingId.trim() === "" ? null : Number(loadingId),
      }),
    })
    setBusy(false)
    if (response.status === 422) {
      const body = await readError(response)
      setErrors(body.field_errors || {})
      setError(body.message || "Could not create invoice")
      return
    }
    if (!response.ok) {
      setError((await readError(response)).message || "Could not create invoice")
      return
    }
    const body = (await response.json()) as { item: InvoiceRow }
    setMessage("Created")
    setTab("lines")
    await onKeep(body.item)
  }

  async function saveHeader() {
    if (!row) return
    setBusy(true)
    setError("")
    setMessage("")
    setErrors({})
    const response = await api(`${API}/${row.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        ref: refValue.trim(),
        container_no: containerNo.trim() || null,
        invoice_date: invoiceDate || null,
        container_loading_id: loadingId.trim() === "" ? null : Number(loadingId),
      }),
    })
    setBusy(false)
    if (response.status === 422) {
      const body = await readError(response)
      setErrors(body.field_errors || {})
      setError(body.message || "Could not save")
      return
    }
    if (!response.ok) {
      setError((await readError(response)).message || "Could not save")
      return
    }
    const body = (await response.json()) as { item: InvoiceRow }
    applyItem(body.item)
    setMessage("Header saved")
    await onKeep(body.item)
  }

  async function saveLines() {
    if (!row || deleted || busy) return
    setBusy(true)
    setError("")
    setMessage("")
    setErrors({})
    const response = await api(`${API}/${row.id}`, {
      method: "PUT",
      body: JSON.stringify({
        ref: refValue.trim() || row.ref,
        container_loading_id: loadingId.trim() === "" ? null : Number(loadingId),
        container_no: containerNo.trim() || null,
        invoice_date: invoiceDate || null,
        title: title.trim() || null,
        plate_line: plateLine.trim() || null,
        coo_line: cooLine.trim() || null,
        filename: filename || "manual",
        lines: lines.map((line, index) => ({
          no: line.no ?? index + 1,
          mark: (line.mark || "").toString().trim() || null,
          shop: (line.shop || "").toString().trim() || null,
          description: (line.description || "").toString().trim() || null,
          coo: (line.coo || "").toString().trim() || null,
          pcs: line.pcs,
          hs_code: (line.hs_code || "").toString().trim() || null,
          type: (line.type || "").toString().trim() || null,
          cartons: line.cartons,
          weight: line.weight,
        })),
      }),
    })
    setBusy(false)
    if (response.status === 422) {
      const body = await readError(response)
      setErrors(body.field_errors || {})
      setError(body.message || "Could not save lines")
      return
    }
    if (!response.ok) {
      setError((await readError(response)).message || "Could not save lines")
      return
    }
    const body = (await response.json()) as { item: InvoiceRow }
    applyItem(body.item)
    setMessage(`Saved ${body.item.line_count || 0} lines`)
    await onKeep(body.item)
  }

  async function uploadFile(file: File) {
    if (!row || deleted) return
    setBusy(true)
    setError("")
    setMessage("")
    const form = new FormData()
    form.append("file", file)
    const response = await api(`${API}/${row.id}/file`, { method: "POST", body: form })
    setBusy(false)
    if (!response.ok) {
      setError((await readError(response)).message || "Upload failed")
      return
    }
    const body = (await response.json()) as { item: InvoiceRow }
    applyItem(body.item)
    setMessage(`Imported ${body.item.line_count || 0} lines from Excel`)
    setTab("lines")
    await onKeep(body.item)
  }

  async function remove() {
    if (!row || !window.confirm("Soft-delete this invoice?")) return
    const response = await api(`${API}/${row.id}`, { method: "DELETE" })
    if (!response.ok) {
      setError("Delete failed")
      return
    }
    await onDone()
  }

  async function restore() {
    if (!row) return
    const response = await api(`${API}/${row.id}/restore`, { method: "POST" })
    if (!response.ok) {
      setError((await readError(response)).message || "Restore failed")
      return
    }
    await onDone()
  }

  return (
    <Drawer
      title={row ? `Invoice ${row.ref}` : "New invoice"}
      onClose={onClose}
      footer={
        <>
          <div>
            {row && !deleted ? (
              <button className="btn-danger" type="button" disabled={busy} onClick={() => void remove()}>
                Delete
              </button>
            ) : null}
            {row && deleted && canRestore ? (
              <button className="btn-quiet" type="button" disabled={busy} onClick={() => void restore()}>
                Restore
              </button>
            ) : null}
          </div>
          {tab === "lines" && row ? (
            <button className="btn" type="button" disabled={deleted || busy} onClick={() => void saveLines()}>
              {busy ? "Saving…" : "Save lines"}
            </button>
          ) : (
            <button
              className="btn"
              type="button"
              disabled={busy || deleted}
              onClick={() => void (row ? saveHeader() : createHeader())}
            >
              {busy ? "Saving…" : row ? "Save" : "Create"}
            </button>
          )}
        </>
      }
    >
      {row ? (
        <div className="tabs">
          <button type="button" className={tab === "edit" ? "on" : ""} onClick={() => setTab("edit")}>Header</button>
          <button type="button" className={tab === "lines" ? "on" : ""} onClick={() => setTab("lines")}>Lines</button>
        </div>
      ) : null}

      {error ? <div className="banner err">{error}</div> : null}
      {message ? <div className="banner ok">{message}</div> : null}

      {tab === "lines" && row ? (
        <div className="container-plan-view">
          <p className="muted">
            Edit packing-list lines here, or upload Excel.
            {filename ? ` · Source: ${filename}` : ""}
          </p>

          <div className="container-loading-actions">
            <button
              className="btn-quiet"
              type="button"
              disabled={deleted || busy}
              onClick={() => fileRef.current?.click()}
            >
              Upload Excel
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".xlsx,.xlsm"
              hidden
              onChange={(event) => {
                const file = event.target.files?.[0]
                event.target.value = ""
                if (file) void uploadFile(file)
              }}
            />
            <button className="btn-quiet" type="button" disabled={deleted || busy} onClick={addRow}>
              Add row
            </button>
          </div>

          <div className="container-plan-totals">
            <div><dt>Lines</dt><dd>{lines.length}</dd></div>
            <div><dt>Groups</dt><dd>{totals.group_count || groups.length || "—"}</dd></div>
            <div><dt>Cartons</dt><dd>{draftCartons || totals.total_cartons || "—"}</dd></div>
            <div>
              <dt>Total weight</dt>
              <dd><strong>{formatWeight(hasDraftWeight ? draftWeight : totals.total_weight)}</strong> kg</dd>
            </div>
          </div>

          {groups.length ? (
            <div className="table-wrap container-plan-mix-summary">
              <table>
                <thead>
                  <tr>
                    <th>Mark</th>
                    <th>Shop</th>
                    <th>Lines</th>
                    <th>CTN</th>
                    <th>kg</th>
                  </tr>
                </thead>
                <tbody>
                  {groups.map((group, index) => (
                    <tr key={`${group.mark}-${group.shop}-${index}`}>
                      <td>{group.mark ?? ""}</td>
                      <td>{group.shop ?? ""}</td>
                      <td>{group.line_count ?? ""}</td>
                      <td>{group.cartons ?? ""}</td>
                      <td>{formatWeight(group.weight)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {loadingMark || loadingId ? (
            <p className="muted">
              Linked loading:{" "}
              {loadingId ? (
                <Link to={`/container-loading?id=${loadingId}`}>{loadingMark || `#${loadingId}`}</Link>
              ) : (
                loadingMark
              )}
            </p>
          ) : null}

          <h3 className="container-plan-heading">Invoice lines</h3>
          <div className="table-wrap">
            <table className="container-plan-edit-table invoice-lines-table">
              <thead>
                <tr>
                  <th>S.No</th>
                  <th>Mark</th>
                  <th>Shop</th>
                  <th>Description</th>
                  <th>COO</th>
                  <th>Pcs</th>
                  <th>HS code</th>
                  <th>Type</th>
                  <th>CTN</th>
                  <th>Weight</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {lines.map((line, index) => (
                  <tr key={index}>
                    <td>
                      <input
                        className="plan-cell"
                        type="number"
                        disabled={deleted || busy}
                        value={line.no ?? ""}
                        onChange={(event) => patchLine(index, { no: numOrNull(event.target.value) })}
                      />
                    </td>
                    <td>
                      <input
                        className="plan-cell"
                        disabled={deleted || busy}
                        value={line.mark ?? ""}
                        onChange={(event) => patchLine(index, { mark: event.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        className="plan-cell"
                        disabled={deleted || busy}
                        value={line.shop ?? ""}
                        onChange={(event) => patchLine(index, { shop: event.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        className={`plan-cell plan-cell-name ${errors[`lines.${index}.description`] ? "invalid" : ""}`}
                        disabled={deleted || busy}
                        value={line.description ?? ""}
                        onChange={(event) => patchLine(index, { description: event.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        className="plan-cell"
                        disabled={deleted || busy}
                        value={line.coo ?? ""}
                        onChange={(event) => patchLine(index, { coo: event.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        className={`plan-cell ${errors[`lines.${index}.pcs`] ? "invalid" : ""}`}
                        type="number"
                        disabled={deleted || busy}
                        value={line.pcs ?? ""}
                        onChange={(event) => patchLine(index, { pcs: numOrNull(event.target.value) })}
                      />
                    </td>
                    <td>
                      <input
                        className="plan-cell plan-cell-hs"
                        disabled={deleted || busy}
                        value={line.hs_code ?? ""}
                        onChange={(event) => patchLine(index, { hs_code: event.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        className="plan-cell"
                        disabled={deleted || busy}
                        value={line.type ?? ""}
                        onChange={(event) => patchLine(index, { type: event.target.value })}
                      />
                    </td>
                    <td>
                      <input
                        className={`plan-cell ${errors[`lines.${index}.cartons`] ? "invalid" : ""}`}
                        type="number"
                        disabled={deleted || busy}
                        value={line.cartons ?? ""}
                        onChange={(event) => patchLine(index, { cartons: numOrNull(event.target.value) })}
                      />
                    </td>
                    <td>
                      <input
                        className={`plan-cell ${errors[`lines.${index}.weight`] ? "invalid" : ""}`}
                        type="number"
                        step="any"
                        disabled={deleted || busy}
                        value={line.weight ?? ""}
                        onChange={(event) => patchLine(index, { weight: numOrNull(event.target.value) })}
                      />
                    </td>
                    <td>
                      <button
                        className="btn-quiet"
                        type="button"
                        disabled={deleted || busy}
                        onClick={() => removeRow(index)}
                      >
                        ×
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <Field label="Title">
            <input disabled={deleted || busy} value={title} onChange={(event) => setTitle(event.target.value)} />
          </Field>
          <Field label="Plate / date line">
            <input disabled={deleted || busy} value={plateLine} onChange={(event) => setPlateLine(event.target.value)} />
          </Field>
          <Field label="COO line">
            <input disabled={deleted || busy} value={cooLine} onChange={(event) => setCooLine(event.target.value)} />
          </Field>
        </div>
      ) : (
        <form
          className="form-grid"
          onSubmit={(event: FormEvent) => {
            event.preventDefault()
            void (row ? saveHeader() : createHeader())
          }}
        >
          <Field label="Ref" error={errors.ref}>
            <input
              className={errors.ref ? "invalid" : ""}
              value={refValue}
              disabled={busy || deleted}
              onChange={(event) => setRefValue(event.target.value)}
              placeholder="DR1249"
            />
          </Field>
          <Field label="Container number" error={errors.container_no}>
            <input
              className={errors.container_no ? "invalid" : ""}
              value={containerNo}
              disabled={busy || deleted}
              onChange={(event) => setContainerNo(event.target.value)}
            />
          </Field>
          <Field label="Invoice date" error={errors.invoice_date}>
            <input
              type="date"
              className={errors.invoice_date ? "invalid" : ""}
              value={invoiceDate}
              disabled={busy || deleted}
              onChange={(event) => setInvoiceDate(event.target.value)}
            />
          </Field>
          <Field label="Container loading" error={errors.container_loading_id} wide>
            <LoadingSelect
              loadingId={loadingId}
              loadingMark={loadingMark}
              invalid={Boolean(errors.container_loading_id)}
              disabled={busy || deleted}
              onSelect={(option) => {
                if (!option) {
                  setLoadingId("")
                  setLoadingMark("")
                  return
                }
                setLoadingId(String(option.id))
                setLoadingMark(option.mark)
                if (!containerNo.trim() && option.container_no) {
                  setContainerNo(option.container_no)
                }
              }}
            />
          </Field>
          {loadingId ? (
            <p className="muted wide">
              Open: <Link to={`/container-loading?id=${loadingId}`}>{loadingMark || `#${loadingId}`}</Link>
            </p>
          ) : null}
          {row ? (
            <p className="muted wide">
              After create, open the Lines tab to edit packing rows or upload Excel.
            </p>
          ) : (
            <p className="muted wide">Create the header first, then add lines or upload Excel.</p>
          )}
        </form>
      )}
    </Drawer>
  )
}

function LoadingSelect({
  loadingId,
  loadingMark,
  invalid,
  disabled,
  onSelect,
}: {
  loadingId: string
  loadingMark: string
  invalid?: boolean
  disabled?: boolean
  onSelect: (option: LoadingOption | null) => void
}) {
  const rootRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [options, setOptions] = useState<LoadingOption[]>([])
  const [fetching, setFetching] = useState(false)

  const selectedLabel = loadingId
    ? loadingLabel({
        id: Number(loadingId),
        mark: loadingMark || `Loading #${loadingId}`,
        container_no: null,
      })
    : ""

  useEffect(() => {
    if (!open) return
    const timer = window.setTimeout(() => {
      setFetching(true)
      const params = new URLSearchParams({ limit: "40", offset: "0" })
      if (query.trim()) params.set("q", query.trim())
      void api(`/api/container-loading?${params}`).then(async (response) => {
        setFetching(false)
        if (!response.ok) {
          setOptions([])
          return
        }
        const body = (await response.json()) as Page<LoadingOption>
        setOptions(body.items.map((item) => ({
          id: item.id,
          mark: item.mark,
          container_no: item.container_no,
        })))
      })
    }, 200)
    return () => window.clearTimeout(timer)
  }, [open, query])

  useEffect(() => {
    if (!open) return
    function onDoc(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", onDoc)
    return () => document.removeEventListener("mousedown", onDoc)
  }, [open])

  return (
    <div className={`loading-select ${invalid ? "invalid" : ""}`} ref={rootRef}>
      <div className="loading-select-control">
        <input
          className={invalid ? "invalid" : ""}
          disabled={disabled}
          value={open ? query : selectedLabel}
          placeholder="Search mark or container…"
          onFocus={() => {
            if (disabled) return
            setOpen(true)
            setQuery("")
          }}
          onChange={(event) => {
            setOpen(true)
            setQuery(event.target.value)
          }}
        />
        {loadingId && !disabled ? (
          <button
            className="btn-quiet"
            type="button"
            onClick={() => {
              onSelect(null)
              setQuery("")
              setOpen(false)
            }}
          >
            Clear
          </button>
        ) : null}
      </div>
      {open && !disabled ? (
        <ul className="loading-select-menu" role="listbox">
          {fetching ? <li className="muted">Searching…</li> : null}
          {!fetching && !options.length ? <li className="muted">No loadings found</li> : null}
          {options.map((option) => (
            <li key={option.id}>
              <button
                type="button"
                className={String(option.id) === loadingId ? "on" : ""}
                onClick={() => {
                  onSelect(option)
                  setOpen(false)
                  setQuery("")
                }}
              >
                <strong>{option.mark}</strong>
                <span className="muted">
                  {option.container_no ? ` · ${option.container_no}` : ""} · #{option.id}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
