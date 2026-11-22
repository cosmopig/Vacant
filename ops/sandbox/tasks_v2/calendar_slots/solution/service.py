"""Elapsed-time availability without host-local timezone assumptions."""
from datetime import timedelta
from checks import instant, integer


def windows(busy):
    result = []
    for start, end in busy:
        start, end = instant(start), instant(end)
        if end < start:
            raise ValueError("invalid busy interval")
        if start != end:
            result.append((start, end))
    return sorted(result)


def coalesce(busy):
    merged = []
    for start, end in windows(busy):
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
    result = []
    current = start
    while current + timedelta(minutes=duration) <= end:
        finish = current + timedelta(minutes=duration)
        if not any(current < right and left < finish for left, right in busy):
            result.append({"start": current.isoformat(), "end": finish.isoformat()})
            if limit is not None and len(result) >= limit:
                break
        current += timedelta(minutes=step)
    return result


def available_minutes(start, end, busy):
    return len(slots(start, end, busy, 1))


def first_slot(start, end, busy, duration):
    result = slots(start, end, busy, duration, limit=1)
    return result[0] if result else None
