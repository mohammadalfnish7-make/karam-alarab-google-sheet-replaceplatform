/** Shared ZK.001 misread scenario: scale 869, model wrongly reads TW as 8869. */

export type TwFields = {
  mark: string
  cartons: number
  total_weight_kg: number
  pallet_weight_kg: number
  scale_weight_kg: number
}

export const TW_FIX_IMAGE = "/demo/air-scale.jpg"
export const TW_FIX_TRUE: TwFields = {
  mark: "ZK.001",
  cartons: 39,
  total_weight_kg: 869,
  pallet_weight_kg: 23,
  scale_weight_kg: 869,
}
/** First-pass extract with the common OCR slip (extra leading 8). */
export const TW_FIX_BAD: TwFields = {
  ...TW_FIX_TRUE,
  total_weight_kg: 8869,
}

export type ChipTone = "ok" | "warn" | "bad" | "empty"

export function scaleVsHand(fields: TwFields): { tone: ChipTone; delta: number; label: string } {
  const delta = Math.round(Math.abs(fields.scale_weight_kg - fields.total_weight_kg) * 1000) / 1000
  if (delta <= 0.05) return { tone: "ok", delta, label: "Matches handwriting" }
  if (delta <= 1) return { tone: "warn", delta, label: `Δ ${delta} kg — OK within 1 kg` }
  return { tone: "bad", delta, label: `Δ ${delta} kg — over 1 kg` }
}

/** 8869 looks like 869 with an extra leading digit. */
export function looksLikeExtraDigit(hand: number, scale: number): boolean {
  if (!Number.isFinite(hand) || !Number.isFinite(scale) || scale <= 0) return false
  const handText = String(Math.round(hand))
  const scaleText = String(Math.round(scale))
  if (handText.length !== scaleText.length + 1) return false
  return handText.slice(1) === scaleText || handText.endsWith(scaleText)
}

export const TW_FIX_OPTIONS = [
  {
    path: "/demo/intake/tw-fix/editable",
    title: "Editable fields",
    blurb: "Operator edits TW from 8869 to 869; validation updates live.",
  },
  {
    path: "/demo/intake/tw-fix/recheck",
    title: "Tighter re-check",
    blurb: "Re-check with a strict prompt mock — second pass returns 869.",
  },
  {
    path: "/demo/intake/tw-fix/auto-digit",
    title: "Auto-correct extra digit",
    blurb: "Detect 8869 ≈ 869 + extra digit and offer to apply scale.",
  },
  {
    path: "/demo/intake/tw-fix/prefer-scale",
    title: "Prefer scale when Δ large",
    blurb: "When Δ is huge, totals default to scale kg; hand stays visible as suspect.",
  },
  {
    path: "/demo/intake/tw-fix/dual-pass",
    title: "Dual / second pass",
    blurb: "Pass A vs Pass B; keep the value closer to the scale.",
  },
  {
    path: "/demo/intake/tw-fix/conflict",
    title: "Conflict + one-click",
    blurb: "Red conflict card with Use scale for TW.",
  },
] as const
