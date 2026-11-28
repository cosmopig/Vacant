from datetime import datetime, time, timedelta
import calendar


def _first_workday(year, month):
    d = datetime(year, month, 1, 8, 0)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _last_workday(year, month):
    last = calendar.monthrange(year, month)[1]
    d = datetime(year, month, last, 8, 0)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def delivery_date(start, description):
    if description == "NOW":
        return start + timedelta(hours=2)

    if description == "ASAP":
        if start.time() <= time(13, 0):
            return start.replace(hour=17, minute=0, second=0, microsecond=0)
        tomorrow = start + timedelta(days=1)
        return tomorrow.replace(hour=13, minute=0, second=0, microsecond=0)

    if description == "EOW":
        if start.weekday() <= 2:
            days = 4 - start.weekday()
            target = start + timedelta(days=days)
            return target.replace(hour=17, minute=0, second=0, microsecond=0)
        days = 6 - start.weekday()
        target = start + timedelta(days=days)
        return target.replace(hour=20, minute=0, second=0, microsecond=0)

    if description.endswith("M"):
        n = int(description[:-1])
        year = start.year if start.month < n else start.year + 1
        return _first_workday(year, n)

    if description.startswith("Q"):
        n = int(description[1:])
        quarter = (start.month - 1) // 3 + 1
        year = start.year if quarter <= n else start.year + 1
        return _last_workday(year, 3 * n)

    raise ValueError(f"Unknown delivery date description: {description}")
