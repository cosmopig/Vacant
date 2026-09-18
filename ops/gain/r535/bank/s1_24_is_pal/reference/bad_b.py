def is_pal(s):
    t = [c.lower() for c in s if c.isalnum()]
    return "yes" if t == t[::-1] else "no"
