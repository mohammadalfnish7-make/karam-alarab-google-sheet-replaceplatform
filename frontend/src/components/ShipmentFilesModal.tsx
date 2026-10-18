import { useEffect, useMemo, useState } from "react"
import { api, readError } from "../api"

export type CargoFileMeta = {
  id: number
  kind: "note" | "scale" | string
  label: string
  file_name: string
  mime: string
  sha256: string
  byte_size: number
  extracted: Record<string, unknown> | null
  created_at: string | null
  is_image: boolean
  is_pdf: boolean
}

type FileTab = "dl" | "delivery_note" | "scale"

type Props = {
  kind: "sea" | "air"
  itemId: number
  shipmentNumber: string | null
  companyName: string | null
  customerCode: string | null
  onClose: () => void
}

const TABS: Array<{ id: FileTab; label: string }> = [
  { id: "dl", label: "DL" },
  { id: "delivery_note", label: "Delivery note" },
  { id: "scale", label: "Scale" },
]

function isDlNote(file: CargoFileMeta) {
  if (file.kind !== "note") return false
  return /^delivery\s*note$/i.test(file.label.trim())
}

function isIntakeNote(file: CargoFileMeta) {
  return file.kind === "note" && !isDlNote(file)
}

function tabFiles(files: CargoFileMeta[], tab: FileTab) {
  if (tab === "dl") return files.filter(isDlNote)
  if (tab === "delivery_note") return files.filter(isIntakeNote)
  return files.filter((file) => file.kind === "scale")
}

function defaultTab(files: CargoFileMeta[]): FileTab {
  for (const tab of TABS) {
    if (tabFiles(files, tab.id).length) return tab.id
  }
  return "dl"
}

function extractedSummary(extracted: Record<string, unknown> | null): string {
  if (!extracted) return ""
  const parts: string[] = []
  if (extracted.cartons != null) parts.push(`${extracted.cartons} CTN`)
  if (extracted.mark != null) parts.push(`TL${extracted.mark}`)
  if (extracted.total_weight_kg != null) parts.push(`TW ${extracted.total_weight_kg}`)
  if (extracted.scale_weight_kg != null) parts.push(`scale ${extracted.scale_weight_kg}`)
  if (extracted.company_name != null) parts.push(String(extracted.company_name))
  return parts.join(" · ")
}

