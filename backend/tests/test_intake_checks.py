from app.intake_checks import (
    build_note_totals,
    build_scale_totals,
    check_scale_vs_handwrite,
    sum_field,
)


def test_sum_field_adds_partial_pallet_values():
    photos = [
        {"cartons": 34, "scale_weight_kg": 87.9, "total_weight_kg": 87.9, "pallet_weight_kg": None},
        {"cartons": 40, "scale_weight_kg": 94.2, "total_weight_kg": 94.2, "pallet_weight_kg": 2.3},
        {"cartons": 37, "scale_weight_kg": 113.65, "total_weight_kg": 113.7, "pallet_weight_kg": 2.3},
        {"cartons": 43, "scale_weight_kg": 87.45, "total_weight_kg": 87.5, "pallet_weight_kg": 2.3},
        {"cartons": 40, "scale_weight_kg": 81.25, "total_weight_kg": 81.25, "pallet_weight_kg": 2.1},
    ]
    assert sum_field(photos, "cartons") == 194
    assert sum_field(photos, "scale_weight_kg") == 464.45
    assert sum_field(photos, "total_weight_kg") == 464.55
    assert sum_field(photos, "pallet_weight_kg") == 9.0


def test_scale_vs_handwrite_flags_mismatch_within_tolerance():
    assert check_scale_vs_handwrite({"scale_weight_kg": 113.65, "total_weight_kg": 113.7}) == "match"
    assert check_scale_vs_handwrite({"scale_weight_kg": 342.5, "total_weight_kg": 343.5}) == "match"
    assert check_scale_vs_handwrite({"scale_weight_kg": 100, "total_weight_kg": 101}) == "match"
    assert check_scale_vs_handwrite({"scale_weight_kg": 100, "total_weight_kg": 101.01}) == "diff"
    assert check_scale_vs_handwrite({"scale_weight_kg": 100, "total_weight_kg": 110}) == "diff"
    assert check_scale_vs_handwrite({"scale_weight_kg": 100, "total_weight_kg": None}) == "empty"


def test_scale_totals_match_message_and_note_cartons():
    # Message totals align with preferred TW (hand TW) and net = TW − PW.
    message = {
        "cartons": 194,
        "total_weight_kg": 464.55,
        "pallet_weight_kg": 9,
        "net_weight_kg": 455.55,
    }
    photos = [
        {"cartons": 34, "scale_weight_kg": 87.9, "total_weight_kg": 87.9, "pallet_weight_kg": None},
        {"cartons": 40, "scale_weight_kg": 94.2, "total_weight_kg": 94.2, "pallet_weight_kg": 2.3},
        {"cartons": 37, "scale_weight_kg": 113.65, "total_weight_kg": 113.7, "pallet_weight_kg": 2.3},
        {"cartons": 43, "scale_weight_kg": 87.45, "total_weight_kg": 87.5, "pallet_weight_kg": 2.3},
        {"cartons": 40, "scale_weight_kg": 81.25, "total_weight_kg": 81.25, "pallet_weight_kg": 2.1},
    ]
    rows = {row["key"]: row for row in build_scale_totals(message, photos)}
    assert rows["cartons"]["result"] == "match"
    assert rows["total_weight_kg"]["result"] == "match"
    assert rows["pallet_weight_kg"]["result"] == "match"
    assert rows["net_weight_kg"]["result"] == "match"

    note_rows = build_note_totals(message, [{"cartons": 194}])
    assert note_rows[0]["result"] == "match"


def test_scale_totals_flag_message_mismatch():
    message = {"cartons": 190, "total_weight_kg": 350, "pallet_weight_kg": 9, "net_weight_kg": 341}
    photos = [
        {"cartons": 100, "scale_weight_kg": 200, "total_weight_kg": 200, "pallet_weight_kg": 4},
        {"cartons": 100, "scale_weight_kg": 200, "total_weight_kg": 200, "pallet_weight_kg": 5},
    ]
    rows = {row["key"]: row for row in build_scale_totals(message, photos)}
    assert rows["cartons"]["result"] == "diff"
    assert rows["scale_weight_kg"]["result"] == "diff"
