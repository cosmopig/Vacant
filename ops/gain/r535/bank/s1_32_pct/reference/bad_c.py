def percentage(part, whole):
    if whole == 0:
        return 0.0
    return round(part * 100 / whole, 1)
