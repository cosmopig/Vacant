def pairwise_diff(xs):
    if not xs:
        return []
    return [0] + [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
