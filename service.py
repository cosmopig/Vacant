"""Elapsed-time availability without host-local timezone assumptions."""
from datetime import timedelta
from checks import instant, integer


def _pair(row):
    if isinstance(row, dict):
        try:
            return row["start"], row["end"]
        except KeyError:
            raise ValueError("invalid busy interval") from None
    if isinstance(row, (str, bytes)):
        raise ValueError("invalid busy interval")
    try:
        start, end = row
    except (TypeError, ValueError):
        raise ValueError("invalid busy interval") from None
    return start, end


def windows(busy):
    result = []
    for row in busy:
        start, end = _pair(row)
        start, end = instant(start), instant(end)
        if end < start:
            raise ValueError("invalid busy interval")
        result.append((start, end))
    return sorted(result)


def coalesce(busy):
    merged = []
    for start, end in windows(busy):
        if start == end:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def slots(start, end, busy, duration, step=None, limit=None):
    start, end = instant(start), instant(end)
    if end < start:
        raise ValueError("end precedes start")
    duration = integer(duration, "duration", 1)
    step = duration if step is None else integer(step, "step", 1)
    if limit is not None:
        limit = integer(limit, "limit")
    busy = coalesce(busy)
    if limit == 0:
        return []
    length = timedelta(minutes=duration)
    stride = timedelta(minutes=step)
    result = []
    index = 0
    current = start
    while current + length <= end:
        finish = current + length
        while index < len(busy) and busy[index][1] <= current:
            index += 1
        if index < len(busy) and busy[index][0] < finish:
            blocked_until = busy[index][1]
            current += stride * max(1, -(-(blocked_until - current) // stride))
            continue
        result.append({"start": current.isoformat(), "end": finish.isoformat()})
        if limit is not None and len(result) >= limit:
            break
        current += stride
    return result


def available_minutes(start, end, busy):
    return len(slots(start, end, busy, 1))


def first_slot(start, end, busy, duration):
    result = slots(start, end, busy, duration, limit=1)
    return result[0] if result else None
