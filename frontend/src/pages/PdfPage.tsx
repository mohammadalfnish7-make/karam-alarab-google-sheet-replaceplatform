import { useEffect, useState } from "react"
import { api, readError } from "../api"
import type { ApiError, Enums, Warning } from "../types"

type Target = "sea" | "air" | "exit"

type Draft = {
  values: Record<string, unknown>
  field_errors: Record<string, string>
  warnings: Warning[]
  code?: string | null
}

const blanks: Record<Target, Record<string, unknown>> = {
  sea: {
    date_received: "", customer_code: "", company_name: "", cartons: "", gross_weight_kg: "",
    gross_is_no_pallet: false, net_weight_kg: "", system_code: "", shipment_number: "",
    shipping_route: "", stage: "",
  },
  air: {
    date_received: "", customer_code: "", company_name: "", cartons: "", gross_weight_kg: "",
    gross_is_no_pallet: false, net_weight_kg: "", system_code: "", shipment_number: "", status: "",
  },
  exit: { mark: "", supplier: "", invoice_no: "", cartons: "", date_of_submission: "", status: "" },
}

function columnsFor(target: Target) {
  if (target === "exit") {
    return [
      ["mark", "Mark"], ["supplier", "Supplier"], ["invoice_no", "Invoice"],
      ["cartons", "Cartons"], ["date_of_submission", "Submitted"], ["status", "Status"],
    ]
  }
  const shared = [
    ["date_received", "Date"], ["customer_code", "TL mark"], ["company_name", "Company"],
    ["cartons", "Cartons"], ["gross_weight_kg", "Gross kg"], ["gross_is_no_pallet", "No pallet"],
    ["net_weight_kg", "Net kg"], ["system_code", "System"], ["shipment_number", "Shipment"],
  ]
  if (target === "sea") return [...shared, ["shipping_route", "Route"], ["stage", "Stage"]]
  return [...shared, ["status", "Status"]]
}

function textValue(value: unknown) {
  if (value == null) return ""
  return String(value)
}

export function PdfPage() {
  const [target, setTarget] = useState<Target>("sea")
  const [file, setFile] = useState<File | null>(null)
  const [documentId, setDocumentId] = useState<number | null>(null)
  const [filename, setFilename] = useState("")
  const [rows, setRows] = useState<Draft[]>([])
  const [enums, setEnums] = useState<Enums | null>(null)
  const [confirmNew, setConfirmNew] = useState(false)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState("")

  useEffect(() => {
    api("/api/lookups/enums").then(async (response) => {
      if (response.ok) setEnums((await response.json()) as Enums)
    })
  }, [])

  const columns = columnsFor(target)

  function setCell(index: number, key: string, value: unknown) {
    setRows((current) => current.map((row, rowIndex) => {
      if (rowIndex !== index) return row
      const field_errors = { ...row.field_errors }
      delete field_errors[key]
      return { ...row, values: { ...row.values, [key]: value }, field_errors }
    }))
  }

  async function upload() {
    if (!file) return
    setBusy("Uploading…")
    setError("")
    setMessage("")
    const body = new FormData()
    body.append("file", file)
    body.append("target", target)
    const response = await api("/api/pdf/upload", { method: "POST", body })
    setBusy("")
    if (!response.ok) {
      const err = await readError(response)
      setError(err.field_errors?.file || err.message || "Upload failed")
      return
    }
    const saved = await response.json()
    setDocumentId(saved.id)
    setFilename(saved.filename)
    setRows([])
  }

  async function extract() {
    if (!documentId) return
    setBusy("Extracting…")
    setError("")
    setMessage("")
    const response = await api(`/api/pdf/${documentId}/extract`, { method: "POST" })
    setBusy("")
    if (response.status === 503) {
      const err = await readError(response)
      setError(err.message || "Extraction is unavailable")
      return
    }
    if (!response.ok) {
      const err = await readError(response)
      setError(err.message || "Extraction failed")
      return
    }
    const body = await response.json()
    setRows((body.rows || []) as Draft[])
    if (!body.rows?.length) setMessage("The model returned no rows. You can add rows by hand.")
  }

  function addRow() {
    setRows((current) => [...current, { values: { ...blanks[target] }, field_errors: {}, warnings: [] }])
  }

  async function submit() {
    if (!documentId) return
    setBusy("Saving…")
    setError("")
    setMessage("")
    const payload = {
      confirm_new_customer: confirmNew,
      confirm_new_company: confirmNew,
      confirm_new_supplier: confirmNew,
      rows: rows.map((row) => clean(target, row.values, confirmNew)),
    }
    const response = await api(`/api/pdf/${documentId}/confirm`, {
      method: "POST",
      body: JSON.stringify(payload),
    })
    setBusy("")
    if (response.status === 422) {
      const err = (await readError(response)) as ApiError
      if (err.row_errors) {
        setRows((current) => current.map((row, index) => {
          const found = err.row_errors?.find((item) => item.index === index)
          if (!found) return row
          return { ...row, field_errors: found.field_errors, warnings: found.warnings || [], code: found.code }
        }))
        setError("Fix the highlighted rows before submitting.")
        if (err.row_errors.some((item) => item.code === "NEW_VALUE_CONFIRMATION_REQUIRED")) setConfirmNew(true)
      } else {
        setError(err.message || "Could not submit")
      }
      return
    }
    if (!response.ok) {
      const err = await readError(response)
      setError(err.message || "Could not submit")
      return
    }
    const body = await response.json()
    setMessage(`Saved ${body.created.length} row${body.created.length === 1 ? "" : "s"}.`)
    setRows([])
  }

  return (
    <main className="page">
      <div className="page-head"><h1>PDF intake</h1></div>
      <p className="muted">Upload a supplier PDF. Extract fills one sea or air row with the TL mark, company, cartons, and weights printed on the file. System code and shipment number stay blank unless the PDF prints them.</p>
      <div className="toolbar">
        <select value={target} onChange={(event) => { setTarget(event.target.value as Target); setRows([]); setDocumentId(null) }}>
          <option value="sea">Sea</option>
          <option value="air">Air</option>
          <option value="exit">Exit</option>
        </select>
        <input type="file" accept="application/pdf,.pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        <button className="btn" type="button" disabled={!file || busy !== ""} onClick={upload}>Upload</button>
        <button className="btn-quiet" type="button" disabled={!documentId || busy !== ""} onClick={extract}>Extract</button>
      </div>
      {filename ? <p className="muted">Uploaded {filename} as #{documentId}</p> : null}
      {busy ? <p>{busy}</p> : null}
      {error ? <div className="banner err">{error}</div> : null}
      {message ? <div className="banner ok">{message}</div> : null}
      {documentId ? (
        <>
          <div className="toolbar">
            <button className="btn-quiet" type="button" onClick={addRow}>Add row</button>
            <label className="check">
              <input type="checkbox" checked={confirmNew} onChange={(event) => setConfirmNew(event.target.checked)} />
              Confirm new customer, company, and supplier names
            </label>
            <button className="btn" type="button" disabled={!rows.length || busy !== ""} onClick={submit}>Submit rows</button>
          </div>
          <div className="table-wrap">
            <table className="pdf-table">
              <thead>
                <tr>
                  {columns.map(([key, label]) => <th key={key}>{label}</th>)}
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <PdfRow
                    key={index}
                    row={row}
                    columns={columns}
                    target={target}
                    enums={enums}
                    onChange={(key, value) => setCell(index, key, value)}
                    onRemove={() => setRows((current) => current.filter((_, rowIndex) => rowIndex !== index))}
                  />
                ))}
                {!rows.length ? <tr><td className="muted" colSpan={columns.length + 1}>No proposed rows yet.</td></tr> : null}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </main>
  )
}

