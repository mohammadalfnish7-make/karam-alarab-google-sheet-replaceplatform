import { Dispatch, FormEvent, SetStateAction, useState } from "react"
import { api, readError } from "../api"
import {
  NOTE_FIELDS,
  SCALE_FIELDS,
  compareCheck,
  emptyIntake,
  parseIntakeMessage,
  showCheckValue,
  SAMPLE_MESSAGE,
  type CheckColumn,
  type CheckResult,
  type IntakeFields,
} from "../intake"

type Extracted = Record<string, string | number | null>

type Attachment = {
  id: string
  file: File
  url: string
  status: "reading" | "done" | "error"
  extracted: Extracted
  error: string
}

function filesOf(list: FileList | null): Attachment[] {
  if (!list?.length) return []
  return Array.from(list).map((file) => ({
    id: crypto.randomUUID(),
    file,
    url: URL.createObjectURL(file),
    status: "reading",
    extracted: {},
    error: "",
  }))
}

async function sampleFile(path: string, name: string) {
  const response = await fetch(path)
  const blob = await response.blob()
  return new File([blob], name, { type: blob.type || "image/jpeg" })
}

async function readSource(file: File, kind: "delivery_note" | "scale") {
  const body = new FormData()
  body.append("kind", kind)
  body.append("file", file)
  const response = await api("/api/intake/read", { method: "POST", body })
  if (!response.ok) {
    const err = await readError(response)
    throw new Error(err.message || "Could not read this file")
  }
  const payload = await response.json()
  return (payload.fields || {}) as Extracted
}

