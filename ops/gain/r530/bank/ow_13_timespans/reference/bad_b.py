"""Known-bad B: real datetimes, one hole per span, nothing validated.

Merging and totalling are right, but subtract can only trim a span from its ends,
zero-length spans survive as spans, and a reversed span is accepted.
"""

import datetime

DATETIME = "%Y-%m-%dT%H:%M:%S"


def _parse(text):
    value = text.strip()
    if len(value) == 10:
        return datetime.datetime.strptime(value, "%Y-%m-%d")
    return datetime.datetime.strptime(value, DATETIME)


def _pairs(spans):
    return sorted((_parse(a), _parse(b)) for a, b in spans)


def _merge(pairs):
    out = []
    for first, last in pairs:
        if out and first <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], last))
        else:
            out.append((first, last))
    return out


def merge(spans):
    return [(a.strftime(DATETIME), b.strftime(DATETIME)) for a, b in _merge(_pairs(spans))]


def subtract(spans, holes):
    cuts = _merge(_pairs(holes))
    out = []
    for first, last in _merge(_pairs(spans)):
        for hole_first, hole_last in cuts:
            if hole_first <= first < hole_last:
                first = min(hole_last, last)
            if hole_first < last <= hole_last:
                last = max(hole_first, first)
        if first < last:
            out.append((first, last))
    return [(a.strftime(DATETIME), b.strftime(DATETIME)) for a, b in out]


def total_seconds(spans):
    return int(sum((b - a).total_seconds() for a, b in _merge(_pairs(spans))))
