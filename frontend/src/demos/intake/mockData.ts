/** Shared French Avenue–style mock for all intake UI demos (no API calls). */

export type CheckTone = "ok" | "warn" | "bad" | "empty"

export type MessageFields = {
  shipment_number: string
  date_received: string
  customer_code: string
  company_name: string
  cartons: number
  total_weight_kg: number
  pallet_weight_kg: number
  net_weight_kg: number
}

export type NoteExtract = {
  id: string
  name: string
  image: string
  company_name: string
  date: string
  mark: string
  cartons: number
  goods: string
  party: string
}

export type ScaleExtract = {
  id: string
  name: string
  image: string
  mark: string
  cartons: number
  total_weight_kg: number
  pallet_weight_kg: number | null
  scale_weight_kg: number
}

export const DEMO_MESSAGE: MessageFields = {
  shipment_number: "D1247",
  date_received: "2026-10-16",
  customer_code: "5523",
  company_name: "French Avenue General Trading LLC",
  cartons: 194,
  total_weight_kg: 464.5,
  pallet_weight_kg: 9.0,
  net_weight_kg: 455.5,
}

export const DEMO_NOTES: NoteExtract[] = [
  {
    id: "note-1",
    name: "french-avenue-page-1.jpg",
    image: "/demo/air-delivery-note.jpg",
    company_name: "French Avenue General Trading LLC",
    date: "2026-10-16",
    mark: "TL5523",
    cartons: 100,
    goods: "Perfumes & cosmetics",
    party: "Karam Al Arab",
  },
  {
    id: "note-2",
    name: "french-avenue-page-2.jpg",
    image: "/demo/air-delivery-note.jpg",
    company_name: "French Avenue General Trading LLC",
    date: "2026-10-16",
    mark: "TL5523",
    cartons: 94,
    goods: "Perfumes & cosmetics",
    party: "Karam Al Arab",
  },
]

/** Five pallets; one deliberate >1 kg mismatch for red state. */
export const DEMO_PHOTOS: ScaleExtract[] = [
  {
    id: "p1",
    name: "pallet-1.jpg",
    image: "/demo/air-scale.jpg",
    mark: "TL5523",
    cartons: 34,
    total_weight_kg: 87.9,
    pallet_weight_kg: null,
    scale_weight_kg: 87.9,
  },
  {
    id: "p2",
    name: "pallet-2.jpg",
    image: "/demo/air-scale.jpg",
    mark: "TL5523",
    cartons: 40,
    total_weight_kg: 94.2,
    pallet_weight_kg: 2.3,
    scale_weight_kg: 94.2,
  },
  {
    id: "p3",
    name: "pallet-3.jpg",
    image: "/demo/air-scale.jpg",
    mark: "TL5523",
    cartons: 37,
    total_weight_kg: 113.7,
    pallet_weight_kg: 2.3,
    scale_weight_kg: 113.65,
  },
  {
    id: "p4",
    name: "pallet-4.jpg",
    image: "/demo/air-scale.jpg",
    mark: "TL5523",
    cartons: 43,
    total_weight_kg: 87.5,
    pallet_weight_kg: 2.3,
    scale_weight_kg: 87.45,
  },
  {
    id: "p5",
    name: "pallet-5.jpg",
    image: "/demo/air-scale.jpg",
    mark: "TL5523",
    cartons: 40,
    total_weight_kg: 81.25,
    pallet_weight_kg: 2.1,
    scale_weight_kg: 79.0,
  },
]

export const SCALE_VS_HAND_TOLERANCE = 1

export function scaleVsHand(photo: ScaleExtract): { tone: CheckTone; delta: number; label: string } {
  const delta = Math.round(Math.abs(photo.scale_weight_kg - photo.total_weight_kg) * 1000) / 1000
  if (delta === 0) return { tone: "ok", delta, label: "Matches handwriting" }
  if (delta <= SCALE_VS_HAND_TOLERANCE) {
    return { tone: "warn", delta, label: `Δ ${delta} kg — OK within 1 kg` }
  }
  return { tone: "bad", delta, label: `Δ ${delta} kg — over 1 kg` }
}

export function sumCartons(photos: ScaleExtract[]) {
  return photos.reduce((n, p) => n + p.cartons, 0)
}

export function sumScale(photos: ScaleExtract[]) {
  return Math.round(photos.reduce((n, p) => n + p.scale_weight_kg, 0) * 1000) / 1000
}

export function sumHand(photos: ScaleExtract[]) {
  return Math.round(photos.reduce((n, p) => n + p.total_weight_kg, 0) * 1000) / 1000
}

export function sumNoteCartons(notes: NoteExtract[]) {
  return notes.reduce((n, note) => n + note.cartons, 0)
}

export function compareNumber(left: number, right: number, tol = 0.05): CheckTone {
  const delta = Math.abs(left - right)
  if (delta <= tol) return "ok"
  if (delta <= SCALE_VS_HAND_TOLERANCE) return "warn"
  return "bad"
}

export const DEMO_OPTIONS = [
  {
    path: "/demo/intake/side-by-side",
    title: "Side-by-side review",
    blurb: "Large image left, extracted fields and validation chips right, thumbnail strip for multi photos.",
  },
  {
    path: "/demo/intake/compare",
    title: "Compare table",
    blurb: "Message vs handwriting vs scale in columns — fast mismatch spotting across pallets.",
  },
  {
    path: "/demo/intake/wizard",
    title: "Step wizard",
    blurb: "Message → notes → scale → totals → done. One job per step.",
  },
  {
    path: "/demo/intake/lightbox",
    title: "Lightbox inspector",
    blurb: "Compact list; open a full-screen overlay to inspect image + fields + retry.",
  },
] as const