export function IntakePage() {
  const [messageText, setMessageText] = useState("")
  const [fields, setFields] = useState<IntakeFields>(emptyIntake())
  const [notes, setNotes] = useState<Attachment[]>([])
  const [photos, setPhotos] = useState<Attachment[]>([])
  const [confirmNew, setConfirmNew] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [busy, setBusy] = useState(false)

  function applyMessage(text: string) {
    setMessageText(text)
    setFields(parseIntakeMessage(text))
    setError("")
    setNotice("")
  }

  function update<K extends keyof IntakeFields>(key: K, value: IntakeFields[K]) {
    setFields((current) => ({ ...current, [key]: value }))
  }

  function readInto(
    item: Attachment,
    kind: "delivery_note" | "scale",
    setList: Dispatch<SetStateAction<Attachment[]>>,
  ) {
    void readSource(item.file, kind)
      .then((extracted) => {
        setList((current) => current.map((row) => (
          row.id === item.id ? { ...row, status: "done", extracted, error: "" } : row
        )))
      })
      .catch((reason: Error) => {
        setList((current) => current.map((row) => (
          row.id === item.id ? { ...row, status: "error", error: reason.message } : row
        )))
      })
  }

  function addNotes(list: FileList | null) {
    const added = filesOf(list)
    if (!added.length) return
    setNotes((current) => [...current, ...added])
    for (const item of added) readInto(item, "delivery_note", setNotes)
  }

  function addPhotos(list: FileList | null) {
    const added = filesOf(list)
    if (!added.length) return
    setPhotos((current) => [...current, ...added])
    for (const item of added) readInto(item, "scale", setPhotos)
  }

  function retry(
    item: Attachment,
    kind: "delivery_note" | "scale",
    setList: Dispatch<SetStateAction<Attachment[]>>,
  ) {
    setList((current) => current.map((row) => (
      row.id === item.id ? { ...row, status: "reading", error: "", extracted: {} } : row
    )))
    readInto(item, kind, setList)
  }

  function remove(id: string, setList: Dispatch<SetStateAction<Attachment[]>>) {
    setList((current) => {
      const found = current.find((item) => item.id === id)
      if (found) URL.revokeObjectURL(found.url)
      return current.filter((item) => item.id !== id)
    })
  }

  async function loadSample() {
    applyMessage(SAMPLE_MESSAGE)
    const [note, photo] = await Promise.all([
      sampleFile("/demo/delivery-note.jpg", "delivery-note.jpg"),
      sampleFile("/demo/pallet-scale.jpg", "pallet-scale.jpg"),
    ])
    const noteItem: Attachment = {
      id: crypto.randomUUID(),
      file: note,
      url: URL.createObjectURL(note),
      status: "reading",
      extracted: {},
      error: "",
    }
    const photoItem: Attachment = {
      id: crypto.randomUUID(),
      file: photo,
      url: URL.createObjectURL(photo),
      status: "reading",
      extracted: {},
      error: "",
    }
    setNotes((current) => {
      for (const item of current) URL.revokeObjectURL(item.url)
      return [noteItem]
    })
    setPhotos((current) => {
      for (const item of current) URL.revokeObjectURL(item.url)
      return [photoItem]
    })
    readInto(noteItem, "delivery_note", setNotes)
    readInto(photoItem, "scale", setPhotos)
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError("")
    setNotice("")
    const payload = {
      date_received: fields.date_received || null,
      customer_code: fields.customer_code || null,
      company_name: fields.company_name || null,
      cartons: fields.cartons ? Number(fields.cartons) : null,
      gross_weight_kg: fields.total_weight_kg ? Number(fields.total_weight_kg) : null,
      gross_is_no_pallet: false,
      net_weight_kg: fields.net_weight_kg ? Number(fields.net_weight_kg) : null,
      system_code: null,
      shipment_number: fields.shipment_number || null,
      shipping_route: null,
      stage: null,
      confirm_new_customer: confirmNew,
      confirm_new_company: confirmNew,
      confirm_new_supplier: false,
    }
    const response = await api("/api/sea", { method: "POST", body: JSON.stringify(payload) })
    setBusy(false)
    if (response.status === 422) {
      const body = await readError(response)
      if (body.code === "NEW_VALUE_CONFIRMATION_REQUIRED") setConfirmNew(true)
      const details = Object.values(body.field_errors || {}).filter(Boolean)
      setError(details[0] || body.message || "Could not save this row")
      return
    }
    if (!response.ok) {
      const body = await readError(response)
      setError(body.message || "Could not save this row")
      return
    }
    setNotice(`Saved sea row ${fields.shipment_number || ""}.`)
  }

  return (
    <main className="page">
      <div className="page-head">
        <h1>Intake check</h1>
        <button className="btn-quiet" type="button" onClick={() => void loadSample()}>Load Madinah sample</button>
      </div>
      <p className="muted">
        Cartons and the shop name are read from each delivery note. Weight is read from each scale photo. Both are shown beside that file and checked against the message.
      </p>

      <section className="panel source-card">
        <div>
          <h2>Message</h2>
          <textarea
            className="message-box"
            value={messageText}
            placeholder={"D1236\nDATE 29/09/2026\nTL4455\nCTN 6\nTW 122.5 KG\nPW 15.5 KG\nNW 107 KG\nSHOP MADINAH AL NOOR\nPERFUME"}
            onChange={(event) => applyMessage(event.target.value)}
          />
        </div>
        <div className="form-grid">
          <Field label="Shipment" value={fields.shipment_number} onChange={(value) => update("shipment_number", value)} />
          <Field label="Date" type="date" value={fields.date_received} onChange={(value) => update("date_received", value)} />
          <Field label="TL mark" value={fields.customer_code} onChange={(value) => update("customer_code", value)} />
          <Field label="Shop" value={fields.company_name} onChange={(value) => update("company_name", value)} />
          <Field label="Cartons" value={fields.cartons} onChange={(value) => update("cartons", value)} />
          <Field label="Goods" value={fields.goods} onChange={(value) => update("goods", value)} />
          <Field label="Total kg (TW)" value={fields.total_weight_kg} onChange={(value) => update("total_weight_kg", value)} />
          <Field label="Pallet kg (PW)" value={fields.pallet_weight_kg} onChange={(value) => update("pallet_weight_kg", value)} />
          <Field label="Net kg (NW)" value={fields.net_weight_kg} onChange={(value) => update("net_weight_kg", value)} />
        </div>
      </section>

      <section className="panel">
        <div className="file-head">
          <h2>Delivery notes</h2>
          <span className="muted">{notes.length ? `${notes.length} paper${notes.length === 1 ? "" : "s"}` : "Add one or more papers"}</span>
        </div>
        <input type="file" accept="image/*,application/pdf,.pdf" multiple onChange={(event) => { addNotes(event.target.files); event.target.value = "" }} />
        {notes.map((item) => (
          <SourceCard
            key={item.id}
            item={item}
            columns={NOTE_FIELDS}
            message={fields}
            onRemove={() => remove(item.id, setNotes)}
            onRetry={() => retry(item, "delivery_note", setNotes)}
          />
        ))}
      </section>

      <section className="panel">
        <div className="file-head">
          <h2>Pallet on scale</h2>
          <span className="muted">{photos.length ? `${photos.length} photo${photos.length === 1 ? "" : "s"}` : "Add one or more photos"}</span>
        </div>
        <input type="file" accept="image/*" multiple onChange={(event) => { addPhotos(event.target.files); event.target.value = "" }} />
        {photos.map((item) => (
          <SourceCard
            key={item.id}
            item={item}
            columns={SCALE_FIELDS}
            message={fields}
            onRemove={() => remove(item.id, setPhotos)}
            onRetry={() => retry(item, "scale", setPhotos)}
          />
        ))}
      </section>

      <form className="panel" onSubmit={save}>
        <h2>Save message row</h2>
        <p className="muted">Saves the message values to the sea sheet. The note and scale stay here for the check.</p>
        <label className="check">
          <input type="checkbox" checked={confirmNew} onChange={(event) => setConfirmNew(event.target.checked)} />
          Confirm new TL mark or shop name
        </label>
        {error ? <div className="banner err">{error}</div> : null}
        {notice ? <div className="banner ok">{notice}</div> : null}
        <button className="btn" type="submit" disabled={busy}>Save to sea sheet</button>
      </form>
    </main>
  )
}

