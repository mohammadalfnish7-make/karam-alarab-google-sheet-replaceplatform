import { Link } from "react-router-dom"
import { TW_FIX_BAD, TW_FIX_OPTIONS, TW_FIX_TRUE } from "./twFixMock"
import "./demos.css"

export function TwFixPickerPage() {
  return (
    <main className="page demo-intake">
      <div className="page-head">
        <div>
          <p className="demo-kicker"><Link to="/demo/intake">Intake UI demos</Link></p>
          <h1>TW misread fix demos</h1>
        </div>
        <div className="page-actions">
          <Link className="btn-quiet" to="/demo/intake">Back</Link>
        </div>
      </div>
      <p className="muted">
        Scenario: scale reads <strong>{TW_FIX_TRUE.scale_weight_kg}</strong>, photo TW is{" "}
        <strong>{TW_FIX_TRUE.total_weight_kg}</strong>, but the model returns{" "}
        <strong>{TW_FIX_BAD.total_weight_kg}</strong>. Try each recovery UX — production intake is unchanged.
      </p>
      <div className="demo-picker-grid">
        {TW_FIX_OPTIONS.map((option, index) => (
          <Link key={option.path} className="demo-picker-card" to={option.path}>
            <div className="demo-picker-visual" aria-hidden />
            <h2>{index + 1}. {option.title}</h2>
            <p>{option.blurb}</p>
            <span className="btn">Open demo</span>
          </Link>
        ))}
      </div>
    </main>
  )
}
