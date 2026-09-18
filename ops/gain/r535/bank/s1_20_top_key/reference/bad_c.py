def most_common(d):
    best = None
    for k in sorted(d):
        if best is None or d[k] > d[best]:
            best = k
    return best
