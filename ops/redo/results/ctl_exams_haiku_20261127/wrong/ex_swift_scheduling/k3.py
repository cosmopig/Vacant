import datetime as dt


def _first_workday(year, month):
    day = dt.datetime(year, month, 1, 8, 0)
    while day.weekday() >= 5:
        day += dt.timedelta(days=1)
    return day


def _last_workday(year, month):
    if month == 12:
        day = dt.datetime(year, 12, 31, 8, 0)
    else:
        day = dt.datetime(year, month + 1, 1, 8, 0) - dt.timedelta(days=1)
    while day.weekday() >= 5:
        day -= dt.timedelta(days=1)
    return day


def delivery_date(start, description):
    if description == "NOW":
        return start + dt.timedelta(hours=2)

    if description == "ASAP":
        if start.hour < 13:
            return start.replace(hour=17, minute=0, second=0, microsecond=0)
        tomorrow = start + dt.timedelta(days=1)
        return tomorrow.replace(hour=13, minute=0, second=0, microsecond=0)

    if description == "EOW":
        weekday = start.weekday()
        if weekday <= 2:
            friday = start + dt.timedelta(days=4 - weekday)
            return friday.replace(hour=17, minute=0, second=0, microsecond=0)
        sunday = start + dt.timedelta(days=6 - weekday)
        return sunday.replace(hour=20, minute=0, second=0, microsecond=0)

    if description.endswith("M"):
        n = int(description[:-1])
        year = start.year if start.month < n else start.year + 1
        return _first_workday(year, n).date()

    if description.startswith("Q"):
        n = int(description[1:])
        year = start.year if start.month <= 3 * n else start.year + 1
        return _last_workday(year, 3 * n).date()

    raise ValueError(f"Unknown delivery date description: {description!r}")
