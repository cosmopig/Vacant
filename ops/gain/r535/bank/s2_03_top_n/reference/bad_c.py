def top_keys(counts, n):
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in ranked[:n]]
