import datetime


class MeetupDayException(ValueError):
    """Exception raised when the Meetup weekday and count do not result in a valid date.

    message: explanation of the error.

    """
    def __init__(self, message=""):
        self.message = message
        super().__init__(message)


WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

ORDINALS = {
    "first": 0,
    "second": 1,
    "third": 2,
    "fourth": 3,
    "fifth": 4,
}


def _days_in_month(year, month):
    if month == 2:
        leap = year % 4 == 0 and year % 100 != 0
        return 29 if leap else 28
    if month in (4, 6, 9, 11):
        return 30
    return 31


def meetup(year, month, week, day_of_week):
    key = str(day_of_week).strip().lower()
    if key not in WEEKDAYS:
        raise MeetupDayException(f"Unknown weekday: {day_of_week!r}.")
    target = WEEKDAYS[key]

    week_key = str(week).strip().lower()
    if week_key not in ORDINALS and week_key not in ("last", "teenth"):
        raise MeetupDayException(f"Unknown week descriptor: {week!r}.")

    days_in_month = _days_in_month(year, month)
    first_weekday = datetime.date(year, month, 1).weekday()
    first_day = 1 + (target - first_weekday) % 7

    if week_key == "teenth":
        day = first_day
        while day < 13:
            day += 7
    elif week_key == "last":
        day = first_day + 28
        while day + 7 <= days_in_month:
            day += 7
    else:
        day = first_day + 7 * ORDINALS[week_key]
        if day > days_in_month:
            raise MeetupDayException(
                f"There is no {week_key} {key} in {year}-{month:02d}."
            )

    return datetime.date(year, month, day)
