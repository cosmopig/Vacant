def flip_map(d):
    out = {}
    for k, v in d.items():
        if v not in out:
            out[v] = k
    return out
