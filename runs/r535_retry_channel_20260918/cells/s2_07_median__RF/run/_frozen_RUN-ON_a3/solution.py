def median(xs):
    if not xs:
        return None
    sorted_xs = sorted(xs)
    n = len(sorted_xs)
    mid = n // 2
    if n % 2 == 1:
        return sorted_xs[mid]
    else:
        return (sorted_xs[mid - 1] + sorted_xs[mid]) / 2.0
