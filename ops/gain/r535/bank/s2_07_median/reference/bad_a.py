def median(xs):
    if not xs:
        raise ValueError("median of nothing")
    ys = sorted(xs)
    return ys[(len(ys) - 1) // 2]
