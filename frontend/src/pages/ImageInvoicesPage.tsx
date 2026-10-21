import { FormEvent, useCallback, useEffect, useRef, useState } from "react"
import { api, readError } from "../api"
import { useAuth } from "../auth"
import type { Page } from "../types"
import { Drawer, Field, Flags, Pager } from "../ui"

type ProductLine = {
  id?: number
  sort_order?: number
  brand_name?: string | null
  barcode?: string | null
  made_in?: string | null
  volume?: string | null
  quantity?: number | null
  file_count?: number
}

type InvoiceRow = {
  id: number
  title: string | null
  line_count?: number
  lines?: ProductLine[] | null
  created_at?: string | null
  deleted_at?: string | null
}

type ProductFile = {
  id: number
  kind: string
  label: string
  file_name: string
  mime: string
  is_image: boolean
  is_pdf: boolean
  deleted_at: string | null
}

const API = "/api/image-invoices"

function emptyLine(): ProductLine {
  return {
    brand_name: "",
    barcode: "",
    made_in: "",
    volume: "",
    quantity: null,
    file_count: 0,
  }
}

function draftFromLines(lines?: ProductLine[] | null): ProductLine[] {
  if (!Array.isArray(lines) || !lines.length) return [emptyLine()]
  return lines.map((line) => ({
    id: line.id,
    sort_order: line.sort_order,
    brand_name: line.brand_name ?? "",
    barcode: line.barcode ?? "",
    made_in: line.made_in ?? "",
    volume: line.volume ?? "",
    quantity: line.quantity ?? null,
    file_count: line.file_count ?? 0,
  }))
}

