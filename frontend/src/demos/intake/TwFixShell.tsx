import type { ReactNode } from "react"
import { Link } from "react-router-dom"
import { StatusChip } from "./shared"
import { TW_FIX_IMAGE, scaleVsHand, type TwFields } from "./twFixMock"
import "./demos.css"
import "./twFix.css"

export function TwFixShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="page demo-intake">
      <div className="page-head">
        <div>
          <p className="demo-kicker">
            <Link to="/demo/intake/tw-fix">TW misread demos</Link>
          </p>
          <h1>{title}</h1>
        </div>
        <div className="page-actions">
          <Link className="btn-quiet" to="/demo/intake/tw-fix">All TW fixes</Link>
          <Link className="btn-quiet" to="/demo/intake">UI demos</Link>
        </div>
      </div>
      <p className="muted demo-scenario">
        Same failure case: photo shows <strong>TW 869</strong> and scale <strong>869.0</strong>, but the
        first extract returns handwritten TW <strong>8869</strong>. Demo only — no API.
      </p>
      {children}
    </main>
  )
}

export function TwFixStage({
  fields,
  children,
  onHandChange,
}: {
  fields: TwFields
  children?: ReactNode
  onHandChange?: (value: number) => void
}) {
  const vs = scaleVsHand(fields)
  return (
    <div className="demo-split tw-fix-split">
      <div>
        <div className="demo-stage">
          <img src={TW_FIX_IMAGE} alt="Scale photo ZK.001" />
        </div>
        <p className="muted" style={{ margin: "8px 0 0" }}>
          Truth on photo: mark ZK.001 · 39 CTN · TW 869 · PW 23 · scale 869.0
        </p>
      </div>
      <aside className="demo-fields">
        <h2>Extracted · scale photo</h2>
        <p className="muted" style={{ marginTop: 0 }}>zk001-scale.jpg (mock)</p>
        {children}
        <dl className="tw-fix-dl">
          <div><dt>Mark</dt><dd>{fields.mark}</dd></div>
          <div><dt>Cartons</dt><dd>{fields.cartons}</dd></div>
          <div>
            <dt>Scale kg</dt>
            <dd>{fields.scale_weight_kg}</dd>
            <StatusChip tone={vs.tone}>{vs.label}</StatusChip>
          </div>
          <div>
            <dt>Hand TW</dt>
            <dd>
              {onHandChange ? (
                <input
                  inputMode="decimal"
                  value={String(fields.total_weight_kg)}
                  onChange={(event) => {
                    const number = Number(event.target.value)
                    if (Number.isFinite(number)) onHandChange(number)
                  }}
                />
              ) : (
                fields.total_weight_kg
              )}
            </dd>
            <StatusChip tone={vs.tone}>{vs.label}</StatusChip>
          </div>
          <div><dt>Pallet PW</dt><dd>{fields.pallet_weight_kg}</dd></div>
        </dl>
      </aside>
    </div>
  )
}
