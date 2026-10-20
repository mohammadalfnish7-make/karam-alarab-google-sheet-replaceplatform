"""Built-in prompt bodies used to seed version 1 and as fallbacks."""

from app.constants import AIR_STATUSES, EXIT_STATUSES, SEA_STAGES, SHIPPING_ROUTES

NOTE_PROMPT = (
    "Read this delivery note. Return one JSON object using only values printed on the page. "
    "Keys: company_name, date, mark, cartons, goods, party. "
    "company_name is the company that issued the note, usually the heading. "
    "Do not use the buyer when the buyer is Karam. "
    "date is YYYY-MM-DD or null. "
    "mark is the MARK value as printed, including a TL prefix. Do not shorten the digits. "
    "cartons is the integer carton count from CTN or boxes, not a piece count, or null. "
    "goods is the goods description or null. "
    "party is the party or shipper printed on the note, or null. "
    "Use null when a value is not printed."
)

SCALE_PROMPT = (
    "Read this photo of goods on a weighing scale. Return one JSON object using only values you can see. "
    "Keys: mark, cartons, total_weight_kg, pallet_weight_kg, scale_weight_kg. "
    "mark is the handwritten TL mark as written. Do not shorten the digits. "
    "cartons is the handwritten carton count, an integer or null. "
    "total_weight_kg is the handwritten total weight labeled TW, in kilograms, or null. "
    "pallet_weight_kg is the handwritten pallet weight labeled PW, in kilograms, or null. "
    "scale_weight_kg is the number shown on the digital scale display, in kilograms, or null. "
    "Do not calculate a net weight. Use null when a value is not visible."
)


def default_pdf_prompt(target: str) -> str:
    if target == "exit":
        return (
            "Extract every goods row from this PDF into a JSON array. "
            "Return only JSON, no markdown. Each object uses these keys: "
            "mark, supplier, invoice_numbers, cartons, date_of_submission, status. "
            "invoice_numbers is an array of every invoice number printed for that shipment. "
            "When a company sends more than one invoice, return each number on its own. "
            "Do not join them into one string. "
            "mark is the TL customer mark as digits only: TL4455, TL-4455, and TL 4455 all become 4455. "
            "Dates are YYYY-MM-DD or null. cartons is an integer count of cartons, CTN, or boxes, not pieces. "
            f"status is one of {EXIT_STATUSES} or null. "
            "Do not invent a row number. Do not invent rows that are not in the document. "
            "Use null for missing values."
        )
    cargo = (
        "This PDF is a supplier file for one shipment. It may contain a delivery note, a packing list, "
        "and a tax invoice, including scanned pages. Return a JSON array with one object for the whole "
        "shipment. Do not return one object per product, perfume, or invoice line. "
        "Return only JSON, no markdown. "
        "customer_code is the TL mark as digits only. TL4455, TL-4455, and TL 4455 all become 4455. "
        "Read it from a MARK column or a TL mark printed on the delivery note. "
        "company_name is the supplier or vendor that issued the document, usually the heading company. "
        "Do not use the buyer when the buyer is Karam Al Arab or Karam Al Oud. "
        "cartons is the integer count of cartons, CTN, or boxes. "
        "A line that says 6 CTN, or boxes numbered BOX-1 through BOX-6, means 6. "
        "Do not use piece counts such as PCS. "
        "gross_weight_kg is the total weight in kilograms as a number, without the KG unit. "
        "If the packing list has one WEIGHT column and a single total, put that total in gross_weight_kg. "
        "net_weight_kg is the net weight in kilograms only when the document prints net separately from gross. "
        "If only one weight is printed, net_weight_kg is null. "
        "If the document says NO PALLET, set gross_is_no_pallet true and gross_weight_kg null. "
        "Otherwise gross_is_no_pallet is false. "
        "system_code is printed text that is DL followed by digits, or null. Do not invent a system code. "
        "date_received is YYYY-MM-DD only when the document labels a received date. "
        "Do not copy the invoice date or the packing-list date into date_received. "
        "Use null for anything that is not printed."
    )
    if target == "air":
        return (
            cargo
            + " shipment_number is printed text that is AR followed by digits, or null. "
            "A supplier invoice number is not a shipment number. "
            f"status is one of {AIR_STATUSES} or null. "
            "Each object uses these keys: "
            "date_received, customer_code, company_name, cartons, gross_weight_kg, "
            "gross_is_no_pallet, net_weight_kg, system_code, shipment_number, status."
        )
    return (
        cargo
        + " shipment_number is printed text that is D followed by digits, or null. "
        "A supplier invoice number is not a shipment number. "
        f"shipping_route is one of {SHIPPING_ROUTES} or null. "
        f"stage is one of {SEA_STAGES} or null. "
        "Each object uses these keys: "
        "date_received, customer_code, company_name, cartons, gross_weight_kg, "
        "gross_is_no_pallet, net_weight_kg, system_code, shipment_number, shipping_route, stage."
    )


