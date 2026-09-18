def uniq(xs):
    out = []
    for x in xs:
        if x in out:
            out.remove(x)
        out.append(x)
    return out
