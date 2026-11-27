import calendar
import datetime

import pytest

from meetup import meetup, MeetupDayException


_DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_YEARS = range(2000, 2031)
_MONTHS = range(1, 13)


def test_returns_date_object():
    """REQ: "Your task is to find the exact date of a meetup, given a month, year, weekday and week."

    The result is a calendar date (datetime.date), as implied by "the exact date".
    """
    result = meetup(2018, 1, "first", "Monday")
    assert isinstance(result, datetime.date)


def test_example_first_monday_january_2018():
    """REQ: "For example, you might be asked to find the date for the meetup on the first Monday in January 2018 (January 1, 2018)."

    Expected value from the text: January 1, 2018.
    """
    assert meetup(2018, 1, "first", "Monday") == datetime.date(2018, 1, 1)


def test_example_third_tuesday_august_2019():
    """REQ: "the third Tuesday of August 2019 (August 20, 2019)"

    Expected value from the text: August 20, 2019.
    """
    assert meetup(2019, 8, "third", "Tuesday") == datetime.date(2019, 8, 20)


def test_example_teenth_wednesday_may_2020():
    """REQ: "the teenth Wednesday of May 2020 (May 13, 2020)"

    Expected value from the text: May 13, 2020.
    """
    assert meetup(2020, 5, "teenth", "Wednesday") == datetime.date(2020, 5, 13)


def test_example_fourth_sunday_july_2021():
    """REQ: "the fourth Sunday of July 2021 (July 25, 2021)"

    Expected value from the text: July 25, 2021.
    """
    assert meetup(2021, 7, "fourth", "Sunday") == datetime.date(2021, 7, 25)


def test_example_last_thursday_november_2022():
    """REQ: "the last Thursday of November 2022 (November 24, 2022)"

    Expected value from the text: November 24, 2022.
    """
    assert meetup(2022, 11, "last", "Thursday") == datetime.date(2022, 11, 24)


def test_example_teenth_saturday_august_1953():
    """REQ: "If asked to find the teenth Saturday of August, 1953, we check its calendar ... From this we find that the teenth Saturday is August 15, 1953."

    Expected value from the text: August 15, 1953.
    """
    assert meetup(1953, 8, "teenth", "Saturday") == datetime.date(1953, 8, 15)


def test_teenth_always_between_13_and_19():
    """REQ: "The teenth week refers to the seven days in a month that end in '-teenth' (13th, 14th, 15th, 16th, 17th, 18th and 19th)."

    Invariant: the teenth date always falls on day 13 to 19 of the month.
    """
    for year in _YEARS:
        for month in _MONTHS:
            for day_name in _DAY_NAMES:
                result = meetup(year, month, "teenth", day_name)
                assert 13 <= result.day <= 19, (
                    f"teenth {day_name} of {year}-{month:02d} gave {result}"
                )


def test_teenth_lower_boundary_is_13():
    """REQ: "The teenth week refers to the seven days in a month that end in '-teenth' (13th, 14th, 15th, 16th, 17th, 18th and 19th)."

    May 2013: the Mondays are the 6th and 13th, so the teenth Monday is the 13th.
    """
    assert meetup(2013, 5, "teenth", "Monday") == datetime.date(2013, 5, 13)


def test_teenth_upper_boundary_is_19():
    """REQ: "The teenth week refers to the seven days in a month that end in '-teenth' (13th, 14th, 15th, 16th, 17th, 18th and 19th)."

    August 2019: the Mondays are the 5th, 12th, 19th and 26th, so the teenth Monday is the 19th.
    """
    assert meetup(2019, 8, "teenth", "Monday") == datetime.date(2019, 8, 19)


def test_ordinal_weeks_fall_in_expected_day_ranges():
    """REQ: "There are six week values to consider: `first`, `second`, `third`, `fourth`, `last`, `teenth`."

    Invariant: first, second, third and fourth fall on days 1-7, 8-14, 15-21 and 22-28 respectively.
    """
    expected = {
        "first": (1, 7),
        "second": (8, 14),
        "third": (15, 21),
        "fourth": (22, 28),
    }
    for year in _YEARS:
        for month in _MONTHS:
            for day_name in _DAY_NAMES:
                for week, (low, high) in expected.items():
                    result = meetup(year, month, week, day_name)
                    assert low <= result.day <= high, (
                        f"{week} {day_name} of {year}-{month:02d} gave {result}"
                    )


