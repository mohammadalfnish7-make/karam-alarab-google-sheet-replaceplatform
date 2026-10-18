import { useState } from "react"
import { TwFixShell, TwFixStage } from "./TwFixShell"
import { TW_FIX_BAD, type TwFields } from "./twFixMock"

export function TwFixEditablePage() {
  const [fields, setFields] = useState<TwFields>(TW_FIX_BAD)

  return (
    <TwFixShell title="1. Editable fields">
      <p className="muted">Edit Hand TW in the panel (try 869) — the validation chip updates live.</p>
      <TwFixStage
        fields={fields}
        onHandChange={(value) => setFields((current) => ({ ...current, total_weight_kg: value }))}
      />
    </TwFixShell>
  )
}
