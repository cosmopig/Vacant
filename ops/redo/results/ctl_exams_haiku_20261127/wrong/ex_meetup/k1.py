import calendar
import datetime


class MeetupDayException(ValueError):
    """Exception raised when the Meetup weekday and count do not result in a valid date.

    message: explanation of the error.

    """
    def __init__(self, message=None):
        super().__init__(message)
        self.message = message


WEEKDAYS = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}

ORDINALS = {
    "first": 0,
    "second": 1,
    "third": 2,
    "fourth": 3,
    "fifth": 4,
}


def meetup(year, month, week, day_of_week):
    if day_of_week not in WEEKDAYS:
        raise MeetupDayException("Unknown weekday: {}".format(day_of_week))
    target = WEEKDAYS[day_of_week]
    days_in_month = calendar.monthrange(year, month)[1]

    if week == "teenth":
        candidates = [
            d for d in range(13, 19)
            if datetime.date(year, month, d).weekday() == target
        ]
        if not candidates:
            raise MeetupDayException("That day does not exist.")
        return datetime.date(year, month, candidates[0])

    matches = [
        d for d in range(1, days_in_month + 1)
        if datetime.date(year, month, d).weekday() == target
    ]

    if week == "last":
        return datetime.date(year, month, matches[-1])

    if week not in ORDINALS:
        raise MeetupDayException("Unknown week descriptor: {}".format(week))

    index = ORDINALS[week]
    if index >= len(matches):
        raise MeetupDayException("That day does not exist.")
    return datetime.date(year, month, matches[index])
