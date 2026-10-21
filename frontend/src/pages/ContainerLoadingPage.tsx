import { FormEvent, useCallback, useEffect, useRef, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { api, readError } from "../api"
import { useAuth } from "../auth"
import {
  emptyPlanLine,
  planToPallets,
  sumPlanWeight,
  type LoadingPlan,
  type PlanLine,
} from "../containerPlanLayout"
import type { Page } from "../types"
import { Drawer, Field, Flags, Pager } from "../ui"
import { Container3DView } from "./Container3DView"

type LoadingMark = {
  name: string
  customer_code?: string | null
  mix?: number | null
  cartons?: number | null
  weight_kg?: number | null
  notes?: string | null
}

type LoadingPallet = {
  side: "left" | "right" | string
  marks: LoadingMark[]
}

type LoadingExtract = {
  pallets: LoadingPallet[]
  issues: string[]
  notes: string | null
  readable: boolean
}

type LoadingCheck = {
  ok: boolean
  matched: string[]
  missing_from_photos: string[]
  extra_in_photos: string[]
  mismatches: { plan_name: string | null; photo_name: string | null; detail: string | null }[]
  notes: string | null
}

type LoadingRow = {
  id: number
  mark: string
  container_no: string | null
  file_count?: number
  plan_filename?: string | null
  plan_line_count?: number
  plan?: LoadingPlan
  check?: LoadingCheck | null
  summary?: { mark_count?: number; photo_count?: number } | null
  invoices?: { id: number; ref: string }[]
  deleted_at?: string | null
}

type LoadingFile = {
  id: number
  kind: string
  label: string
  file_name: string
  mime: string
  is_image: boolean
  is_pdf: boolean
  extracted: LoadingExtract | null
  deleted_at: string | null
  created_at: string | null
}

const API = "/api/container-loading"

const emptyExtract = (): LoadingExtract => ({
  pallets: [
    { side: "left", marks: [] },
    { side: "right", marks: [] },
  ],
  issues: [],
  notes: null,
  readable: true,
})

export function ContainerLoadingPage() {
  const { user } = useAuth()
  const [searchParams] = useSearchParams()
  const [rows, setRows] = useState<LoadingRow[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [draftQ, setDraftQ] = useState("")
  const [q, setQ] = useState("")
  const [includeDeleted, setIncludeDeleted] = useState(false)
  const [error, setError] = useState("")
  const [editing, setEditing] = useState<LoadingRow | null>(null)
  const [creating, setCreating] = useState(false)
  const limit = 50
  const openId = searchParams.get("id")

  const load = useCallback(async () => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (q) params.set("q", q)
    if (includeDeleted) params.set("include_deleted", "true")
    const response = await api(`${API}?${params}`)
    if (!response.ok) {
      setError("Could not load container loading rows")
      return
    }
    const body = (await response.json()) as Page<LoadingRow>
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
      const body = (await response.json()) as { item: LoadingRow }
      setCreating(false)
      setEditing(body.item)
    })
  }, [openId])

  return (
    <main className="page">
      <div className="page-head">
        <h1>Container loading</h1>
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
          placeholder="Search mark or container number…"
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
              <th>Mark</th>
              <th>Container number</th>
              <th>Photos</th>
              <th>Plan</th>
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
                <td>{row.mark}</td>
                <td>{row.container_no ?? ""}</td>
                <td>{row.file_count ?? 0}</td>
                <td>{row.plan_line_count ? `${row.plan_line_count} lines` : "—"}</td>
                <td>
                  <Flags legacy={false} review={false} deleted={Boolean(row.deleted_at)} />
                </td>
              </tr>
            ))}
            {!rows.length ? (
              <tr><td colSpan={5} className="muted">No container loading rows</td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <Pager offset={offset} limit={limit} total={total} onPage={setOffset} />
      {creating || editing ? (
        <LoadingDrawer
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
          onFilesChanged={load}
        />
      ) : null}
    </main>
  )
}

