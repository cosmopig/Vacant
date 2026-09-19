def cumsum(xs):
    out = []
    t = 0
    for x in xs:
        t += x
        out.append(t)
    return out
