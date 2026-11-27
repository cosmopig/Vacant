import datetime

import pytest

from meetup import MeetupDayException, meetup


def test_example_dates_from_requirements():
    # SRC: "the first Monday in January 2018 (January 1, 2018)"
    assert meetup(2018, 1, "first", "Monday") == datetime.date(2018, 1, 1)
    # SRC: "the third Tuesday of August 2019 (August 20, 2019)"
    assert meetup(2019, 8, "third", "Tuesday") == datetime.date(2019, 8, 20)
    # SRC: "the teenth Wednesday of May 2020 (May 13, 2020)"
    assert meetup(2020, 5, "teenth", "Wednesday") == datetime.date(2020, 5, 13)
    # SRC: "the fourth Sunday of July 2021 (July 25, 2021)"
    assert meetup(2021, 7, "fourth", "Sunday") == datetime.date(2021, 7, 25)
    # SRC: "the last Thursday of November 2022 (November 24, 2022)"
    assert meetup(2022, 11, "last", "Thursday") == datetime.date(2022, 11, 24)
    # SRC: "the teenth Saturday of August 1953 (August 15, 1953)"
    assert meetup(1953, 8, "teenth", "Saturday") == datetime.date(1953, 8, 15)


def test_second_and_third_week_values():
    # SRC: "There are six week values to consider"
    assert meetup(2018, 1, "second", "Tuesday") == datetime.date(2018, 1, 9)
    # SRC: "There are six week values to consider"
    assert meetup(2018, 1, "third", "Monday") == datetime.date(2018, 1, 15)


def test_last_week_value_including_month_end():
    # SRC: "the last Thursday of November 2022 (November 24, 2022)"
    assert meetup(2018, 1, "last", "Wednesday") == datetime.date(2018, 1, 31)
    # SRC: "the last Thursday of November 2022 (November 24, 2022)"
    assert meetup(2021, 2, "last", "Sunday") == datetime.date(2021, 2, 28)


def test_teenth_boundary_days():
    # SRC: "The teenth week refers to the seven days in a month that end in '-teenth' (13th, 14th, 15th, 16th, 17th, 18th and 19th)."
    assert meetup(2018, 2, "teenth", "Monday") == datetime.date(2018, 2, 19)
    # SRC: "The teenth week refers to the seven days in a month that end in '-teenth' (13th, 14th, 15th, 16th, 17th, 18th and 19th)."
    assert meetup(2018, 2, "teenth", "Sunday") == datetime.date(2018, 2, 18)


def test_fifth_weekday_exists():
    # SRC: "We have added an additional week descriptor (`fifth`) for the fifth weekday of the month, if there is one."
    assert meetup(2018, 1, "fifth", "Monday") == datetime.date(2018, 1, 29)


def test_fifth_weekday_missing_raises():
    # SRC: "If there is not a fifth weekday in a month, you should raise an exception."
    with pytest.raises(MeetupDayException):
        meetup(2018, 2, "fifth", "Monday")
