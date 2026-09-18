def top_n(counts, n):
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    return [k for k, _ in ranked[:n]]
