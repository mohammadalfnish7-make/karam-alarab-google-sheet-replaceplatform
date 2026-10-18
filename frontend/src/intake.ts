export type IntakeFields = {
  shipment_number: string
  date_received: string
  customer_code: string
  cartons: string
  total_weight_kg: string
  pallet_weight_kg: string
  net_weight_kg: string
  company_name: string
  goods: string
  pieces: string
}

export const emptyIntake = (): IntakeFields => ({
  shipment_number: "",
  date_received: "",
  customer_code: "",
  cartons: "",
  total_weight_kg: "",
  pallet_weight_kg: "",
  net_weight_kg: "",
  company_name: "",
  goods: "",
  pieces: "",
})

export const SAMPLE_MESSAGE = `D1236
DATE 29/09/2026
TL4455
CTN 6
TW 122.5 KG
PW 15 .5 KG
NW 107 KG
SHOP MADINAH AL NOOR
PERFUME`

export const AIR_SAMPLE_MESSAGE = `AR085
DATE 05/10/2026
TL4431
CTN 11
PCS
TW 342.5 KG
PW 15 KG
NW 327.5 KG
SHOP BURNABY PERFUME
PERFUME *`

const MONTHS: Record<string, string> = {
  jan: "01",
  feb: "02",
  mar: "03",
  apr: "04",
  may: "05",
  jun: "06",
  jul: "07",
  aug: "08",
  sep: "09",
  oct: "10",
  nov: "11",
  dec: "12",
}

function weight(raw: string) {
  const match = raw.replace(/\s+/g, "").match(/(\d+(?:\.\d+)?)/)
  return match ? match[1] : ""
}

function sheetDate(raw: string) {
  const text = raw.trim()
  const numeric = text.match(/^(\d{1,2})[/.\\-](\d{1,2})[/.\\-](\d{2,4})$/)
  if (numeric) {
    const day = numeric[1].padStart(2, "0")
    const month = numeric[2].padStart(2, "0")
    const year = numeric[3].length === 2 ? `20${numeric[3]}` : numeric[3]
    return `${year}-${month}-${day}`
  }
  const named = text.match(/^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$/)
  if (!named) return ""
  const month = MONTHS[named[2].slice(0, 3).toLowerCase()]
  if (!month) return ""
  return `${named[3]}-${month}-${named[1].padStart(2, "0")}`
}

function netFromWeights(total: string, pallet: string, printed: string) {
  if (printed) return printed
  const gross = Number(total)
  const palletWeight = Number(pallet)
  if (!Number.isFinite(gross) || !Number.isFinite(palletWeight)) return ""
  const net = Math.round((gross - palletWeight) * 1000) / 1000
  if (net < 0) return ""
  return String(net)
}

export type CompareKind = "number" | "mark" | "name" | "date" | "none"

export type CheckColumn = {
  key: string
  label: string
  compare: CompareKind
  messageKey: keyof IntakeFields | ""
}

export const NOTE_FIELDS: CheckColumn[] = [
  { key: "company_name", label: "Company", compare: "name", messageKey: "company_name" },
  { key: "date", label: "Date", compare: "date", messageKey: "date_received" },
  { key: "mark", label: "Mark", compare: "mark", messageKey: "customer_code" },
  { key: "cartons", label: "Cartons", compare: "number", messageKey: "cartons" },
  { key: "goods", label: "Goods", compare: "name", messageKey: "goods" },
  { key: "party", label: "Party", compare: "none", messageKey: "" },
]

export const SCALE_FIELDS: CheckColumn[] = [
  { key: "mark", label: "Mark", compare: "mark", messageKey: "customer_code" },
  { key: "cartons", label: "Cartons", compare: "number", messageKey: "cartons" },
  { key: "scale_weight_kg", label: "Scale kg", compare: "number", messageKey: "total_weight_kg" },
  { key: "total_weight_kg", label: "Handwritten TW", compare: "number", messageKey: "total_weight_kg" },
  { key: "pallet_weight_kg", label: "Pallet PW", compare: "number", messageKey: "pallet_weight_kg" },
]

export type CheckResult = "match" | "diff" | "empty"
/** UI chip tone: exact/near match, within 1 kg, hard fail, or no value. */
export type CheckTone = "ok" | "warn" | "bad" | "empty"

export type ScalePhotoFields = {
  mark?: string | number | null
  cartons?: string | number | null
  total_weight_kg?: string | number | null
  pallet_weight_kg?: string | number | null
  scale_weight_kg?: string | number | null
}

export type NoteFields = {
  cartons?: string | number | null
}

export type TotalCheck = {
  key: string
  label: string
  summed: number | null
  messageValue: string
  result: CheckResult
}

const WEIGHT_TOLERANCE = 0.05
/** Policy tolerance X (docs/intake-weight-policy.md). */
export const SCALE_VS_HANDWRITE_TOLERANCE = 1

