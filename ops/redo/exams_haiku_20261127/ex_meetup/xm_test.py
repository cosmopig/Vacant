import pytest
from datetime import date

from meetup import meetup, MeetupDayException


def test_first_monday_january_2018():
    assert meetup(2018, 1, "first", "Monday") == date(2018, 1, 1)


def test_third_tuesday_august_2019():
    assert meetup(2019, 8, "third", "Tuesday") == date(2019, 8, 20)


def test_teenth_wednesday_may_2020():
    assert meetup(2020, 5, "teenth", "Wednesday") == date(2020, 5, 13)


def test_fourth_sunday_july_2021():
    assert meetup(2021, 7, "fourth", "Sunday") == date(2021, 7, 25)


def test_last_thursday_november_2022():
    assert meetup(2022, 11, "last", "Thursday") == date(2022, 11, 24)


def test_teenth_saturday_august_1953():
    assert meetup(1953, 8, "teenth", "Saturday") == date(1953, 8, 15)


def test_second_monday_august_2019():
    assert meetup(2019, 8, "second", "Monday") == date(2019, 8, 12)


def test_teenth_lower_boundary_13th_august_2019():
    # Tuesday falls on the 13th, the first day of the teenth range
    assert meetup(2019, 8, "teenth", "Tuesday") == date(2019, 8, 13)


def test_teenth_upper_boundary_19th_august_2019():
    # Monday falls on the 19th, the last day of the teenth range
    assert meetup(2019, 8, "teenth", "Monday") == date(2019, 8, 19)


def test_first_thursday_july_2021_on_first_of_month():
    assert meetup(2021, 7, "first", "Thursday") == date(2021, 7, 1)


def test_fourth_friday_may_2020_when_five_fridays_exist():
    assert meetup(2020, 5, "fourth", "Friday") == date(2020, 5, 22)


def test_fifth_friday_may_2020_exists():
    assert meetup(2020, 5, "fifth", "Friday") == date(2020, 5, 29)


def test_last_friday_february_2024_leap_year():
    assert meetup(2024, 2, "last", "Friday") == date(2024, 2, 23)


def test_last_tuesday_february_2023_non_leap_year():
    assert meetup(2023, 2, "last", "Tuesday") == date(2023, 2, 28)


def test_last_saturday_december_2025():
    assert meetup(2025, 12, "last", "Saturday") == date(2025, 12, 27)


def test_fifth_monday_february_2021_does_not_exist():
    with pytest.raises(MeetupDayException):
        meetup(2021, 2, "fifth", "Monday")
