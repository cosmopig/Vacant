def pairs_to_map(keys, values):
    out = {}
    for k, v in zip(keys, values):
        if k not in out:
            out[k] = v
    return out
