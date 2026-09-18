def deltas(xs):
    return [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
