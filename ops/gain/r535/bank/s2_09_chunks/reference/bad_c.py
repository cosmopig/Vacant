def chunk(xs, n):
    if n <= 0:
        raise ValueError("n must be positive")
    return [xs[i:i + n] for i in range(0, len(xs), n)]
