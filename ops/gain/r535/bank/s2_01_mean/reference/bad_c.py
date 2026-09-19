def average(xs):
    if not xs:
        return 0.0
    return round(sum(xs) / len(xs), 3)