function LoadingDrawer({
  row,
  canRestore,
  onClose,
  onDone,
  onKeep,
  onFilesChanged,
}: {
  row: LoadingRow | null
  canRestore: boolean
  onClose: () => void
  onDone: () => Promise<void>
  onKeep: (row: LoadingRow) => Promise<void>
  onFilesChanged: () => Promise<void>
}) {
  const [mark, setMark] = useState(row?.mark || "")
  const [containerNo, setContainerNo] = useState(row?.container_no || "")
  const [tab, setTab] = useState<"edit" | "photos" | "plan" | "invoice" | "3d">(row ? "photos" : "edit")
  const [message, setMessage] = useState("")
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [check, setCheck] = useState<LoadingCheck | null>(row?.check || null)
  const [summarizing, setSummarizing] = useState(false)
  const [plan, setPlan] = useState<LoadingPlan>(row?.plan || null)
  const [planInfo, setPlanInfo] = useState({
    filename: row?.plan_filename || "",
    lineCount: row?.plan_line_count || 0,
  })
  const invoiceCount = row?.invoices?.length || 0

  useEffect(() => {
    setMark(row?.mark || "")
    setContainerNo(row?.container_no || "")
    setCheck(row?.check || null)
    setPlan(row?.plan || null)
    setPlanInfo({
      filename: row?.plan_filename || "",
      lineCount: row?.plan_line_count || 0,
    })
  }, [row])

  useEffect(() => {
    if (row) return
    void api(`${API}/next-mark`).then(async (response) => {
      if (!response.ok) return
      const body = (await response.json()) as { mark: string }
      setMark(body.mark)
    })
  }, [row])

  async function save() {
    const payload = { mark: mark.trim(), container_no: containerNo.trim() || null }
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
    const body = (await response.json()) as { item: LoadingRow }
    setErrors({})
    setMark(body.item.mark)
    setContainerNo(body.item.container_no || "")
    if (!row) {
      setMessage("Saved")
      await onKeep(body.item)
      setTab("photos")
      return
    }
    await onDone()
  }

  async function remove() {
    if (!row || !window.confirm("Soft-delete this container loading row?")) return
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
      setMessage("Restore failed")
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
    const body = (await response.json()) as {
      item: LoadingRow
      check: LoadingCheck | null
      plan_required?: boolean
    }
    setCheck(body.check)
    setContainerNo(body.item.container_no || "")
    setPlanInfo({
      filename: body.item.plan_filename || "",
      lineCount: body.item.plan_line_count || 0,
    })
    setMessage(
      body.plan_required
        ? "Photos extracted. Upload a loading plan to run the plan check."
        : body.check?.ok
          ? "Plan check OK"
          : "Plan check finished — review missing / mismatches",
    )
    await onKeep(body.item)
  }

  return (
    <Drawer
      title={row ? `Container loading ${row.mark}` : "New container loading"}
      onClose={onClose}
      wide={tab === "3d" || tab === "plan" || tab === "invoice"}
      footer={
        tab === "photos" ? (
          <div className="container-loading-actions">
            {row && !row.deleted_at ? (
              <button className="btn" type="button" disabled={summarizing} onClick={() => void summarize()}>
                {summarizing ? "Working…" : "Extract & check"}
              </button>
            ) : null}
            <button className="btn-quiet" type="button" onClick={onClose}>Close</button>
          </div>
        ) : tab === "3d" || tab === "plan" || tab === "invoice" ? (
          <button className="btn-quiet" type="button" onClick={onClose}>Close</button>
        ) : (
          <>
            <div>
              {row && !row.deleted_at ? (
                <button className="btn-danger" type="button" onClick={() => void remove()}>Delete</button>
              ) : null}
              {row && row.deleted_at && canRestore ? (
                <button className="btn-quiet" type="button" onClick={() => void restore()}>Restore</button>
              ) : null}
            </div>
            <button className="btn" type="button" onClick={() => void save()} disabled={Boolean(row?.deleted_at)}>
              Save
            </button>
          </>
        )
      }
    >
      {row ? (
        <div className="tabs">
          <button type="button" className={tab === "edit" ? "on" : ""} onClick={() => setTab("edit")}>Edit</button>
          <button type="button" className={tab === "photos" ? "on" : ""} onClick={() => setTab("photos")}>Photos</button>
          <button type="button" className={tab === "plan" ? "on" : ""} onClick={() => setTab("plan")}>Plan</button>
          <button type="button" className={tab === "invoice" ? "on" : ""} onClick={() => setTab("invoice")}>
            Invoice{invoiceCount ? ` (${invoiceCount})` : ""}
          </button>
          <button type="button" className={tab === "3d" ? "on" : ""} onClick={() => setTab("3d")}>3D</button>
        </div>
      ) : null}
      {tab === "plan" && row ? (
        <PlanEditor
          itemId={row.id}
          plan={plan}
          filename={planInfo.filename}
          disabled={Boolean(row.deleted_at)}
          onPlanChange={(item) => {
            setPlan(item.plan || null)
            setPlanInfo({
              filename: item.plan_filename || "",
              lineCount: item.plan_line_count || 0,
            })
            setContainerNo(item.container_no || "")
            setCheck(item.check || null)
            void onKeep(item)
          }}
        />
      ) : null}
      {tab === "invoice" && row ? (
        <LoadingInvoicesPanel loadingId={row.id} linked={row.invoices || []} />
      ) : null}
      {tab === "3d" && row ? (
        <Container3DView plan={plan} label={row.mark} />
      ) : null}
      {tab === "photos" && row ? (
        <>
          <ContainerLoadingPanel
            itemId={row.id}
            canRestore={canRestore}
            disabled={Boolean(row.deleted_at)}
            planFilename={planInfo.filename}
            planLineCount={planInfo.lineCount}
            onPlanChange={(item) => {
              setPlan(item.plan || null)
              setPlanInfo({
                filename: item.plan_filename || "",
                lineCount: item.plan_line_count || 0,
              })
              setContainerNo(item.container_no || "")
              setCheck(item.check || null)
              void onKeep(item)
            }}
            onFilesChanged={onFilesChanged}
          />
          {check ? <CheckCard check={check} /> : (
            <p className="muted">Build or upload a loading plan (Plan tab or Excel here), add photos, then Extract &amp; check.</p>
          )}
          {message ? <div className="banner ok">{message}</div> : null}
        </>
      ) : null}
      {tab === "edit" || !row ? (
        <form className="form-grid" onSubmit={(event: FormEvent) => { event.preventDefault(); void save() }}>
          {message ? <div className="banner ok wide">{message}</div> : null}
          <Field label="Mark" error={errors.mark}>
            <input
              className={errors.mark ? "invalid" : ""}
              value={mark}
              onChange={(event) => {
                setMark(event.target.value)
                setErrors((current) => ({ ...current, mark: "" }))
              }}
              placeholder="CL1 or any mark"
            />
          </Field>
          <Field label="Container number" error={errors.container_no} wide>
            <input
              className={errors.container_no ? "invalid" : ""}
              value={containerNo}
              onChange={(event) => setContainerNo(event.target.value)}
              placeholder="Container number"
            />
          </Field>
          {row?.invoices?.length ? (
            <div className="field wide">
              <span>Linked invoices</span>
              <p className="muted" style={{ margin: 0 }}>
                {row.invoices.map((invoice, index) => (
                  <span key={invoice.id}>
                    {index ? " · " : null}
                    <Link to={`/invoices?id=${invoice.id}`}>{invoice.ref}</Link>
                  </span>
                ))}
              </p>
            </div>
          ) : null}
        </form>
      ) : null}
    </Drawer>
  )
}