export function ShipmentFilesModal({
  kind,
  itemId,
  shipmentNumber,
  companyName,
  customerCode,
  onClose,
}: Props) {
  const [files, setFiles] = useState<CargoFileMeta[]>([])
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<FileTab>("dl")
  const [activeId, setActiveId] = useState<number | null>(null)
  const [loadedIds, setLoadedIds] = useState<Set<number>>(() => new Set())
  const [previewUrl, setPreviewUrl] = useState("")

  const visibleFiles = useMemo(() => tabFiles(files, tab), [files, tab])
  const active = visibleFiles.find((file) => file.id === activeId) || null
  const counts = useMemo(
    () => ({
      dl: tabFiles(files, "dl").length,
      delivery_note: tabFiles(files, "delivery_note").length,
      scale: tabFiles(files, "scale").length,
    }),
    [files],
  )

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault()
        onClose()
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError("")
    void api(`/api/${kind}/${itemId}/files`)
      .then(async (response) => {
        if (!response.ok) {
          const body = await readError(response)
          throw new Error(body.message || "Could not load files")
        }
        return response.json()
      })
      .then((payload) => {
        if (cancelled) return
        const items = (payload.items || []) as CargoFileMeta[]
        setFiles(items)
        setTab(defaultTab(items))
        setActiveId(null)
      })
      .catch((reason: Error) => {
        if (!cancelled) setError(reason.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [kind, itemId])

  useEffect(() => {
    if (activeId != null && !visibleFiles.some((file) => file.id === activeId)) {
      setActiveId(null)
    }
  }, [visibleFiles, activeId])

  useEffect(() => {
    if (activeId == null) {
      setPreviewUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev)
        return ""
      })
      return
    }
    let objectUrl = ""
    let cancelled = false
    void api(`/api/${kind}/${itemId}/files/${activeId}`)
      .then(async (response) => {
        if (!response.ok) {
          const body = await readError(response)
          throw new Error(body.message || "Could not open file")
        }
        return response.blob()
      })
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setPreviewUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev)
          return objectUrl
        })
        setLoadedIds((current) => new Set(current).add(activeId))
      })
      .catch((reason: Error) => {
        if (!cancelled) setError(reason.message)
      })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [kind, itemId, activeId])

  async function download(file: CargoFileMeta) {
    setError("")
    const response = await api(`/api/${kind}/${itemId}/files/${file.id}/download`)
    if (!response.ok) {
      const body = await readError(response)
      setError(body.message || "Could not download file")
      return
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = file.file_name
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  function switchTab(next: FileTab) {
    setTab(next)
    setActiveId(null)
    setError("")
  }

  return (
    <div
      className="sf-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label={`Files for ${shipmentNumber || itemId}`}
      onClick={onClose}
    >
      <div className="sf-modal" onClick={(event) => event.stopPropagation()}>
        <header className="sf-modal-head">
          <div>
            <p className="sf-kicker">Evidence · split inspector</p>
            <h2>{shipmentNumber || `Row ${itemId}`}</h2>
            <p className="muted" style={{ margin: 0 }}>
              {customerCode ? `TL${customerCode}` : "—"}
              {companyName ? ` · ${companyName}` : ""}
              {" · "}{files.length} file{files.length === 1 ? "" : "s"}
              {" · "}Esc to close
            </p>
          </div>
          <button className="btn-quiet sf-modal-close" type="button" onClick={onClose}>
            Close
          </button>
        </header>

        {!loading ? (
          <div className="sf-tabs" role="tablist" aria-label="File type">
            {TABS.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={tab === item.id}
                className={`sf-tab${tab === item.id ? " active" : ""}`}
                onClick={() => switchTab(item.id)}
              >
                {item.label}
                <span className="sf-tab-count">{counts[item.id]}</span>
              </button>
            ))}
          </div>
        ) : null}

        {error ? <div className="banner err sf-modal-error">{error}</div> : null}
        {loading ? <p className="muted sf-modal-loading">Loading files…</p> : null}

        {!loading ? (
          <div className="sf-split">
            <div className="sf-split-list" role="listbox" aria-label={`${TABS.find((item) => item.id === tab)?.label} files`}>
              {!visibleFiles.length ? (
                <p className="muted" style={{ margin: 8 }}>
                  No {TABS.find((item) => item.id === tab)?.label.toLowerCase()} files.
                </p>
              ) : null}
              {visibleFiles.map((file) => {
                const selected = activeId === file.id
                return (
                  <button
                    key={file.id}
                    type="button"
                    role="option"
                    aria-selected={selected}
                    className={`sf-split-item${selected ? " active" : ""}`}
                    onClick={() => { setError(""); setActiveId(file.id) }}
                  >
                    <span className={`sf-mime ${file.is_pdf ? "sf-mime-pdf" : "sf-mime-image"}`}>
                      {file.is_pdf ? "PDF" : "IMG"}
                    </span>
                    <span className="sf-split-text">
                      <strong>{file.label}</strong>
                      <span className="muted">{extractedSummary(file.extracted) || file.file_name}</span>
                    </span>
                    {loadedIds.has(file.id) ? <span className="sf-chip-ok">Loaded</span> : null}
                  </button>
                )
              })}
            </div>
            <div className="sf-split-preview">
              {active && previewUrl ? (
                <>
                  <div className="sf-preview-toolbar">
                    <span className="sf-preview-title">{active.label} · {active.file_name}</span>
                    <button className="btn-quiet sf-download" type="button" onClick={() => void download(active)}>
                      Download
                    </button>
                  </div>
                  <div className="sf-preview-media">
                    {active.is_image ? (
                      <img src={previewUrl} alt={active.file_name} />
                    ) : (
                      <iframe title={active.file_name} src={previewUrl} className="sf-pdf" />
                    )}
                  </div>
                </>
              ) : (
                <div className="sf-preview-empty">
                  {visibleFiles.length
                    ? "Select a file on the left to preview. Download from the toolbar. Esc closes."
                    : "No files in this tab."}
                </div>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
