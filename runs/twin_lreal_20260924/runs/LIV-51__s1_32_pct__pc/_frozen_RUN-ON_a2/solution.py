def pct(part, whole):
    if whole == 0:
        return None
    return round((part / whole) * 100, 1)
