def pct(part, whole):
    if whole == 0:
        return 0.0
    res = (part / whole) * 100
    return round(res, 1)