function compactName(value: string) {
  return value.toUpperCase().replace(/[^A-Z0-9]/g, "")
}

function markDigits(value: string) {
  const marked = value.toUpperCase().match(/TL[-\s]*([0-9]+)/)
  if (marked) return marked[1]
  const digits = value.match(/[0-9]+/)
  return digits ? digits[0] : ""
}

export function showCheckValue(value: unknown) {
  if (value == null || value === "") return ""
  const text = String(value)
  const date = text.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (date) return `${date[3]}/${date[2]}/${date[1]}`
  return text
}

export function asNumber(value: unknown): number | null {
  if (value == null || value === "") return null
  const number = Number(String(value).replace(/\s+/g, ""))
  return Number.isFinite(number) ? number : null
}

export function numbersClose(left: number, right: number, tol = WEIGHT_TOLERANCE): boolean {
  return Math.abs(left - right) <= tol
}

export function compareCheck(kind: CompareKind, messageValue: string, extracted: unknown): CheckResult {
  const other = showCheckValue(extracted)
  if (!other || kind === "none") return "empty"
  if (!messageValue) return "empty"
  if (kind === "date") return messageValue === String(extracted).slice(0, 10) ? "match" : "diff"
  if (kind === "number") {
    const left = asNumber(messageValue)
    const right = asNumber(extracted)
    if (left == null || right == null) return "diff"
    return numbersClose(left, right) ? "match" : "diff"
  }
  if (kind === "mark") {
    const left = markDigits(messageValue)
    const right = markDigits(other)
    if (!left || !right) return "diff"
    return left === right ? "match" : "diff"
  }
  const left = compactName(messageValue)
  const right = compactName(other)
  if (!left || !right) return "diff"
  return left === right || left.includes(right) || right.includes(left) ? "match" : "diff"
}

export function sumField(rows: Array<Record<string, unknown>>, key: string): number | null {
  let total = 0
  let any = false
  for (const row of rows) {
    const number = asNumber(row[key])
    if (number == null) continue
    total += number
    any = true
  }
  if (!any) return null
  return Math.round(total * 1000) / 1000
}

/** Digital scale vs handwritten TW on the same pallet photo (≤ 1 kg OK). */
export function checkScaleVsHandwrite(photo: ScalePhotoFields): CheckResult {
  const detail = scaleVsHandDetail(photo)
  if (detail.tone === "empty") return "empty"
  if (detail.tone === "bad") return "diff"
  return "match"
}

export function scaleVsHandDetail(photo: ScalePhotoFields): { tone: CheckTone; delta: number | null; label: string } {
  const scale = asNumber(photo.scale_weight_kg)
  const hand = asNumber(photo.total_weight_kg)
  if (scale == null || hand == null) return { tone: "empty", delta: null, label: "" }
  const delta = Math.round(Math.abs(scale - hand) * 1000) / 1000
  if (delta === 0 || delta <= WEIGHT_TOLERANCE) {
    return { tone: "ok", delta, label: "Match" }
  }
  if (delta <= SCALE_VS_HANDWRITE_TOLERANCE) {
    return { tone: "warn", delta, label: `OK ≤ ${SCALE_VS_HANDWRITE_TOLERANCE} kg` }
  }
  return { tone: "bad", delta, label: "Conflict" }
}

export function checkToneFromResult(result: CheckResult): CheckTone {
  if (result === "match") return "ok"
  if (result === "diff") return "bad"
  return "empty"
}

/** Preferred TW for a photo after operator edits (hand TW field is the working value). */
export function preferredTw(photo: ScalePhotoFields): number | null {
  return asNumber(photo.total_weight_kg) ?? asNumber(photo.scale_weight_kg)
}

export function preferredPhotoTotals(photos: ScalePhotoFields[]): {
  cartons: number | null
  total_weight_kg: number | null
  pallet_weight_kg: number | null
  net_weight_kg: number | null
} {
  const cartons = sumField(photos, "cartons")
  let tw = 0
  let pw = 0
  let anyTw = false
  let anyPw = false
  for (const photo of photos) {
    const preferred = preferredTw(photo)
    if (preferred != null) {
      tw += preferred
      anyTw = true
    }
    const pallet = asNumber(photo.pallet_weight_kg)
    if (pallet != null) {
      pw += pallet
      anyPw = true
    }
  }
  const total_weight_kg = anyTw ? Math.round(tw * 1000) / 1000 : null
  const pallet_weight_kg = anyPw ? Math.round(pw * 1000) / 1000 : null
  const net_weight_kg =
    total_weight_kg != null && pallet_weight_kg != null
      ? Math.round((total_weight_kg - pallet_weight_kg) * 1000) / 1000
      : total_weight_kg != null && !anyPw
        ? total_weight_kg
        : null
  return { cartons, total_weight_kg, pallet_weight_kg, net_weight_kg }
}

export type PhotoSaveState = {
  status: "reading" | "done" | "error"
  extracted: ScalePhotoFields
  warnConfirmed?: boolean
}

