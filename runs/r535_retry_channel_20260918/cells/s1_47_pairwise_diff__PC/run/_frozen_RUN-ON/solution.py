def pairwise_diff(xs):
    if len(xs) < 2:
        return []
    return [xs[i+1] - xs[i] for i in range(len(xs) - 1)]
