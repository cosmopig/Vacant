def pct(part, whole):
    if whole == 0:
        return "0.0%"
    return "%.1f%%" % (part * 100 / whole)
