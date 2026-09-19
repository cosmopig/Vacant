def mid(xs):
    sorted_xs = sorted(xs)
    n = len(sorted_xs)
    if n % 2 == 1:
        return float(sorted_xs[n // 2])
    else:
        mid1 = sorted_xs[n // 2 - 1]
        mid2 = sorted_xs[n // 2]
        return (mid1 + mid2) / 2.0
