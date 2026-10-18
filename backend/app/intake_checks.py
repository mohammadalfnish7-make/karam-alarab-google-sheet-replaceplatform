"""Sum multi-scale / multi-note intake readings and cross-check sources.

Weight policy: docs/intake-weight-policy.md (tolerance X = SCALE_VS_HANDWRITE_TOLERANCE).
"""

from __future__ import annotations

WEIGHT_TOLERANCE = 0.05
# Policy X: Δ ≤ X → warn + confirm; Δ > X → conflict (hard block).
SCALE_VS_HANDWRITE_TOLERANCE = 1.0


def as_number(value) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(" ", "")
    try:
        return float(text)
    except ValueError:
        return None


def numbers_close(left: float, right: float, tol: float = WEIGHT_TOLERANCE) -> bool:
    return abs(left - right) <= tol


def sum_field(rows: list[dict], key: str) -> float | None:
    total = 0.0
    any_value = False
    for row in rows:
        number = as_number(row.get(key))
        if number is None:
            continue
        total += number
        any_value = True
    if not any_value:
        return None
    return round(total, 3)


def scale_vs_hand_detail(photo: dict) -> dict:
    """Return tone match|warn|conflict|empty plus delta for one scale photo."""
    scale = as_number(photo.get("scale_weight_kg"))
    hand = as_number(photo.get("total_weight_kg"))
    if scale is None or hand is None:
        return {"tone": "empty", "delta": None, "label": ""}
    delta = round(abs(scale - hand), 3)
    if delta == 0 or delta <= WEIGHT_TOLERANCE:
        return {"tone": "match", "delta": delta, "label": "Match"}
    if delta <= SCALE_VS_HANDWRITE_TOLERANCE:
        return {
            "tone": "warn",
            "delta": delta,
            "label": f"OK ≤ {SCALE_VS_HANDWRITE_TOLERANCE:g} kg",
        }
    return {"tone": "conflict", "delta": delta, "label": "Conflict"}


def check_scale_vs_handwrite(photo: dict) -> str:
    """Legacy: match if Δ ≤ X, else diff. Prefer scale_vs_hand_detail for UI."""
    tone = scale_vs_hand_detail(photo)["tone"]
    if tone == "empty":
        return "empty"
    if tone in ("match", "warn"):
        return "match"
    return "diff"


def preferred_tw(photo: dict) -> float | None:
    return as_number(photo.get("total_weight_kg")) or as_number(photo.get("scale_weight_kg"))


def preferred_photo_totals(photos: list[dict]) -> dict:
    cartons = sum_field(photos, "cartons")
    tw = 0.0
    pw = 0.0
    any_tw = False
    any_pw = False
    for photo in photos:
        preferred = preferred_tw(photo)
        if preferred is not None:
            tw += preferred
            any_tw = True
        pallet = as_number(photo.get("pallet_weight_kg"))
        if pallet is not None:
            pw += pallet
            any_pw = True
    total_weight_kg = round(tw, 3) if any_tw else None
    pallet_weight_kg = round(pw, 3) if any_pw else None
    if total_weight_kg is not None and pallet_weight_kg is not None:
        net_weight_kg = round(total_weight_kg - pallet_weight_kg, 3)
    elif total_weight_kg is not None and not any_pw:
        net_weight_kg = total_weight_kg
    else:
        net_weight_kg = None
    return {
        "cartons": cartons,
        "total_weight_kg": total_weight_kg,
        "pallet_weight_kg": pallet_weight_kg,
        "net_weight_kg": net_weight_kg,
    }


def intake_save_gate(photos: list[dict]) -> dict:
    """photos: {status, extracted, warn_confirmed?} — mirrors frontend gate."""
    blockers: list[str] = []
    needs_warn_confirm = False
    if not photos:
        return {"can_save": True, "needs_warn_confirm": False, "blockers": []}
    for index, photo in enumerate(photos):
        label = f"Scale {index + 1}"
        status = photo.get("status") or "done"
        if status == "reading":
            blockers.append(f"{label} is still reading")
        if status == "error":
            blockers.append(f"{label} failed — re-check or remove")
        if status != "done":
            continue
        detail = scale_vs_hand_detail(photo.get("extracted") or photo)
        if detail["tone"] == "conflict":
            blockers.append(f"{label}: Conflict — resolve with Use scale / Use hand / Edit")
        if detail["tone"] == "warn" and not photo.get("warn_confirmed"):
            needs_warn_confirm = True
    if needs_warn_confirm:
        blockers.append(f"Confirm OK ≤ {SCALE_VS_HANDWRITE_TOLERANCE:g} kg gaps before save")
    return {
        "can_save": len(blockers) == 0,
        "needs_warn_confirm": needs_warn_confirm,
        "blockers": blockers,
    }


def _total_row(key: str, label: str, summed: float | None, message_value) -> dict:
    message_number = as_number(message_value)
    if summed is None or message_number is None:
        result = "empty"
    else:
        result = "match" if numbers_close(summed, message_number) else "diff"
    return {
        "key": key,
        "label": label,
        "summed": summed,
        "message_value": message_number,
        "result": result,
    }


def build_scale_totals(message: dict, photos: list[dict]) -> list[dict]:
    preferred = preferred_photo_totals(photos)
    sum_scale = sum_field(photos, "scale_weight_kg")
    return [
        _total_row("cartons", "Cartons sum", preferred["cartons"], message.get("cartons")),
        _total_row("scale_weight_kg", "Scale kg sum", sum_scale, message.get("total_weight_kg")),
        _total_row(
            "total_weight_kg",
            "Preferred TW sum",
            preferred["total_weight_kg"],
            message.get("total_weight_kg"),
        ),
        _total_row(
            "pallet_weight_kg",
            "Pallet PW sum",
            preferred["pallet_weight_kg"],
            message.get("pallet_weight_kg"),
        ),
        _total_row(
            "net_weight_kg",
            "Net (TW − PW)",
            preferred["net_weight_kg"],
            message.get("net_weight_kg"),
        ),
    ]


def build_note_totals(message: dict, notes: list[dict]) -> list[dict]:
    return [_total_row("cartons", "Cartons sum", sum_field(notes, "cartons"), message.get("cartons"))]
