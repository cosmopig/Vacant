from datetime import datetime

from swift_scheduling import delivery_date


def test_now_is_two_hours_after_meeting_start():
    # SRC: "Two hours after the meeting started"
    assert delivery_date(datetime(2024, 1, 1, 10, 0), "NOW") == datetime(2024, 1, 1, 12, 0)


def test_now_crosses_midnight():
    # SRC: "Two hours after the meeting started"
    assert delivery_date(datetime(2024, 1, 1, 23, 30), "NOW") == datetime(2024, 1, 2, 1, 30)


def test_asap_before_13_is_today_at_17():
    # SRC: "Today at 17:00"
    assert delivery_date(datetime(2024, 1, 1, 10, 0), "ASAP") == datetime(2024, 1, 1, 17, 0)


def test_asap_one_minute_before_13_is_today_at_17():
    # SRC: "Before 13:00"
    assert delivery_date(datetime(2024, 1, 1, 12, 59), "ASAP") == datetime(2024, 1, 1, 17, 0)


def test_asap_at_13_is_tomorrow_at_13():
    # SRC: "After or at 13:00"
    assert delivery_date(datetime(2024, 1, 1, 13, 0), "ASAP") == datetime(2024, 1, 2, 13, 0)


def test_asap_after_13_is_tomorrow_at_13_across_month_end():
    # SRC: "Tomorrow at 13:00"
    assert delivery_date(datetime(2024, 1, 31, 14, 0), "ASAP") == datetime(2024, 2, 1, 13, 0)


def test_eow_on_monday_is_friday_at_17():
    # SRC: "Monday, Tuesday, or Wednesday"
    assert delivery_date(datetime(2024, 1, 1, 9, 0), "EOW") == datetime(2024, 1, 5, 17, 0)


def test_eow_on_wednesday_is_friday_at_17():
    # SRC: "Friday at 17:00"
    assert delivery_date(datetime(2024, 1, 3, 9, 0), "EOW") == datetime(2024, 1, 5, 17, 0)


def test_eow_on_thursday_is_sunday_at_20():
    # SRC: "Thursday or Friday"
    assert delivery_date(datetime(2024, 1, 4, 9, 0), "EOW") == datetime(2024, 1, 7, 20, 0)


def test_eow_on_friday_is_sunday_at_20():
    # SRC: "Sunday at 20:00"
    assert delivery_date(datetime(2024, 1, 5, 9, 0), "EOW") == datetime(2024, 1, 7, 20, 0)


def test_month_before_nth_month_is_first_workday_this_year():
    # SRC: "At 8:00 on the _first_ workday of this year's N-th month"
    assert delivery_date(datetime(2024, 2, 10, 9, 0), "6M") == datetime(2024, 6, 3, 8, 0)


def test_month_in_nth_month_is_first_workday_next_year():
    # SRC: "After or in N-th month"
    assert delivery_date(datetime(2024, 6, 15, 9, 0), "6M") == datetime(2025, 6, 2, 8, 0)


def test_month_after_nth_month_is_first_workday_next_year():
    # SRC: "At 8:00 on the _first_ workday of next year's N-th month"
    assert delivery_date(datetime(2024, 7, 1, 9, 0), "3M") == datetime(2025, 3, 3, 8, 0)


def test_quarter_before_nth_quarter_is_last_workday_this_year():
    # SRC: "At 8:00 on the _last_ workday of this year's N-th quarter"
    assert delivery_date(datetime(2024, 2, 1, 9, 0), "Q1") == datetime(2024, 3, 29, 8, 0)


def test_quarter_in_nth_quarter_is_last_workday_this_year():
    # SRC: "Before or in N-th quarter"
    assert delivery_date(datetime(2024, 6, 30, 9, 0), "Q2") == datetime(2024, 6, 28, 8, 0)


def test_quarter_after_nth_quarter_is_last_workday_next_year():
    # SRC: "At 8:00 on the _last_ workday of next year's N-th quarter"
    assert delivery_date(datetime(2024, 7, 15, 9, 0), "Q2") == datetime(2025, 6, 30, 8, 0)


def test_quarter_after_nth_quarter_for_q1_from_q2():
    # SRC: "After N-th quarter"
    assert delivery_date(datetime(2024, 4, 1, 9, 0), "Q1") == datetime(2025, 3, 31, 8, 0)
