# System notes

## Exit tracker invoice number

Some companies, such as EMAROS, send multiple invoices, not one. The exit tracker must keep every invoice number for that shipment, not a single invoice only.

## Cash payments

Qusai is responsible for paying cash, with a limit of 2000 DH, for some warehouse staff. The payments cover company expenses such as stretch film, pallets, security tips, and car oil.

## Mark prefixes (future)

Marks are not TL-only. Real codes use prefixes such as TL, MO, SY, and EM (and others like GR). Today intake and PDF extract hardcode TL and often store digits only; the sheet also keeps letter prefixes for non-TL marks.

When we generalize:

1. Store mark prefixes (and/or full mark families) in a table so new prefixes can be added without code changes.
2. Parse and normalize marks from that table, not from a hardcoded TL regex.
3. Connect each mark (or mark family) to a driver so cargo/exit flows know which driver owns that mark.

## Intake sample: French Avenue / TL5523

Example chat intake from 16/10/2026. Image: `intake/examples/french-avenue-tl5523-2026-10-16.jpg`.

One message bundle has three parts:

1. **Delivery note** — French Avenue General Trading LLC, DO/SO numbers, buyer, goods list, total **194 CTN**.
2. **Pallet scale photos** — several pallets, each handwritten with the same mark **TL5523**, carton count, TW, and often PW; scale reading visible under the load.
3. **Text summary** — system/shipment style code **D1247**, date, mark **TL5523**, total **CTN 194**, then weight line(s).

What this implies for the system:

- Mark is repeated on every pallet; pallet cartons must sum to the delivery-note / message total (here 34+40+37+43+40 = 194).
- Intake is not one photo: delivery note + N pallet photos + short text.
- Per-pallet CTN / TW / PW are real fields before the cargo row totals are trusted.
- Company name on the note (French Avenue) is separate from the TL mark (5523 / TL5523).

## LLM providers (evolvable)

Image/PDF reading goes through `backend/app/agents/providers/`. Default:

- `LLM_PROVIDER=anthropic`
- `LLM_MODEL=claude-haiku-5-5`
- `ANTHROPIC_API_KEY=...`

To add a future provider: implement `DocumentProvider` in a new module, call `register(...)`, set `LLM_PROVIDER` / `LLM_MODEL`. Do not hardcode provider branches in intake/PDF routes.

Multi-image intake uses `/api/intake/read-batch` so reads run in parallel.

## Developer tracking

Admin **Tracking** page (`/runs`):

1. **Agent runs** — every intake/PDF model call: provider, model, total `duration_ms`, per-step timing, token usage, input/output, errors.
2. **HTTP requests** — every `/api/*` call (except health): method, path, status, `duration_ms`, user, IP.

## Multi-scale photos: sum and cross-check

When intake has more than one scale image for the same shipment:

1. Read each scale photo (digital reading) and each handwritten TW / PW / CTN on that pallet.
2. **Sum** the weights across all scale images to get the shipment total.
3. **Check** that total against the weight line(s) in the chat message.
4. **Check** each scale reading against the handwritten weight on the same pallet (and flag mismatch).
5. Same idea for cartons: sum per-pallet CTN and check against message CTN and delivery-note total.

Do not trust a single source alone — scale, handwriting, and message must agree under the locked policy.

### Scale vs handwritten (locked policy)

Full decisions (authority, ≤ X warn+confirm, > X hard block, overrides, audit, operator cases for tutorials): see [docs/intake-weight-policy.md](docs/intake-weight-policy.md).

Summary:

- Gross kg authority: **digital scale + human confirm**.
- Mark / CTN: **handwriting + message**.
- Δ ≤ X kg (default X = 1): chip **OK ≤ X kg**, **force confirm** before save.
- Δ > X kg: chip **Conflict**, **block save** until resolved (edit / use scale / use hand / re-check).
- Save extracted + overrides; full audit; override events in agent tracking; net = TW − PW.
- Scale “wrong” is usually a **model misread** — allow scale override and flag **`needs_review`**.