EXPENSE_RECEIPT_PROMPT = (
    "You are reading one or more expense receipt photos for Qusai. "
    "Return one JSON object that summarizes everything readable across all images. "
    "Return only JSON, no markdown. Use these keys: "
    "vendor, date, amount, currency, receipt_no, category, payment_method, "
    "vat_amount, subtotal, total, line_items, notes, raw_text. "
    "date is YYYY-MM-DD or null. "
    "amount, vat_amount, subtotal, and total are numbers or null. "
    "currency is a short code such as AED, USD, or EUR, or null. "
    "Prefer AED when the receipt shows Dhs, Dirham, or د.إ. "
    "category is a short label such as Meals, Transport, Parking, Hardware, Labor, Equipment, or Other, or null. "
    "payment_method is Cash, Card, or Other when visible, or null. "
    "line_items is an array of objects with keys description, qty, amount; use [] when none. "
    "notes captures handwritten remarks or useful extras. "
    "raw_text is a short free-text catch-all for leftover useful text. "
    "Use null for missing scalar values. Do not invent amounts or vendors."
)


CONTAINER_LOADING_PHOTO_PROMPT = (
    "You are reading one container loading photo of exactly two pallets (left and right). "
    "FOCUS on the bold black handwritten DETAIL LINE on each pallet — usually written under a circled mix number. "
    "That line typically looks like: CUSTOMER NAME or CODE / weight kgs / carton count ctn "
    "(example: 'HADIA RAY BNLH / 803kgs / 26ctn' or 'SY 8800 / 1089kgs / 49ctn'). "
    "Return only JSON, no markdown, with keys: pallets, issues, notes, readable. "
    "pallets must be exactly two objects with side 'left' then 'right'. "
    "Each pallet has marks: an array of objects with keys "
    "name, customer_code, mix, cartons, weight_kg, notes. "
    "For each black detail line create one mark: "
    "name = customer/brand/code part only (HADIA RAY BNLH, SY 8800, PARIS CORNER). "
    "customer_code = short code when present (SY8800, EM5550), else null. "
    "mix = the circled/large handwritten number for that pallet (often 1 left, 2 right). "
    "weight_kg = the kilograms number from that same black line (803, 1089), else null. "
    "cartons = the CTN/ctn number from that same black line (26, 49), else null. "
    "Do NOT invent a separate mark from faint logistics-only scribbles (M3, CBM, PW, space). "
    "Never put kgs/ctn/M3 text into name — put numbers into weight_kg and cartons. "
    "Multiple black customer detail lines on one pallet = multiple marks. "
    "Use marks [] when that side has no readable black detail line. "
    "issues is short problem strings. readable is true when at least one mark is readable. "
    "Do not invent marks."
)


CONTAINER_LOADING_CHECK_PROMPT = (
    "You compare a container LOADING PLAN against PHOTO EXTRACTS from loading photos. "
    "Return only JSON, no markdown, with keys: ok, matched, missing_from_photos, "
    "extra_in_photos, mismatches, notes. "
    "matched / missing_from_photos / extra_in_photos are arrays of plan or photo name strings. "
    "mismatches is an array of objects with plan_name, photo_name, detail. "
    "ok is true only when every plan line is matched and there are no important mismatches. "
    "Match flexibly on name text and mix numbers (e.g. PARIS CORNER 1). "
    "Do not invent plan lines. Prefer reporting missing_from_photos over guessing."
)


PROMPT_CATALOG: dict[str, tuple[str, str]] = {
    "intake.note": ("Intake delivery note", NOTE_PROMPT),
    "intake.scale": ("Intake scale photo", SCALE_PROMPT),
    "pdf.sea": ("PDF sea extraction", default_pdf_prompt("sea")),
    "pdf.air": ("PDF air extraction", default_pdf_prompt("air")),
    "pdf.exit": ("PDF exit extraction", default_pdf_prompt("exit")),
    "expenses.receipt": ("Expense receipt summary", EXPENSE_RECEIPT_PROMPT),
    "container_loading.photo": ("Container loading photo extract", CONTAINER_LOADING_PHOTO_PROMPT),
    "container_loading.check": ("Container loading plan check", CONTAINER_LOADING_CHECK_PROMPT),
}

APP_SETTING_KEYS = frozenset({"llm_model", "llm_timeout_sec"})
