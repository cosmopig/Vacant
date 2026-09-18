def group_first(words):
    out = {}
    for w in words:
        out.setdefault(w[0], []).append(w)
    return out
