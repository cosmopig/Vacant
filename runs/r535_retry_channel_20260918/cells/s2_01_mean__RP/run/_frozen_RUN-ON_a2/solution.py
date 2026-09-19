def mean(xs):
    if not xs:
        return 0.0
    res = sum(xs) / len(xs)
    return round(res, 3)
