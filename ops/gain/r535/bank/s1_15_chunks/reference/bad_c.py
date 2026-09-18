def split_into_chunks(xs, n):
    return [xs[i:i + n] for i in range(0, len(xs), n)]
