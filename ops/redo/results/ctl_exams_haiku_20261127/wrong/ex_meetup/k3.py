import calendar
from datetime import date, datetime

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEK_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}


class MeetupDayException(ValueError):
    """Exception raised when the Meetup weekday and count do not result in a valid date.

    message: explanation of the error.

    """
    def __init__(self, message=""):
        self.message = message
        super().__init__(message)


def meetup(year, month, week, day_of_week):
    if day_of_week not in WEEKDAYS:
        raise MeetupDayException(f"Unknown weekday: {day_of_week!r}")
    target = WEEKDAYS.index(day_of_week)

    days_in_month = calendar.monthrange(year, month)[1]
    first_weekday = date(year, month, 1).weekday()
    first_match = 1 + (target - first_weekday) % 7

    if week == "teenth":
        day = first_match
        while day < 13:
            day += 7
    elif week == "last":
        day = first_match + 7 * ((days_in_month - first_match) // 7)
    elif week in WEEK_ORDINALS:
        day = first_match + 7 * (WEEK_ORDINALS[week] - 1)
        if day > days_in_month:
            raise MeetupDayException(
                f"There is no {week} {day_of_week} in {year}-{month:02d}."
            )
    else:
        raise MeetupDayException(f"Unknown week descriptor: {week!r}")

    if week == "last":
        return datetime(year, month, day)
    return date(year, month, day)