function PdfRow({
  row,
  columns,
  target,
  enums,
  onChange,
  onRemove,
}: {
  row: Draft
  columns: string[][]
  target: Target
  enums: Enums | null
  onChange: (key: string, value: unknown) => void
  onRemove: () => void
}) {
  const errorText = Object.entries(row.field_errors).map(([key, message]) => `${key}: ${message}`).join(" · ")
  const warningText = (row.warnings || []).map((item) => item.message).join(" · ")
  return (
    <>
      <tr>
        {columns.map(([key]) => (
          <td key={key}>
            <Cell
              name={key}
              target={target}
              value={row.values[key]}
              invalid={Boolean(row.field_errors[key])}
              enums={enums}
              onChange={(value) => onChange(key, value)}
            />
          </td>
        ))}
        <td><button className="btn-quiet" type="button" onClick={onRemove}>Remove</button></td>
      </tr>
      {errorText ? <tr className="error-note"><td colSpan={columns.length + 1}>{errorText}</td></tr> : null}
      {warningText ? <tr className="warn-note"><td colSpan={columns.length + 1}>{warningText}</td></tr> : null}
    </>
  )
}

function Cell({
  name,
  target,
  value,
  invalid,
  enums,
  onChange,
}: {
  name: string
  target: Target
  value: unknown
  invalid: boolean
  enums: Enums | null
  onChange: (value: unknown) => void
}) {
  const className = invalid ? "invalid" : ""
  if (name === "gross_is_no_pallet") {
    return <input type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} />
  }
  if (name === "date_received" || name === "date_of_submission") {
    return <input className={className} type="date" value={textValue(value).slice(0, 10)} onChange={(event) => onChange(event.target.value)} />
  }
  const options = name === "stage" ? enums?.stages
    : name === "shipping_route" ? enums?.shipping_routes
    : name === "status" ? (target === "air" ? enums?.air_statuses : enums?.exit_statuses)
    : null
  if (options) {
    const current = textValue(value)
    const list = current && !options.includes(current) ? [current, ...options] : options
    return (
      <select className={className} value={current} onChange={(event) => onChange(event.target.value)}>
        <option value="">—</option>
        {list.map((item) => <option key={item} value={item}>{item}</option>)}
      </select>
    )
  }
  return <input className={className} value={textValue(value)} onChange={(event) => onChange(event.target.value)} />
}

function clean(target: Target, values: Record<string, unknown>, confirmNew: boolean) {
  const text = (value: unknown) => {
    if (value == null) return null
    const trimmed = String(value).trim()
    return trimmed || null
  }
  const num = (value: unknown) => {
    if (value == null || value === "") return null
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : value
  }
  const flags = {
    confirm_new_customer: confirmNew,
    confirm_new_company: confirmNew,
    confirm_new_supplier: confirmNew,
  }
  if (target === "exit") {
    return {
      ...flags,
      mark: text(values.mark),
      supplier: text(values.supplier),
      invoice_no: text(values.invoice_no),
      cartons: num(values.cartons),
      date_of_submission: text(values.date_of_submission),
      status: text(values.status),
    }
  }
  return {
    ...flags,
    date_received: text(values.date_received),
    customer_code: text(values.customer_code),
    company_name: text(values.company_name),
    cartons: num(values.cartons),
    gross_weight_kg: values.gross_is_no_pallet ? null : num(values.gross_weight_kg),
    gross_is_no_pallet: Boolean(values.gross_is_no_pallet),
    net_weight_kg: num(values.net_weight_kg),
    system_code: text(values.system_code),
    shipment_number: text(values.shipment_number),
    shipping_route: target === "sea" ? text(values.shipping_route) : null,
    stage: target === "sea" ? text(values.stage) : null,
    status: target === "air" ? text(values.status) : null,
  }
}
