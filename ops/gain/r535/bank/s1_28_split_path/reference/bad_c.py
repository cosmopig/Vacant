def path_parts(p):
    head, _, tail = p.rpartition("/")
    base, dot, ext = tail.rpartition(".")
    if not dot:
        base, ext = tail, ""
    return {"dir": head, "name": base, "ext": ext}
