def mask_tail(s, keep):
    if keep >= len(s):
        return s
    return "*" * (len(s) - keep) + s[len(s) - keep:]
