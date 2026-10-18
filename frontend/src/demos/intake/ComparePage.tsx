import { Fragment } from "react"
import { DEMO_MESSAGE, DEMO_NOTES, DEMO_PHOTOS, scaleVsHand } from "./mockData"
import { DemoShell, MessageSummary, StatusChip, TotalsScoreboard } from "./shared"

export function IntakeDemoComparePage() {
  return (
    <DemoShell title="Compare table">
      <section className="panel" style={{ marginBottom: 12 }}>
        <h2 style={{ marginTop: 0, fontSize: 15 }}>Message</h2>
        <MessageSummary />
      </section>

      <div className="demo-compare-strip">
        {[...DEMO_NOTES, ...DEMO_PHOTOS].map((item) => (
          <figure key={item.id}>
            <img src={item.image} alt={item.name} />
            <figcaption>{item.name.replace(".jpg", "")}</figcaption>
          </figure>
        ))}
      </div>

      <div className="demo-table-wrap">
        <table>
          <thead>
            <tr>
              <th>Source</th>
              <th>Field</th>
              <th>Message</th>
              <th>Extracted</th>
              <th>Scale</th>
              <th>Δ</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            <tr className="group-row"><td colSpan={7}>Delivery notes ({DEMO_NOTES.length})</td></tr>
            {DEMO_NOTES.map((note) => (
              <Fragment key={note.id}>
                <tr>
                  <td>{note.name}</td>
                  <td>Cartons</td>
                  <td>{DEMO_MESSAGE.cartons} (total)</td>
                  <td>{note.cartons}</td>
                  <td>—</td>
                  <td>—</td>
                  <td><StatusChip tone="ok">Part of sum</StatusChip></td>
                </tr>
                <tr>
                  <td>{note.name}</td>
                  <td>Mark</td>
                  <td>TL{DEMO_MESSAGE.customer_code}</td>
                  <td>{note.mark}</td>
                  <td>—</td>
                  <td>—</td>
                  <td><StatusChip tone="ok">Match</StatusChip></td>
                </tr>
              </Fragment>
            ))}

            <tr className="group-row"><td colSpan={7}>Scale photos ({DEMO_PHOTOS.length})</td></tr>
            {DEMO_PHOTOS.map((photo) => {
              const vs = scaleVsHand(photo)
              return (
                <tr key={photo.id}>
                  <td>{photo.name}</td>
                  <td>TW vs scale</td>
                  <td>—</td>
                  <td>{photo.total_weight_kg} kg · {photo.cartons} CTN</td>
                  <td>{photo.scale_weight_kg} kg</td>
                  <td>{vs.delta} kg</td>
                  <td><StatusChip tone={vs.tone}>{vs.label}</StatusChip></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <TotalsScoreboard />
    </DemoShell>
  )
}
