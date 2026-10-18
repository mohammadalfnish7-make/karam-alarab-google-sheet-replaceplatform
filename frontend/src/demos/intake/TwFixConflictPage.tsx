import { useState } from "react"
import { TwFixShell, TwFixStage } from "./TwFixShell"
import { TW_FIX_BAD, scaleVsHand, type TwFields } from "./twFixMock"

export function TwFixConflictPage() {
  const [fields, setFields] = useState<TwFields>(TW_FIX_BAD)
  const vs = scaleVsHand(fields)
  const conflict = vs.tone === "bad"

  return (
    <TwFixShell title="6. Conflict + one-click">
      {conflict ? (
        <div className="tw-fix-banner bad">
          <strong>Scale vs handwriting conflict</strong>
          <span>
            Scale {fields.scale_weight_kg} kg · Hand {fields.total_weight_kg} kg · {vs.label}
          </span>
          <div className="tw-fix-actions">
            <button
              className="btn"
              type="button"
              onClick={() => setFields((current) => ({ ...current, total_weight_kg: current.scale_weight_kg }))}
            >
              Use scale for TW
            </button>
            <button className="btn-quiet" type="button" onClick={() => setFields(TW_FIX_BAD)}>
              Keep hand TW
            </button>
          </div>
        </div>
      ) : (
        <div className="tw-fix-banner ok">
          <span>Conflict resolved — TW matches scale.</span>
          <button className="btn-quiet" type="button" onClick={() => setFields(TW_FIX_BAD)}>Show conflict again</button>
        </div>
      )}
      <TwFixStage fields={fields} />
    </TwFixShell>
  )
}
