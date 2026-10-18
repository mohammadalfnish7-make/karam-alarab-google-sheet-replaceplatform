import { useMemo, useState } from "react"
import { TwFixShell, TwFixStage } from "./TwFixShell"
import { TW_FIX_BAD, looksLikeExtraDigit, type TwFields } from "./twFixMock"

export function TwFixAutoDigitPage() {
  const [fields, setFields] = useState<TwFields>(TW_FIX_BAD)
  const suggest = useMemo(
    () => looksLikeExtraDigit(fields.total_weight_kg, fields.scale_weight_kg),
    [fields],
  )

  return (
    <TwFixShell title="3. Auto-correct extra digit">
      {suggest ? (
        <div className="tw-fix-banner warn">
          <strong>Likely OCR slip</strong>
          <span>
            Hand TW {fields.total_weight_kg} looks like scale {fields.scale_weight_kg} with an extra leading digit.
          </span>
          <div className="tw-fix-actions">
            <button
              className="btn"
              type="button"
              onClick={() => setFields((current) => ({ ...current, total_weight_kg: current.scale_weight_kg }))}
            >
              Apply scale {fields.scale_weight_kg} to TW
            </button>
            <button className="btn-quiet" type="button" onClick={() => setFields(TW_FIX_BAD)}>
              Keep handwriting
            </button>
          </div>
        </div>
      ) : (
        <div className="tw-fix-banner ok">
          <span>No extra-digit pattern — values look consistent (or already fixed).</span>
          <button className="btn-quiet" type="button" onClick={() => setFields(TW_FIX_BAD)}>Reset misread</button>
        </div>
      )}
      <TwFixStage fields={fields} />
    </TwFixShell>
  )
}
