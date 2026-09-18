def pairwise_diff(xs):
    return [xs[i] - xs[i + 1] for i in range(len(xs) - 1)]
