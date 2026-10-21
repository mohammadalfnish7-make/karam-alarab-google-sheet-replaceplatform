import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { api } from "../api"

type Actor = {
  id: string
  label: string
  kind: string
  summary: string
}

type DataType = {
  id: string
  label: string
  route: string | null
  fields: string[]
  evidence: string[]
  record_count?: number | null
}

type Process = {
  id: string
  label: string
  summary: string
  steps: string[]
}

type FillEdge = { actor_id: string; data_id: string; relation: string }
type ProcessUse = { process_id: string; data_id: string }
type Share = { from: string; to: string; via: string; note: string }

type LiveFill = {
  data_id: string
  label: string
  actions: Record<string, number>
  total: number
}

type LiveActor = {
  id: string
  user_id: number | null
  email: string
  role: string
  fills: LiveFill[]
  last_at: string | null
}

type LiveEntity = {
  data_id: string
  label: string
  creates: number
  updates: number
  deletes: number
  other: number
  unique_actors: number
}

type GraphPayload = {
  actors: Actor[]
  data_types: DataType[]
  processes: Process[]
  fills: FillEdge[]
  process_uses: ProcessUse[]
  shares: Share[]
  live: { by_actor: LiveActor[]; by_entity: LiveEntity[] }
  record_counts: Record<string, number>
}

type Selection =
  | { kind: "actor"; id: string }
  | { kind: "data"; id: string }
  | { kind: "process"; id: string }
  | { kind: "live"; id: string }
  | null

