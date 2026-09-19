def tally(items):
    out = {}
    for it in items:
        out[it] = out.get(it, 0) + 1
    return out