function SourceCard({
  item,
  columns,
  message,
  onRemove,
  onRetry,
}: {
  item: Attachment
  columns: CheckColumn[]
  message: IntakeFields
  onRemove: () => void
  onRetry: () => void
}) {
  return (
    <article className="source-card">
      <figure className="preview">
        {item.file.type.startsWith("image/") ? <img src={item.url} alt={item.file.name} /> : <div className="pdf-chip">PDF</div>}
        <figcaption>{item.file.name}</figcaption>
        <button className="btn-quiet" type="button" onClick={onRemove}>Remove</button>
      </figure>
      <div>
        {item.status === "reading" ? <p>Reading this file…</p> : null}
        {item.status === "error" ? (
          <>
            <div className="banner err">{item.error}</div>
            <button className="btn-quiet" type="button" onClick={onRetry}>Try again</button>
          </>
        ) : null}
        {item.status === "done" ? (
          <dl className="check-list">
            {columns.map((column) => {
              const value = item.extracted[column.key]
              const messageValue = column.messageKey ? message[column.messageKey] : ""
              const result = compareCheck(column.compare, messageValue, value)
              return (
                <div key={column.key}>
                  <dt>{column.label}</dt>
                  <dd>{showCheckValue(value) || "—"}</dd>
                  <CheckMark result={result} messageValue={showCheckValue(messageValue)} />
                </div>
              )
            })}
          </dl>
        ) : null}
      </div>
    </article>
  )
}

function CheckMark({ result, messageValue }: { result: CheckResult; messageValue: string }) {
  if (result === "empty") return <span className="muted"> </span>
  if (result === "match") return <span className="check-ok">Matches message</span>
  return <span className="check-bad">Message says {messageValue}</span>
}

function Field({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string
  value: string
  onChange: (value: string) => void
  type?: string
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  )
}
