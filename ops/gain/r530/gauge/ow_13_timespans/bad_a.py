"""Known-bad A: sorts the strings and only joins what strictly overlaps.

Dates are compared as text, which happens to work for one written form and not for
two, spans that touch end to end are left as two, and the total is the sum of the
raw spans so overlapping time is counted twice.
"""


def merge(spans):
    ordered = sorted(spans)
    out = []
    for start, end in ordered:
        if out and start < out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def subtract(spans, holes):
    out = []
    for start, end in merge(spans):
        covered = False
        for hole_start, hole_end in holes:
            if hole_start <= start and hole_end >= end:
                covered = True
        if not covered:
            out.append((start, end))
    return out


def total_seconds(spans):
    total = 0
    for start, end in spans:
        total += (int(end[11:13] or 0) - int(start[11:13] or 0)) * 3600
    return total
