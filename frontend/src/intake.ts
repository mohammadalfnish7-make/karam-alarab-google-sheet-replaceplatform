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

export function compareCheck(kind: CompareKind, messageValue: string, extracted: unknown): CheckResult {
  const other = showCheckValue(extracted)
  if (!other || kind === "none") return "empty"
  if (!messageValue) return "empty"
  if (kind === "date") return messageValue === String(extracted).slice(0, 10) ? "match" : "diff"
  if (kind === "number") {
    const left = Number(messageValue)
    const right = Number(String(extracted).replace(/\s+/g, ""))
    if (!Number.isFinite(left) || !Number.isFinite(right)) return "diff"
    return Math.abs(left - right) < 0.05 ? "match" : "diff"
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

export function parseIntakeMessage(text: string): IntakeFields {
  const fields = emptyIntake()
  const goods: string[] = []
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim()
    if (!line) continue
    const shipment = line.match(/^D\s*(\d+)$/i)
    if (shipment) {
      fields.shipment_number = `D${shipment[1]}`
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
