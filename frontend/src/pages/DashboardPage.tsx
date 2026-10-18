import { useEffect, useState } from "react"
import { Link, Navigate } from "react-router-dom"
import { api } from "../api"
import { useAuth } from "../auth"
import type { Breakdown, Dashboard, SheetSummary } from "../types"

const SHEETS: { key: keyof Dashboard; title: string; href: string; progress: string }[] = [
  { key: "sea", title: "Sea goods", href: "/sea", progress: "Stage" },
  { key: "air", title: "Air shipment", href: "/air", progress: "Status" },
  { key: "exit", title: "Exit tracker", href: "/exit", progress: "Status" },
]

function Bars({ items }: { items: Breakdown[] }) {
  const peak = Math.max(1, ...items.map((item) => item.count))
  const shown = items.filter((item) => item.count > 0)
  if (!shown.length) return <p className="muted">No rows yet</p>
  return (
    <ul className="bars">
      {shown.map((item) => (
        <li key={item.label}>
          <span>{item.label}</span>
          <span className="bar-track">
            <span className="bar-fill" style={{ width: `${Math.max(4, (item.count / peak) * 100)}%` }} />
          </span>
          <strong>{item.count}</strong>
        </li>
      ))}
    </ul>
  )
}

function Card({ title, href, progress, summary }: { title: string; href: string; progress: string; summary: SheetSummary }) {
  return (
    <section className="panel summary-card">
      <div className="file-head">
        <h2>{title}</h2>
        <Link to={href}>Open</Link>
      </div>
      <p className="summary-count">{summary.rows}</p>
      <p className="muted">{summary.cartons} cartons · {summary.needs_review} need review</p>
      <h3>{progress}</h3>
      <Bars items={summary.breakdown} />
    </section>
  )
}

export function DashboardPage() {
  const { user } = useAuth()
  const [data, setData] = useState<Dashboard | null>(null)
  const [error, setError] = useState("")

  useEffect(() => {
    api("/api/dashboard").then(async (response) => {
      if (!response.ok) {
        setError("Could not load the dashboard")
        return
      }
      setData((await response.json()) as Dashboard)
      setError("")
    })
  }, [])

  if (user && user.role !== "admin") return <Navigate to="/sea" replace />

  return (
    <main className="page">
      <div className="page-head">
        <h1>Dashboard</h1>
        <Link className="btn" to="/tracker">Shipment tracker</Link>
      </div>
      {error ? <div className="banner err">{error}</div> : null}
      {data ? (
        <div className="summary-grid">
          {SHEETS.map((sheet) => (
            <Card key={sheet.key} title={sheet.title} href={sheet.href} progress={sheet.progress} summary={data[sheet.key]} />
          ))}
        </div>
      ) : error ? null : <p className="muted">Loading…</p>}
    </main>
  )
}
