def pct(part, whole):
    if whole == 0 or whole is None:
        return None
    return round((part / whole) * 100, 1)