export function GraphKnowledgePage() {
  const [data, setData] = useState<GraphPayload | null>(null)
  const [error, setError] = useState("")
  const [selection, setSelection] = useState<Selection>(null)
  const [view, setView] = useState<"map" | "live">("map")

  useEffect(() => {
    void api("/api/knowledge-graph").then(async (response) => {
      if (!response.ok) {
        setError("Could not load knowledge graph")
        return
      }
      setData((await response.json()) as GraphPayload)
      setError("")
    })
  }, [])

  const detail = useMemo(() => {
    if (!data || !selection) return null
    if (selection.kind === "actor") {
      const actor = data.actors.find((item) => item.id === selection.id)
      if (!actor) return null
      const fills = data.fills.filter((edge) => edge.actor_id === actor.id)
      return {
        title: actor.label,
        subtitle: actor.kind,
        body: actor.summary,
        rows: fills.map((edge) => {
          const dt = data.data_types.find((item) => item.id === edge.data_id)
          return {
            key: edge.data_id,
            label: dt?.label || edge.data_id,
            meta: edge.relation,
            href: dt?.route || null,
          }
        }),
      }
    }
    if (selection.kind === "data") {
      const dt = data.data_types.find((item) => item.id === selection.id)
      if (!dt) return null
      const filledBy = data.fills.filter((edge) => edge.data_id === dt.id)
      const processes = data.process_uses.filter((edge) => edge.data_id === dt.id)
      const shares = data.shares.filter((edge) => edge.from === dt.id || edge.to === dt.id)
      return {
        title: dt.label,
        subtitle: dt.record_count != null ? `${dt.record_count} active rows` : "data type",
        body: `Fields: ${dt.fields.join(", ")}${dt.evidence.length ? `. Evidence: ${dt.evidence.join(", ")}` : ""}`,
        rows: [
          ...filledBy.map((edge) => {
            const actor = data.actors.find((item) => item.id === edge.actor_id)
            return {
              key: `a-${edge.actor_id}`,
              label: actor?.label || edge.actor_id,
              meta: edge.relation,
              href: null as string | null,
            }
          }),
          ...processes.map((edge) => {
            const process = data.processes.find((item) => item.id === edge.process_id)
            return {
              key: `p-${edge.process_id}`,
              label: process?.label || edge.process_id,
              meta: "process uses this data",
              href: null as string | null,
            }
          }),
          ...shares.map((edge) => ({
            key: `s-${edge.from}-${edge.to}`,
            label: `${edge.from === dt.id ? "→" : "←"} ${edge.from === dt.id ? edge.to : edge.from}`,
            meta: `${edge.via} — ${edge.note}`,
            href: null as string | null,
          })),
        ],
      }
    }
    if (selection.kind === "process") {
      const process = data.processes.find((item) => item.id === selection.id)
      if (!process) return null
      const uses = data.process_uses.filter((edge) => edge.process_id === process.id)
      return {
        title: process.label,
        subtitle: "process",
        body: process.summary,
        rows: [
          ...process.steps.map((step, index) => ({
            key: `step-${index}`,
            label: step,
            meta: `step ${index + 1}`,
            href: null as string | null,
          })),
          ...uses.map((edge) => {
            const dt = data.data_types.find((item) => item.id === edge.data_id)
            return {
              key: edge.data_id,
              label: dt?.label || edge.data_id,
              meta: "data involved",
              href: dt?.route || null,
            }
          }),
        ],
      }
    }
    if (selection.kind === "live") {
      const actor = data.live.by_actor.find((item) => item.id === selection.id)
      if (!actor) return null
      return {
        title: actor.email,
        subtitle: `${actor.role}${actor.last_at ? ` · last ${actor.last_at.slice(0, 16).replace("T", " ")}` : ""}`,
        body: "What this login has actually written (from audit log).",
        rows: actor.fills.map((fill) => {
          const dt = data.data_types.find((item) => item.id === fill.data_id)
          const actions = Object.entries(fill.actions)
            .map(([name, count]) => `${name} ${count}`)
            .join(", ")
          return {
            key: fill.data_id,
            label: fill.label,
            meta: `${fill.total} events · ${actions}`,
            href: dt?.route || null,
          }
        }),
      }
    }
    return null
  }, [data, selection])

  return (
    <main className="page gk-page">
      <div className="page-head">
        <h1>Graph knowledge</h1>
        <div className="tabs">
          <button type="button" className={view === "map" ? "on" : ""} onClick={() => setView("map")}>
            Map
          </button>
          <button type="button" className={view === "live" ? "on" : ""} onClick={() => setView("live")}>
            Who fills what
          </button>
        </div>
      </div>
      <p className="muted gk-intro">
        Bird&apos;s-eye view of actors, the data they fill, shared handoffs, and the ops process —
        so you can decide where to simplify or automate next.
      </p>
      {error ? <div className="banner err">{error}</div> : null}
      {!data && !error ? <p className="muted">Loading…</p> : null}

      {data && view === "map" ? (
        <div className="gk-layout">
          <div className="gk-map">
            <section className="gk-lane">
              <h2>Actors</h2>
              <div className="gk-nodes">
                {data.actors.map((actor) => (
                  <button
                    key={actor.id}
                    type="button"
                    className={`gk-node actor ${actor.kind} ${selection?.kind === "actor" && selection.id === actor.id ? "on" : ""}`}
                    onClick={() => setSelection({ kind: "actor", id: actor.id })}
                  >
                    <strong>{actor.label}</strong>
                    <span>{actor.kind}</span>
                  </button>
                ))}
              </div>
            </section>

            <section className="gk-lane">
              <h2>Process</h2>
              <div className="gk-process-flow">
                {data.processes.map((process, index) => (
                  <button
                    key={process.id}
                    type="button"
                    className={`gk-node process ${selection?.kind === "process" && selection.id === process.id ? "on" : ""}`}
                    onClick={() => setSelection({ kind: "process", id: process.id })}
                  >
                    <strong>{process.label}</strong>
                    <span>{process.steps.length} steps</span>
                    {index < data.processes.length - 1 ? <em className="gk-arrow" aria-hidden>→</em> : null}
                  </button>
                ))}
              </div>
            </section>

            <section className="gk-lane">
              <h2>Data types</h2>
              <div className="gk-nodes data-grid">
                {data.data_types.map((dt) => {
                  const hot =
                    selection?.kind === "actor" &&
                    data.fills.some((edge) => edge.actor_id === selection.id && edge.data_id === dt.id)
                  const inProcess =
                    selection?.kind === "process" &&
                    data.process_uses.some((edge) => edge.process_id === selection.id && edge.data_id === dt.id)
                  return (
                    <button
                      key={dt.id}
                      type="button"
                      className={`gk-node data ${selection?.kind === "data" && selection.id === dt.id ? "on" : ""} ${hot || inProcess ? "linked" : ""}`}
                      onClick={() => setSelection({ kind: "data", id: dt.id })}
                    >
                      <strong>{dt.label}</strong>
                      <span>{dt.record_count ?? "—"} rows</span>
                    </button>
                  )
                })}
              </div>
            </section>

            <section className="gk-lane">
              <h2>Shared handoffs</h2>
              <ul className="gk-shares">
                {data.shares.map((share) => (
                  <li key={`${share.from}-${share.to}`}>
                    <button type="button" className="btn-quiet" onClick={() => setSelection({ kind: "data", id: share.from })}>
                      {data.data_types.find((item) => item.id === share.from)?.label || share.from}
                    </button>
                    <span className="muted">→ {share.via} →</span>
                    <button type="button" className="btn-quiet" onClick={() => setSelection({ kind: "data", id: share.to })}>
                      {data.data_types.find((item) => item.id === share.to)?.label || share.to}
                    </button>
                    <span className="muted gk-share-note">{share.note}</span>
                  </li>
                ))}
              </ul>
            </section>
          </div>

          <aside className="gk-detail panel">
            {detail ? (
              <>
                <h2>{detail.title}</h2>
                <p className="muted">{detail.subtitle}</p>
                <p>{detail.body}</p>
                <ul className="gk-detail-list">
                  {detail.rows.map((row) => (
                    <li key={row.key}>
                      <div>
                        <strong>{row.label}</strong>
                        <span className="muted">{row.meta}</span>
                      </div>
                      {row.href ? <Link to={row.href}>Open</Link> : null}
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <>
                <h2>Select a node</h2>
                <p className="muted">
                  Click an actor to see what they fill, a process for the workflow steps, or a data type for fields and handoffs.
                </p>
              </>
            )}
          </aside>
        </div>
      ) : null}

      {data && view === "live" ? (
        <div className="gk-layout">
          <div className="gk-map">
            <section className="gk-lane">
              <h2>People (from audit)</h2>
              {!data.live.by_actor.length ? (
                <p className="muted">No audit events yet — create or edit records to populate this.</p>
              ) : (
                <div className="table-wrap gk-live-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Actor</th>
                        <th>Role</th>
                        <th>Top data</th>
                        <th>Events</th>
                        <th>Last</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.live.by_actor.map((actor) => {
                        const total = actor.fills.reduce((sum, fill) => sum + fill.total, 0)
                        const top = actor.fills.slice(0, 3).map((fill) => fill.label).join(", ")
                        return (
                          <tr
                            key={actor.id}
                            className={selection?.kind === "live" && selection.id === actor.id ? "clickable active" : "clickable"}
                            onClick={() => setSelection({ kind: "live", id: actor.id })}
                          >
                            <td>{actor.email}</td>
                            <td>{actor.role}</td>
                            <td className="clip">{top || "—"}</td>
                            <td>{total}</td>
                            <td>{actor.last_at ? actor.last_at.slice(0, 16).replace("T", " ") : ""}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="gk-lane">
              <h2>Data types (audit volume)</h2>
              <div className="table-wrap gk-live-table">
                <table>
                  <thead>
                    <tr>
                      <th>Data</th>
                      <th>Creates</th>
                      <th>Updates</th>
                      <th>Deletes</th>
                      <th>Actors</th>
                      <th>Rows now</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.live.by_entity.map((entity) => (
                      <tr
                        key={entity.data_id}
                        className="clickable"
                        onClick={() => setSelection({ kind: "data", id: entity.data_id })}
                      >
                        <td>{entity.label}</td>
                        <td>{entity.creates}</td>
                        <td>{entity.updates}</td>
                        <td>{entity.deletes}</td>
                        <td>{entity.unique_actors}</td>
                        <td>{data.record_counts[entity.data_id] ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>

          <aside className="gk-detail panel">
            {detail ? (
              <>
                <h2>{detail.title}</h2>
                <p className="muted">{detail.subtitle}</p>
                <p>{detail.body}</p>
                <ul className="gk-detail-list">
                  {detail.rows.map((row) => (
                    <li key={row.key}>
                      <div>
                        <strong>{row.label}</strong>
                        <span className="muted">{row.meta}</span>
                      </div>
                      {row.href ? <Link to={row.href}>Open</Link> : null}
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <>
                <h2>Pick a person or data type</h2>
                <p className="muted">Live numbers come from the audit log — useful to see who actually owns which screens.</p>
              </>
            )}
          </aside>
        </div>
      ) : null}
    </main>
  )
}
