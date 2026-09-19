def dedupe(xs):
    out = {}
    for x in xs:
        out[x.lower()] = x
    return list(out.values())
