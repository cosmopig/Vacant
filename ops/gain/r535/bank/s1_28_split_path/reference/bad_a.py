def split_path(p):
    head, _, tail = p.rpartition("/")
    base, dot, ext = tail.rpartition(".")
    if not dot:
        return {"dir": head, "name": tail, "ext": ""}
    return {"dir": head, "name": base, "ext": "." + ext}
