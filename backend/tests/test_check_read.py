from app.check_read import normalize_check


def test_delivery_note_fields_keep_printed_mark_and_cartons():
    fields = normalize_check(
        "delivery_note",
        {
            "company_name": "  MADINAH   AL NOOR PERFUMES TRADING LLC ",
            "date": "29 SEP 2026",
            "mark": "TL-4455",
            "cartons": "6CTN",
            "goods": "PERFUME GOODS",
            "party": "KARAM AL OUD PERFUMES CO.LLC",
        },
    )
    assert fields["company_name"] == "MADINAH AL NOOR PERFUMES TRADING LLC"
    assert fields["date"] == "2026-09-29"
    assert fields["mark"] == "TL-4455"
    assert fields["cartons"] == 6
    assert fields["goods"] == "PERFUME GOODS"


def test_scale_photo_keeps_display_and_handwritten_weights():
    fields = normalize_check(
        "scale",
        {
            "mark": "TL4455",
            "cartons": "6 CTN",
            "total_weight_kg": "122.5KG",
            "pallet_weight_kg": "15 .5",
            "scale_weight_kg": 122.5,
        },
    )
    assert fields["mark"] == "TL4455"
    assert fields["cartons"] == 6
    assert fields["total_weight_kg"] == 122.5
    assert fields["pallet_weight_kg"] == 15.5
    assert fields["scale_weight_kg"] == 122.5
