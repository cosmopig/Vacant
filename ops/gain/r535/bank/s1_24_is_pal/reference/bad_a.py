def is_pal(s):
    t = [c for c in s if c.isalnum()]
    return t == t[::-1]
