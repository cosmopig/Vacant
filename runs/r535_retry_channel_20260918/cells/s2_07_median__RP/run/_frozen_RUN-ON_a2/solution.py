def median(xs):
    if not xs:
        raise ValueError("Empty list")
    sorted_xs = sorted(xs)
    n = len(sorted_xs)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_xs[mid - 1] + sorted_xs[mid]) / 2
    else:
        return sorted_xs[mid]