/** Gate save per docs/intake-weight-policy.md. */
export function intakeSaveGate(photos: PhotoSaveState[]): {
  canSave: boolean
  needsWarnConfirm: boolean
  blockers: string[]
} {
  const blockers: string[] = []
  let needsWarnConfirm = false
  if (!photos.length) {
    return { canSave: true, needsWarnConfirm: false, blockers: [] }
  }
  for (const [index, photo] of photos.entries()) {
    const label = `Scale ${index + 1}`
    if (photo.status === "reading") blockers.push(`${label} is still reading`)
    if (photo.status === "error") blockers.push(`${label} failed — re-check or remove`)
    if (photo.status !== "done") continue
    const detail = scaleVsHandDetail(photo.extracted)
    if (detail.tone === "bad") blockers.push(`${label}: Conflict — resolve with Use scale / Use hand / Edit`)
    if (detail.tone === "warn" && !photo.warnConfirmed) needsWarnConfirm = true
  }
  if (needsWarnConfirm) blockers.push(`Confirm OK ≤ ${SCALE_VS_HANDWRITE_TOLERANCE} kg gaps before save`)
  return { canSave: blockers.length === 0, needsWarnConfirm, blockers }
}

function totalRow(
  key: string,
  label: string,
  summed: number | null,
  messageValue: string,
): TotalCheck {
  if (summed == null || !messageValue) {
    return { key, label, summed, messageValue, result: "empty" }
  }
  const messageNumber = asNumber(messageValue)
  if (messageNumber == null) {
    return { key, label, summed, messageValue, result: "diff" }
  }
  return {
    key,
    label,
    summed,
    messageValue,
    result: numbersClose(summed, messageNumber) ? "match" : "diff",
  }
}

/** Sum scale photos and check totals against the chat message (preferred TW / net). */
export function buildScaleTotals(message: IntakeFields, photos: ScalePhotoFields[]): TotalCheck[] {
  const preferred = preferredPhotoTotals(photos)
  const sumScale = sumField(photos, "scale_weight_kg")

  return [
    totalRow("cartons", "Cartons sum", preferred.cartons, message.cartons),
    totalRow("scale_weight_kg", "Scale kg sum", sumScale, message.total_weight_kg),
    totalRow("total_weight_kg", "Preferred TW sum", preferred.total_weight_kg, message.total_weight_kg),
    totalRow("pallet_weight_kg", "Pallet PW sum", preferred.pallet_weight_kg, message.pallet_weight_kg),
    totalRow("net_weight_kg", "Net (TW − PW)", preferred.net_weight_kg, message.net_weight_kg),
  ]
}

/** Sum delivery-note cartons and check against the chat message. */
export function buildNoteTotals(message: IntakeFields, notes: NoteFields[]): TotalCheck[] {
  return [totalRow("cartons", "Cartons sum", sumField(notes, "cartons"), message.cartons)]
}

export function parseIntakeMessage(text: string, kind: "sea" | "air" = "sea"): IntakeFields {
  const fields = emptyIntake()
  const goods: string[] = []
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim()
    if (!line) continue
    const shipment = kind === "air" ? line.match(/^AR\s*(\d+)$/i) : line.match(/^D\s*(\d+)$/i)
    if (shipment) {
      fields.shipment_number = `${kind === "air" ? "AR" : "D"}${shipment[1]}`
      continue
    }
    const pieces = line.match(/^PCS(?:\s+(\d+))?$/i)
    if (pieces) {
      fields.pieces = pieces[1] ?? ""
      continue
    }
    const date = line.match(/^DATE\s+(.+)$/i)
    if (date) {
      fields.date_received = sheetDate(date[1])
      continue
    }
    const mark = line.match(/^TL[-\s]*(\d+)$/i)
    if (mark) {
      fields.customer_code = mark[1]
      continue
    }
    const cartons = line.match(/^CTN\s+(\d+)/i)
    if (cartons) {
      fields.cartons = cartons[1]
      continue
    }
    const total = line.match(/^TW\s+(.+)$/i)
    if (total) {
      fields.total_weight_kg = weight(total[1])
      continue
    }
    const pallet = line.match(/^PW\s+(.+)$/i)
    if (pallet) {
      fields.pallet_weight_kg = weight(pallet[1])
      continue
    }
    const net = line.match(/^NW\s+(.+)$/i)
    if (net) {
      fields.net_weight_kg = weight(net[1])
      continue
    }
    const shop = line.match(/^SHOP\s+(.+)$/i)
    if (shop) {
      fields.company_name = shop[1].trim()
      continue
    }
    goods.push(line.replace(/\s+\*\s*$/, "").trim())
  }
  fields.goods = goods.filter(Boolean).join(" ")
  fields.net_weight_kg = netFromWeights(fields.total_weight_kg, fields.pallet_weight_kg, fields.net_weight_kg)
  return fields
}
