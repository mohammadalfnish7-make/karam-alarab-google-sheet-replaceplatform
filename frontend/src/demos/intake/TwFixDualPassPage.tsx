import { useMemo, useState } from "react"
import { StatusChip } from "./shared"
import { TwFixShell, TwFixStage } from "./TwFixShell"
import { TW_FIX_BAD, TW_FIX_TRUE, type TwFields } from "./twFixMock"

export function TwFixDualPassPage() {
  const passA = TW_FIX_BAD
  const passB = TW_FIX_TRUE
  const closer = useMemo(() => {
    const dA = Math.abs(passA.total_weight_kg - passA.scale_weight_kg)
    const dB = Math.abs(passB.total_weight_kg - passB.scale_weight_kg)
    return dA <= dB ? "A" : "B"
  }, [])
  const [chosen, setChosen] = useState<"A" | "B">(closer)
  const fields: TwFields = chosen === "A" ? passA : passB

  return (
    <TwFixShell title="5. Dual / second pass">
      <p className="muted">Two extracts of the same photo. Keep the TW closer to the scale reading.</p>
      <div className="tw-fix-dual">
        <button
          type="button"
          className={`tw-fix-pass${chosen === "A" ? " active" : ""}`}
          onClick={() => setChosen("A")}
        >
          <h3>Pass A (first)</h3>
          <span>TW {passA.total_weight_kg} · scale {passA.scale_weight_kg}</span>
          <StatusChip tone="bad">Δ {Math.abs(passA.total_weight_kg - passA.scale_weight_kg)} kg</StatusChip>
        </button>
        <button
          type="button"
          className={`tw-fix-pass${chosen === "B" ? " active" : ""}`}
          onClick={() => setChosen("B")}
        >
          <h3>Pass B (retry)</h3>
          <span>TW {passB.total_weight_kg} · scale {passB.scale_weight_kg}</span>
          <StatusChip tone="ok">Closer to scale</StatusChip>
        </button>
      </div>
      <div className="tw-fix-banner ok">
        <span>Auto-pick recommends <strong>Pass {closer}</strong>. Selected: Pass {chosen}.</span>
      </div>
      <TwFixStage fields={fields} />
    </TwFixShell>
  )
}
