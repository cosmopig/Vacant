def truncate(s, n):
    if len(s) <= n:
        return s
    return s[:max(n - 1, 0)] + "…"
