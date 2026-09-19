def is_pal(s):
    t = [c.lower() for c in s if c.isalnum()]
    return t == t[::-1]