type LinkedInvoiceLine = {
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

type LinkedInvoiceGroup = {
  mark?: string | null
  shop?: string | null
  cartons?: number | null
  weight?: number | null
  line_count?: number
}

type LinkedInvoiceDetail = {
  id: number
  ref: string
  container_no: string | null
  invoice_date: string | null
  filename: string | null
  line_count?: number
  group_count?: number
  total_cartons?: number | null
  total_weight?: number | null
  invoice?: {
    lines?: LinkedInvoiceLine[]
    groups?: LinkedInvoiceGroup[]
    title?: string | null
    plate_line?: string | null
    coo_line?: string | null
  }
}

function formatInvoiceWeight(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—"
  return Number.isInteger(value) ? String(value) : value.toFixed(2)
}

function LoadingInvoicesPanel({
  loadingId,
  linked,
}: {
  loadingId: number
  linked: { id: number; ref: string }[]
}) {
  const [items, setItems] = useState<LinkedInvoiceDetail[]>([])
  const [activeId, setActiveId] = useState<number | null>(linked[0]?.id ?? null)
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError("")
    void api(`/api/loading-invoices?container_loading_id=${loadingId}&limit=50`).then(async (response) => {
      if (cancelled) return
      if (!response.ok) {
        setLoading(false)
        setError("Could not load invoices")
        return
      }
      const body = (await response.json()) as Page<{ id: number }>
      const ids = body.items.map((item) => item.id)
      if (!ids.length) {
        setItems([])
        setActiveId(null)
        setLoading(false)
        return
      }
      const details = await Promise.all(
        ids.map(async (id) => {
          const detail = await api(`/api/loading-invoices/${id}`)
          if (!detail.ok) return null
          const payload = (await detail.json()) as { item: LinkedInvoiceDetail }
          return payload.item
        }),
      )
      if (cancelled) return
      const next = details.filter((item): item is LinkedInvoiceDetail => Boolean(item))
      setItems(next)
      setActiveId((current) => {
        if (current && next.some((item) => item.id === current)) return current
        return next[0]?.id ?? null
      })
      setLoading(false)
    })
    return () => { cancelled = true }
  }, [loadingId])

  const active = items.find((item) => item.id === activeId) || null
  const lines = active?.invoice?.lines || []
  const groups = active?.invoice?.groups || []

  if (loading) return <p className="muted">Loading invoices…</p>
  if (error) return <div className="banner err">{error}</div>
  if (!items.length) {
    return (
      <div className="container-plan-view">
        <p className="muted">No invoice linked to this loading yet.</p>
        <p>
          <Link className="btn" to="/invoices">Create / link an invoice</Link>
        </p>
        {linked.length ? (
          <p className="muted">
            Stale links:{" "}
            {linked.map((invoice, index) => (
              <span key={invoice.id}>
                {index ? " · " : null}
                <Link to={`/invoices?id=${invoice.id}`}>{invoice.ref}</Link>
              </span>
            ))}
          </p>
        ) : null}
      </div>
    )
  }

  return (
    <div className="container-plan-view">
      <div className="container-loading-actions">
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className={item.id === activeId ? "btn" : "btn-quiet"}
            onClick={() => setActiveId(item.id)}
          >
            {item.ref}
          </button>
        ))}
        {active ? (
          <Link className="btn-quiet" to={`/invoices?id=${active.id}`}>Edit invoice</Link>
        ) : null}
      </div>

      {active ? (
        <>
          <p className="muted">
            {active.invoice?.title || active.ref}
            {active.filename ? ` · ${active.filename}` : ""}
            {active.invoice_date ? ` · ${active.invoice_date.slice(0, 10)}` : ""}
            {active.container_no ? ` · cont ${active.container_no}` : ""}
          </p>
          {active.invoice?.plate_line ? <p className="muted">{active.invoice.plate_line}</p> : null}
          {active.invoice?.coo_line ? <p className="muted">{active.invoice.coo_line}</p> : null}

          <div className="container-plan-totals">
            <div><dt>Lines</dt><dd>{active.line_count ?? lines.length}</dd></div>
            <div><dt>Groups</dt><dd>{active.group_count ?? groups.length}</dd></div>
            <div><dt>Cartons</dt><dd>{active.total_cartons ?? "—"}</dd></div>
            <div><dt>Weight</dt><dd><strong>{formatInvoiceWeight(active.total_weight)}</strong> kg</dd></div>
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
                      <td>{formatInvoiceWeight(group.weight)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
                </tr>
              </thead>
              <tbody>
                {lines.map((line, index) => (
                  <tr key={index}>
                    <td>{line.no ?? index + 1}</td>
                    <td>{line.mark ?? ""}</td>
                    <td>{line.shop ?? ""}</td>
                    <td>{line.description ?? ""}</td>
                    <td>{line.coo ?? ""}</td>
                    <td>{line.pcs ?? ""}</td>
                    <td>{line.hs_code ?? ""}</td>
                    <td>{line.type ?? ""}</td>
                    <td>{line.cartons ?? ""}</td>
                    <td>{formatInvoiceWeight(line.weight)}</td>
                  </tr>
                ))}
                {!lines.length ? (
                  <tr><td colSpan={10} className="muted">No lines</td></tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  )
}

function draftFromPlan(plan: LoadingPlan): PlanLine[] {
  const lines = plan?.lines
  if (!lines?.length) return [emptyPlanLine(0)]
  return lines.map((line, index) => ({
    no: line.no ?? index + 1,
    customer_code: line.customer_code ?? "",
    cust_name: line.cust_name ?? null,
    mix: typeof line.mix === "number" ? line.mix : 1,
    name: line.name ?? "",
    cartons: line.cartons ?? null,
    weight: line.weight ?? line.total_weight ?? null,
    pw: line.pw ?? null,
    total_weight: line.total_weight ?? line.weight ?? null,
    hidden: line.hidden,
  }))
}

function PlanEditor({
  itemId,
  plan,
  filename,
  disabled,
  onPlanChange,
}: {
  itemId: number
  plan: LoadingPlan
  filename: string
  disabled: boolean
  onPlanChange: (item: LoadingRow) => void
}) {
  const [lines, setLines] = useState<PlanLine[]>(() => draftFromPlan(plan))
  const [containerNumber, setContainerNumber] = useState(plan?.container_number || "")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    setLines(draftFromPlan(plan))
    setContainerNumber(plan?.container_number || "")
    setError("")
    setMessage("")
    setFieldErrors({})
  }, [plan])

  const draftPlan = { lines, container_number: containerNumber || null }
  const pallets = planToPallets(draftPlan)
  const totalWeight = sumPlanWeight(draftPlan)
  const validCount = lines.filter((line) => (line.name || "").trim() && typeof line.mix === "number" && line.mix >= 1).length
  const warnings = plan?.warnings || []
  const hiddenCount = plan?.hidden_row_count || lines.filter((r) => r.hidden).length

  function patchLine(index: number, patch: Partial<PlanLine>) {
    setLines((current) => current.map((line, i) => (i === index ? { ...line, ...patch } : line)))
    setFieldErrors((current) => {
      const next = { ...current }
      for (const key of Object.keys(next)) {
        if (key.startsWith(`lines.${index}.`)) delete next[key]
      }
      return next
    })
  }

  function addRow() {
    setLines((current) => [...current, emptyPlanLine(current.length)])
  }

  function removeRow(index: number) {
    setLines((current) => {
      if (current.length <= 1) return [emptyPlanLine(0)]
      return current.filter((_, i) => i !== index).map((line, i) => ({ ...line, no: line.no ?? i + 1 }))
    })
  }

  async function savePlan() {
    if (disabled || busy) return
    const named = lines.filter((line) => (line.name || "").trim())
    if (!named.length) {
      setError("Add at least one row with a name and mix")
      return
    }
    setBusy(true)
    setError("")
    setMessage("")
    setFieldErrors({})
    const response = await api(`${API}/${itemId}/plan`, {
      method: "PUT",
      body: JSON.stringify({
        container_number: containerNumber.trim() || null,
        lines: lines.map((line, index) => ({
          no: line.no ?? index + 1,
          customer_code: (line.customer_code || "").toString().trim() || null,
          cust_name: line.cust_name || null,
          mix: line.mix,
          name: (line.name || "").trim(),
          cartons: line.cartons,
          weight: line.weight,
          pw: line.pw,
          total_weight: line.weight ?? line.total_weight,
        })),
      }),
    })
    setBusy(false)
    if (response.status === 422) {
      const body = await readError(response)
      setFieldErrors(body.field_errors || {})
      setError(body.message || "Could not save plan")
      return
    }
    if (!response.ok) {
      setError((await readError(response)).message || "Could not save plan")
      return
    }
    const body = (await response.json()) as { item: LoadingRow }
    setMessage(`Saved ${body.item.plan_line_count || 0} plan rows`)
    onPlanChange(body.item)
  }

  return (
    <div className="container-plan-view">
      <p className="muted">
        Edit the loading plan here (or import Excel on Photos). Mix numbers drive 3D pallets.
        {filename ? ` · Source: ${filename}` : ""}
      </p>
      {warnings.map((warning, index) => (
        <div key={index} className="banner warn">{warning.message}</div>
      ))}
      {hiddenCount && !warnings.length ? (
        <div className="banner warn">
          {hiddenCount} row(s) were hidden in Excel but are still included until you save edits.
        </div>
      ) : null}
      {error ? <div className="banner err">{error}</div> : null}
      {message ? <div className="banner ok">{message}</div> : null}

      <Field label="Container number (from plan)">
        <input
          value={containerNumber}
          disabled={disabled || busy}
          onChange={(event) => setContainerNumber(event.target.value)}
          placeholder="Optional"
        />
      </Field>

      <div className="container-plan-totals">
        <div><dt>Rows</dt><dd>{lines.length}</dd></div>
        <div><dt>Valid marks</dt><dd>{validCount}</dd></div>
        <div><dt>Pallets (mix)</dt><dd>{pallets.length}</dd></div>
        <div><dt>Total weight</dt><dd><strong>{formatWeight(totalWeight)}</strong> kg</dd></div>
      </div>

      {pallets.length ? (
        <div className="table-wrap container-plan-mix-summary">
          <table>
            <thead>
              <tr>
                <th>Mix / pallet</th>
                <th>Side</th>
                <th>Marks</th>
                <th>Names</th>
              </tr>
            </thead>
            <tbody>
              {pallets.map((pallet) => (
                <tr key={pallet.mix} className={pallet.marks.length > 1 ? "plan-mix-multi" : undefined}>
                  <td>P{pallet.mix}</td>
                  <td>{pallet.side}</td>
                  <td><strong>{pallet.marks.length}</strong></td>
                  <td className="muted">{pallet.marks.map((m) => m.name).join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <div className="container-loading-actions">
        <button className="btn" type="button" disabled={disabled || busy || validCount < 1} onClick={() => void savePlan()}>
          {busy ? "Saving…" : "Save plan"}
        </button>
        <button className="btn-quiet" type="button" disabled={disabled || busy} onClick={addRow}>
          Add row
        </button>
      </div>

      <h3 className="container-plan-heading">Plan rows</h3>
      <div className="table-wrap">
        <table className="container-plan-edit-table">
          <thead>
            <tr>
              <th>No</th>
              <th>Mix</th>
              <th>Code</th>
              <th>Name</th>
              <th>CTN</th>
              <th>kg</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line, index) => (
              <tr key={index} className={line.hidden ? "plan-row-hidden" : undefined}>
                <td>
                  <input
                    className="plan-cell"
                    type="number"
                    disabled={disabled || busy}
                    value={line.no ?? ""}
                    onChange={(event) => patchLine(index, { no: numOrNull(event.target.value) })}
                  />
                </td>
                <td>
                  <input
                    className={`plan-cell ${fieldErrors[`lines.${index}.mix`] ? "invalid" : ""}`}
                    type="number"
                    min={1}
                    disabled={disabled || busy}
                    value={line.mix ?? ""}
                    onChange={(event) => patchLine(index, { mix: numOrNull(event.target.value) })}
                  />
                </td>
                <td>
                  <input
                    className="plan-cell"
                    disabled={disabled || busy}
                    value={line.customer_code ?? ""}
                    onChange={(event) => patchLine(index, { customer_code: event.target.value })}
                  />
                </td>
                <td>
                  <input
                    className={`plan-cell plan-cell-name ${fieldErrors[`lines.${index}.name`] ? "invalid" : ""}`}
                    disabled={disabled || busy}
                    value={line.name ?? ""}
                    onChange={(event) => patchLine(index, { name: event.target.value })}
                    placeholder="Mark name"
                  />
                </td>
                <td>
                  <input
                    className="plan-cell"
                    type="number"
                    disabled={disabled || busy}
                    value={line.cartons ?? ""}
                    onChange={(event) => patchLine(index, { cartons: numOrNull(event.target.value) })}
                  />
                </td>
                <td>
                  <input
                    className="plan-cell"
                    type="number"
                    step="any"
                    disabled={disabled || busy}
                    value={line.weight ?? ""}
                    onChange={(event) => patchLine(index, { weight: floatOrNull(event.target.value) })}
                  />
                </td>
                <td>
                  <button
                    className="btn-quiet"
                    type="button"
                    disabled={disabled || busy}
                    onClick={() => removeRow(index)}
                  >
                    Remove
                  </button>
                  {line.hidden ? <span className="badge warn">Hidden</span> : null}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={5} className="muted">Total weight</td>
              <td><strong>{formatWeight(totalWeight)}</strong></td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  )
}

function numOrNull(raw: string): number | null {
  if (raw.trim() === "") return null
  const value = Number(raw)
  return Number.isFinite(value) ? Math.trunc(value) : null
}

function floatOrNull(raw: string): number | null {
  if (raw.trim() === "") return null
  const value = Number(raw)
  return Number.isFinite(value) ? value : null
}

function formatWeight(value: number): string {
  if (!Number.isFinite(value)) return "0"
  return Number.isInteger(value) ? String(value) : String(Math.round(value * 100) / 100)
}

function CheckCard({ check }: { check: LoadingCheck }) {
  return (
    <div className="expense-summary">
      <h3>Plan check {check.ok ? "· OK" : "· review"}</h3>
      <dl className="expense-summary-grid">
        <div><dt>Matched</dt><dd>{check.matched?.length ?? 0}</dd></div>
        <div><dt>Missing</dt><dd>{check.missing_from_photos?.length ?? 0}</dd></div>
        <div><dt>Extra</dt><dd>{check.extra_in_photos?.length ?? 0}</dd></div>
        <div><dt>Mismatches</dt><dd>{check.mismatches?.length ?? 0}</dd></div>
      </dl>
      {check.missing_from_photos?.length ? (
        <p><strong>Missing from photos:</strong> {check.missing_from_photos.join(", ")}</p>
      ) : null}
      {check.extra_in_photos?.length ? (
        <p><strong>Extra in photos:</strong> {check.extra_in_photos.join(", ")}</p>
      ) : null}
      {check.mismatches?.length ? (
        <ul>
          {check.mismatches.map((item, index) => (
            <li key={index}>
              {item.plan_name || "—"} ↔ {item.photo_name || "—"}
              {item.detail ? ` — ${item.detail}` : ""}
            </li>
          ))}
        </ul>
      ) : null}
      {check.notes ? <p className="muted">{check.notes}</p> : null}
    </div>
  )
}

function markCount(extract: LoadingExtract | null | undefined) {
  if (!extract?.pallets) return 0
  return extract.pallets.reduce((n, pallet) => n + (pallet.marks?.length || 0), 0)
}

function ContainerLoadingPanel({
  itemId,
  canRestore,
  disabled,
  planFilename,
  planLineCount,
  onPlanChange,
  onFilesChanged,
}: {
  itemId: number
  canRestore: boolean
  disabled: boolean
  planFilename: string
  planLineCount: number
  onPlanChange: (item: LoadingRow) => void
  onFilesChanged: () => Promise<void>
}) {
  const [files, setFiles] = useState<LoadingFile[]>([])
  const [previews, setPreviews] = useState<Record<number, string>>({})
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [busy, setBusy] = useState(false)
  const [openFileId, setOpenFileId] = useState<number | null>(null)
  const uploadRef = useRef<HTMLInputElement>(null)
  const cameraRef = useRef<HTMLInputElement>(null)
  const planRef = useRef<HTMLInputElement>(null)
  const previewUrls = useRef<Record<number, string>>({})

  const load = useCallback(async () => {
    const params = canRestore ? "?include_deleted=true" : ""
    const response = await api(`${API}/${itemId}/files${params}`)
    if (!response.ok) {
      setError("Could not load photos")
      return
    }
    const body = (await response.json()) as { items: LoadingFile[] }
    setFiles(body.items)
    setError("")
  }, [itemId, canRestore])

  useEffect(() => { void load() }, [load])

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
    return () => {
      cancelled = true
    }
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
      form.append("labels", `Loading ${files.filter((item) => !item.deleted_at).length + index + 1}`)
    })
    const response = await api(`${API}/${itemId}/files`, { method: "POST", body: form })
    setBusy(false)
    if (!response.ok) {
      const body = await readError(response)
      setError(body.message || "Upload failed")
      return
    }
    await load()
    await onFilesChanged()
  }

  async function uploadPlan(list: FileList | null) {
    if (!list?.length || disabled) return
    setBusy(true)
    setError("")
    setNotice("")
    const form = new FormData()
    form.append("file", list[0])
    const response = await api(`${API}/${itemId}/plan`, { method: "POST", body: form })
    setBusy(false)
    if (!response.ok) {
      const body = await readError(response)
      setError(body.message || "Plan upload failed")
      return
    }
    const body = (await response.json()) as { item: LoadingRow }
    const warn = body.item.plan?.warnings?.[0]?.message
    const hidden = body.item.plan?.hidden_row_count || 0
    if (warn) setNotice(warn)
    else if (hidden) setNotice(`${hidden} Excel row(s) were hidden but still loaded into the plan.`)
    onPlanChange(body.item)
  }

  async function clearPlan() {
    if (!window.confirm("Remove the loading plan from this row?")) return
    setBusy(true)
    const response = await api(`${API}/${itemId}/plan`, { method: "DELETE" })
    setBusy(false)
    if (!response.ok) {
      setError("Could not clear plan")
      return
    }
    const body = (await response.json()) as { item: LoadingRow }
    onPlanChange(body.item)
  }

  async function removeFile(file: LoadingFile) {
    if (!window.confirm("Remove this photo?")) return
    setBusy(true)
    const response = await api(`${API}/${itemId}/files/${file.id}`, { method: "DELETE" })
    setBusy(false)
    if (!response.ok) {
      setError("Delete failed")
      return
    }
    if (openFileId === file.id) setOpenFileId(null)
    await load()
    await onFilesChanged()
  }

  async function restoreFile(file: LoadingFile) {
    setBusy(true)
    const response = await api(`${API}/${itemId}/files/${file.id}/restore`, { method: "POST" })
    setBusy(false)
    if (!response.ok) {
      setError("Restore failed")
      return
    }
    await load()
    await onFilesChanged()
  }

  const active = files.filter((file) => !file.deleted_at)
  const deleted = files.filter((file) => file.deleted_at)
  const openFile = openFileId == null ? null : files.find((file) => file.id === openFileId) || null

  return (
    <div className="container-loading">
      <p className="muted">
        Click a photo to view and extract marks (2 pallets, multiple customers). Upload a loading plan Excel to check against.
      </p>
      {error ? <div className="banner err">{error}</div> : null}
      {notice ? <div className="banner warn">{notice}</div> : null}

      <div className="container-loading-actions">
        <button className="btn" type="button" disabled={disabled || busy} onClick={() => uploadRef.current?.click()}>
          Upload photos
        </button>
        <button className="btn-quiet" type="button" disabled={disabled || busy} onClick={() => cameraRef.current?.click()}>
          Take photo
        </button>
        <button className="btn-quiet" type="button" disabled={disabled || busy} onClick={() => planRef.current?.click()}>
          Upload plan
        </button>
        {planFilename ? (
          <button className="btn-quiet" type="button" disabled={disabled || busy} onClick={() => void clearPlan()}>
            Clear plan
          </button>
        ) : null}
        <input
          ref={uploadRef}
          type="file"
          accept="image/*,application/pdf,.pdf"
          multiple
          hidden
          onChange={(event) => { void uploadList(event.target.files); event.target.value = "" }}
        />
        <input
          ref={cameraRef}
          type="file"
          accept="image/*"
          capture="environment"
          hidden
          onChange={(event) => { void uploadList(event.target.files); event.target.value = "" }}
        />
        <input
          ref={planRef}
          type="file"
          accept=".xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          hidden
          onChange={(event) => { void uploadPlan(event.target.files); event.target.value = "" }}
        />
      </div>
      <p className="muted">
        Plan: {planFilename ? `${planFilename} (${planLineCount} lines)` : "none yet"}
      </p>

      {!active.length ? <p className="muted">No photos yet.</p> : null}
      <div className="thumbs loading-thumbs">
        {active.map((file) => {
          const marks = markCount(file.extracted)
          return (
            <figure key={file.id} className="thumb loading-thumb">
              <button
                type="button"
                className="loading-thumb-open"
                onClick={() => setOpenFileId(file.id)}
                aria-label={`Open ${file.label || file.file_name}`}
              >
                {file.is_image && previews[file.id] ? (
                  <img src={previews[file.id]} alt="" />
                ) : (
                  <div className="pdf-chip">{file.is_pdf ? "PDF" : "File"}</div>
                )}
                <span className={`loading-thumb-badge ${file.extracted ? "ok" : ""}`}>
                  {file.extracted ? `${marks} marks` : "Open"}
                </span>
              </button>
              <figcaption>{file.label || file.file_name}</figcaption>
              <div className="container-loading-thumb-actions">
                <button className="btn" type="button" onClick={() => setOpenFileId(file.id)}>
                  View & extract
                </button>
                {!disabled ? (
                  <button className="btn-danger" type="button" disabled={busy} onClick={() => void removeFile(file)}>
                    Delete
                  </button>
                ) : null}
              </div>
            </figure>
          )
        })}
      </div>
      {canRestore && deleted.length ? (
        <div className="container-loading-deleted">
          <h3>Deleted</h3>
          <div className="thumbs loading-thumbs">
            {deleted.map((file) => (
              <figure key={file.id} className="thumb loading-thumb deleted">
                <button type="button" className="loading-thumb-open" onClick={() => setOpenFileId(file.id)}>
                  {file.is_image && previews[file.id] ? (
                    <img src={previews[file.id]} alt="" />
                  ) : (
                    <div className="pdf-chip">{file.is_pdf ? "PDF" : "File"}</div>
                  )}
                </button>
                <figcaption>{file.label || file.file_name}</figcaption>
                <div className="container-loading-thumb-actions">
                  <button className="btn-quiet" type="button" onClick={() => setOpenFileId(file.id)}>View</button>
                  <button className="btn-quiet" type="button" disabled={busy} onClick={() => void restoreFile(file)}>
                    Restore
                  </button>
                </div>
              </figure>
            ))}
          </div>
        </div>
      ) : null}

      {openFile ? (
        <PhotoInspectModal
          itemId={itemId}
          file={openFile}
          previewUrl={previews[openFile.id] || ""}
          disabled={disabled || Boolean(openFile.deleted_at)}
          busy={busy}
          setBusy={setBusy}
          onClose={() => setOpenFileId(null)}
          onError={setError}
          onUpdated={(next) => {
            setFiles((current) => current.map((item) => (item.id === next.id ? next : item)))
            setOpenFileId(next.id)
          }}
        />
      ) : null}
    </div>
  )
}

function PhotoInspectModal({
  itemId,
  file,
  previewUrl,
  disabled,
  busy,
  setBusy,
  onClose,
  onError,
  onUpdated,
}: {
  itemId: number
  file: LoadingFile
  previewUrl: string
  disabled: boolean
  busy: boolean
  setBusy: (value: boolean) => void
  onClose: () => void
  onError: (message: string) => void
  onUpdated: (file: LoadingFile) => void
}) {
  const [viewUrl, setViewUrl] = useState(previewUrl)
  const [draft, setDraft] = useState<LoadingExtract>(
    file.extracted ? structuredClone(file.extracted) : emptyExtract(),
  )
  const [message, setMessage] = useState("")
  const [dirty, setDirty] = useState(false)
  const ownedUrl = useRef("")

  useEffect(() => {
    setDraft(file.extracted ? structuredClone(file.extracted) : emptyExtract())
    setDirty(false)
    setMessage("")
  }, [file.id, file.extracted])

  useEffect(() => {
    if (previewUrl) {
      setViewUrl(previewUrl)
      return
    }
    let cancelled = false
    void api(`${API}/${itemId}/files/${file.id}`).then(async (response) => {
      if (!response.ok || cancelled) return
      const blob = await response.blob()
      if (cancelled) return
      const url = URL.createObjectURL(blob)
      ownedUrl.current = url
      setViewUrl(url)
    })
    return () => {
      cancelled = true
      if (ownedUrl.current) {
        URL.revokeObjectURL(ownedUrl.current)
        ownedUrl.current = ""
      }
    }
  }, [itemId, file.id, previewUrl])

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  function updateMark(palletIndex: number, markIndex: number, key: keyof LoadingMark, value: string) {
    setDirty(true)
    setDraft((current) => {
      const next = structuredClone(current)
      const mark = next.pallets[palletIndex].marks[markIndex]
      if (key === "mix" || key === "cartons" || key === "weight_kg") {
        mark[key] = value.trim() === "" ? null : Number(value)
      } else {
        mark[key] = value
      }
      return next
    })
  }

  function addMark(palletIndex: number) {
    setDirty(true)
    setDraft((current) => {
      const next = structuredClone(current)
      next.pallets[palletIndex].marks.push({
        name: "",
        customer_code: null,
        mix: null,
        cartons: null,
        weight_kg: null,
        notes: null,
      })
      return next
    })
  }

  function removeMark(palletIndex: number, markIndex: number) {
    setDirty(true)
    setDraft((current) => {
      const next = structuredClone(current)
      next.pallets[palletIndex].marks.splice(markIndex, 1)
      return next
    })
  }

  async function extract() {
    setBusy(true)
    onError("")
    setMessage("")
    const response = await api(`${API}/${itemId}/files/${file.id}/extract`, { method: "POST" })
    setBusy(false)
    if (!response.ok) {
      const body = await readError(response)
      onError(body.message || "Extract failed")
      setMessage(body.message || "Extract failed")
      return
    }
    const body = (await response.json()) as { item: LoadingFile; extracted: LoadingExtract }
    onUpdated({ ...file, ...body.item, extracted: body.extracted })
    setDraft(structuredClone(body.extracted))
    setDirty(false)
    setMessage("Extracted — review and edit marks if needed")
  }

  async function save() {
    setBusy(true)
    onError("")
    setMessage("")
    const response = await api(`${API}/${itemId}/files/${file.id}/extracted`, {
      method: "PATCH",
      body: JSON.stringify(draft),
    })
    setBusy(false)
    if (!response.ok) {
      const body = await readError(response)
      onError(body.message || "Save extract failed")
      setMessage(body.message || "Save extract failed")
      return
    }
    const body = (await response.json()) as { item: LoadingFile; extracted: LoadingExtract }
    onUpdated({ ...file, ...body.item, extracted: body.extracted })
    setDraft(structuredClone(body.extracted))
    setDirty(false)
    setMessage("Marks saved")
  }

  const left = draft.pallets[0] || { side: "left", marks: [] }
  const right = draft.pallets[1] || { side: "right", marks: [] }

  return (
    <div
      className="loading-inspect"
      role="dialog"
      aria-modal="true"
      aria-label={file.label || file.file_name}
      onClick={onClose}
    >
      <div className="loading-inspect-panel" onClick={(event) => event.stopPropagation()}>
        <header className="loading-inspect-head">
          <div>
            <strong>{file.label || file.file_name}</strong>
            <p className="muted">
              Read the black detail line on each pallet: name · weight kg · cartons
              {dirty ? " · unsaved edits" : ""}
            </p>
          </div>
          <button className="btn-quiet" type="button" onClick={onClose}>Close</button>
        </header>

        <div className="loading-inspect-body">
          <section className="loading-inspect-media">
            {!viewUrl ? (
              <p className="muted">Loading photo…</p>
            ) : file.is_image ? (
              <img src={viewUrl} alt={file.label || file.file_name} />
            ) : file.is_pdf ? (
              <iframe className="loading-inspect-pdf" title={file.label || file.file_name} src={viewUrl} />
            ) : (
              <p className="muted">Preview not available.</p>
            )}
          </section>

          <section className="loading-inspect-side">
            <div className="loading-inspect-side-head">
              <h3>Extracted marks</h3>
              <span className="loading-inspect-count">{markCount(draft)} marks</span>
            </div>

            {message ? <div className={`banner ${message.includes("failed") ? "err" : "ok"}`}>{message}</div> : null}

            <div className="loading-pallet-grid">
              {[left, right].map((pallet, palletIndex) => (
                <div key={pallet.side || palletIndex} className="loading-pallet-card">
                  <div className="loading-pallet-card-head">
                    <strong>{palletIndex === 0 ? "Left pallet" : "Right pallet"}</strong>
                    <span className="muted">{pallet.marks.length} mark{pallet.marks.length === 1 ? "" : "s"}</span>
                  </div>
                  {!pallet.marks.length ? (
                    <p className="muted loading-pallet-empty">No marks yet</p>
                  ) : null}
                  {pallet.marks.map((mark, markIndex) => (
                    <div key={markIndex} className="loading-mark-card">
                      <label>
                        Name
                        <input
                          disabled={disabled}
                          placeholder="PARIS CORNER 1"
                          value={mark.name || ""}
                          onChange={(event) => updateMark(palletIndex, markIndex, "name", event.target.value)}
                        />
                      </label>
                      <div className="loading-mark-meta">
                        <label>
                          Mix
                          <input
                            disabled={disabled}
                            inputMode="numeric"
                            placeholder="1"
                            value={mark.mix ?? ""}
                            onChange={(event) => updateMark(palletIndex, markIndex, "mix", event.target.value)}
                          />
                        </label>
                        <label>
                          Weight (kg)
                          <input
                            disabled={disabled}
                            inputMode="decimal"
                            placeholder="803"
                            value={mark.weight_kg ?? ""}
                            onChange={(event) => updateMark(palletIndex, markIndex, "weight_kg", event.target.value)}
                          />
                        </label>
                        <label>
                          CTN
                          <input
                            disabled={disabled}
                            inputMode="numeric"
                            placeholder="26"
                            value={mark.cartons ?? ""}
                            onChange={(event) => updateMark(palletIndex, markIndex, "cartons", event.target.value)}
                          />
                        </label>
                      </div>
                      {!disabled ? (
                        <button
                          className="btn-quiet loading-mark-remove"
                          type="button"
                          onClick={() => removeMark(palletIndex, markIndex)}
                        >
                          Remove mark
                        </button>
                      ) : null}
                    </div>
                  ))}
                  {!disabled ? (
                    <button className="btn-quiet" type="button" onClick={() => addMark(palletIndex)}>
                      + Add mark
                    </button>
                  ) : null}
                </div>
              ))}
            </div>

            <label className="loading-notes">
              Notes
              <textarea
                disabled={disabled}
                value={draft.notes || ""}
                onChange={(event) => {
                  setDirty(true)
                  setDraft((current) => ({ ...current, notes: event.target.value || null }))
                }}
                placeholder="Blurry side, covered label…"
              />
            </label>
          </section>
        </div>

        <footer className="loading-inspect-foot">
          <div className="container-loading-actions">
            {!disabled ? (
              <>
                <button className="btn" type="button" disabled={busy || !file.is_image} onClick={() => void extract()}>
                  {busy ? "Working…" : file.extracted ? "Re-extract" : "Extract with AI"}
                </button>
                <button className="btn" type="button" disabled={busy || !dirty} onClick={() => void save()}>
                  Save marks
                </button>
              </>
            ) : null}
          </div>
          <button className="btn-quiet" type="button" onClick={onClose}>Done</button>
        </footer>
      </div>
    </div>
  )
}
