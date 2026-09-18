def chunks(xs, n):
    return [xs[i:i + n] for i in range(0, len(xs), n) if i + n <= len(xs)]
