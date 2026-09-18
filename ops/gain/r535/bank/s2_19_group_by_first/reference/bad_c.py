def group_first(words):
    out = {}
    for w in words:
        if not w:
            continue
        out.setdefault(w[0].lower(), []).append(w)
    return out
