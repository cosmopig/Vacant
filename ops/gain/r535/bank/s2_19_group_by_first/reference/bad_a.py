def group_by_first(words):
    out = {}
    for w in words:
        if not w:
            continue
        out.setdefault(w[0], []).append(w)
    return out
