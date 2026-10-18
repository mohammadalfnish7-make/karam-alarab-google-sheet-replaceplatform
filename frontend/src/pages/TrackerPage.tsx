import { FormEvent, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { api } from "../api"
import { Flags, Pager } from "../ui"
import type { Enums, Page, Shipment } from "../types"

export function TrackerPage() {
  const [rows, setRows] = useState<Shipment[]>([])
  const [total, setTotal] = useState(0)
  const [enums, setEnums] = useState<Enums | null>(null)
  const [draftQ, setDraftQ] = useState("")
  const [q, setQ] = useState("")
  const [kind, setKind] = useState("")
  const [progress, setProgress] = useState("")
  const [review, setReview] = useState("")
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState("")
  const limit = 50

  useEffect(() => {
    api("/api/lookups/enums").then(async (response) => {
      if (response.ok) setEnums(await response.json())
    })
  }, [])

  useEffect(() => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
    if (q) params.set("q", q)
    if (kind) params.set("kind", kind)
    if (progress) params.set("progress", progress)
    if (review) params.set("needs_review", review)
    api(`/api/shipments?${params}`).then(async (response) => {
      if (!response.ok) {
        setError("Could not load shipments")
        return
      }
      const body = (await response.json()) as Page<Shipment>
      setRows(body.items)
      setTotal(body.total)
      setError("")
    })
  }, [q, kind, progress, review, offset])

  const progressOptions = kind === "air"
    ? enums?.air_statuses ?? []
    : kind === "sea"
      ? enums?.stages ?? []
      : [...(enums?.stages ?? []), ...(enums?.air_statuses ?? []).filter((item) => !(enums?.stages ?? []).includes(item))]

  function search(event: FormEvent) {
    event.preventDefault()
    setOffset(0)
    setQ(draftQ.trim())
  }

  return (
    <main className="page">
      <div className="page-head">
        <h1>Shipment tracker</h1>
      </div>
      <form className="toolbar" onSubmit={search}>
        <input type="search" placeholder="Search shipment, system, company…" value={draftQ} onChange={(event) => setDraftQ(event.target.value)} />
        <button className="btn-quiet" type="submit">Search</button>
        <select value={kind} onChange={(event) => { setOffset(0); setKind(event.target.value); setProgress("") }}>
          <option value="">Sea and air</option>
          <option value="sea">Sea</option>
          <option value="air">Air</option>
        </select>
        <select value={progress} onChange={(event) => { setOffset(0); setProgress(event.target.value) }}>
          <option value="">{kind === "air" ? "All statuses" : kind === "sea" ? "All stages" : "All stages and statuses"}</option>
          {progressOptions.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <select value={review} onChange={(event) => { setOffset(0); setReview(event.target.value) }}>
          <option value="">All rows</option>
          <option value="true">Needs review</option>
          <option value="false">No review flag</option>
        </select>
      </form>
      {error ? <div className="banner err">{error}</div> : null}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Kind</th>
              <th>Date</th>
              <th>Shipment</th>
              <th>System</th>
              <th>Company</th>
              <th>Customer</th>
              <th>Cartons</th>
              <th>Route</th>
              <th>Stage / status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.kind}-${row.id}`}>
                <td>{row.kind === "sea" ? "Sea" : "Air"}</td>
                <td>{row.date_received ?? ""}</td>
                <td>{row.shipment_number ?? ""}</td>
                <td>{row.system_code ?? ""}</td>
                <td className="clip">{row.company_name ?? ""}</td>
                <td>{row.customer_code ?? ""}</td>
                <td>{row.cartons ?? ""}</td>
                <td>{row.shipping_route ?? ""}</td>
                <td>{row.progress ?? ""}</td>
                <td>
                  <Flags review={row.needs_review} />
                  <Link to={row.kind === "sea" ? "/sea" : "/air"}>Open</Link>
                </td>
              </tr>
            ))}
            {!rows.length ? <tr><td colSpan={10} className="muted">No shipments</td></tr> : null}
          </tbody>
        </table>
      </div>
      <Pager offset={offset} limit={limit} total={total} onPage={setOffset} />
    </main>
  )
}
