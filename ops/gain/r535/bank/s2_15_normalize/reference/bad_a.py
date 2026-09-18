def normalize(p):
    while "//" in p:
        p = p.replace("//", "/")
    return p.rstrip("/")
