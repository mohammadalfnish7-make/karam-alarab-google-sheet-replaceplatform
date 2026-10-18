import { useMemo, useState } from "react"
import {
  DEMO_NOTES,
  DEMO_PHOTOS,
  scaleVsHand,
  type CheckTone,
  type NoteExtract,
  type ScaleExtract,
} from "./mockData"
import { DemoShell, MessageSummary, StatusChip, TotalsScoreboard } from "./shared"

type Item =
  | { kind: "note"; data: NoteExtract }
  | { kind: "photo"; data: ScaleExtract }

export function IntakeDemoSideBySidePage() {
  const items = useMemo<Item[]>(
    () => [
      ...DEMO_NOTES.map((data) => ({ kind: "note" as const, data })),
      ...DEMO_PHOTOS.map((data) => ({ kind: "photo" as const, data })),
    ],
    [],
  )
  const [selectedId, setSelectedId] = useState(items[0]?.data.id || "")
  const selected = items.find((item) => item.data.id === selectedId) || items[0]

  return (
    <DemoShell title="Side-by-side review">
      <section className="panel" style={{ marginBottom: 12 }}>
        <h2 style={{ marginTop: 0, fontSize: 15 }}>Message</h2>
        <MessageSummary />
      </section>

      <div className="demo-split">
        <div>
          <div className="demo-stage">
            {selected ? <img src={selected.data.image} alt={selected.data.name} /> : null}
          </div>
          <div className="demo-thumbs">
            {items.map((item) => (
              <button
                key={item.data.id}
                type="button"
                className={`demo-thumb${item.data.id === selected?.data.id ? " active" : ""}`}
                onClick={() => setSelectedId(item.data.id)}
              >
                <img src={item.data.image} alt="" />
                <span className="demo-thumb-label">
                  {item.kind === "note" ? "Note" : "Scale"} {item.kind === "note"
                    ? DEMO_NOTES.findIndex((n) => n.id === item.data.id) + 1
                    : DEMO_PHOTOS.findIndex((p) => p.id === item.data.id) + 1}
                </span>
              </button>
            ))}
          </div>
        </div>

        <aside className="demo-fields">
          {selected?.kind === "note" ? <NoteFields note={selected.data} /> : null}
          {selected?.kind === "photo" ? <PhotoFields photo={selected.data} /> : null}
        </aside>
      </div>

      <TotalsScoreboard />
    </DemoShell>
  )
}

function NoteFields({ note }: { note: NoteExtract }) {
  const rows: Array<{ label: string; value: string; tone: CheckTone; chip: string }> = [
    { label: "Company", value: note.company_name, tone: "ok", chip: "Matches message shop" },
    { label: "Date", value: note.date, tone: "ok", chip: "Match" },
    { label: "Mark", value: note.mark, tone: "ok", chip: "TL5523" },
    { label: "Cartons", value: String(note.cartons), tone: "ok", chip: "Part of sum" },
    { label: "Goods", value: note.goods, tone: "empty", chip: "Info only" },
    { label: "Party", value: note.party, tone: "empty", chip: "Info only" },
  ]
  return (
    <>
      <h2>Extracted · delivery note</h2>
      <p className="muted" style={{ marginTop: 0 }}>{note.name}</p>
      <dl>
        {rows.map((row) => (
          <div className="demo-field-row" key={row.label}>
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
            <StatusChip tone={row.tone}>{row.chip}</StatusChip>
          </div>
        ))}
      </dl>
    </>
  )
}

function PhotoFields({ photo }: { photo: ScaleExtract }) {
  const vs = scaleVsHand(photo)
  const rows: Array<{ label: string; value: string; tone: CheckTone; chip: string }> = [
    { label: "Mark", value: photo.mark, tone: "ok", chip: "Match" },
    { label: "Cartons", value: String(photo.cartons), tone: "ok", chip: "Part of sum" },
    { label: "Hand TW", value: `${photo.total_weight_kg} kg`, tone: vs.tone, chip: vs.label },
    {
      label: "PW",
      value: photo.pallet_weight_kg == null ? "—" : `${photo.pallet_weight_kg} kg`,
      tone: "empty",
      chip: "Optional",
    },
    { label: "Scale kg", value: `${photo.scale_weight_kg} kg`, tone: vs.tone, chip: vs.label },
  ]
  return (
    <>
      <h2>Extracted · scale photo</h2>
      <p className="muted" style={{ marginTop: 0 }}>{photo.name}</p>
      <dl>
        {rows.map((row) => (
          <div className="demo-field-row" key={row.label}>
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
            <StatusChip tone={row.tone}>{row.chip}</StatusChip>
          </div>
        ))}
      </dl>
    </>
  )
}
