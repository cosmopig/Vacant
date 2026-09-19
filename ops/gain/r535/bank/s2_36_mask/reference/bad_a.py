def mask(s, keep):
    if keep >= len(s):
        return s
    return s[:keep] + "*" * (len(s) - keep)
