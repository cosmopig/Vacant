def chunks(xs, n):
    return [tuple(xs[i:i + n]) for i in range(0, len(xs), n)]
