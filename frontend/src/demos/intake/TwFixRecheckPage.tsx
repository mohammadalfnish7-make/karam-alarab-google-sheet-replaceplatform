import { useState } from "react"
import { TwFixShell, TwFixStage } from "./TwFixShell"
import { TW_FIX_BAD, TW_FIX_TRUE, type TwFields } from "./twFixMock"

export function TwFixRecheckPage() {
  const [fields, setFields] = useState<TwFields>(TW_FIX_BAD)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState("First pass used the normal prompt (misread TW).")

  function recheck() {
    setBusy(true)
    setNote("Strict re-check: prefer digits that match the scale when handwriting is unclear…")
    window.setTimeout(() => {
      setFields(TW_FIX_TRUE)
      setNote("Second pass returned TW 869 (matches scale).")
      setBusy(false)
    }, 900)
  }

  return (
    <TwFixShell title="2. Tighter re-check">
      <div className={`tw-fix-banner ${fields.total_weight_kg === 869 ? "ok" : "warn"}`}>
        <span>{note}</span>
        <div className="tw-fix-actions">
          <button className="btn" type="button" disabled={busy} onClick={recheck}>
            {busy ? "Re-checking…" : "Re-check (strict prompt)"}
          </button>
          <button className="btn-quiet" type="button" disabled={busy} onClick={() => { setFields(TW_FIX_BAD); setNote("Reset to first-pass misread.") }}>
            Reset misread
          </button>
        </div>
      </div>
      <TwFixStage fields={fields} />
    </TwFixShell>
  )
}
