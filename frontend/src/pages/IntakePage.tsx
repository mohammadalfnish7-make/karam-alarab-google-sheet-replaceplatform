import { Dispatch, FormEvent, SetStateAction, useEffect, useMemo, useState } from "react"
import { api, readError } from "../api"
import {
  NOTE_FIELDS,
  SCALE_FIELDS,
  SCALE_VS_HANDWRITE_TOLERANCE,
  asNumber,
  buildNoteTotals,
  buildScaleTotals,
  checkToneFromResult,
  compareCheck,
  emptyIntake,
  intakeSaveGate,
  parseIntakeMessage,
  preferredPhotoTotals,
  scaleVsHandDetail,
  showCheckValue,
  AIR_SAMPLE_MESSAGE,
  SAMPLE_MESSAGE,
  type CheckColumn,
  type CheckTone,
  type IntakeFields,
  type TotalCheck,
} from "../intake"

type Kind = "sea" | "air"

type Extracted = Record<string, string | number | null>

type FieldOverride = {
  field: string
  from: string | number | null
  to: string | number | null
  why: string
  at: string
}

type Attachment = {
  id: string
  file: File
  url: string
  status: "reading" | "done" | "error"
  extracted: Extracted
  originalExtracted: Extracted
  error: string
  warnConfirmed: boolean
  scaleOverridden: boolean
  overrides: FieldOverride[]
}

type ReviewItem =
  | { kind: "note"; item: Attachment; index: number }
  | { kind: "photo"; item: Attachment; index: number }

