def ordinal(n):
    if n % 100 in (11, 12, 13):
        tail = "th"
    else:
        tail = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return "%d%s" % (n, tail)
