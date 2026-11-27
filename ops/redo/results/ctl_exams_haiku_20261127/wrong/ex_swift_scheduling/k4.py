from datetime import datetime, timedelta


def _last_workday(year, month):
    if month == 12:
        last = datetime(year, 12, 31)
    else:
        last = datetime(year, month + 1, 1) - timedelta(days=1)
    while last.weekday() >= 5:
        last -= timedelta(days=1)
    return last


def _first_workday(year, month):
    first = datetime(year, month, 1)
    while first.weekday() >= 5:
        first += timedelta(days=1)
    return first


def delivery_date(start, description):
    if description == "NOW":
        return start + timedelta(hours=2)
    if description == "ASAP":
        if start.hour <= 13:
            return start.replace(hour=17, minute=0, second=0, microsecond=0)
        return (start + timedelta(days=1)).replace(hour=13, minute=0, second=0, microsecond=0)
    if description == "EOW":
        if start.weekday() <= 2:
            friday = start + timedelta(days=4 - start.weekday())
            return friday.replace(hour=17, minute=0, second=0, microsecond=0)
        sunday = start + timedelta(days=6 - start.weekday())
        return sunday.replace(hour=20, minute=0, second=0, microsecond=0)
    if description.endswith("M"):
        n = int(description[:-1])
        year = start.year if start.month < n else start.year + 1
        return _first_workday(year, n).replace(hour=8, minute=0, second=0, microsecond=0)
    if description.startswith("Q"):
        n = int(description[1:])
        quarter = (start.month - 1) // 3 + 1
        year = start.year if quarter <= n else start.year + 1
        last_month = 3 * n
        return _last_workday(year, last_month).replace(hour=8, minute=0, second=0, microsecond=0)
    raise ValueError("unknown delivery date description")
