def normalize(p):
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p
