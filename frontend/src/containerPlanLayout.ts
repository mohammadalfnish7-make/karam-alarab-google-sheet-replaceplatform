/** Flatten loading-plan lines into one pallet per unique mix (DRY: plan_json only). */

export type PlanLine = {
  no?: number | null
  customer_code?: string | null
  cust_name?: string | null
  mix?: number | null
  name?: string | null
  cartons?: number | null
  weight?: number | null
  pw?: number | null
  total_weight?: number | null
  hidden?: boolean | null
  excel_row?: number | null
}

export type PlanWarning = {
  code?: string
  message?: string
}

export type PlanMark = {
  name: string
  customer_code: string | null
  cartons: number | null
  weight_kg: number | null
}

export type PlanPallet = {
  mix: number
  side: "left" | "right"
  marks: PlanMark[]
}

export type LoadingPlan = {
  container_number?: string | null
  line_count?: number
  total_weight?: number | null
  hidden_row_count?: number
  warnings?: PlanWarning[]
  lines?: PlanLine[]
  filename?: string | null
} | null | undefined

export function emptyPlanLine(index = 0): PlanLine {
  return {
    no: index + 1,
    customer_code: "",
    cust_name: null,
    mix: 1,
    name: "",
    cartons: null,
    weight: null,
    pw: null,
    total_weight: null,
  }
}

/** Sum of line weights (weight, else total_weight). */
export function sumPlanWeight(plan: LoadingPlan | { lines?: PlanLine[] } | null | undefined): number {
  const lines = plan?.lines
  if (!lines?.length) return 0
  let total = 0
  for (const line of lines) {
    const value = line.weight ?? line.total_weight
    if (typeof value === "number" && Number.isFinite(value)) total += value
  }
  return total
}

/** Odd mix → left column, even → right; ordered by mix along the container. */
export function planToPallets(plan: LoadingPlan): PlanPallet[] {
  const lines = plan?.lines
  if (!lines?.length) return []

  const byMix = new Map<number, PlanMark[]>()
  for (const line of lines) {
    const mix = typeof line.mix === "number" && Number.isFinite(line.mix) ? line.mix : null
    if (mix == null || mix < 1) continue
    // Only real named marks count — skip weight/carton-only filler rows
    const name = (line.name || "").trim()
    if (!name) continue
    const marks = byMix.get(mix) || []
    marks.push({
      name,
      customer_code: line.customer_code ? String(line.customer_code).trim() : null,
      cartons: line.cartons ?? null,
      weight_kg: line.weight ?? line.total_weight ?? null,
    })
    byMix.set(mix, marks)
  }

  return [...byMix.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([mix, marks]) => ({
      mix,
      side: mix % 2 === 1 ? "left" : "right",
      marks,
    }))
}

/** Flat plan lines for the review table (same filter as 3D). */
export function planReviewRows(plan: LoadingPlan): PlanLine[] {
  const lines = plan?.lines
  if (!lines?.length) return []
  return lines.filter((line) => {
    const mix = typeof line.mix === "number" && Number.isFinite(line.mix) ? line.mix : null
    if (mix == null || mix < 1) return false
    return Boolean((line.name || "").trim())
  })
}
