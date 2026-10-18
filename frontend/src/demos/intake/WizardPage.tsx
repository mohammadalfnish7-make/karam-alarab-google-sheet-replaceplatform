import { useState } from "react"
import { DEMO_NOTES, DEMO_PHOTOS, scaleVsHand } from "./mockData"
import { DemoShell, MessageSummary, StatusChip, TotalsScoreboard } from "./shared"

const STEPS = ["Message", "Notes", "Scale", "Totals", "Done"] as const

export function IntakeDemoWizardPage() {
  const [step, setStep] = useState(0)

  return (
    <DemoShell title="Step wizard">
      <div className="demo-steps">
        {STEPS.map((label, index) => (
          <button
            key={label}
            type="button"
            className={`demo-step-pill${index === step ? " active" : ""}${index < step ? " done" : ""}`}
            onClick={() => setStep(index)}
          >
            {index + 1}. {label}
          </button>
        ))}
      </div>

      <div className="demo-wizard-panel">
        {step === 0 ? (
          <>
            <h2 style={{ marginTop: 0 }}>1. Confirm message</h2>
            <p className="muted">Paste or edit the chat summary before checking papers and scales.</p>
            <MessageSummary />
          </>
        ) : null}

        {step === 1 ? (
          <>
            <h2 style={{ marginTop: 0 }}>2. Delivery notes ({DEMO_NOTES.length})</h2>
            <p className="muted">Each paper is read on its own; cartons should sum to the message.</p>
            <div className="demo-wizard-grid">
              {DEMO_NOTES.map((note) => (
                <article key={note.id} className="demo-wizard-card">
                  <img src={note.image} alt={note.name} />
                  <div className="body">
                    <strong>{note.name}</strong>
                    <span>{note.mark} · {note.cartons} CTN</span>
                    <StatusChip tone="ok">Shop match</StatusChip>
                  </div>
                </article>
              ))}
            </div>
          </>
        ) : null}

        {step === 2 ? (
          <>
            <h2 style={{ marginTop: 0 }}>3. Scale photos ({DEMO_PHOTOS.length})</h2>
            <p className="muted">Scale vs handwriting: ≤ 1 kg is OK (amber).</p>
            <div className="demo-wizard-grid">
              {DEMO_PHOTOS.map((photo) => {
                const vs = scaleVsHand(photo)
                return (
                  <article key={photo.id} className="demo-wizard-card">
                    <img src={photo.image} alt={photo.name} />
                    <div className="body">
                      <strong>{photo.name}</strong>
                      <span>{photo.cartons} CTN · TW {photo.total_weight_kg} · scale {photo.scale_weight_kg}</span>
                      <StatusChip tone={vs.tone}>{vs.label}</StatusChip>
                    </div>
                  </article>
                )
              })}
            </div>
          </>
        ) : null}

        {step === 3 ? (
          <>
            <h2 style={{ marginTop: 0 }}>4. Totals check</h2>
            <p className="muted">Sum every photo and note, then compare to the message.</p>
            <TotalsScoreboard />
          </>
        ) : null}

        {step === 4 ? (
          <>
            <h2 style={{ marginTop: 0 }}>5. Ready to save</h2>
            <p className="muted">
              In production this step would write the message row to the sea/air sheet.
              Demos do not save.
            </p>
            <MessageSummary />
            <p style={{ marginTop: 16 }}>
              <StatusChip tone="warn">Demo only — Save disabled</StatusChip>
            </p>
          </>
        ) : null}
      </div>

      <div className="demo-wizard-actions">
        <button className="btn-quiet" type="button" disabled={step === 0} onClick={() => setStep((s) => Math.max(0, s - 1))}>
          Back
        </button>
        <button
          className="btn"
          type="button"
          disabled={step >= STEPS.length - 1}
          onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
        >
          Next
        </button>
      </div>
    </DemoShell>
  )
}
