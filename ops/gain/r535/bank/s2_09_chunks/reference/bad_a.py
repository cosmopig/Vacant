def chunks(xs, n):
    if n <= 0:
        return []
    return [xs[i:i + n] for i in range(0, len(xs), n)]
