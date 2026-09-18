def running_total(xs):
    out = []
    t = 0
    for x in xs:
        out.append(t)
        t += x
    return out
