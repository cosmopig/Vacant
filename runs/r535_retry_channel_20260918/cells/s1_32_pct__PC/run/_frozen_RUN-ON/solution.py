def pct(part, whole):
    if not whole:
        return None
    return round((part / whole) * 100, 1)