function filesOf(list: FileList | null): Attachment[] {
  if (!list?.length) return []
  return Array.from(list).map((file) => ({
    id: crypto.randomUUID(),
    file,
    url: URL.createObjectURL(file),
    status: "reading",
    extracted: {},
    originalExtracted: {},
    error: "",
    warnConfirmed: false,
    scaleOverridden: false,
    overrides: [],
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

async function readSources(items: Attachment[], kind: "delivery_note" | "scale") {
  if (items.length === 1) {
    const fields = await readSource(items[0].file, kind)
    return [{ id: items[0].id, fields, error: "" as string }]
  }
  const body = new FormData()
  body.append("kind", kind)
  for (const item of items) body.append("files", item.file)
  const response = await api("/api/intake/read-batch", { method: "POST", body })
  if (!response.ok) {
    const err = await readError(response)
    throw new Error(err.message || "Could not read these files")
  }
  const payload = await response.json()
  const results = (payload.results || []) as Array<{ fields?: Extracted | null; error?: string | null }>
  return items.map((item, index) => {
    const row = results[index] || {}
    return {
      id: item.id,
      fields: (row.fields || {}) as Extracted,
      error: row.error || "",
    }
  })
}

function numOrNull(value: string | number | null | undefined): number | null {
  if (value == null || value === "") return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

export function IntakePage({ kind, onBack }: { kind: Kind; onBack: () => void }) {
  const [messageText, setMessageText] = useState("")
  const [fields, setFields] = useState<IntakeFields>(emptyIntake())
  const [notes, setNotes] = useState<Attachment[]>([])
  const [photos, setPhotos] = useState<Attachment[]>([])
  const [selectedId, setSelectedId] = useState("")
  const [confirmNew, setConfirmNew] = useState(false)
  const [confirmWeightGap, setConfirmWeightGap] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [busy, setBusy] = useState(false)

  const reviewItems = useMemo<ReviewItem[]>(
    () => [
      ...notes.map((item, index) => ({ kind: "note" as const, item, index })),
      ...photos.map((item, index) => ({ kind: "photo" as const, item, index })),
    ],
    [notes, photos],
  )

  const selected = reviewItems.find((row) => row.item.id === selectedId) || reviewItems[0] || null

  const saveGate = useMemo(() => {
    const photoStates = photos.map((photo) => ({
      status: photo.status,
      extracted: photo.extracted,
      warnConfirmed: photo.warnConfirmed || confirmWeightGap,
    }))
    const noteBlockers: string[] = []
    for (const [index, note] of notes.entries()) {
      if (note.status === "reading") noteBlockers.push(`Note ${index + 1} is still reading`)
      if (note.status === "error") noteBlockers.push(`Note ${index + 1} failed — re-check or remove`)
    }
    const gate = intakeSaveGate(photoStates)
    return {
      canSave: gate.canSave && noteBlockers.length === 0,
      needsWarnConfirm: gate.needsWarnConfirm,
      blockers: [...noteBlockers, ...gate.blockers],
    }
  }, [photos, notes, confirmWeightGap])

  useEffect(() => {
    if (!reviewItems.length) {
      setSelectedId("")
      return
    }
    if (!reviewItems.some((row) => row.item.id === selectedId)) {
      setSelectedId(reviewItems[0].item.id)
    }
  }, [reviewItems, selectedId])

  useEffect(() => {
    if (!saveGate.needsWarnConfirm) setConfirmWeightGap(false)
  }, [saveGate.needsWarnConfirm])

  function applyMessage(text: string) {
    setMessageText(text)
    setFields(parseIntakeMessage(text, kind))
    setError("")
    setNotice("")
  }

  function update<K extends keyof IntakeFields>(key: K, value: IntakeFields[K]) {
    setFields((current) => ({ ...current, [key]: value }))
  }

  function applyReadResults(
    results: Array<{ id: string; fields: Extracted; error: string }>,
    setList: Dispatch<SetStateAction<Attachment[]>>,
  ) {
    const byId = new Map(results.map((row) => [row.id, row]))
    setList((current) => current.map((row) => {
      const result = byId.get(row.id)
      if (!result) return row
      if (result.error) {
        return {
          ...row,
          status: "error",
          error: result.error,
          extracted: {},
          originalExtracted: {},
          warnConfirmed: false,
          scaleOverridden: false,
          overrides: [],
        }
      }
      return {
        ...row,
        status: "done",
        extracted: result.fields,
        originalExtracted: { ...result.fields },
        error: "",
        warnConfirmed: false,
        scaleOverridden: false,
        overrides: [],
      }
    }))
  }

  function readBatch(
    items: Attachment[],
    readKind: "delivery_note" | "scale",
    setList: Dispatch<SetStateAction<Attachment[]>>,
  ) {
    if (!items.length) return
    void readSources(items, readKind)
      .then((results) => applyReadResults(results, setList))
      .catch((reason: Error) => {
        setList((current) => current.map((row) => (
          items.some((item) => item.id === row.id)
            ? { ...row, status: "error", error: reason.message }
            : row
        )))
      })
  }

  function addNotes(list: FileList | null) {
    const added = filesOf(list)
    if (!added.length) return
    setNotes((current) => [...current, ...added])
    setSelectedId(added[0].id)
    readBatch(added, "delivery_note", setNotes)
  }

  function addPhotos(list: FileList | null) {
    const added = filesOf(list)
    if (!added.length) return
    setPhotos((current) => [...current, ...added])
    setSelectedId(added[0].id)
    readBatch(added, "scale", setPhotos)
  }

  function retry(item: Attachment, readKind: "delivery_note" | "scale") {
    const setList = readKind === "delivery_note" ? setNotes : setPhotos
    const next = {
      ...item,
      status: "reading" as const,
      error: "",
      extracted: {},
      originalExtracted: {},
      warnConfirmed: false,
      scaleOverridden: false,
      overrides: [],
    }
    setList((current) => current.map((row) => (row.id === item.id ? next : row)))
    readBatch([next], readKind, setList)
  }

  function remove(id: string, setList: Dispatch<SetStateAction<Attachment[]>>) {
    setList((current) => {
      const found = current.find((item) => item.id === id)
      if (found) URL.revokeObjectURL(found.url)
      return current.filter((item) => item.id !== id)
    })
  }

  function patchPhoto(id: string, patch: (row: Attachment) => Attachment) {
    setPhotos((current) => current.map((row) => (row.id === id ? patch(row) : row)))
  }

  function patchNote(id: string, patch: (row: Attachment) => Attachment) {
    setNotes((current) => current.map((row) => (row.id === id ? patch(row) : row)))
  }

  function recordOverride(
    row: Attachment,
    field: string,
    from: string | number | null,
    to: string | number | null,
    why: string,
  ): FieldOverride[] {
    return [
      ...row.overrides,
      { field, from, to, why, at: new Date().toISOString() },
    ]
  }

  function editExtract(item: Attachment, mode: "note" | "scale", key: string, raw: string) {
    const nextValue = raw === "" ? null : (asNumber(raw) != null && /^-?\d+(\.\d+)?$/.test(raw.trim()) ? Number(raw) : raw)
    const patch = (row: Attachment): Attachment => {
      const from = row.extracted[key] ?? null
      if (String(from ?? "") === String(nextValue ?? "")) return row
      const extracted = { ...row.extracted, [key]: nextValue }
      const scaleOverridden =
        mode === "scale" && key === "scale_weight_kg" ? true : row.scaleOverridden
      const original = row.originalExtracted[key] ?? null
      const overrides =
        String(original ?? "") === String(nextValue ?? "")
          ? row.overrides.filter((entry) => entry.field !== key)
          : recordOverride(
            { ...row, overrides: row.overrides.filter((entry) => entry.field !== key || entry.why !== "edit") },
            key,
            original,
            nextValue,
            "edit",
          )
      return {
        ...row,
        extracted,
        warnConfirmed: false,
        scaleOverridden,
        overrides,
      }
    }
    if (mode === "note") patchNote(item.id, patch)
    else patchPhoto(item.id, patch)
  }

  function useScaleForTw(item: Attachment) {
    const scale = item.extracted.scale_weight_kg ?? null
    const from = item.extracted.total_weight_kg ?? null
    patchPhoto(item.id, (row) => ({
      ...row,
      extracted: { ...row.extracted, total_weight_kg: scale },
      warnConfirmed: false,
      overrides: recordOverride(row, "total_weight_kg", from, scale, "use_scale"),
    }))
  }

  function useHandForTw(item: Attachment) {
    const hand = item.extracted.total_weight_kg ?? null
    const from = item.extracted.scale_weight_kg ?? null
    patchPhoto(item.id, (row) => ({
      ...row,
      extracted: { ...row.extracted, scale_weight_kg: hand },
      warnConfirmed: false,
      scaleOverridden: true,
      overrides: recordOverride(row, "scale_weight_kg", from, hand, "use_hand"),
    }))
  }

  function applyPreferredToMessage() {
    const done = photos.filter((row) => row.status === "done").map((row) => row.extracted)
    if (!done.length) return
    const preferred = preferredPhotoTotals(done)
    setFields((current) => ({
      ...current,
      cartons: preferred.cartons != null ? String(preferred.cartons) : current.cartons,
      total_weight_kg: preferred.total_weight_kg != null ? String(preferred.total_weight_kg) : current.total_weight_kg,
      pallet_weight_kg: preferred.pallet_weight_kg != null ? String(preferred.pallet_weight_kg) : current.pallet_weight_kg,
      net_weight_kg: preferred.net_weight_kg != null ? String(preferred.net_weight_kg) : current.net_weight_kg,
    }))
  }

  async function loadSample() {
    const sample = kind === "air"
      ? {
          message: AIR_SAMPLE_MESSAGE,
          notePath: "/demo/air-delivery-note.jpg",
          noteName: "air-delivery-note.jpg",
          photoPath: "/demo/air-scale.jpg",
          photoName: "air-scale.jpg",
        }
      : {
          message: SAMPLE_MESSAGE,
          notePath: "/demo/delivery-note.jpg",
          noteName: "delivery-note.jpg",
          photoPath: "/demo/pallet-scale.jpg",
          photoName: "pallet-scale.jpg",
        }
    applyMessage(sample.message)
    const [note, photo] = await Promise.all([
      sampleFile(sample.notePath, sample.noteName),
      sampleFile(sample.photoPath, sample.photoName),
    ])
    const blank = (): Omit<Attachment, "id" | "file" | "url"> => ({
      status: "reading",
      extracted: {},
      originalExtracted: {},
      error: "",
      warnConfirmed: false,
      scaleOverridden: false,
      overrides: [],
    })
    const noteAttach: Attachment = {
      id: crypto.randomUUID(),
      file: note,
      url: URL.createObjectURL(note),
      ...blank(),
    }
    const photoItem: Attachment = {
      id: crypto.randomUUID(),
      file: photo,
      url: URL.createObjectURL(photo),
      ...blank(),
    }
    setNotes((current) => {
      for (const item of current) URL.revokeObjectURL(item.url)
      return [noteAttach]
    })
    setPhotos((current) => {
      for (const item of current) URL.revokeObjectURL(item.url)
      return [photoItem]
    })
    setSelectedId(noteAttach.id)
    setConfirmWeightGap(false)
    readBatch([noteAttach], "delivery_note", setNotes)
    readBatch([photoItem], "scale", setPhotos)
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!saveGate.canSave) {
      setError(saveGate.blockers[0] || "Resolve weight checks before save")
      return
    }
    setBusy(true)
    setError("")
    setNotice("")

    const donePhotos = photos.filter((row) => row.status === "done")
    const preferred = preferredPhotoTotals(donePhotos.map((row) => row.extracted))
    const cartons = preferred.cartons ?? numOrNull(fields.cartons)
    const gross = preferred.total_weight_kg ?? numOrNull(fields.total_weight_kg)
    const net = preferred.net_weight_kg ?? numOrNull(fields.net_weight_kg)
    const scaleOverridden = donePhotos.some((row) => row.scaleOverridden)
    const allOverrides = donePhotos.flatMap((row) =>
      row.overrides.map((entry) => ({
        ...entry,
        photo_id: row.id,
        file_name: row.file.name,
      })),
    )

    const intake_check = donePhotos.length
      ? {
          confirm_weight_gap: confirmWeightGap || donePhotos.every((row) => {
            const detail = scaleVsHandDetail(row.extracted)
            return detail.tone !== "warn" || row.warnConfirmed || confirmWeightGap
          }),
          scale_overridden: scaleOverridden,
          preferred,
          overrides: allOverrides,
          photos: donePhotos.map((row) => ({
            file_name: row.file.name,
            original: row.originalExtracted,
            extracted: row.extracted,
            warn_confirmed: row.warnConfirmed || confirmWeightGap,
            scale_overridden: row.scaleOverridden,
            overrides: row.overrides,
            scale_vs_hand: scaleVsHandDetail(row.extracted),
          })),
        }
      : null

    const payload = {
      date_received: fields.date_received || null,
      customer_code: fields.customer_code || null,
      company_name: fields.company_name || null,
      cartons,
      gross_weight_kg: gross,
      gross_is_no_pallet: false,
      net_weight_kg: net,
      system_code: null,
      shipment_number: fields.shipment_number || null,
      shipping_route: null,
      stage: kind === "sea" ? "📦 WH" : null,
      status: null,
      confirm_new_customer: confirmNew,
      confirm_new_company: confirmNew,
      confirm_new_supplier: false,
      intake_check,
    }
    const response = await api(`/api/${kind}`, { method: "POST", body: JSON.stringify(payload) })
    if (response.status === 422) {
      setBusy(false)
      const body = await readError(response)
      if (body.code === "NEW_VALUE_CONFIRMATION_REQUIRED") setConfirmNew(true)
      const details = Object.values(body.field_errors || {}).filter(Boolean)
      setError(details[0] || body.message || "Could not save this row")
      return
    }
    if (!response.ok) {
      setBusy(false)
      const body = await readError(response)
      setError(body.message || "Could not save this row")
      return
    }
    const saved = await response.json() as { item?: { id?: number } }
    const itemId = saved.item?.id
    const evidence = [
      ...notes.filter((row) => row.status === "done" || row.status === "error").map((row, index) => ({
        file: row.file,
        kindTag: "note" as const,
        label: `Note ${index + 1}`,
        extracted: row.extracted,
      })),
      ...photos.filter((row) => row.status === "done" || row.status === "error").map((row, index) => ({
        file: row.file,
        kindTag: "scale" as const,
        label: `Scale ${index + 1}`,
        extracted: row.extracted,
      })),
    ]
    let fileNote = ""
    if (itemId && evidence.length) {
      const form = new FormData()
      for (const item of evidence) {
        form.append("files", item.file)
        form.append("kinds", item.kindTag)
        form.append("labels", item.label)
        form.append("extracted", JSON.stringify(item.extracted || {}))
      }
      const upload = await api(`/api/${kind}/${itemId}/files`, { method: "POST", body: form })
      if (!upload.ok) {
        const body = await readError(upload)
        fileNote = ` Row saved, but files failed: ${body.message || "upload error"}.`
      } else {
        fileNote = ` ${evidence.length} file${evidence.length === 1 ? "" : "s"} stored.`
      }
    }
    setBusy(false)
    setNotice(
      `Saved ${kind} row ${fields.shipment_number || ""}${scaleOverridden ? " (needs review — scale overridden)" : ""}.${fileNote}`,
    )
  }

  const noteMulti = notes.filter((row) => row.status === "done").length > 1
  const photoMulti = photos.filter((row) => row.status === "done").length > 1

  return (
    <main className="page intake-page">
      <div className="page-head">
        <h1>{kind === "sea" ? "Sea intake" : "Air intake"}</h1>
        <div className="page-actions">
          <button className="btn-quiet" type="button" onClick={onBack}>Back to sheet</button>
          <button className="btn-quiet" type="button" onClick={() => void loadSample()}>
            {kind === "sea" ? "Load Madinah sample" : "Load Burnaby sample"}
          </button>
        </div>
      </div>
      <p className="muted">
        Side-by-side review. Scale vs hand: Match · OK ≤ {SCALE_VS_HANDWRITE_TOLERANCE} kg (confirm) · Conflict (block until resolved).
        Net = preferred TW − PW.
      </p>

      <section className="panel source-card">
        <div>
          <h2>Message</h2>
          <textarea
            className="message-box"
            value={messageText}
            placeholder={kind === "air" ? AIR_SAMPLE_MESSAGE : SAMPLE_MESSAGE}
            onChange={(event) => applyMessage(event.target.value)}
          />
        </div>
        <div className="form-grid">
          <Field label="Shipment" value={fields.shipment_number} onChange={(value) => update("shipment_number", value)} />
          <Field label="Date" value={fields.date_received} onChange={(value) => update("date_received", value)} placeholder="YYYY-MM-DD" />
          <Field label="TL mark" value={fields.customer_code} onChange={(value) => update("customer_code", value)} />
          <Field label="Shop" value={fields.company_name} onChange={(value) => update("company_name", value)} />
          <Field label="Cartons" value={fields.cartons} onChange={(value) => update("cartons", value)} />
          {kind === "air" ? <Field label="Pieces" value={fields.pieces} onChange={(value) => update("pieces", value)} /> : null}
          <Field label="Goods" value={fields.goods} onChange={(value) => update("goods", value)} />
          <Field label="Total kg (TW)" value={fields.total_weight_kg} onChange={(value) => update("total_weight_kg", value)} />
          <Field label="Pallet kg (PW)" value={fields.pallet_weight_kg} onChange={(value) => update("pallet_weight_kg", value)} />
          <Field label="Net kg (NW)" value={fields.net_weight_kg} onChange={(value) => update("net_weight_kg", value)} />
        </div>
      </section>

      <section className="panel intake-upload-bar">
        <div className="file-head">
          <h2>Sources</h2>
          <span className="muted">
            {notes.length} note{notes.length === 1 ? "" : "s"} · {photos.length} photo{photos.length === 1 ? "" : "s"}
          </span>
        </div>
        <div className="intake-upload-actions">
          <label className="btn-quiet intake-file-btn">
            Add delivery notes
            <input type="file" accept="image/*,application/pdf,.pdf" multiple hidden onChange={(event) => { addNotes(event.target.files); event.target.value = "" }} />
          </label>
          <label className="btn-quiet intake-file-btn">
            Add scale photos
            <input type="file" accept="image/*" multiple hidden onChange={(event) => { addPhotos(event.target.files); event.target.value = "" }} />
          </label>
          {photos.some((row) => row.status === "done") ? (
            <button className="btn-quiet" type="button" onClick={applyPreferredToMessage}>
              Apply preferred totals to message
            </button>
          ) : null}
        </div>
      </section>

      {reviewItems.length ? (
        <section className="panel intake-review">
          <div className="intake-split">
            <div>
              <div className="intake-stage">
                {selected?.item.file.type.startsWith("image/") ? (
                  <img src={selected.item.url} alt={selected.item.file.name} />
                ) : selected ? (
                  <div className="pdf-chip intake-stage-pdf">PDF</div>
                ) : null}
                {selected?.item.status === "reading" ? (
                  <div className="intake-stage-overlay">Reading…</div>
                ) : null}
              </div>
              <div className="intake-thumbs">
                {reviewItems.map((row) => (
                  <button
                    key={row.item.id}
                    type="button"
                    className={`intake-thumb${row.item.id === selected?.item.id ? " active" : ""}${row.item.status === "error" ? " bad" : ""}`}
                    onClick={() => setSelectedId(row.item.id)}
                  >
                    {row.item.file.type.startsWith("image/") ? (
                      <img src={row.item.url} alt="" />
                    ) : (
                      <span className="intake-thumb-pdf">PDF</span>
                    )}
                    <span className="intake-thumb-label">
                      {row.kind === "note" ? "Note" : "Scale"} {row.index + 1}
                      {row.item.status === "reading" ? "…" : ""}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            <aside className="intake-fields">
              {selected ? (
                <ReviewFields
                  row={selected}
                  message={fields}
                  multi={selected.kind === "note" ? noteMulti : photoMulti}
                  onRemove={() => remove(
                    selected.item.id,
                    selected.kind === "note" ? setNotes : setPhotos,
                  )}
                  onRetry={() => retry(
                    selected.item,
                    selected.kind === "note" ? "delivery_note" : "scale",
                  )}
                  onEdit={(key, value) => editExtract(selected.item, selected.kind === "note" ? "note" : "scale", key, value)}
                  onUseScale={() => useScaleForTw(selected.item)}
                  onUseHand={() => useHandForTw(selected.item)}
                  onConfirmWarn={() => patchPhoto(selected.item.id, (row) => ({ ...row, warnConfirmed: true }))}
                />
              ) : null}
            </aside>
          </div>
        </section>
      ) : (
        <section className="panel">
          <p className="muted" style={{ margin: 0 }}>
            Add delivery notes and scale photos to start the side-by-side check.
          </p>
        </section>
      )}

      <TotalsScoreboard
        title="Note totals vs message"
        rows={buildNoteTotals(
          fields,
          notes.filter((item) => item.status === "done").map((item) => item.extracted),
        )}
        visible={notes.some((item) => item.status === "done")}
      />
      <TotalsScoreboard
        title="Scale totals vs message (preferred TW)"
        rows={buildScaleTotals(
          fields,
          photos.filter((item) => item.status === "done").map((item) => item.extracted),
        )}
        visible={photos.some((item) => item.status === "done")}
      />

      <form className="panel" onSubmit={save}>
        <h2>Save message row</h2>
        <p className="muted">
          Saves preferred totals (when scale photos are present) to the {kind} sheet. Original extract and overrides are audited.
        </p>
        {saveGate.blockers.length ? (
          <div className="banner err">
            {saveGate.blockers.map((line) => (
              <div key={line}>{line}</div>
            ))}
          </div>
        ) : null}
        {saveGate.needsWarnConfirm ? (
          <label className="check">
            <input
              type="checkbox"
              checked={confirmWeightGap}
              onChange={(event) => setConfirmWeightGap(event.target.checked)}
            />
            Confirm OK ≤ {SCALE_VS_HANDWRITE_TOLERANCE} kg gaps on scale photos
          </label>
        ) : null}
        <label className="check">
          <input type="checkbox" checked={confirmNew} onChange={(event) => setConfirmNew(event.target.checked)} />
          Confirm new TL mark or shop name
        </label>
        {error ? <div className="banner err">{error}</div> : null}
        {notice ? <div className="banner ok">{notice}</div> : null}
        <button className="btn" type="submit" disabled={busy || !saveGate.canSave}>
          Save to {kind} sheet
        </button>
      </form>
    </main>
  )
}

function ReviewFields({
  row,
  message,
  multi,
  onRemove,
  onRetry,
  onEdit,
  onUseScale,
  onUseHand,
  onConfirmWarn,
}: {
  row: ReviewItem
  message: IntakeFields
  multi: boolean
  onRemove: () => void
  onRetry: () => void
  onEdit: (key: string, value: string) => void
  onUseScale: () => void
  onUseHand: () => void
  onConfirmWarn: () => void
}) {
  const mode = row.kind === "note" ? "note" : "scale"
  const columns = mode === "note" ? NOTE_FIELDS : SCALE_FIELDS
  const { item } = row
  const weightDetail = mode === "scale" && item.status === "done" ? scaleVsHandDetail(item.extracted) : null

  return (
    <>
      <div className="intake-fields-head">
        <div>
          <h2>{mode === "note" ? "Extracted · delivery note" : "Extracted · scale photo"}</h2>
          <p className="muted" style={{ margin: 0 }}>{item.file.name}</p>
        </div>
        <div className="intake-fields-actions">
          {mode === "scale" && item.status === "done" && weightDetail?.tone === "bad" ? (
            <>
              <button className="btn-quiet" type="button" onClick={onUseScale}>Use scale</button>
              <button className="btn-quiet" type="button" onClick={onUseHand}>Use hand</button>
            </>
          ) : null}
          {item.status === "error" || item.status === "done" ? (
            <button className="btn-quiet" type="button" onClick={onRetry}>Re-check</button>
          ) : null}
          <button className="btn-quiet" type="button" onClick={onRemove}>Remove</button>
        </div>
      </div>

      {item.status === "reading" ? <p>Reading this file…</p> : null}
      {item.status === "error" ? <div className="banner err">{item.error}</div> : null}
      {mode === "scale" && item.status === "done" && weightDetail?.tone === "warn" && !item.warnConfirmed ? (
        <label className="check" style={{ marginBottom: 10 }}>
          <input type="checkbox" checked={item.warnConfirmed} onChange={onConfirmWarn} />
          Confirm OK ≤ {SCALE_VS_HANDWRITE_TOLERANCE} kg on this photo
        </label>
      ) : null}
      {item.status === "done" ? (
        <dl className="intake-field-list">
          {columns.map((column) => {
            const value = item.extracted[column.key]
            const original = item.originalExtracted[column.key]
            const check = fieldCheck(mode, multi, column, message, item.extracted)
            const edited = String(value ?? "") !== String(original ?? "") && original !== undefined
            return (
              <div className="intake-field-row" key={column.key}>
                <dt>{column.label}</dt>
                <dd>
                  <input
                    className="intake-extract-input"
                    value={value == null ? "" : String(value)}
                    onChange={(event) => onEdit(column.key, event.target.value)}
                  />
                  {edited ? (
                    <span className="muted intake-original">was {showCheckValue(original) || "—"}</span>
                  ) : null}
                </dd>
                {check.tone !== "empty" ? <StatusChip tone={check.tone}>{check.label}</StatusChip> : <span />}
              </div>
            )
          })}
        </dl>
      ) : null}
    </>
  )
}

function fieldCheck(
  mode: "note" | "scale",
  multi: boolean,
  column: CheckColumn,
  message: IntakeFields,
  extracted: Extracted,
): { tone: CheckTone; label: string } {
  const messageValue = column.messageKey ? showCheckValue(message[column.messageKey]) : ""

  if (mode === "scale" && (column.key === "scale_weight_kg" || column.key === "total_weight_kg")) {
    const detail = scaleVsHandDetail(extracted)
    if (detail.tone === "empty") return { tone: "empty", label: "" }
    return { tone: detail.tone, label: detail.label }
  }

  const summedKeys = new Set(["cartons", "total_weight_kg", "pallet_weight_kg", "scale_weight_kg"])
  if (multi && summedKeys.has(column.key) && column.compare === "number") {
    return { tone: "empty", label: "" }
  }

  if (column.compare === "none") return { tone: "empty", label: "" }

  const result = compareCheck(
    column.compare,
    column.messageKey ? message[column.messageKey] : "",
    extracted[column.key],
  )
  if (result === "empty") return { tone: "empty", label: "" }
  if (result === "match") return { tone: "ok", label: "Matches message" }

  const left = asNumber(messageValue)
  const right = asNumber(extracted[column.key])
  if (column.compare === "number" && left != null && right != null) {
    const delta = Math.round(Math.abs(left - right) * 1000) / 1000
    if (delta <= SCALE_VS_HANDWRITE_TOLERANCE) {
      return { tone: "warn", label: `OK ≤ ${SCALE_VS_HANDWRITE_TOLERANCE} kg` }
    }
  }
  return {
    tone: "bad",
    label: messageValue ? `Message says ${messageValue}` : "Does not match message",
  }
}

function TotalsScoreboard({ title, rows, visible }: { title: string; rows: TotalCheck[]; visible: boolean }) {
  if (!visible) return null
  const useful = rows.filter((row) => row.summed != null || row.messageValue)
  if (!useful.length) return null
  return (
    <section className="intake-scoreboard">
      <h2>{title}</h2>
      <div className="intake-score-grid">
        {useful.map((row) => {
          const tone = toneForTotal(row)
          return (
            <article key={row.key} className={`intake-score intake-score-${tone}`}>
              <span className="intake-score-label">{row.label}</span>
              <strong>{row.summed == null ? "—" : showCheckValue(row.summed)}</strong>
              <span className="muted">
                {row.messageValue ? `message ${showCheckValue(row.messageValue)}` : "no message value"}
              </span>
              {tone !== "empty" ? (
                <StatusChip tone={tone}>
                  {tone === "ok" ? "Match" : tone === "warn" ? `OK ≤ ${SCALE_VS_HANDWRITE_TOLERANCE} kg` : "Mismatch"}
                </StatusChip>
              ) : null}
            </article>
          )
        })}
      </div>
    </section>
  )
}

function toneForTotal(row: TotalCheck): CheckTone {
  if (row.result === "empty") return "empty"
  if (row.result === "diff") {
    const left = asNumber(row.summed)
    const right = asNumber(row.messageValue)
    if (left != null && right != null && Math.abs(left - right) <= SCALE_VS_HANDWRITE_TOLERANCE) return "warn"
    return "bad"
  }
  return checkToneFromResult(row.result)
}

function StatusChip({ tone, children }: { tone: CheckTone; children: string }) {
  return <span className={`intake-chip intake-chip-${tone}`}>{children}</span>
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  type?: string
  placeholder?: string
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  )
}
