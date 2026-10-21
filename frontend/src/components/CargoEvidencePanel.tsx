import { useCallback, useEffect, useRef, useState } from "react"
import { api, readError } from "../api"

export type CargoEvidenceFile = {
  id: number
  kind: string
  label: string
  file_name: string
  mime: string
  is_image: boolean
  is_pdf: boolean
  deleted_at: string | null
}

type FileKind = "papers" | "scale"

type Props = {
  kind: "sea" | "air"
  itemId: number
  canRestore: boolean
  disabled: boolean
  onChanged?: () => void
}

export function CargoEvidencePanel({ kind, itemId, canRestore, disabled, onChanged }: Props) {
  const [files, setFiles] = useState<CargoEvidenceFile[]>([])
  const [previews, setPreviews] = useState<Record<number, string>>({})
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [section, setSection] = useState<FileKind>("papers")
  const [viewing, setViewing] = useState<CargoEvidenceFile | null>(null)
  const [viewUrl, setViewUrl] = useState("")
  const papersRef = useRef<HTMLInputElement>(null)
  const scaleRef = useRef<HTMLInputElement>(null)
  const replaceRef = useRef<HTMLInputElement>(null)
  const replaceTarget = useRef<CargoEvidenceFile | null>(null)
  const previewUrls = useRef<Record<number, string>>({})
  const viewUrlRef = useRef("")

  const base = `/api/${kind}/${itemId}/files`

  const load = useCallback(async () => {
    const params = canRestore ? "?include_deleted=true" : ""
    const response = await api(`${base}${params}`)
    if (!response.ok) {
      setError("Could not load files")
      return
    }
    const body = (await response.json()) as { items: CargoEvidenceFile[] }
    setFiles(body.items)
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

  async function uploadList(list: FileList | null, fileKind: FileKind) {
    if (!list?.length || disabled) return
    setBusy(true)
    setError("")
    const active = files.filter((item) => !item.deleted_at && item.kind === fileKind)
    const form = new FormData()
    Array.from(list).forEach((file, index) => {
      form.append("files", file)
      form.append("kinds", fileKind)
      form.append("labels", `${fileKind === "papers" ? "Papers" : "Scale"} ${active.length + index + 1}`)
    })
    const response = await api(base, { method: "POST", body: form })
    setBusy(false)
    if (!response.ok) {
      setError((await readError(response)).message || "Upload failed")
      return
    }
    await load()
    onChanged?.()
  }

  async function removeFile(file: CargoEvidenceFile) {
    if (!window.confirm(`Remove ${file.label || file.file_name}?`)) return
    setBusy(true)
    setError("")
    const response = await api(`${base}/${file.id}`, { method: "DELETE" })
    setBusy(false)
    if (!response.ok) {
      setError((await readError(response)).message || "Delete failed")
      return
    }
    if (viewing?.id === file.id) setViewing(null)
    await load()
    onChanged?.()
  }

  async function restoreFile(file: CargoEvidenceFile) {
    setBusy(true)
    setError("")
    const response = await api(`${base}/${file.id}/restore`, { method: "POST" })
    setBusy(false)
    if (!response.ok) {
      setError((await readError(response)).message || "Restore failed")
      return
    }
    await load()
    onChanged?.()
  }

  async function replaceFile(file: CargoEvidenceFile, next: File | null) {
    if (!next || disabled) return
    setBusy(true)
    setError("")
    const form = new FormData()
    form.append("file", next)
    const response = await api(`${base}/${file.id}/replace`, { method: "POST", body: form })
    setBusy(false)
    if (!response.ok) {
      setError((await readError(response)).message || "Reupload failed")
      return
    }
    if (viewing?.id === file.id) setViewing(null)
    await load()
    onChanged?.()
  }

  function startReplace(file: CargoEvidenceFile) {
    replaceTarget.current = file
    replaceRef.current?.click()
  }

  const papers = files.filter((file) => file.kind === "papers" && !file.deleted_at)
  const scales = files.filter((file) => file.kind === "scale" && !file.deleted_at)
  const notes = files.filter((file) => file.kind === "note" && !file.deleted_at)
  const deleted = files.filter((file) => file.deleted_at)
  const active = section === "papers" ? papers : scales

  return (
    <div className="container-loading">
      <p className="muted">
        Upload multiple Papers and Scale files. View, remove, or reupload (replaces the old file in one step).
      </p>
      {error ? <div className="banner err">{error}</div> : null}

      <div className="tabs">
        <button type="button" className={section === "papers" ? "on" : ""} onClick={() => setSection("papers")}>
          Papers ({papers.length})
        </button>
        <button type="button" className={section === "scale" ? "on" : ""} onClick={() => setSection("scale")}>
          Scale ({scales.length})
        </button>
      </div>

      <div className="container-loading-actions">
        <button
          className="btn"
          type="button"
          disabled={disabled || busy}
          onClick={() => (section === "papers" ? papersRef : scaleRef).current?.click()}
        >
          Upload {section === "papers" ? "papers" : "scale"}
        </button>
        <input
          ref={papersRef}
          type="file"
          accept="image/*,application/pdf,.pdf"
          multiple
          hidden
          onChange={(event) => {
            void uploadList(event.target.files, "papers")
            event.target.value = ""
          }}
        />
        <input
          ref={scaleRef}
          type="file"
          accept="image/*,application/pdf,.pdf"
          multiple
          hidden
          onChange={(event) => {
            void uploadList(event.target.files, "scale")
            event.target.value = ""
          }}
        />
        <input
          ref={replaceRef}
          type="file"
          accept="image/*,application/pdf,.pdf"
          hidden
          onChange={(event) => {
            const target = replaceTarget.current
            const file = event.target.files?.[0] || null
            event.target.value = ""
            replaceTarget.current = null
            if (target) void replaceFile(target, file)
          }}
        />
      </div>

      {!active.length ? (
        <p className="muted">No {section} files yet.</p>
      ) : null}

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
                <>
                  <button className="btn-quiet" type="button" disabled={busy} onClick={() => startReplace(file)}>
                    Reupload
                  </button>
                  <button className="btn-danger" type="button" disabled={busy} onClick={() => void removeFile(file)}>
                    Remove
                  </button>
                </>
              ) : null}
            </div>
          </figure>
        ))}
      </div>

      {notes.length ? (
        <div className="container-loading-deleted">
          <h3>Other notes (intake / DL)</h3>
          <div className="thumbs">
            {notes.map((file) => (
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
                    <>
                      <button className="btn-quiet" type="button" disabled={busy} onClick={() => startReplace(file)}>
                        Reupload
                      </button>
                      <button className="btn-danger" type="button" disabled={busy} onClick={() => void removeFile(file)}>
                        Remove
                      </button>
                    </>
                  ) : null}
                </div>
              </figure>
            ))}
          </div>
        </div>
      ) : null}

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
                <figcaption>{file.label || file.file_name} · {file.kind}</figcaption>
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
            {viewUrl ? (
              viewing.is_image ? (
                <img src={viewUrl} alt={viewing.file_name} />
              ) : (
                <iframe title={viewing.file_name} src={viewUrl} />
              )
            ) : (
              <p className="muted">Loading…</p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  )
}
