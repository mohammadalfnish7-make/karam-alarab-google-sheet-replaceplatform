import { useMemo, useState } from "react"
import { StatusChip } from "./shared"
import { TwFixShell, TwFixStage } from "./TwFixShell"
import { TW_FIX_BAD, scaleVsHand, type TwFields } from "./twFixMock"

export function TwFixPreferScalePage() {
  const [fields] = useState<TwFields>(TW_FIX_BAD)
  const vs = scaleVsHand(fields)
  const preferScale = vs.tone === "bad"
  const preferredTw = preferScale ? fields.scale_weight_kg : fields.total_weight_kg

  const scoreTone = useMemo(() => {
    if (!preferScale) return "ok" as const
    return "warn" as const
  }, [preferScale])

  return (
    <TwFixShell title="4. Prefer scale when Δ large">
      <div className={`tw-fix-banner ${preferScale ? "warn" : "ok"}`}>
        <strong>Preferred TW for totals: {preferredTw} kg</strong>
        <span>
          {preferScale
            ? "Δ is large, so the scoreboard uses scale kg. Handwriting stays visible for review."
            : "Scale and handwriting agree — using handwritten TW."}
        </span>
      </div>
      <TwFixStage fields={fields} />
      <section className="demo-scoreboard" style={{ marginTop: 16 }}>
        <h2>Totals (preferred source)</h2>
        <div className="demo-score-grid">
          <article className={`demo-score demo-score-${scoreTone}`}>
            <span className="demo-score-label">TW used for save</span>
            <strong>{preferredTw} kg</strong>
            <span className="muted">
              hand {fields.total_weight_kg} · scale {fields.scale_weight_kg}
            </span>
            <StatusChip tone={scoreTone}>{preferScale ? "Using scale" : "Using hand"}</StatusChip>
          </article>
        </div>
      </section>
    </TwFixShell>
  )
}
