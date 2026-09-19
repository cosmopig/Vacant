def mean(xs):
    if not xs:
        return 0.0
    avg = sum(xs) / len(xs)
    return round(avg, 3)
