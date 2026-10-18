import { useState } from "react"
import {
  DEMO_NOTES,
  DEMO_PHOTOS,
  scaleVsHand,
  type NoteExtract,
  type ScaleExtract,
} from "./mockData"
import { DemoShell, MessageSummary, StatusChip, TotalsScoreboard } from "./shared"

type OpenItem =
  | { kind: "note"; data: NoteExtract }
  | { kind: "photo"; data: ScaleExtract }

export function IntakeDemoLightboxPage() {
  const [open, setOpen] = useState<OpenItem | null>(null)
  const [retryFlash, setRetryFlash] = useState("")

  return (
    <DemoShell title="Lightbox inspector">
      <section className="panel" style={{ marginBottom: 12 }}>
        <h2 style={{ marginTop: 0, fontSize: 15 }}>Message</h2>
        <MessageSummary />
      </section>

      <h2 style={{ fontSize: 15 }}>Delivery notes</h2>
      <div className="demo-list">
        {DEMO_NOTES.map((note) => (
          <button
            key={note.id}
            type="button"
            className="demo-list-item"
            onClick={() => { setRetryFlash(""); setOpen({ kind: "note", data: note }) }}
          >
            <img src={note.image} alt="" />
            <div>
              <strong>{note.name}</strong>
              <div className="muted">{note.mark} · {note.cartons} CTN · {note.company_name}</div>
            </div>
            <StatusChip tone="ok">Match</StatusChip>
          </button>
        ))}
      </div>

      <h2 style={{ fontSize: 15, marginTop: 20 }}>Scale photos</h2>
      <div className="demo-list">
        {DEMO_PHOTOS.map((photo) => {
          const vs = scaleVsHand(photo)
          return (
            <button
              key={photo.id}
              type="button"
              className="demo-list-item"
              onClick={() => { setRetryFlash(""); setOpen({ kind: "photo", data: photo }) }}
            >
              <img src={photo.image} alt="" />
              <div>
                <strong>{photo.name}</strong>
                <div className="muted">
                  {photo.cartons} CTN · TW {photo.total_weight_kg} · scale {photo.scale_weight_kg}
                </div>
              </div>
              <StatusChip tone={vs.tone}>{vs.label}</StatusChip>
            </button>
          )
        })}
      </div>

      <TotalsScoreboard />

      {open ? (
        <div className="demo-lightbox" role="dialog" aria-modal="true" onClick={() => setOpen(null)}>
          <div className="demo-lightbox-card" onClick={(event) => event.stopPropagation()}>
            <div className="media">
              <img src={open.data.image} alt={open.data.name} />
            </div>
            <div className="side">
              <h2>{open.data.name}</h2>
              {open.kind === "note" ? (
                <dl className="demo-message-grid">
                  <div><dt>Company</dt><dd>{open.data.company_name}</dd></div>
                  <div><dt>Mark</dt><dd>{open.data.mark}</dd></div>
                  <div><dt>Cartons</dt><dd>{open.data.cartons}</dd></div>
                  <div><dt>Goods</dt><dd>{open.data.goods}</dd></div>
                </dl>
              ) : (
                <>
                  <dl className="demo-message-grid">
                    <div><dt>Mark</dt><dd>{open.data.mark}</dd></div>
                    <div><dt>Cartons</dt><dd>{open.data.cartons}</dd></div>
                    <div><dt>Hand TW</dt><dd>{open.data.total_weight_kg} kg</dd></div>
                    <div><dt>Scale</dt><dd>{open.data.scale_weight_kg} kg</dd></div>
                  </dl>
                  <StatusChip tone={scaleVsHand(open.data).tone}>{scaleVsHand(open.data).label}</StatusChip>
                </>
              )}
              {retryFlash ? <div className="banner ok">{retryFlash}</div> : null}
              <div className="demo-lightbox-actions">
                <button
                  className="btn"
                  type="button"
                  onClick={() => setRetryFlash("Demo re-check queued (no API call).")}
                >
                  Re-check from image
                </button>
                <button className="btn-quiet" type="button" onClick={() => setOpen(null)}>Close</button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </DemoShell>
  )
}
