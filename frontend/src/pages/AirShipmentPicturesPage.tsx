import { FormEvent, useCallback, useEffect, useRef, useState } from "react"
import { api, readError } from "../api"
import { useAuth } from "../auth"
import type { Page } from "../types"
import { Drawer, Field, Flags, Pager } from "../ui"

type PictureRow = {
  id: number
  number: string
  date: string | null
  cartons: number | null
  file_count?: number
  deleted_at?: string | null
}

type PhotoFile = {
  id: number
  kind: string
  label: string
  file_name: string
  mime: string
  is_image: boolean
  is_pdf: boolean
  deleted_at: string | null
}

const API = "/api/air-shipment-pictures"

export function AirShipmentPicturesPage() {
  const { user } = useAuth()
  const [rows, setRows] = useState<PictureRow[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [draftQ, setDraftQ] = useState("")
  const [q, setQ] = useState("")
  const [includeDeleted, setIncludeDeleted] = useState(false)
  const [error, setError] = useState("")
  const [editing, setEditing] = useState<PictureRow | null>(null)
  const [creating, setCreating] = useState(false)
  const limit = 50

  const load = useCallback(async () => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (q) params.set("q", q)
    if (includeDeleted) params.set("include_deleted", "true")
    const response = await api(`${API}?${params}`)
    if (!response.ok) {
      setError("Could not load air shipment pictures")
      return
    }
    const body = (await response.json()) as Page<PictureRow>
    setRows(body.items)
    setTotal(body.total)
    setError("")
  }, [q, offset, includeDeleted])

  useEffect(() => { setOffset(0) }, [q, includeDeleted])
  useEffect(() => { void load() }, [load])

  return (
    <main className="page">
      <div className="page-head">
        <h1>Air shipment pictures</h1>
        <button className="btn" type="button" onClick={() => { setEditing(null); setCreating(true) }}>
          Add
        </button>
      </div>
      <form className="toolbar" onSubmit={(event) => { event.preventDefault(); setQ(draftQ.trim()) }}>
        <input
          type="search"
          placeholder="Search number (AR087)…"
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
              <th>Number</th>
              <th>Date</th>
              <th>Cartons</th>
              <th>Photos</th>
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
                <td>{row.number}</td>
                <td>{row.date ?? ""}</td>
                <td>{row.cartons == null ? "" : `${row.cartons} CTN`}</td>
                <td>{row.file_count ?? 0}</td>
                <td><Flags legacy={false} review={false} deleted={Boolean(row.deleted_at)} /></td>
              </tr>
            ))}
            {!rows.length ? <tr><td colSpan={5} className="muted">No air shipment pictures</td></tr> : null}
          </tbody>
        </table>
      </div>
      <Pager offset={offset} limit={limit} total={total} onPage={setOffset} />
      {creating || editing ? (
        <PictureDrawer
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

function PictureDrawer({
  row,
  canRestore,
  onClose,
  onDone,
  onKeep,
}: {
  row: PictureRow | null
  canRestore: boolean
  onClose: () => void
  onDone: () => Promise<void>
  onKeep: (row: PictureRow) => Promise<void>
}) {
  const [number, setNumber] = useState(row?.number || "")
  const [dateValue, setDateValue] = useState(row?.date || new Date().toISOString().slice(0, 10))
  const [cartons, setCartons] = useState(row?.cartons == null ? "" : String(row.cartons))
  const [tab, setTab] = useState<"edit" | "photos">(row ? "photos" : "edit")
  const [message, setMessage] = useState("")
  const [errors, setErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    if (row) return
    void api(`${API}/next-number`).then(async (response) => {
      if (!response.ok) return
      const body = (await response.json()) as { number: string }
      setNumber(body.number)
    })
  }, [row])

  async function save() {
    const payload = {
      number: number.trim(),
      date: dateValue,
      cartons: cartons.trim() === "" ? null : cartons.trim(),
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
    const body = (await response.json()) as { item: PictureRow }
    setErrors({})
    setNumber(body.item.number)
    setDateValue(body.item.date || "")
    setCartons(body.item.cartons == null ? "" : String(body.item.cartons))
    if (!row) {
      setMessage("Saved")
      await onKeep(body.item)
      setTab("photos")
      return
    }
    await onDone()
  }

  async function remove() {
    if (!row || !window.confirm("Soft-delete this air shipment picture row?")) return
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

  return (
    <Drawer
      title={row ? `Air shipment ${row.number}` : "New air shipment picture"}
      onClose={onClose}
      footer={
        tab === "photos" ? (
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
        </div>
      ) : null}
      {tab === "photos" && row ? (
        <PhotosPanel itemId={row.id} canRestore={canRestore} disabled={Boolean(row.deleted_at)} />
      ) : (
        <form className="form-grid" onSubmit={(event: FormEvent) => { event.preventDefault(); void save() }}>
          {message ? <div className="banner ok wide">{message}</div> : null}
          <Field label="Number (auto)" error={errors.number}>
            <input
              className={errors.number ? "invalid" : ""}
              value={number}
              onChange={(event) => setNumber(event.target.value)}
              placeholder="AR087"
            />
          </Field>
          <Field label="Date (auto)" error={errors.date}>
            <input
              type="date"
              className={errors.date ? "invalid" : ""}
              value={dateValue}
              onChange={(event) => setDateValue(event.target.value)}
            />
          </Field>
          <Field label="Cartons (CTN)" error={errors.cartons} wide>
            <input
              className={errors.cartons ? "invalid" : ""}
              inputMode="numeric"
              value={cartons}
              onChange={(event) => setCartons(event.target.value)}
              placeholder="85"
            />
          </Field>
        </form>
      )}
    </Drawer>
  )
}

function PhotosPanel({
  itemId,
  canRestore,
  disabled,
}: {
  itemId: number
  canRestore: boolean
  disabled: boolean
}) {
  const [files, setFiles] = useState<PhotoFile[]>([])
  const [previews, setPreviews] = useState<Record<number, string>>({})
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [viewing, setViewing] = useState<PhotoFile | null>(null)
  const [viewUrl, setViewUrl] = useState("")
  const uploadRef = useRef<HTMLInputElement>(null)
  const cameraRef = useRef<HTMLInputElement>(null)
  const previewUrls = useRef<Record<number, string>>({})
  const viewUrlRef = useRef("")

  const load = useCallback(async () => {
    const params = canRestore ? "?include_deleted=true" : ""
    const response = await api(`${API}/${itemId}/files${params}`)
    if (!response.ok) {
      setError("Could not load photos")
      return
    }
    const body = (await response.json()) as { items: PhotoFile[] }
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
      form.append("labels", `Photo ${files.filter((item) => !item.deleted_at).length + index + 1}`)
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

  async function removeFile(file: PhotoFile) {
    if (!window.confirm("Remove this photo?")) return
    setBusy(true)
    const response = await api(`${API}/${itemId}/files/${file.id}`, { method: "DELETE" })
    setBusy(false)
    if (!response.ok) {
      setError("Delete failed")
      return
    }
    await load()
  }

  async function restoreFile(file: PhotoFile) {
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
      <p className="muted">Upload or take multiple shipment photos.</p>
      {error ? <div className="banner err">{error}</div> : null}
      <div className="container-loading-actions">
        <button className="btn" type="button" disabled={disabled || busy} onClick={() => uploadRef.current?.click()}>
          Upload
        </button>
        <button className="btn-quiet" type="button" disabled={disabled || busy} onClick={() => cameraRef.current?.click()}>
          Take photo
        </button>
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
      </div>
      {!active.length ? <p className="muted">No photos yet.</p> : null}
      <div className="thumbs">
        {active.map((file) => (
          <figure key={file.id} className="thumb">
            {file.is_image && previews[file.id] ? (
              <img src={previews[file.id]} alt={file.label} />
            ) : (
              <div className="pdf-chip">{file.is_pdf ? "PDF" : "File"}</div>
            )}
            <figcaption>{file.label || file.file_name}</figcaption>
            <div className="container-loading-thumb-actions">
              <button className="btn-quiet" type="button" onClick={() => setViewing(file)}>View</button>
              {!disabled ? (
                <button className="btn-danger" type="button" disabled={busy} onClick={() => void removeFile(file)}>
                  Delete
                </button>
              ) : null}
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
                {file.is_image && previews[file.id] ? (
                  <img src={previews[file.id]} alt={file.label} />
                ) : (
                  <div className="pdf-chip">{file.is_pdf ? "PDF" : "File"}</div>
                )}
                <figcaption>{file.label || file.file_name}</figcaption>
                <div className="container-loading-thumb-actions">
                  <button className="btn-quiet" type="button" onClick={() => setViewing(file)}>View</button>
                  <button className="btn-quiet" type="button" disabled={busy} onClick={() => void restoreFile(file)}>
                    Restore
                  </button>
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
              {!viewUrl ? (
                <p className="muted">Loading…</p>
              ) : viewing.is_image ? (
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
