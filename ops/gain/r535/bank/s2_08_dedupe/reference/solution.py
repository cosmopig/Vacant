def dedupe(xs):
    seen = set()
    out = []
    for x in xs:
        k = x.lower()
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out
