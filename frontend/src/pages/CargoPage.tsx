import { FormEvent, useCallback, useEffect, useRef, useState } from "react"
import { api, readError } from "../api"
import { useAuth } from "../auth"
import { CargoEvidencePanel } from "../components/CargoEvidencePanel"
import { ShipmentFilesModal } from "../components/ShipmentFilesModal"
import type { Cargo, Enums, Page, SaveResult, Warning } from "../types"
import { IntakePage } from "./IntakePage"
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
  grossText,
  lookupNames,
  withCurrent,
} from "../ui"

type Kind = "sea" | "air"

type FormState = {
  date_received: string
  customer_code: string
  company_name: string
  cartons: string
  gross_weight_kg: string
  pallet_weight_kg: string
  gross_is_no_pallet: boolean
  net_weight_kg: string
  system_code: string
  shipment_number: string
  shipping_route: string
  stage: string
  status: string
}

function parseKg(value: string): number | null {
  if (!value.trim()) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function formatKg(value: number): string {
  const rounded = Math.round(value * 1000) / 1000
  return Number.isInteger(rounded) ? String(rounded) : String(rounded)
}

/** Net = gross when no pallet; otherwise gross − pallet when both are set. */
function autoNetKg(gross: string, pallet: string, noPallet: boolean): string | null {
  const g = parseKg(gross)
  if (g == null) return null
  if (noPallet) return formatKg(g)
  const p = parseKg(pallet)
  if (p == null) return null
  return formatKg(g - p)
}

function palletFromGrossNet(gross: number | null, net: number | null, noPallet: boolean): string {
  if (noPallet || gross == null || net == null) return ""
  return formatKg(gross - net)
}

const emptyForm = (): FormState => ({
  date_received: "",
  customer_code: "",
  company_name: "",
  cartons: "",
  gross_weight_kg: "",
  pallet_weight_kg: "",
  gross_is_no_pallet: false,
  net_weight_kg: "",
  system_code: "",
  shipment_number: "",
  shipping_route: "",
  stage: "",
  status: "",
})

function fromRow(row: Cargo): FormState {
  const gross = row.gross_weight_kg == null ? null : Number(row.gross_weight_kg)
  const net = row.net_weight_kg == null ? null : Number(row.net_weight_kg)
  return {
    date_received: row.date_received ?? "",
    customer_code: row.customer_code ?? "",
    company_name: row.company_name ?? "",
    cartons: row.cartons == null ? "" : String(row.cartons),
    gross_weight_kg: row.gross_weight_kg == null ? "" : String(row.gross_weight_kg),
    pallet_weight_kg: palletFromGrossNet(
      Number.isFinite(gross as number) ? gross : null,
      Number.isFinite(net as number) ? net : null,
      row.gross_is_no_pallet,
    ),
    gross_is_no_pallet: row.gross_is_no_pallet,
    net_weight_kg: row.net_weight_kg == null ? "" : String(row.net_weight_kg),
    system_code: row.system_code ?? "",
    shipment_number: row.shipment_number ?? "",
    shipping_route: row.shipping_route ?? "",
    stage: row.stage ?? "",
    status: row.status ?? "",
  }
}

function textOrNull(value: string) {
  const trimmed = value.trim()
  return trimmed ? trimmed : null
}

function shipmentInputValue(kind: Kind, value: string | null | undefined) {
  const text = value ?? ""
  if (kind !== "sea") return text
  const match = text.trim().match(/^[dD]\s*(\d+)$/)
  return match ? match[1] : text
}

function formFromRow(kind: Kind, row: Cargo | null): FormState {
  const form = row ? fromRow(row) : emptyForm()
  form.shipment_number = shipmentInputValue(kind, form.shipment_number)
  if (!row && kind === "sea" && !form.stage) form.stage = "📦 WH"
  return form
}

function numberOrNull(value: string) {
  if (!value.trim()) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : value
}

function draftStorageKey(kind: Kind) {
  return `karam.cargo.addDraft.${kind}`
}

function formHasDraft(form: FormState) {
  return Object.entries(form).some(([key, value]) => {
    if (key === "gross_is_no_pallet") return value === true
    if (key === "stage" && value === "📦 WH") return false
    if (key === "pallet_weight_kg") return typeof value === "string" && value.trim() !== ""
    return typeof value === "string" ? value.trim() !== "" : Boolean(value)
  })
}

function readAddDraft(kind: Kind): FormState | null {
  try {
    const raw = sessionStorage.getItem(draftStorageKey(kind))
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<FormState>
    return { ...emptyForm(), ...parsed, shipment_number: shipmentInputValue(kind, parsed.shipment_number ?? "") }
  } catch {
    return null
  }
}

function writeAddDraft(kind: Kind, form: FormState) {
  try {
    if (!formHasDraft(form)) {
      sessionStorage.removeItem(draftStorageKey(kind))
      return
    }
    sessionStorage.setItem(draftStorageKey(kind), JSON.stringify(form))
  } catch {
    /* ignore quota / private mode */
  }
}

function clearAddDraft(kind: Kind) {
  try {
    sessionStorage.removeItem(draftStorageKey(kind))
  } catch {
    /* ignore */
  }
}

export function CargoPage({ kind }: { kind: Kind }) {
  const { user } = useAuth()
  const [rows, setRows] = useState<Cargo[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [draftQ, setDraftQ] = useState("")
  const [q, setQ] = useState("")
  const [filesFor, setFilesFor] = useState<Cargo | null>(null)
  const [filesTabForId, setFilesTabForId] = useState<number | null>(null)
  const [uploadingDlId, setUploadingDlId] = useState<number | null>(null)
  const [stage, setStage] = useState("")
  const [route, setRoute] = useState("")
  const [status, setStatus] = useState("")
  const [review, setReview] = useState("")
  const [includeDeleted, setIncludeDeleted] = useState(false)
  const [enums, setEnums] = useState<Enums | null>(null)
  const [error, setError] = useState("")
  const [editing, setEditing] = useState<Cargo | null>(null)
  const [creating, setCreating] = useState(false)
  const [extractor, setExtractor] = useState(false)
  const [hasAddDraft, setHasAddDraft] = useState(() => {
    const draft = readAddDraft(kind)
    return Boolean(draft && formHasDraft(draft))
  })
  const limit = 50

  useEffect(() => {
    const draft = readAddDraft(kind)
    setHasAddDraft(Boolean(draft && formHasDraft(draft)))
  }, [kind, creating])

  const loadCustomers = useCallback((query: string) => lookupNames("/api/lookups/customers", "code", query), [])
  const loadCompanies = useCallback((query: string) => lookupNames("/api/lookups/companies", "name", query), [])

  useEffect(() => {
    api("/api/lookups/enums").then(async (response) => {
      if (response.ok) setEnums((await response.json()) as Enums)
    })
  }, [])

  const load = useCallback(async () => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (q) params.set("q", q)
    if (review) params.set("needs_review", review)
    if (kind === "sea" && stage) params.set("stage", stage)
    if (kind === "sea" && route) params.set("shipping_route", route)
    if (kind === "air" && status) params.set("status", status)
    if (includeDeleted) params.set("include_deleted", "true")
    const response = await api(`/api/${kind}?${params}`)
    if (!response.ok) {
      setError("Could not load rows")
      return
    }
    const body = (await response.json()) as Page<Cargo>
    setRows(body.items)
    setTotal(body.total)
    setError("")
  }, [kind, q, review, stage, route, status, includeDeleted, offset])

  useEffect(() => {
    setExtractor(false)
  }, [kind])

  useEffect(() => {
    setOffset(0)
  }, [kind, q, review, stage, route, status, includeDeleted])

  useEffect(() => {
    load()
  }, [load])

  function openNew() {
    setEditing(null)
    setCreating(true)
  }

  async function uploadDlFile(row: Cargo, file: File | null) {
    if (!file) return
    setUploadingDlId(row.id)
    setError("")
    const form = new FormData()
    form.append("files", file)
    form.append("kinds", "note")
    form.append("labels", "Delivery note")
    form.append("extracted", "{}")
    const response = await api(`/api/${kind}/${row.id}/files`, { method: "POST", body: form })
    setUploadingDlId(null)
    if (!response.ok) {
      const body = await readError(response)
      setError(body.message || "Could not upload DL file")
      return
    }
    await load()
  }

  if (extractor) return <IntakePage kind={kind} onBack={() => setExtractor(false)} />

  return (
    <main className="page">
      <div className="page-head">
        <h1>{kind === "sea" ? "Sea goods" : "Air shipment"}</h1>
        <div className="page-actions">
          <button className="btn btn-ai" type="button" onClick={() => setExtractor(true)}>
            <AiMark />
            Ai extractor
          </button>
          <button className="btn" type="button" onClick={openNew}>
            Add{hasAddDraft ? " · draft" : ""}
          </button>
        </div>
      </div>
      <form className="toolbar" onSubmit={(event) => { event.preventDefault(); setQ(draftQ.trim()) }}>
        <input type="search" placeholder="Search customer, company, code…" value={draftQ} onChange={(event) => setDraftQ(event.target.value)} />
        <button className="btn-quiet" type="submit">Search</button>
        {kind === "sea" ? (
          <>
            <select value={stage} onChange={(event) => setStage(event.target.value)}>
              <option value="">All stages</option>
              {(enums?.stages ?? []).map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            <select value={route} onChange={(event) => setRoute(event.target.value)}>
              <option value="">All routes</option>
              {(enums?.shipping_routes ?? []).map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </>
        ) : (
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">All statuses</option>
            {(enums?.air_statuses ?? []).map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        )}
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
              <th>Date</th>
              <th>Customer</th>
              <th>Company</th>
              <th>Cartons</th>
              <th>Gross</th>
              <th>Net</th>
              <th>System</th>
              <th>Shipment</th>
              {kind === "sea" ? <th>Route</th> : null}
              <th>{kind === "sea" ? "Stage" : "Status"}</th>
              <th>Files</th>
              <th>DL</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className={row.deleted_at ? "clickable deleted" : "clickable"} onClick={() => { setCreating(false); setEditing(row) }}>
                <td>{row.date_received ?? ""}</td>
                <td>{row.customer_code ?? ""}</td>
                <td className="clip">{row.company_name ?? ""}</td>
                <td>{row.cartons ?? ""}</td>
                <td>{grossText(row)}</td>
                <td>{row.net_weight_kg ?? ""}</td>
                <td>{row.system_code ?? ""}</td>
                <td>{row.shipment_number ?? ""}</td>
                {kind === "sea" ? <td>{row.shipping_route ?? ""}</td> : null}
                <td>{kind === "sea" ? row.stage ?? "" : row.status ?? ""}</td>
                <td onClick={(event) => event.stopPropagation()}>
                  {(row.file_count ?? 0) > 0 ? (
                    <button
                      className="btn-quiet sf-view-files"
                      type="button"
                      title={`View files (${row.file_count})`}
                      aria-label={`View files (${row.file_count})`}
                      onClick={() => setFilesFor(row)}
                    >
                      <ViewFilesIcon />
                      <span className="sf-file-count">{row.file_count}</span>
                    </button>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                <td onClick={(event) => event.stopPropagation()}>
                  {row.deleted_at ? (
                    <span className="muted">—</span>
                  ) : (
                    <label
                      className={`btn-quiet sf-upload-dl${uploadingDlId === row.id ? " disabled" : ""}`}
                      title={uploadingDlId === row.id ? "Uploading…" : "Upload delivery note"}
                      aria-label={uploadingDlId === row.id ? "Uploading delivery note" : "Upload delivery note"}
                    >
                      {uploadingDlId === row.id ? <UploadSpinner /> : <UploadIcon />}
                      <input
                        type="file"
                        accept="image/*,application/pdf,.pdf"
                        hidden
                        disabled={uploadingDlId === row.id}
                        onChange={(event) => {
                          const file = event.target.files?.[0] || null
                          event.target.value = ""
                          void uploadDlFile(row, file)
                        }}
                      />
                    </label>
                  )}
                </td>
                <td><Flags legacy={row.legacy} review={row.needs_review} deleted={Boolean(row.deleted_at)} /></td>
              </tr>
            ))}
            {!rows.length ? (
              <tr><td colSpan={13} className="muted">No rows</td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <Pager offset={offset} limit={limit} total={total} onPage={setOffset} />
      {creating || editing ? (
        <CargoDrawer
          key={editing ? String(editing.id) : "new"}
          kind={kind}
          row={editing}
          enums={enums}
          canRestore={user?.role === "admin"}
          loadCustomers={loadCustomers}
          loadCompanies={loadCompanies}
          preferFilesTab={filesTabForId != null && editing?.id === filesTabForId}
          onClose={(draft) => {
            if (!editing && draft) {
              writeAddDraft(kind, draft)
              setHasAddDraft(formHasDraft(draft))
            }
            setCreating(false)
            setEditing(null)
            setFilesTabForId(null)
          }}
          onKeep={async (item, opts) => {
            if (opts?.openFiles || !editing) {
              clearAddDraft(kind)
              setHasAddDraft(false)
            }
            setCreating(false)
            setEditing(item)
            if (opts?.openFiles) setFilesTabForId(item.id)
            await load()
          }}
          onDone={async () => {
            clearAddDraft(kind)
            setHasAddDraft(false)
            setCreating(false)
            setEditing(null)
            setFilesTabForId(null)
            await load()
          }}
        />
      ) : null}
      {filesFor ? (
        <ShipmentFilesModal
          kind={kind}
          itemId={filesFor.id}
          shipmentNumber={filesFor.shipment_number}
          companyName={filesFor.company_name}
          customerCode={filesFor.customer_code}
          onClose={() => setFilesFor(null)}
        />
      ) : null}
    </main>
  )
}

function AiMark() {
  return (
    <svg className="ai-mark" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
      <path fill="currentColor" d="M8 1.2 9.3 6.7 14.8 8 9.3 9.3 8 14.8 6.7 9.3 1.2 8 6.7 6.7 8 1.2Z" />
    </svg>
  )
}

function UploadIcon() {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
      <path
        fill="currentColor"
        d="M10 12.5a.75.75 0 0 1-.75-.75V3.56L7.03 5.78a.75.75 0 1 1-1.06-1.06l3.5-3.5a.75.75 0 0 1 1.06 0l3.5 3.5a.75.75 0 1 1-1.06 1.06L10.75 3.56v8.19a.75.75 0 0 1-.75.75Zm-5.5 1a.75.75 0 0 1 .75.75v1.5c0 .69.56 1.25 1.25 1.25h7c.69 0 1.25-.56 1.25-1.25v-1.5a.75.75 0 0 1 1.5 0v1.5A2.75 2.75 0 0 1 13.5 18h-7A2.75 2.75 0 0 1 3.75 15.25v-1.5a.75.75 0 0 1 .75-.75Z"
      />
    </svg>
  )
}

function ViewFilesIcon() {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
      <path
        fill="currentColor"
        d="M10 4.5c-3.6 0-6.7 2.2-8 5.5 1.3 3.3 4.4 5.5 8 5.5s6.7-2.2 8-5.5c-1.3-3.3-4.4-5.5-8-5.5Zm0 9.5a4 4 0 1 1 0-8 4 4 0 0 1 0 8Zm0-2.25a1.75 1.75 0 1 0 0-3.5 1.75 1.75 0 0 0 0 3.5Z"
      />
    </svg>
  )
}

function UploadSpinner() {
  return (
    <svg className="sf-upload-spin" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
      <circle cx="10" cy="10" r="7" fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="28" strokeLinecap="round" opacity="0.85" />
    </svg>
  )
}

function CargoDrawer({
  kind,
  row,
  enums,
  canRestore,
  loadCustomers,
  loadCompanies,
  preferFilesTab,
  onClose,
  onKeep,
  onDone,
}: {
  kind: Kind
  row: Cargo | null
  enums: Enums | null
  canRestore: boolean
  loadCustomers: (query: string) => Promise<string[]>
  loadCompanies: (query: string) => Promise<string[]>
  preferFilesTab?: boolean
  onClose: (draft?: FormState) => void
  onKeep: (row: Cargo, opts?: { openFiles?: boolean }) => Promise<void>
  onDone: () => Promise<void>
}) {
  const [form, setForm] = useState<FormState>(() => {
    if (row) return formFromRow(kind, row)
    return readAddDraft(kind) || formFromRow(kind, null)
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [warnings, setWarnings] = useState<Warning[]>([])
  const [proposed, setProposed] = useState<Record<string, string>>({})
  const [tab, setTab] = useState<"edit" | "files" | "history">(preferFilesTab ? "files" : "edit")
  const [message, setMessage] = useState("")
  const [nextShipment, setNextShipment] = useState<{ shipment_number: string; number: number } | null>(null)
  const [savedRow, setSavedRow] = useState<Cargo | null>(row)
  const formRef = useRef(form)
  formRef.current = form

  useEffect(() => {
    if (kind !== "sea") return
    let cancelled = false
    api("/api/sea/next-shipment").then(async (response) => {
      if (!response.ok || cancelled) return
      const body = (await response.json()) as { shipment_number: string; number: number }
      if (!cancelled && body.shipment_number && Number.isFinite(body.number)) setNextShipment(body)
    })
    return () => {
      cancelled = true
    }
  }, [kind])

  useEffect(() => {
    if (row) return
    const timer = window.setTimeout(() => writeAddDraft(kind, form), 250)
    return () => window.clearTimeout(timer)
  }, [form, kind, row])

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => {
      const next = { ...current, [key]: value }
      if (key === "gross_is_no_pallet" && value === true) {
        next.pallet_weight_kg = ""
      }
      if (key === "gross_weight_kg" || key === "pallet_weight_kg" || key === "gross_is_no_pallet") {
        const net = autoNetKg(next.gross_weight_kg, next.pallet_weight_kg, next.gross_is_no_pallet)
        if (net != null) next.net_weight_kg = net
      }
      return next
    })
    setErrors((current) => {
      const cleared = { ...current, [key]: "" }
      if (key === "gross_weight_kg" || key === "pallet_weight_kg" || key === "gross_is_no_pallet") {
        cleared.net_weight_kg = ""
      }
      return cleared
    })
    setProposed({})
  }

  function closeDrawer() {
    if (!row && !savedRow) onClose(formRef.current)
    else onClose()
  }

  async function save(forceNew: boolean) {
    const flags = forceNew
      ? {
          confirm_new_customer: "customer_code" in proposed,
          confirm_new_company: "company_name" in proposed,
          confirm_new_supplier: false,
        }
      : { confirm_new_customer: false, confirm_new_company: false, confirm_new_supplier: false }
    const payload = {
      date_received: textOrNull(form.date_received),
      customer_code: textOrNull(form.customer_code),
      company_name: textOrNull(form.company_name),
      cartons: numberOrNull(form.cartons),
      gross_weight_kg: numberOrNull(form.gross_weight_kg),
      gross_is_no_pallet: form.gross_is_no_pallet,
      net_weight_kg: numberOrNull(
        autoNetKg(form.gross_weight_kg, form.pallet_weight_kg, form.gross_is_no_pallet) ?? form.net_weight_kg,
      ),
      system_code: textOrNull(form.system_code),
      shipment_number: textOrNull(form.shipment_number),
      shipping_route: kind === "sea" ? textOrNull(form.shipping_route) : null,
      stage: kind === "sea" ? textOrNull(form.stage) : null,
      status: kind === "air" ? textOrNull(form.status) : null,
      ...flags,
    }
    const response = await api(row ? `/api/${kind}/${row.id}` : `/api/${kind}`, {
      method: row ? "PATCH" : "POST",
      body: JSON.stringify(payload),
    })
    if (response.status === 422) {
      const error = await readError(response)
      setErrors(error.field_errors || {})
      setWarnings(error.warnings || [])
      setProposed(error.code === "NEW_VALUE_CONFIRMATION_REQUIRED" ? error.proposed || {} : {})
      setMessage("")
      return
    }
    if (!response.ok) {
      const error = await readError(response)
      setMessage(error.message || "Save failed")
      return
    }
    const body = (await response.json()) as SaveResult<Cargo>
    setWarnings(body.warnings || [])
    setErrors({})
    setProposed({})
    setForm(formFromRow(kind, body.item))
    setSavedRow(body.item)
    if (!row) {
      clearAddDraft(kind)
      setMessage(body.warnings?.length ? "Saved with warnings — add Papers / Scale files" : "Saved — add Papers / Scale files")
      await onKeep(body.item, { openFiles: true })
      setTab("files")
      return
    }
    if (body.warnings?.length) {
      setMessage("Saved with warnings")
      await onKeep(body.item)
      return
    }
    await onDone()
  }

  const activeRow = savedRow || row

  async function remove() {
    if (!activeRow || !window.confirm("Soft-delete this row? It will leave the working list.")) return
    const response = await api(`/api/${kind}/${activeRow.id}`, { method: "DELETE" })
    if (!response.ok) {
      const error = await readError(response)
      setMessage(error.message || "Delete failed")
      return
    }
    await onDone()
  }

  async function restore() {
    if (!activeRow) return
    const response = await api(`/api/${kind}/${activeRow.id}/restore`, { method: "POST" })
    if (!response.ok) {
      const error = await readError(response)
      setMessage(error.message || "Restore failed")
      return
    }
    await onDone()
  }

  const stages = withCurrent(enums?.stages ?? [], form.stage)
  const routes = withCurrent(enums?.shipping_routes ?? [], form.shipping_route)
  const statuses = withCurrent(enums?.air_statuses ?? [], form.status)

  return (
    <Drawer
      title={activeRow ? `${kind === "sea" ? "Sea" : "Air"} #${activeRow.id}` : `New ${kind} row`}
      onClose={closeDrawer}
      wide={tab === "files"}
      footer={
        tab === "files" ? (
          <button className="btn-quiet" type="button" onClick={closeDrawer}>Close</button>
        ) : (
          <>
            <div>
              {activeRow && !activeRow.deleted_at ? (
                <button className="btn-danger" type="button" onClick={remove}>Delete</button>
              ) : null}
              {activeRow?.deleted_at && canRestore ? (
                <button className="btn-quiet" type="button" onClick={restore}>Restore</button>
              ) : null}
            </div>
            <button className="btn" type="button" onClick={() => save(false)} disabled={Boolean(activeRow?.deleted_at)}>
              Save
            </button>
          </>
        )
      }
    >
      {activeRow ? (
        <div className="tabs">
          <button type="button" className={tab === "edit" ? "on" : ""} onClick={() => setTab("edit")}>Edit</button>
          <button type="button" className={tab === "files" ? "on" : ""} onClick={() => setTab("files")}>
            Papers &amp; scale
          </button>
          <button type="button" className={tab === "history" ? "on" : ""} onClick={() => setTab("history")}>History</button>
        </div>
      ) : (
        <p className="muted">
          Save the row first, then you can upload Papers and Scale files.
          {formHasDraft(form) ? " Your typed fields are kept if you close this window." : ""}
        </p>
      )}
      {tab === "files" && activeRow ? (
        <CargoEvidencePanel
          kind={kind}
          itemId={activeRow.id}
          canRestore={canRestore}
          disabled={Boolean(activeRow.deleted_at)}
          onChanged={() => void onKeep(activeRow)}
        />
      ) : null}
      {tab === "history" && activeRow ? (
        <History path={`/api/${kind}/${activeRow.id}/history`} legacy={activeRow.legacy} />
      ) : null}
      {tab === "edit" ? (
        <form className="form-grid" onSubmit={(event: FormEvent) => { event.preventDefault(); save(false) }}>
          {activeRow ? (
            <div className="wide">
              <Flags
                legacy={activeRow.legacy}
                review={activeRow.needs_review}
                deleted={Boolean(activeRow.deleted_at)}
              />
            </div>
          ) : null}
          {message ? <div className="banner ok wide">{message}</div> : null}
          <WarningList warnings={warnings} />
          {row ? <IssueList issues={row.issues || []} /> : null}
          <Field label="Date received" error={errors.date_received}>
            <input className={errors.date_received ? "invalid" : ""} type="date" value={form.date_received} onChange={(event) => update("date_received", event.target.value)} />
          </Field>
          <Field label="Customer" error={errors.customer_code}>
            <Suggest id={`${kind}-customer`} value={form.customer_code} invalid={Boolean(errors.customer_code)} onChange={(value) => update("customer_code", value)} loader={loadCustomers} />
          </Field>
          <Field label="Company" error={errors.company_name} wide>
            <Suggest id={`${kind}-company`} value={form.company_name} invalid={Boolean(errors.company_name)} onChange={(value) => update("company_name", value)} loader={loadCompanies} />
          </Field>
          <Field label="Cartons" error={errors.cartons}>
            <input className={errors.cartons ? "invalid" : ""} inputMode="numeric" value={form.cartons} onChange={(event) => update("cartons", event.target.value)} />
          </Field>
          <Field label="Gross kg" error={errors.gross_weight_kg}>
            <input
              className={errors.gross_weight_kg ? "invalid" : ""}
              inputMode="decimal"
              value={form.gross_weight_kg}
              onChange={(event) => update("gross_weight_kg", event.target.value)}
            />
          </Field>
          <Field label="Pallet kg (PW)">
            <input
              inputMode="decimal"
              disabled={form.gross_is_no_pallet}
              value={form.gross_is_no_pallet ? "" : form.pallet_weight_kg}
              onChange={(event) => update("pallet_weight_kg", event.target.value)}
              placeholder="Optional"
            />
            <small>Net = Gross − Pallet. With No pallet, Net = Gross.</small>
          </Field>
          <label className="check wide">
            <input
              type="checkbox"
              checked={form.gross_is_no_pallet}
              onChange={(event) => update("gross_is_no_pallet", event.target.checked)}
            />
            No pallet
          </label>
          <Field label="Net kg (auto)" error={errors.net_weight_kg}>
            <input
              className={errors.net_weight_kg ? "invalid" : ""}
              inputMode="decimal"
              value={form.net_weight_kg}
              onChange={(event) => update("net_weight_kg", event.target.value)}
            />
          </Field>
          <Field label="System code (optional)" error={errors.system_code}>
            <input
              className={errors.system_code ? "invalid" : ""}
              value={form.system_code}
              onChange={(event) => update("system_code", event.target.value)}
              placeholder="Filled later from Zokhar"
            />
            <small>Not required when adding a row — usually comes from Zokhar upload.</small>
          </Field>
          <Field label="Shipment" error={errors.shipment_number} wide={kind === "sea"}>
            <input
              className={errors.shipment_number ? "invalid" : ""}
              inputMode={kind === "sea" ? "numeric" : undefined}
              value={form.shipment_number}
              onChange={(event) => update("shipment_number", event.target.value)}
            />
            {kind === "sea" ? (
              <>
                {nextShipment ? (
                  <span className="shipment-suggest">
                    <span>Suggested next number: {nextShipment.shipment_number}</span>
                    <button type="button" className="btn-quiet" onClick={() => update("shipment_number", String(nextShipment.number))}>
                      Use {nextShipment.number}
                    </button>
                  </span>
                ) : null}
                <small>
                  Goods can leave the warehouse later, so this can stay empty. When it is filled it is D plus the last number plus 1, because Iran or Turkey is chosen later.
                </small>
              </>
            ) : null}
          </Field>
          {kind === "sea" ? (
            <>
              <Field label="Route" error={errors.shipping_route}>
                <select className={errors.shipping_route ? "invalid" : ""} value={form.shipping_route} onChange={(event) => update("shipping_route", event.target.value)}>
                  <option value="">—</option>
                  {routes.map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
              </Field>
              <Field label="Stage" error={errors.stage}>
                <select className={errors.stage ? "invalid" : ""} value={form.stage} onChange={(event) => update("stage", event.target.value)}>
                  <option value="">—</option>
                  {stages.map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
              </Field>
            </>
          ) : (
            <Field label="Status" error={errors.status}>
              <select className={errors.status ? "invalid" : ""} value={form.status} onChange={(event) => update("status", event.target.value)}>
                <option value="">—</option>
                {statuses.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </Field>
          )}
          <div className="wide">
            <ConfirmNew proposed={proposed} onConfirm={() => save(true)} />
          </div>
        </form>
      ) : null}
    </Drawer>
  )
}
