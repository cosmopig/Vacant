def mask(s, keep):
    if keep >= len(s):
        return s
    return "x" * (len(s) - keep) + s[len(s) - keep:]
