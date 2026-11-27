import datetime

from swift_scheduling import delivery_date


def test_now_is_two_hours_after_meeting_start():
    start = datetime.datetime(2012, 12, 21, 10, 0)  # Friday
    assert delivery_date(start, "NOW") == datetime.datetime(2012, 12, 21, 12, 0)


def test_now_crosses_midnight():
    start = datetime.datetime(2012, 12, 21, 23, 30)  # Friday
    assert delivery_date(start, "NOW") == datetime.datetime(2012, 12, 22, 1, 30)


def test_asap_before_13_is_today_at_17():
    start = datetime.datetime(2012, 12, 21, 10, 0)  # Friday
    assert delivery_date(start, "ASAP") == datetime.datetime(2012, 12, 21, 17, 0)


def test_asap_just_before_13_is_today_at_17():
    start = datetime.datetime(2012, 12, 21, 12, 59)  # Friday
    assert delivery_date(start, "ASAP") == datetime.datetime(2012, 12, 21, 17, 0)


def test_asap_at_13_is_tomorrow_at_13():
    start = datetime.datetime(2012, 12, 21, 13, 0)  # Friday
    assert delivery_date(start, "ASAP") == datetime.datetime(2012, 12, 22, 13, 0)


def test_asap_after_13_is_tomorrow_at_13():
    start = datetime.datetime(2012, 12, 21, 14, 30)  # Friday
    assert delivery_date(start, "ASAP") == datetime.datetime(2012, 12, 22, 13, 0)


def test_eow_monday_is_friday_at_17():
    start = datetime.datetime(2012, 12, 24, 9, 0)  # Monday
    assert delivery_date(start, "EOW") == datetime.datetime(2012, 12, 28, 17, 0)


def test_eow_tuesday_is_friday_at_17():
    start = datetime.datetime(2012, 12, 25, 9, 0)  # Tuesday
    assert delivery_date(start, "EOW") == datetime.datetime(2012, 12, 28, 17, 0)


def test_eow_wednesday_is_friday_at_17():
    start = datetime.datetime(2012, 12, 26, 9, 0)  # Wednesday
    assert delivery_date(start, "EOW") == datetime.datetime(2012, 12, 28, 17, 0)


def test_eow_thursday_is_sunday_at_20():
    start = datetime.datetime(2012, 12, 27, 9, 0)  # Thursday
    assert delivery_date(start, "EOW") == datetime.datetime(2012, 12, 30, 20, 0)


def test_eow_friday_is_sunday_at_20():
    start = datetime.datetime(2012, 12, 28, 9, 0)  # Friday
    assert delivery_date(start, "EOW") == datetime.datetime(2012, 12, 30, 20, 0)


def test_month_before_n_uses_this_year():
    start = datetime.datetime(2012, 3, 15, 10, 0)
    assert delivery_date(start, "5M") == datetime.datetime(2012, 5, 1, 8, 0)


def test_month_in_n_uses_next_year():
    start = datetime.datetime(2012, 5, 15, 10, 0)
    assert delivery_date(start, "5M") == datetime.datetime(2013, 5, 1, 8, 0)


def test_month_after_n_uses_next_year():
    start = datetime.datetime(2012, 12, 21, 10, 0)
    assert delivery_date(start, "3M") == datetime.datetime(2013, 3, 1, 8, 0)


def test_month_first_day_on_weekend_uses_first_workday():
    # September 1, 2012 is a Saturday, so the first workday is Monday, September 3.
    start = datetime.datetime(2012, 6, 10, 10, 0)
    assert delivery_date(start, "9M") == datetime.datetime(2012, 9, 3, 8, 0)


def test_quarter_in_n_uses_this_years_last_workday():
    start = datetime.datetime(2012, 12, 21, 10, 0)  # in Q4
    assert delivery_date(start, "Q4") == datetime.datetime(2012, 12, 31, 8, 0)


def test_quarter_before_n_uses_this_years_last_workday():
    start = datetime.datetime(2012, 2, 10, 10, 0)  # in Q1
    # June 30, 2012 is a Saturday, so the last workday is Friday, June 29.
    assert delivery_date(start, "Q2") == datetime.datetime(2012, 6, 29, 8, 0)


def test_quarter_same_quarter_is_this_years_last_workday():
    start = datetime.datetime(2012, 5, 1, 10, 0)  # in Q2
    assert delivery_date(start, "Q2") == datetime.datetime(2012, 6, 29, 8, 0)


def test_quarter_after_n_uses_next_years_last_workday():
    start = datetime.datetime(2012, 12, 21, 10, 0)  # after Q1
    # March 31, 2013 is a Sunday, so the last workday is Friday, March 29.
    assert delivery_date(start, "Q1") == datetime.datetime(2013, 3, 29, 8, 0)
