from datetime import datetime, timedelta

from swift_scheduling import delivery_date


def test_output_is_datetime_for_fixed_and_variable_descriptions():
    """REQ: "Your task is to convert delivery date descriptions to _actual_ delivery dates, based on when the meeting started."

    Every kind of description (fixed NOW/ASAP/EOW and variable N-M/Q-N) yields a datetime instance.
    """
    start = datetime(2026, 1, 15, 9, 30)
    assert isinstance(delivery_date(start, "NOW"), datetime)
    assert isinstance(delivery_date(start, "ASAP"), datetime)
    assert isinstance(delivery_date(start, "EOW"), datetime)
    assert isinstance(delivery_date(start, "3M"), datetime)
    assert isinstance(delivery_date(start, "Q2"), datetime)


def test_now_is_two_hours_after_meeting_start():
    """REQ: "Two hours after the meeting started" (table row for "NOW").

    Meeting starts at 09:30 on 2026-01-15, so delivery is 11:30 the same day.
    """
    start = datetime(2026, 1, 15, 9, 30)
    result = delivery_date(start, "NOW")
    assert result == datetime(2026, 1, 15, 11, 30)
    assert result - start == timedelta(hours=2)


def test_now_two_hours_after_start_crosses_midnight():
    """REQ: "Two hours after the meeting started" (table row for "NOW").

    Meeting starts at 23:30 on 2026-01-15, so delivery is 01:30 on 2026-01-16.
    """
    start = datetime(2026, 1, 15, 23, 30)
    assert delivery_date(start, "NOW") == datetime(2026, 1, 16, 1, 30)


def test_asap_before_1300_is_today_at_1700():
    """REQ: "ASAP" with meeting start "Before 13:00" gives "Today at 17:00".

    Meeting starts at 09:00 on 2026-01-15, so delivery is 17:00 the same day.
    """
    start = datetime(2026, 1, 15, 9, 0)
    assert delivery_date(start, "ASAP") == datetime(2026, 1, 15, 17, 0)


def test_asap_one_second_before_1300_is_today_at_1700():
    """REQ: "ASAP" with meeting start "Before 13:00" gives "Today at 17:00".

    Boundary: meeting starts at 12:59:59, still before 13:00, so delivery is 17:00 the same day.
    """
    start = datetime(2026, 1, 15, 12, 59, 59)
    assert delivery_date(start, "ASAP") == datetime(2026, 1, 15, 17, 0)


def test_asap_at_exactly_1300_is_tomorrow_at_1300():
    """REQ: "ASAP" with meeting start "After or at 13:00" gives "Tomorrow at 13:00".

    Boundary: meeting starts exactly at 13:00 on 2026-01-15, so delivery is 13:00 on 2026-01-16.
    """
    start = datetime(2026, 1, 15, 13, 0)
    assert delivery_date(start, "ASAP") == datetime(2026, 1, 16, 13, 0)


def test_asap_after_1300_is_tomorrow_at_1300():
    """REQ: "ASAP" with meeting start "After or at 13:00" gives "Tomorrow at 13:00".

    Meeting starts at 15:45 on 2026-01-15, so delivery is 13:00 on 2026-01-16.
    """
    start = datetime(2026, 1, 15, 15, 45)
    assert delivery_date(start, "ASAP") == datetime(2026, 1, 16, 13, 0)


def test_asap_after_1300_on_last_day_of_month_rolls_into_next_month():
    """REQ: "ASAP" with meeting start "After or at 13:00" gives "Tomorrow at 13:00".

    Meeting starts at 14:00 on 2026-01-31, so tomorrow is 2026-02-01 at 13:00.
    """
    start = datetime(2026, 1, 31, 14, 0)
    assert delivery_date(start, "ASAP") == datetime(2026, 2, 1, 13, 0)


def test_eow_monday_tuesday_wednesday_is_friday_at_1700():
    """REQ: "EOW" with meeting start "Monday, Tuesday, or Wednesday" gives "Friday at 17:00".

    Starts on Mon 2026-01-05, Tue 2026-01-06 and Wed 2026-01-07 all deliver Fri 2026-01-09 at 17:00.
    """
    assert delivery_date(datetime(2026, 1, 5, 0, 0), "EOW") == datetime(2026, 1, 9, 17, 0)
    assert delivery_date(datetime(2026, 1, 6, 12, 0), "EOW") == datetime(2026, 1, 9, 17, 0)
    assert delivery_date(datetime(2026, 1, 7, 23, 59), "EOW") == datetime(2026, 1, 9, 17, 0)


