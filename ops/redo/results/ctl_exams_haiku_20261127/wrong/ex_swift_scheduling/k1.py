from datetime import date, datetime, time, timedelta


def _first_workday(year, month):
    day = date(year, month, 1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def _last_workday(year, month):
    if month == 12:
        day = date(year, 12, 31)
    else:
        day = date(year, month + 1, 1) - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def delivery_date(start, description):
    if description == "NOW":
        return start + timedelta(hours=2)

    if description == "ASAP":
        if start.time() <= time(13, 0):
            return datetime.combine(start.date(), time(17, 0))
        tomorrow = start.date() + timedelta(days=1)
        return datetime.combine(tomorrow, time(13, 0))

    if description == "EOW":
        if start.weekday() < 3:
            friday = start.date() + timedelta(days=4 - start.weekday())
            return datetime.combine(friday, time(17, 0))
        sunday = start.date() + timedelta(days=6 - start.weekday())
        return datetime.combine(sunday, time(20, 0))

    if description.endswith("M"):
        n = int(description[:-1])
        year = start.year if start.month < n else start.year + 1
        return datetime.combine(_first_workday(year, n), time(8, 0))

    if description.startswith("Q"):
        n = int(description[1:])
        current_quarter = (start.month - 1) // 3 + 1
        year = start.year if current_quarter <= n else start.year + 1
        return datetime.combine(_last_workday(year, 3 * n), time(8, 0))

    raise ValueError(f"Unknown delivery date description: {description}")
