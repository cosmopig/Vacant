def normalize(p):
    while "//" in p:
        p = p.replace("//", "/")
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p