def test_eow_on_monday_is_independent_of_time_of_day():
    """REQ: "EOW" with meeting start "Monday, Tuesday, or Wednesday" gives "Friday at 17:00".

    Only the weekday matters for this row: Monday 00:00 and Monday 23:59 both give Friday 17:00.
    """
    assert delivery_date(datetime(2026, 1, 5, 0, 0), "EOW") == datetime(2026, 1, 9, 17, 0)
    assert delivery_date(datetime(2026, 1, 5, 23, 59), "EOW") == datetime(2026, 1, 9, 17, 0)


def test_eow_thursday_friday_is_sunday_at_2000():
    """REQ: "EOW" with meeting start "Thursday or Friday" gives "Sunday at 20:00".

    Thu 2026-01-08 and Fri 2026-01-09 both deliver Sun 2026-01-11 at 20:00.
    """
    assert delivery_date(datetime(2026, 1, 8, 8, 0), "EOW") == datetime(2026, 1, 11, 20, 0)
    assert delivery_date(datetime(2026, 1, 9, 17, 30), "EOW") == datetime(2026, 1, 11, 20, 0)


def test_nM_before_month_is_first_workday_of_this_years_month():
    """REQ: "At 8:00 on the _first_ workday of this year's N-th month" (meeting start "Before N-th month").

    Meeting starts 2026-01-15, before March and August. March 1 2026 is a Sunday, so the first workday is
    Mon 2026-03-02. August 1 2026 is a Saturday, so the first workday is Mon 2026-08-03.
    """
    start = datetime(2026, 1, 15, 10, 0)
    assert delivery_date(start, "3M") == datetime(2026, 3, 2, 8, 0)
    assert delivery_date(start, "8M") == datetime(2026, 8, 3, 8, 0)


def test_nM_first_workday_skips_weekend_at_start_of_month():
    """REQ: "At 8:00 on the _first_ workday of this year's N-th month" (meeting start "Before N-th month").

    Boundary on weekends: February 1 2026 is a Sunday, so the first workday is Mon 2026-02-02 at 08:00.
    """
    start = datetime(2026, 1, 15, 10, 0)
    assert delivery_date(start, "2M") == datetime(2026, 2, 2, 8, 0)


def test_nM_in_or_after_month_is_first_workday_of_next_years_month():
    """REQ: "At 8:00 on the _first_ workday of next year's N-th month" (meeting start "After or in N-th month").

    Meeting starts 2026-06-10 (in June) so "6M" uses June 2027; June 1 2027 is a Tuesday.
    Meeting starts 2026-11-27 (after May) so "5M" uses May 2027; May 1 2027 is a Saturday, so Mon 2027-05-03.
    """
    assert delivery_date(datetime(2026, 6, 10, 12, 0), "6M") == datetime(2027, 6, 1, 8, 0)
    assert delivery_date(datetime(2026, 11, 27, 12, 0), "5M") == datetime(2027, 5, 3, 8, 0)


def test_nM_boundary_at_start_of_month_switches_to_next_year():
    """REQ: "After or in N-th month" vs "Before N-th month" for "<N>M".

    Boundary: 2026-02-28 23:59:59 is before March, so "3M" uses March 2026 (Mon 2026-03-02).
    2027-03-01 00:00 is in March, so "3M" uses March 2027 (Mon 2027-03-01 is a workday).
    """
    assert delivery_date(datetime(2026, 2, 28, 23, 59, 59), "3M") == datetime(2026, 3, 2, 8, 0)
    assert delivery_date(datetime(2026, 3, 1, 0, 0), "3M") == datetime(2027, 3, 1, 8, 0)


def test_Q_before_or_in_quarter_is_last_workday_of_this_years_quarter():
    """REQ: "At 8:00 on the _last_ workday of this year's N-th quarter" (meeting start "Before or in N-th quarter").

    Q1 2026 ends Tue 2026-03-31. Q4 2026 ends Thu 2026-12-31. Start 2026-01-01 is in Q1,
    start 2026-11-27 is in Q4; both use this year's quarter.
    """
    assert delivery_date(datetime(2026, 1, 1, 0, 0), "Q1") == datetime(2026, 3, 31, 8, 0)
    assert delivery_date(datetime(2026, 11, 27, 12, 0), "Q4") == datetime(2026, 12, 31, 8, 0)


