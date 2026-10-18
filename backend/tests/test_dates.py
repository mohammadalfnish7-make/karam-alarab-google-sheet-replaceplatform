from datetime import date

from app.validation import bring_date_not_after_today, parse_compact_dmy
from tests.conftest import login, sea_payload

TODAY = date(2026, 10, 13)


def test_swapped_month_and_day_come_back_before_today():
    assert bring_date_not_after_today(date(2026, 11, 2), TODAY) == date(2026, 2, 11)
    assert bring_date_not_after_today(date(2026, 12, 9), TODAY) == date(2026, 9, 12)


def test_filled_down_year_returns_to_this_year():
    assert bring_date_not_after_today(date(2037, 2, 28), TODAY) == date(2026, 2, 28)
    assert bring_date_not_after_today(date(2029, 8, 18), TODAY) == date(2026, 8, 18)


def test_exit_serials_are_the_typed_day_and_month():
    assert bring_date_not_after_today(date(2026, 11, 7), TODAY) == date(2026, 7, 11)
    assert bring_date_not_after_today(date(2026, 11, 6), TODAY) == date(2026, 6, 11)


def test_missing_slash_is_day_then_month():
    assert parse_compact_dmy("1107/2026") == date(2026, 7, 11)


def test_dates_on_or_before_today_stay():
    assert bring_date_not_after_today(date(2026, 10, 10), TODAY) == date(2026, 10, 10)
    assert bring_date_not_after_today(date(2026, 2, 11), TODAY) == date(2026, 2, 11)


def test_new_row_cannot_use_a_date_after_today(client):
    login(client)
    response = client.post("/api/sea", json=sea_payload(date_received="2099-01-15", system_code="DL9901"))
    assert response.status_code == 422
    assert response.json()["field_errors"]["date_received"] == "Date is after today"
