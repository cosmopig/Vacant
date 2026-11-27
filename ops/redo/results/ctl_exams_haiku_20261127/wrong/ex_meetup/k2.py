import calendar
from datetime import date


class MeetupDayException(ValueError):
    """Exception raised when the Meetup weekday and count do not result in a valid date.

    message: explanation of the error.

    """
    def __init__(self, message=""):
        self.message = message
        super().__init__(message)


WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
ORDINALS = {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4}


def meetup(year, month, week, day_of_week):
    if day_of_week not in WEEKDAYS:
        raise MeetupDayException(f"Unknown weekday: {day_of_week}")

    weekday = WEEKDAYS.index(day_of_week)
    last_day = calendar.monthrange(year, month)[1]
    matches = [
        day for day in range(1, last_day + 1)
        if date(year, month, day).weekday() == weekday
    ]

    if week == "teenth":
        for day in matches:
            if 13 <= day <= 18:
                return date(year, month, day)
        raise MeetupDayException(
            f"No teenth {day_of_week} in {year}-{month:02d}."
        )

    if week == "last":
        return date(year, month, matches[-1])

    if week in ORDINALS:
        index = ORDINALS[week]
        if index >= len(matches):
            raise MeetupDayException(
                f"There is no {week} {day_of_week} in {year}-{month:02d}."
            )
        return date(year, month, matches[index])

    raise MeetupDayException(f"Unknown week descriptor: {week}")