def test_Q_boundary_one_minute_before_next_quarter_still_uses_this_years_quarter():
    """REQ: "At 8:00 on the _last_ workday of this year's N-th quarter" (meeting start "Before or in N-th quarter").

    Start 2026-03-31 23:59 is still before Q2, so "Q2" gives this year's Q2 end: Tue 2026-06-30 at 08:00.
    Start 2026-07-01 00:00 is in Q3, so "Q3" gives this year's Q3 end: Wed 2026-09-30 at 08:00.
    """
    assert delivery_date(datetime(2026, 3, 31, 23, 59), "Q2") == datetime(2026, 6, 30, 8, 0)
    assert delivery_date(datetime(2026, 7, 1, 0, 0), "Q3") == datetime(2026, 9, 30, 8, 0)


def test_Q_after_quarter_is_last_workday_of_next_years_quarter():
    """REQ: "At 8:00 on the _last_ workday of next year's N-th quarter" (meeting start "After N-th quarter").

    Start 2026-04-01 is after Q1, so "Q1" uses Q1 2027, which ends Wed 2027-03-31.
    Start 2026-11-27 is after Q3, so "Q3" uses Q3 2027, which ends Thu 2027-09-30.
    """
    assert delivery_date(datetime(2026, 4, 1, 0, 0), "Q1") == datetime(2027, 3, 31, 8, 0)
    assert delivery_date(datetime(2026, 11, 27, 12, 0), "Q3") == datetime(2027, 9, 30, 8, 0)


def test_Q_last_workday_skips_weekend_when_quarter_ends_on_weekend():
    """REQ: "A workday is a Monday, Tuesday, Wednesday, Thursday, or Friday." (applied to "At 8:00 on the _last_ workday of this year's N-th quarter").

    Q4 2028 ends Sun 2028-12-31, so the last workday is Fri 2028-12-29 at 08:00.
    Start 2028-11-01 is in Q4, so this year's quarter is used.
    """
    assert delivery_date(datetime(2028, 11, 1, 0, 0), "Q4") == datetime(2028, 12, 29, 8, 0)


def test_variable_results_are_at_0800_on_a_workday():
    """REQ: "At 8:00 on the _first_ workday of this year's N-th month" (and the matching quarter rule).

    For a set of "<N>M" and "Q<N>" examples, the result is exactly 08:00:00 and falls on Monday-Friday.
    """
    examples = [
        (datetime(2026, 1, 15, 10, 0), "3M"),
        (datetime(2026, 1, 15, 10, 0), "8M"),
        (datetime(2026, 11, 27, 12, 0), "5M"),
        (datetime(2026, 1, 1, 0, 0), "Q1"),
        (datetime(2026, 11, 27, 12, 0), "Q4"),
        (datetime(2026, 4, 1, 0, 0), "Q1"),
        (datetime(2028, 11, 1, 0, 0), "Q4"),
    ]
    for start, description in examples:
        result = delivery_date(start, description)
        assert result.hour == 8, description
        assert result.minute == 0, description
        assert result.second == 0, description
        assert result.microsecond == 0, description
        assert result.weekday() < 5, description


def test_delivery_is_strictly_after_meeting_start_for_all_examples():
    """REQ: "convert delivery date descriptions to _actual_ delivery dates, based on when the meeting started." (every row of the tables implies a delivery after the meeting start).

    For each documented example, the delivery date is later than the meeting start.
    """
    examples = [
        (datetime(2026, 1, 15, 9, 30), "NOW"),
        (datetime(2026, 1, 15, 9, 0), "ASAP"),
        (datetime(2026, 1, 15, 15, 45), "ASAP"),
        (datetime(2026, 1, 7, 23, 59), "EOW"),
        (datetime(2026, 1, 8, 8, 0), "EOW"),
        (datetime(2026, 1, 15, 10, 0), "3M"),
        (datetime(2026, 6, 10, 12, 0), "6M"),
        (datetime(2026, 1, 1, 0, 0), "Q1"),
        (datetime(2026, 4, 1, 0, 0), "Q1"),
        (datetime(2026, 11, 27, 12, 0), "Q4"),
    ]
    for start, description in examples:
        assert delivery_date(start, description) > start, description
