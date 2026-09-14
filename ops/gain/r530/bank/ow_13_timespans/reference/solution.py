"""Reference solution for ow_13_timespans (gauge only; never enters a workspace)."""

import datetime

DATE = "%Y-%m-%d"
DATETIME = "%Y-%m-%dT%H:%M:%S"


def parse_instant(text):
    if not isinstance(text, str):
        raise ValueError("not an instant: %r" % (text,))
    value = text.strip()
    shape = DATE if len(value) == 10 else DATETIME
    try:
        return datetime.datetime.strptime(value, shape)
    except ValueError:
        raise ValueError("not an instant: %r" % (text,)) from None


def format_instant(moment):
    return moment.strftime(DATETIME)


def normalise(spans):
    """Parsed, validated, sorted, merged. The one place the half-open rule lives.

    Touching spans join because the first one does not cover its own end instant,
    so there is no gap between them to keep them apart.
    """
    pieces = []
    for span in spans:
        start, end = span
        first, last = parse_instant(start), parse_instant(end)
        if last < first:
            raise ValueError("span ends before it starts: %r" % (span,))
        if first == last:
            continue
        pieces.append((first, last))
    pieces.sort()
    merged = []
    for first, last in pieces:
        if merged and first <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], last))
        else:
            merged.append((first, last))
    return merged


def merge(spans):
    return [(format_instant(a), format_instant(b)) for a, b in normalise(spans)]


def subtract(spans, holes):
    cuts = normalise(holes)
    out = []
    for first, last in normalise(spans):
        pieces = [(first, last)]
        for hole_first, hole_last in cuts:
            remaining = []
            for piece_first, piece_last in pieces:
                if hole_last <= piece_first or hole_first >= piece_last:
                    remaining.append((piece_first, piece_last))
                    continue
                if hole_first > piece_first:
                    remaining.append((piece_first, hole_first))
                if hole_last < piece_last:
                    remaining.append((hole_last, piece_last))
            pieces = remaining
        out.extend(pieces)
    return [(format_instant(a), format_instant(b)) for a, b in out]


def total_seconds(spans):
    return int(sum((last - first).total_seconds() for first, last in normalise(spans)))
