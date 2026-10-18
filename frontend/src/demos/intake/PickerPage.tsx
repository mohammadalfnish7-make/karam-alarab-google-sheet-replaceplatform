import { Link } from "react-router-dom"
import { DEMO_MESSAGE, DEMO_NOTES, DEMO_OPTIONS, DEMO_PHOTOS } from "./mockData"
import "./demos.css"

export function IntakeDemoPickerPage() {
  return (
    <main className="page demo-intake">
      <div className="page-head">
        <h1>Intake UI demos</h1>
      </div>
      <p className="muted">
        Same mock shipment for every layout: <strong>{DEMO_MESSAGE.shipment_number}</strong> / TL
        {DEMO_MESSAGE.customer_code}, {DEMO_NOTES.length} delivery notes, {DEMO_PHOTOS.length} scale
        photos. Open each option and pick what feels right for operators — production intake is unchanged.
      </p>
      <div className="demo-picker-grid">
        {DEMO_OPTIONS.map((option, index) => (
          <Link key={option.path} className="demo-picker-card" to={option.path}>
            <div className="demo-picker-visual" aria-hidden />
            <h2>{index + 1}. {option.title}</h2>
            <p>{option.blurb}</p>
            <span className="btn">Open demo</span>
          </Link>
        ))}
        <Link className="demo-picker-card" to="/demo/intake/tw-fix">
          <div className="demo-picker-visual" aria-hidden />
          <h2>TW misread fixes</h2>
          <p>
            Six recovery UX demos for when scale is 869 but the model reads handwritten TW as 8869.
          </p>
          <span className="btn">Open TW fix demos</span>
        </Link>
      </div>
    </main>
  )
}
