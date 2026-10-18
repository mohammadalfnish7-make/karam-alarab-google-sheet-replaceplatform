import type { ReactNode } from "react"
import { Link } from "react-router-dom"
import {
  DEMO_MESSAGE,
  DEMO_PHOTOS,
  compareNumber,
  sumCartons,
  sumHand,
  sumNoteCartons,
  sumScale,
  type CheckTone,
  DEMO_NOTES,
} from "./mockData"
import "./demos.css"

export function DemoShell({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <main className="page demo-intake">
      <div className="page-head">
        <div>
          <p className="demo-kicker"><Link to="/demo/intake">Intake UI demos</Link></p>
          <h1>{title}</h1>
        </div>
        <div className="page-actions">
          <Link className="btn-quiet" to="/demo/intake">All demos</Link>
        </div>
      </div>
      <p className="muted demo-scenario">
        Mock shipment <strong>D1247 / TL5523</strong> — French Avenue · {DEMO_NOTES.length} delivery notes ·{" "}
        {DEMO_PHOTOS.length} scale photos · cartons {DEMO_MESSAGE.cartons}. No API calls.
      </p>
      {children}
    </main>
  )
}

export function StatusChip({ tone, children }: { tone: CheckTone; children: ReactNode }) {
  return <span className={`demo-chip demo-chip-${tone}`}>{children}</span>
}

export function TotalsScoreboard() {
  const noteCartons = sumNoteCartons(DEMO_NOTES)
  const photoCartons = sumCartons(DEMO_PHOTOS)
  const scaleSum = sumScale(DEMO_PHOTOS)
  const handSum = sumHand(DEMO_PHOTOS)
  const rows: Array<{ label: string; summed: number; message: number; unit?: string }> = [
    { label: "Note cartons", summed: noteCartons, message: DEMO_MESSAGE.cartons },
    { label: "Photo cartons", summed: photoCartons, message: DEMO_MESSAGE.cartons },
    { label: "Scale kg sum", summed: scaleSum, message: DEMO_MESSAGE.total_weight_kg, unit: "kg" },
    { label: "Hand TW sum", summed: handSum, message: DEMO_MESSAGE.total_weight_kg, unit: "kg" },
  ]
  return (
    <section className="demo-scoreboard">
      <h2>Totals vs message</h2>
      <div className="demo-score-grid">
        {rows.map((row) => {
          const tone = compareNumber(row.summed, row.message)
          const delta = Math.round(Math.abs(row.summed - row.message) * 1000) / 1000
          return (
            <article key={row.label} className={`demo-score demo-score-${tone}`}>
              <span className="demo-score-label">{row.label}</span>
              <strong>
                {row.summed}
                {row.unit ? ` ${row.unit}` : ""}
              </strong>
              <span className="muted">
                message {row.message}
                {row.unit ? ` ${row.unit}` : ""}
                {delta ? ` · Δ ${delta}` : ""}
              </span>
              <StatusChip tone={tone}>
                {tone === "ok" ? "Match" : tone === "warn" ? "Within 1 kg" : "Mismatch"}
              </StatusChip>
            </article>
          )
        })}
      </div>
    </section>
  )
}

export function MessageSummary() {
  const m = DEMO_MESSAGE
  return (
    <dl className="demo-message-grid">
      <div><dt>Shipment</dt><dd>{m.shipment_number}</dd></div>
      <div><dt>Date</dt><dd>{m.date_received}</dd></div>
      <div><dt>TL mark</dt><dd>{m.customer_code}</dd></div>
      <div><dt>Shop</dt><dd>{m.company_name}</dd></div>
      <div><dt>Cartons</dt><dd>{m.cartons}</dd></div>
      <div><dt>TW / PW / NW</dt><dd>{m.total_weight_kg} / {m.pallet_weight_kg} / {m.net_weight_kg} kg</dd></div>
    </dl>
  )
}