def test_result_matches_requested_year_month_and_weekday():
    """REQ: "For example, you might be asked to find the date for the meetup on the first Monday in January 2018 (January 1, 2018)."

    Invariant: the returned date is in the requested year and month and falls on the requested weekday.
    """
    weeks = ("first", "second", "third", "fourth", "last", "teenth")
    for year in _YEARS:
        for month in _MONTHS:
            for day_name in _DAY_NAMES:
                for week in weeks:
                    result = meetup(year, month, week, day_name)
                    assert result.year == year
                    assert result.month == month
                    assert _DAY_NAMES[result.weekday()] == day_name


def test_last_is_within_final_seven_days_of_month():
    """REQ: "There are six week values to consider: `first`, `second`, `third`, `fourth`, `last`, `teenth`."

    Invariant: "last" is the final occurrence of the weekday, so it falls in the last seven days of the month.
    """
    for year in _YEARS:
        for month in _MONTHS:
            days_in_month = calendar.monthrange(year, month)[1]
            for day_name in _DAY_NAMES:
                result = meetup(year, month, "last", day_name)
                assert days_in_month - 6 <= result.day <= days_in_month, (
                    f"last {day_name} of {year}-{month:02d} gave {result}"
                )


def test_last_is_fifth_occurrence_when_month_has_five():
    """REQ: "There are six week values to consider: `first`, `second`, `third`, `fourth`, `last`, `teenth`."

    March 2015 starts on a Sunday, so it has five Mondays (2, 9, 16, 23, 30). "last" is the 30th.
    """
    assert meetup(2015, 3, "last", "Monday") == datetime.date(2015, 3, 30)


def test_fourth_is_not_last_when_month_has_five():
    """REQ: "There are six week values to consider: `first`, `second`, `third`, `fourth`, `last`, `teenth`."

    March 2015 has five Mondays (2, 9, 16, 23, 30), so "fourth" is the 23rd and differs from "last".
    """
    assert meetup(2015, 3, "fourth", "Monday") == datetime.date(2015, 3, 23)


def test_last_on_leap_day():
    """REQ: "the last Thursday of November 2022 (November 24, 2022)"

    February 2016 is a leap year starting on a Monday, so its Mondays are 1, 8, 15, 22 and 29. "last" is the 29th.
    """
    assert meetup(2016, 2, "last", "Monday") == datetime.date(2016, 2, 29)


def test_consecutive_weeks_are_seven_days_apart():
    """REQ: "There are six week values to consider: `first`, `second`, `third`, `fourth`, `last`, `teenth`."

    Invariant: for the same month and weekday, second is 7 days after first, third is 7 days after second, and fourth is 7 days after third.
    """
    for year in _YEARS:
        for month in _MONTHS:
            for day_name in _DAY_NAMES:
                first = meetup(year, month, "first", day_name)
                second = meetup(year, month, "second", day_name)
                third = meetup(year, month, "third", day_name)
                fourth = meetup(year, month, "fourth", day_name)
                assert second - first == datetime.timedelta(days=7)
                assert third - second == datetime.timedelta(days=7)
                assert fourth - third == datetime.timedelta(days=7)


def test_fifth_weekday_returned_when_present():
    """REQ: "We have added an additional week descriptor (`fifth`) for the fifth weekday of the month, if there is one."

    March 2015 has five Mondays (2, 9, 16, 23, 30), so the fifth Monday is March 30, 2015.
    """
    assert meetup(2015, 3, "fifth", "Monday") == datetime.date(2015, 3, 30)


def test_fifth_weekday_missing_raises_exception():
    """REQ: "If there is not a fifth weekday in a month, you should raise an exception."

    February 2015 starts on a Sunday and has only four Mondays (2, 9, 16, 23), so a fifth Monday does not exist.
    """
    with pytest.raises(MeetupDayException):
        meetup(2015, 2, "fifth", "Monday")


def test_exception_has_meaningful_message():
    """REQ: "When you do this, you should always include a **meaningful error message** to indicate what the source of the error is."

    The raised MeetupDayException must carry a non-empty message, either as its string form or as a message attribute.
    """
    with pytest.raises(MeetupDayException) as info:
        meetup(2015, 2, "fifth", "Monday")
    text = str(info.value) or getattr(info.value, "message", "")
    assert isinstance(text, str)
    assert text.strip()
