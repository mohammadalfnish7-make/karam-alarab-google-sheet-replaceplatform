from app.pdf_service import normalize_extracted_row


def test_supplier_pdf_fills_cargo_fields_and_drops_invoice_numbers():
    row = normalize_extracted_row(
        "sea",
        {
            "customer_code": "TL-445",
            "company_name": "  MADINAH AL NOOR   PERFUMES TRADING LLC ",
            "cartons": "6 CTN",
            "gross_weight_kg": "106.2KG",
            "net_weight_kg": None,
            "gross_is_no_pallet": False,
            "system_code": "MANPTL/26/918",
            "shipment_number": "MANPTL/26/918",
            "date_received": "",
        },
        "MADINAH AL NOOR TL4455 VAT.pdf",
    )
    assert row["customer_code"] == "4455"
    assert row["company_name"] == "MADINAH AL NOOR PERFUMES TRADING LLC"
    assert row["cartons"] == 6
    assert row["gross_weight_kg"] == 106.2
    assert row["net_weight_kg"] is None
    assert row["system_code"] is None
    assert row["shipment_number"] is None
    assert row["date_received"] is None


def test_printed_system_and_shipment_codes_are_kept():
    row = normalize_extracted_row(
        "sea",
        {
            "customer_code": "4455",
            "company_name": "TOP LUXURY",
            "cartons": 1,
            "gross_weight_kg": "NO PALLET",
            "net_weight_kg": "2.5",
            "system_code": "dl545",
            "shipment_number": "D 1201",
        },
        "load.pdf",
    )
    assert row["customer_code"] == "4455"
    assert row["gross_is_no_pallet"] is True
    assert row["gross_weight_kg"] is None
    assert row["net_weight_kg"] == 2.5
    assert row["system_code"] == "DL545"
    assert row["shipment_number"] == "D1201"


def test_air_shipment_keeps_ar_prefix_only():
    row = normalize_extracted_row(
        "air",
        {
            "customer_code": "TL 874",
            "company_name": "NEST",
            "cartons": 2,
            "shipment_number": "AR 88",
            "system_code": "D1201",
        },
        "",
    )
    assert row["customer_code"] == "874"
    assert row["shipment_number"] == "AR88"
    assert row["system_code"] is None
