# Intake weight & identity policy

Status: **implemented in intake UI + cargo save** — operator tutorials still later.  
Audience: product, engineering, and future operator training.

Tolerance **X** defaults to **1 kg** unless ops changes it. Wording in the UI uses that value (e.g. “OK ≤ 1 kg”).

---

## 1. Authority

| Question | Decision |
|----------|----------|
| What is authoritative for **gross weight (kg)**? | **Digital scale**, with **human confirm** when there is any disagreement. |
| Identity (**mark / CTN**) | Prefer **handwriting + message**, not the scale. |
| Net weight | **TW − PW** (preferred TW minus pallet/tare PW), using per-pallet preferred values then summed. |

### Weight vs identity (CTO rule of thumb)

- **Weight kg** → prefer digital scale when conflict is large; operator must confirm or override.
- **Mark / CTN** → prefer handwriting and the chat message; never invent from the scale display.

---

## 2. Scale vs handwritten TW on the same photo

Let **Δ** = `|scale_kg − handwritten_TW|`.

| Case | Chip | Save |
|------|------|------|
| Δ = 0 (or tiny rounding) | **Match** | Allowed |
| Δ ≤ X kg | **OK ≤ X kg** (warn) | Allowed only after **force confirm** (checkbox / explicit confirm) |
| Δ > X kg | **Conflict** | **Hard block** — operator must resolve before save. Save only when everything is done. |

“Everything is done” means: every note/photo is read or removed, every Conflict is resolved, and any ≤ X warn has been confirmed.

---

## 3. Two mismatch types (separate policies)

### A) Scale value looks wrong (hand / message look OK)

Usually the **physical scale is fine**; the **reading model misread** the display.

| Action | Decision |
|--------|----------|
| Operator override of scale field | **Allowed** (operators and admin) |
| Flag shipment | Set **`needs_review`** when scale was overridden (or conflict involved scale override) |
| Re-photograph | **Not required at this stage** |

### B) Handwriting looks wrong (scale looks OK)

| Action | Decision |
|--------|----------|
| Extracted fields | **Editable** (TW, and other extract fields as needed) |
| Prefer scale for TW when Δ > X | Yes, as the default recovery path (e.g. “Use scale for TW”), still with human action |
| Re-check from image | Available as a recovery action (see UX) |

---

## 4. UX (what the operator sees)

| Decision | Locked choice |
|----------|----------------|
| Show both scale and hand always? | **Yes** |
| Chip language | **Match** / **OK ≤ X kg** / **Conflict** |
| Recovery actions | **Edit** · **Use scale** · **Use hand** · **Re-check** · **Remove photo** |
| Save on ≤ X warn | Soft warn + **confirm checkbox** (force confirm) |
| Save on Conflict (Δ > X) | **Hard block** until resolved |
| Multi-pallet totals | Sum **preferred** kg per photo (after resolve/confirm), not raw conflicting pairs |

Always show both raw values even after override, so the operator can see what the model first read.

---

## 5. What gets saved & audited

| Decision | Locked choice |
|----------|----------------|
| Sheet / cargo row | Save **extracted values + overrides** (preferred/final fields used for the row) |
| Audit trail | Log **original extract**, **override**, **who**, **why** — **all** of these |
| Agent tracking | Existing agent runs stay; also **store override events** (linked to user and photo/source) |
| Net weight | **TW − PW** from preferred per-pallet values (then totals as designed) |

---

## 6. Ops / roles

| Decision | Locked choice |
|----------|----------------|
| Who can override? | **Operators and admin** |
| When to re-photograph? | **Not for this stage** (fix with edit / use scale / use hand / re-check) |

---

## 7. Operator case guide (for future tutorials)

Use this as the outline for training content. Each case = what they see + what they do + when save unlocks.

### Case 1 — Match

- Chip: Match  
- Action: none  
- Save: OK  

### Case 2 — OK ≤ X kg (warn)

- Chip: OK ≤ X kg  
- Action: read both numbers; tick **confirm** that the gap is acceptable  
- Save: blocked until confirm  

### Case 3 — Conflict, handwriting likely wrong (e.g. TW 8869 vs scale 869)

- Chip: Conflict  
- Prefer: **Use scale for TW** or **Edit** hand TW  
- Optional: **Re-check**  
- Save: blocked until Conflict cleared  

### Case 4 — Conflict, scale reading likely wrong (model misread display)

- Chip: Conflict  
- Prefer: **Edit** scale field or **Use hand** if handwriting is clear  
- Flag: **`needs_review`** when scale was overridden  
- Save: blocked until Conflict cleared  

### Case 5 — Identity (mark / CTN) disagrees with message

- Prefer message + handwriting on notes/photos  
- Edit extract or message as needed; do not take mark from scale digits  
- Save: follow same “everything done” rule for any remaining weight conflicts  

### Case 6 — Multi-pallet

- Resolve each photo (Match / confirmed ≤ X / resolved Conflict)  
- Totals use **preferred** per photo  
- Net = sum of preferred TW − sum of PW (or equivalent per-pallet then sum — implement consistently)  
- Save: only when all photos are resolved and confirms are done  

---

## 8. Implementation notes

Shipped against this policy:

1. Tolerance **X** = `SCALE_VS_HANDWRITE_TOLERANCE` (default 1) in `frontend/src/intake.ts` and `backend/app/intake_checks.py`.  
2. Chips Match / OK ≤ X kg / Conflict; force-confirm checkbox; hard block on Conflict / unread / failed sources.  
3. Editable extract + Use scale / Use hand / Re-check / Remove on Intake page.  
4. Save sends `intake_check` (originals, overrides, preferred); audit `after_json` stores it; `AgentRun` `intake.override` records override events.  
5. `needs_review` set when scale was overridden (`use_hand` or edit of scale kg).  
6. Operator tutorials from §7 still later.

Related demos (UX exploration): `/demo/intake/tw-fix`.

---

## 9. Decision log

| Date | Decision |
|------|----------|
| 2026-10-17 | Locked policy in this doc from CTO / product answers (scale + human confirm; ≤ X warn+confirm; > X block; editable extract; overrides by operator/admin; full audit; override events; net = TW−PW; no re-photo stage). |