export function ImageInvoicesPage() {
  const { user } = useAuth()
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

  const load = useCallback(async () => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (q) params.set("q", q)
    if (includeDeleted) params.set("include_deleted", "true")
    const response = await api(`${API}?${params}`)
    if (!response.ok) {
      setError("Could not load image invoices")
      return
    }
    const body = (await response.json()) as Page<InvoiceRow>
    setRows(body.items)
    setTotal(body.total)
    setError("")
  }, [q, offset, includeDeleted])

  useEffect(() => { setOffset(0) }, [q, includeDeleted])
  useEffect(() => { void load() }, [load])

  return (
    <main className="page">
      <div className="page-head">
        <h1>Image invoices</h1>
        <button className="btn" type="button" onClick={() => { setEditing(null); setCreating(true) }}>
          Add
        </button>
      </div>
      <form className="toolbar" onSubmit={(event: FormEvent) => { event.preventDefault(); setQ(draftQ.trim()) }}>
        <input
          type="search"
          placeholder="Search title…"
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
              <th>Title</th>
              <th>Rows</th>
              <th>Created</th>
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
                <td>{row.title || `Image invoice #${row.id}`}</td>
                <td>{row.line_count ?? 0}</td>
                <td className="muted">{row.created_at ? row.created_at.slice(0, 10) : ""}</td>
                <td><Flags legacy={false} review={false} deleted={Boolean(row.deleted_at)} /></td>
              </tr>
            ))}
            {!rows.length ? <tr><td colSpan={4} className="muted">No image invoices</td></tr> : null}
          </tbody>
        </table>
      </div>
      <Pager offset={offset} limit={limit} total={total} onPage={setOffset} />
      {creating || editing ? (
        <ImageInvoiceDrawer
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

function ImageInvoiceDrawer({
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
  const [itemId, setItemId] = useState<number | null>(row?.id ?? null)
  const [title, setTitle] = useState(row?.title || "")
  const [exportName, setExportName] = useState(row?.title || "")
  const [lines, setLines] = useState<ProductLine[]>(() => draftFromLines(row?.lines))
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [extracting, setExtracting] = useState(false)
  const deleted = Boolean(row?.deleted_at)

  const loadDetail = useCallback(async (id: number) => {
    const response = await api(`${API}/${id}`)
    if (!response.ok) {
      setError("Could not load invoice")
      return null
    }
    const body = (await response.json()) as { item: InvoiceRow }
    setTitle(body.item.title || "")
    setExportName((current) => current || body.item.title || `image-invoice-${body.item.id}`)
    setLines(draftFromLines(body.item.lines))
    setItemId(body.item.id)
    setSelectedIndex(0)
    setError("")
    return body.item
  }, [])

  useEffect(() => {
    if (!row?.id) return
    void loadDetail(row.id)
  }, [row?.id, loadDetail])

  async function ensureCreated(): Promise<number | null> {
    if (itemId) return itemId
    setBusy(true)
    setError("")
    const response = await api(API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title.trim() || null }),
    })
    setBusy(false)
    if (!response.ok) {
      const body = await readError(response)
      setError(body.message || "Create failed")
      return null
    }
    const body = (await response.json()) as { item: InvoiceRow }
    setItemId(body.item.id)
    setTitle(body.item.title || "")
    setMessage("Created")
    return body.item.id
  }

  async function saveHeaderAndLines() {
    const id = await ensureCreated()
    if (id == null) return
    setBusy(true)
    setError("")
    const patch = await api(`${API}/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title.trim() || null }),
    })
    if (!patch.ok) {
      setBusy(false)
      const body = await readError(patch)
      setError(body.message || "Save failed")
      return
    }
    const put = await api(`${API}/${id}/lines`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lines: lines.map((line, index) => ({
          id: line.id,
          sort_order: index + 1,
          brand_name: line.brand_name || null,
          barcode: line.barcode || null,
          made_in: line.made_in || null,
          volume: line.volume || null,
          quantity: line.quantity,
        })),
      }),
    })
    setBusy(false)
    if (!put.ok) {
      const body = await readError(put)
      setError(body.message || "Save lines failed")
      return
    }
    const body = (await put.json()) as { item: InvoiceRow }
    setLines(draftFromLines(body.item.lines))
    setMessage("Saved")
    await onKeep(body.item)
  }

  async function addRow() {
    const id = await ensureCreated()
    if (id == null) return
    setBusy(true)
    const response = await api(`${API}/${id}/lines`, { method: "POST" })
    setBusy(false)
    if (!response.ok) {
      const body = await readError(response)
      setError(body.message || "Add row failed")
      return
    }
    const body = (await response.json()) as { item: ProductLine }
    setLines((current) => {
      const next = [...current, { ...emptyLine(), ...body.item }]
      setSelectedIndex(next.length - 1)
      return next
    })
    setMessage("Row added")
  }

  async function removeSelectedRow() {
    const line = lines[selectedIndex]
    if (!line) return
    if (!window.confirm("Remove this product row?")) return
    if (!itemId || !line.id) {
      setLines((current) => {
        const next = current.filter((_, index) => index !== selectedIndex)
        setSelectedIndex(Math.max(0, Math.min(selectedIndex, next.length - 1)))
        return next.length ? next : [emptyLine()]
      })
      return
    }
    setBusy(true)
    const response = await api(`${API}/${itemId}/lines/${line.id}`, { method: "DELETE" })
    setBusy(false)
    if (!response.ok) {
      const body = await readError(response)
      setError(body.message || "Delete row failed")
      return
    }
    const body = (await response.json()) as { item: InvoiceRow }
    const next = draftFromLines(body.item.lines)
    setLines(next)
    setSelectedIndex(0)
    setMessage("Row removed")
  }

  async function extractAi(overwrite = false) {
    const line = lines[selectedIndex]
    if (!itemId || !line?.id) {
      setError("Save the row first, then upload photos")
      return
    }
    if (!(line.file_count ?? 0)) {
      setError("Upload product photos for this row first")
      return
    }
    setExtracting(true)
    setError("")
    const response = await api(`${API}/${itemId}/lines/${line.id}/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ overwrite }),
    })
    setExtracting(false)
    if (!response.ok) {
      const body = await readError(response)
      setError(body.message || "Extract failed")
      return
    }
    const body = (await response.json()) as { item: ProductLine; changed_fields?: string[] }
    setLines((current) => current.map((row, index) => (
      index === selectedIndex
        ? {
            ...row,
            ...body.item,
            brand_name: body.item.brand_name ?? "",
            barcode: body.item.barcode ?? "",
            made_in: body.item.made_in ?? "",
            volume: body.item.volume ?? "",
          }
        : row
    )))
    const changed = body.changed_fields?.length ? body.changed_fields.join(", ") : "no empty fields to fill"
    setMessage(`AI extract: ${changed}`)
  }

  async function removeInvoice() {
    if (!itemId) return
    if (!window.confirm("Delete this image invoice?")) return
    setBusy(true)
    const response = await api(`${API}/${itemId}`, { method: "DELETE" })
    setBusy(false)
    if (!response.ok) {
      setError("Delete failed")
      return
    }
    await onDone()
  }

  async function exportExcel() {
    const id = await ensureCreated()
    if (id == null) return
    // Persist current edits so the sheet matches the editor
    setBusy(true)
    setError("")
    const put = await api(`${API}/${id}/lines`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lines: lines.map((line, index) => ({
          id: line.id,
          sort_order: index + 1,
          brand_name: line.brand_name || null,
          barcode: line.barcode || null,
          made_in: line.made_in || null,
          volume: line.volume || null,
          quantity: line.quantity,
        })),
      }),
    })
    if (!put.ok) {
      setBusy(false)
      const body = await readError(put)
      setError(body.message || "Save before export failed")
      return
    }
    const saved = (await put.json()) as { item: InvoiceRow }
    setLines(draftFromLines(saved.item.lines))

    const response = await api(`${API}/${id}/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: exportName.trim() || title.trim() || null }),
    })
    setBusy(false)
    if (!response.ok) {
      const body = await readError(response)
      setError(body.message || "Export failed")
      return
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    const disposition = response.headers.get("Content-Disposition") || ""
    const match = /filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i.exec(disposition)
    const rawName = decodeURIComponent(match?.[1] || match?.[2] || `${exportName || "image-invoice"}.xlsx`)
    const downloadName = rawName.toLowerCase().endsWith(".xlsx") ? rawName : `${rawName}.xlsx`
    link.href = url
    link.download = downloadName
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    setMessage(`Exported ${downloadName}`)
  }

  async function restoreInvoice() {
    if (!itemId) return
    setBusy(true)
    const response = await api(`${API}/${itemId}/restore`, { method: "POST" })
    setBusy(false)
    if (!response.ok) {
      setError("Restore failed")
      return
    }
    const body = (await response.json()) as { item: InvoiceRow }
    await onKeep(body.item)
  }

  const selected = lines[selectedIndex] || null

  return (
    <Drawer
      title={itemId ? (title || `Image invoice #${itemId}`) : "New image invoice"}
      onClose={onClose}
      wide
      className="image-invoice-drawer"
      footer={(
        <>
          <div className="drawer-footer-actions">
            {!deleted ? (
              <>
                <button className="btn" type="button" disabled={busy || extracting} onClick={() => void saveHeaderAndLines()}>
                  Save
                </button>
                <button className="btn-quiet" type="button" disabled={busy || extracting} onClick={() => void addRow()}>
                  Add row
                </button>
                <button className="btn-quiet" type="button" disabled={busy || extracting || !selected?.id} onClick={() => void extractAi(false)}>
                  {extracting ? "Extracting…" : "Extract with AI"}
                </button>
                <button className="btn-quiet" type="button" disabled={busy || extracting || !lines.length} onClick={() => void exportExcel()}>
                  Export Excel
                </button>
              </>
            ) : null}
            {deleted && canRestore ? (
              <button className="btn" type="button" disabled={busy} onClick={() => void restoreInvoice()}>Restore</button>
            ) : null}
            {itemId && !deleted ? (
              <button className="btn-danger" type="button" disabled={busy} onClick={() => void removeInvoice()}>Delete</button>
            ) : null}
          </div>
          <button className="btn-quiet" type="button" onClick={onClose}>Close</button>
        </>
      )}
    >
      {error ? <div className="banner err">{error}</div> : null}
      {message ? <div className="banner ok">{message}</div> : null}
      <div className="form-grid" style={{ marginBottom: 12 }}>
        <Field label="Title">
          <input
            value={title}
            disabled={deleted || busy}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Optional session title"
          />
        </Field>
        <Field label="Export file name">
          <input
            value={exportName}
            disabled={deleted || busy}
            onChange={(event) => setExportName(event.target.value)}
            placeholder="e.g. shelf-scan-2026"
          />
          <small>.xlsx is added automatically</small>
        </Field>
      </div>
      <div className="image-invoice-split">
        <div className="image-invoice-lines">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Brand</th>
                  <th>Barcode</th>
                  <th>Made in</th>
                  <th>Volume</th>
                  <th>Qty</th>
                  <th>Photos</th>
                </tr>
              </thead>
              <tbody>
                {lines.map((line, index) => (
                  <tr
                    key={line.id ?? `new-${index}`}
                    className={index === selectedIndex ? "clickable image-invoice-row-selected" : "clickable"}
                    onClick={() => setSelectedIndex(index)}
                  >
                    <td>
                      <input
                        value={line.brand_name ?? ""}
                        disabled={deleted || busy}
                        onChange={(event) => {
                          const value = event.target.value
                          setLines((current) => current.map((row, i) => (i === index ? { ...row, brand_name: value } : row)))
                        }}
                        onClick={(event) => event.stopPropagation()}
                      />
                    </td>
                    <td>
                      <input
                        value={line.barcode ?? ""}
                        disabled={deleted || busy}
                        onChange={(event) => {
                          const value = event.target.value
                          setLines((current) => current.map((row, i) => (i === index ? { ...row, barcode: value } : row)))
                        }}
                        onClick={(event) => event.stopPropagation()}
                      />
                    </td>
                    <td>
                      <input
                        value={line.made_in ?? ""}
                        disabled={deleted || busy}
                        onChange={(event) => {
                          const value = event.target.value
                          setLines((current) => current.map((row, i) => (i === index ? { ...row, made_in: value } : row)))
                        }}
                        onClick={(event) => event.stopPropagation()}
                      />
                    </td>
                    <td>
                      <input
                        value={line.volume ?? ""}
                        disabled={deleted || busy}
                        onChange={(event) => {
                          const value = event.target.value
                          setLines((current) => current.map((row, i) => (i === index ? { ...row, volume: value } : row)))
                        }}
                        onClick={(event) => event.stopPropagation()}
                      />
                    </td>
                    <td>
                      <input
                        value={line.quantity == null ? "" : String(line.quantity)}
                        disabled={deleted || busy}
                        inputMode="decimal"
                        onChange={(event) => {
                          const raw = event.target.value.trim()
                          const quantity = raw === "" ? null : Number(raw)
                          setLines((current) => current.map((row, i) => (
                            i === index
                              ? { ...row, quantity: quantity != null && Number.isFinite(quantity) ? quantity : null }
                              : row
                          )))
                        }}
                        onClick={(event) => event.stopPropagation()}
                      />
                    </td>
                    <td className="muted">{line.file_count ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!deleted ? (
            <div className="image-invoice-line-actions">
              <button className="btn-quiet" type="button" disabled={busy} onClick={() => void removeSelectedRow()}>
                Remove selected row
              </button>
              <button className="btn-quiet" type="button" disabled={busy || extracting || !selected?.id} onClick={() => void extractAi(true)}>
                AI overwrite filled fields
              </button>
            </div>
          ) : null}
        </div>
        <div className="image-invoice-photos">
          {itemId && selected?.id ? (
            <LinePhotosPanel
              invoiceId={itemId}
              lineId={selected.id}
              canRestore={canRestore}
              disabled={deleted || busy}
              onCountChange={(count) => {
                setLines((current) => current.map((row, index) => (
                  index === selectedIndex ? { ...row, file_count: count } : row
                )))
              }}
            />
          ) : (
            <p className="muted">
              {itemId
                ? "Save this row first to attach product photos."
                : "Save the invoice, then select a row to upload product photos."}
            </p>
          )}
        </div>
      </div>
    </Drawer>
  )
}

function LinePhotosPanel({
  invoiceId,
  lineId,
  canRestore,
  disabled,
  onCountChange,
}: {
  invoiceId: number
  lineId: number
  canRestore: boolean
  disabled: boolean
  onCountChange: (count: number) => void
}) {
  const [files, setFiles] = useState<ProductFile[]>([])
  const [previews, setPreviews] = useState<Record<number, string>>({})
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [viewing, setViewing] = useState<ProductFile | null>(null)
  const [viewUrl, setViewUrl] = useState("")
  const uploadRef = useRef<HTMLInputElement>(null)
  const cameraRef = useRef<HTMLInputElement>(null)
  const previewUrls = useRef<Record<number, string>>({})
  const viewUrlRef = useRef("")
  const onCountChangeRef = useRef(onCountChange)
  onCountChangeRef.current = onCountChange
  const base = `${API}/${invoiceId}/lines/${lineId}/files`

  const load = useCallback(async () => {
    const params = canRestore ? "?include_deleted=true" : ""
    const response = await api(`${base}${params}`)
    if (!response.ok) {
      setError("Could not load photos")
      return
    }
    const body = (await response.json()) as { items: ProductFile[] }
    setFiles(body.items)
    onCountChangeRef.current(body.items.filter((file) => !file.deleted_at).length)
    setError("")
  }, [base, canRestore])

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
    void api(`${base}/${viewing.id}`).then(async (response) => {
      if (!response.ok || cancelled) return
      const blob = await response.blob()
      if (cancelled) return
      const url = URL.createObjectURL(blob)
      viewUrlRef.current = url
      setViewUrl(url)
    })
    return () => { cancelled = true }
  }, [viewing, previews, base])

  useEffect(() => {
    let cancelled = false
    const next: Record<number, string> = {}
    const tasks = files
      .filter((file) => file.is_image && (!file.deleted_at || canRestore))
      .map(async (file) => {
        const response = await api(`${base}/${file.id}`)
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
  }, [files, base, canRestore])

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
      form.append("labels", `Product ${files.filter((item) => !item.deleted_at).length + index + 1}`)
    })
    const response = await api(base, { method: "POST", body: form })
    setBusy(false)
    if (!response.ok) {
      const body = await readError(response)
      setError(body.message || "Upload failed")
      return
    }
    await load()
  }

  async function removeFile(file: ProductFile) {
    if (!window.confirm("Remove this product photo?")) return
    setBusy(true)
    const response = await api(`${base}/${file.id}`, { method: "DELETE" })
    setBusy(false)
    if (!response.ok) {
      setError("Delete failed")
      return
    }
    if (viewing?.id === file.id) setViewing(null)
    await load()
  }

  async function restoreFile(file: ProductFile) {
    setBusy(true)
    const response = await api(`${base}/${file.id}/restore`, { method: "POST" })
    setBusy(false)
    if (!response.ok) {
      setError("Restore failed")
      return
    }
    await load()
  }

  const active = files.filter((file) => !file.deleted_at)
  const deletedFiles = files.filter((file) => file.deleted_at)

  return (
    <div className="container-loading">
      <p className="muted">Upload front / back / side photos for the selected product.</p>
      {error ? <div className="banner err">{error}</div> : null}
      <div className="container-loading-actions">
        <button className="btn" type="button" disabled={disabled || busy} onClick={() => uploadRef.current?.click()}>Upload</button>
        <button className="btn-quiet" type="button" disabled={disabled || busy} onClick={() => cameraRef.current?.click()}>Take photo</button>
        <input ref={uploadRef} type="file" accept="image/*" multiple hidden onChange={(event) => { void uploadList(event.target.files); event.target.value = "" }} />
        <input ref={cameraRef} type="file" accept="image/*" capture="environment" hidden onChange={(event) => { void uploadList(event.target.files); event.target.value = "" }} />
      </div>
      {!active.length ? <p className="muted">No photos yet.</p> : null}
      <div className="thumbs">
        {active.map((file) => (
          <figure
            key={file.id}
            className={viewing?.id === file.id ? "thumb image-invoice-thumb-active" : "thumb"}
          >
            {file.is_image && previews[file.id] ? (
              <img src={previews[file.id]} alt={file.label} onClick={() => setViewing(file)} />
            ) : (
              <div className="pdf-chip">File</div>
            )}
            <figcaption>{file.label || file.file_name}</figcaption>
            <div className="container-loading-thumb-actions">
              <button className="btn-quiet" type="button" onClick={() => setViewing(file)}>View</button>
              {!disabled ? <button className="btn-danger" type="button" disabled={busy} onClick={() => void removeFile(file)}>Remove</button> : null}
            </div>
          </figure>
        ))}
      </div>
      {viewing && viewUrl ? (
        <div className="image-invoice-preview">
          <img src={viewUrl} alt={viewing.label || viewing.file_name} />
        </div>
      ) : null}
      {canRestore && deletedFiles.length ? (
        <div className="container-loading-deleted">
          <h3>Deleted</h3>
          <div className="thumbs">
            {deletedFiles.map((file) => (
              <figure key={file.id} className="thumb deleted">
                {file.is_image && previews[file.id] ? <img src={previews[file.id]} alt={file.label} /> : <div className="pdf-chip">File</div>}
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
    </div>
  )
}
