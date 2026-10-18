import { FormEvent, Fragment, useCallback, useEffect, useState } from "react"
import { api, readError } from "../api"
import { History } from "../ui"

type ExpiryStatus = "expired" | "urgent" | "soon" | "ok" | "unknown"
type Category = "company" | "employee" | "vehicle"

type ExpiryItem = {
  id: number
  category: Category
  sl_no: number | null
  title: string
  document_type: string | null
  document_no: string | null
  company_name: string | null
  holder_name: string | null
  plate_no: string | null
  expiry_date: string | null
  status: ExpiryStatus
  days_left: number | null
  status_label: string
}

type ExpiryPayload = {
  items: ExpiryItem[]
  summary: {
    total: number
    expired: number
    urgent: number
    soon: number
    ok: number
    unknown: number
  }
  as_of: string
}

const CATEGORIES: Array<{ id: Category | ""; label: string }> = [
  { id: "company", label: "Company docs" },
  { id: "employee", label: "Employee docs" },
  { id: "vehicle", label: "Vehicles" },
  { id: "", label: "All" },
]

const STATUSES: Array<{ id: ExpiryStatus | ""; label: string }> = [
  { id: "", label: "All statuses" },
  { id: "expired", label: "Expired" },
  { id: "urgent", label: "Urgent (≤30d)" },
  { id: "soon", label: "Soon (≤90d)" },
  { id: "ok", label: "OK" },
]

function detailFor(item: ExpiryItem) {
  if (item.category === "employee") {
    return [item.holder_name, item.document_type, item.company_name].filter(Boolean).join(" · ")
  }
  if (item.category === "vehicle") {
    return [item.document_type, item.plate_no ? `Plate ${item.plate_no}` : null].filter(Boolean).join(" · ")
  }
  return [item.company_name, item.document_no ? `No. ${item.document_no}` : null].filter(Boolean).join(" · ")
}

/** Match the workbook: day/month/year. */
function formatDmy(iso: string | null) {
  if (!iso) return ""
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  if (!match) return iso
  return `${Number(match[3])}/${Number(match[2])}/${match[1]}`
}

function ExpiryDateCell({
  item,
  onSaved,
  onError,
}: {
  item: ExpiryItem
  onSaved: (next: ExpiryItem) => void
  onError: (message: string) => void
}) {
  const [value, setValue] = useState(formatDmy(item.expiry_date))
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setValue(formatDmy(item.expiry_date))
  }, [item.expiry_date, item.id])

  async function save() {
    const next = value.trim()
    const current = formatDmy(item.expiry_date)
    if (next === current) return
    setSaving(true)
    onError("")
    const response = await api(`/api/expiry/${item.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expiry_date: next || null }),
    })
    setSaving(false)
    if (!response.ok) {
      const body = await readError(response)
      onError(body.message || body.field_errors?.expiry_date || "Could not save date")
      setValue(current)
      return
    }
    onSaved((await response.json()) as ExpiryItem)
  }

  return (
    <input
      className="cell-input expiry-date-input"
      type="text"
      inputMode="numeric"
      placeholder="DD/MM/YYYY"
      value={value}
      disabled={saving}
      onChange={(event) => setValue(event.target.value)}
      onBlur={() => void save()}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault()
          ;(event.target as HTMLInputElement).blur()
        }
      }}
      aria-label={`Expiry date for ${item.title}`}
    />
  )
}

export function ExpiryPage() {
  const [category, setCategory] = useState<Category | "">("company")
  const [status, setStatus] = useState<ExpiryStatus | "">("")
  const [data, setData] = useState<ExpiryPayload | null>(null)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [historyId, setHistoryId] = useState<number | null>(null)

  const load = useCallback(async () => {
    const params = new URLSearchParams()
    if (category) params.set("category", category)
    if (status) params.set("status", status)
    const query = params.toString()
    const response = await api(`/api/expiry${query ? `?${query}` : ""}`)
    if (!response.ok) {
      setError("Could not load expiry reminders")
      return
    }
    setData((await response.json()) as ExpiryPayload)
    setError("")
  }, [category, status])

  useEffect(() => {
    void load()
  }, [load])

  function onSaved(next: ExpiryItem) {
    setNotice(`Saved expiry for ${next.title}`)
    void load()
  }

  function onToolbarSubmit(event: FormEvent) {
    event.preventDefault()
  }

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Document expiry</h1>
          <p className="muted" style={{ margin: "4px 0 0" }}>
            Company, employee & vehicle reminders · edit dates as DD/MM/YYYY · as of {data?.as_of ?? "…"}
          </p>
        </div>
      </div>

      {data ? (
        <div className="expiry-summary">
          <article className="expiry-stat expiry-stat-expired">
            <span>Expired</span>
            <strong>{data.summary.expired}</strong>
          </article>
          <article className="expiry-stat expiry-stat-urgent">
            <span>Urgent ≤30d</span>
            <strong>{data.summary.urgent}</strong>
          </article>
          <article className="expiry-stat expiry-stat-soon">
            <span>Soon ≤90d</span>
            <strong>{data.summary.soon}</strong>
          </article>
          <article className="expiry-stat">
            <span>OK</span>
            <strong>{data.summary.ok}</strong>
          </article>
        </div>
      ) : null}

      <form className="toolbar" onSubmit={onToolbarSubmit}>
        <select value={category} onChange={(event) => setCategory(event.target.value as Category | "")}>
          {CATEGORIES.map((item) => (
            <option key={item.id || "all"} value={item.id}>{item.label}</option>
          ))}
        </select>
        <select value={status} onChange={(event) => setStatus(event.target.value as ExpiryStatus | "")}>
          {STATUSES.map((item) => (
            <option key={item.id || "all"} value={item.id}>{item.label}</option>
          ))}
        </select>
      </form>

      {error ? <div className="banner err">{error}</div> : null}
      {notice ? <div className="banner ok">{notice}</div> : null}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Document</th>
              <th>Details</th>
              <th>Doc no.</th>
              <th>Expiry</th>
              <th>Days</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {(data?.items || []).map((item) => (
              <Fragment key={item.id}>
                <tr className={`expiry-row expiry-row-${item.status}`}>
                  <td>
                    <span className={`expiry-chip expiry-chip-${item.status}`}>{item.status_label}</span>
                  </td>
                  <td><strong>{item.title}</strong></td>
                  <td className="clip">{detailFor(item)}</td>
                  <td>{item.document_no ?? "—"}</td>
                  <td>
                    <ExpiryDateCell item={item} onSaved={onSaved} onError={setError} />
                  </td>
                  <td>{item.days_left == null ? "—" : item.days_left}</td>
                  <td>
                    <button
                      className="btn-quiet"
                      type="button"
                      onClick={() => setHistoryId(historyId === item.id ? null : item.id)}
                    >
                      {historyId === item.id ? "Hide" : "History"}
                    </button>
                  </td>
                </tr>
                {historyId === item.id ? (
                  <tr className="expiry-history-row">
                    <td colSpan={7}>
                      <History path={`/api/expiry/${item.id}/history`} />
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            ))}
            {!data?.items.length ? (
              <tr>
                <td colSpan={7} className="muted">No documents match these filters.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </main>
  )
}
