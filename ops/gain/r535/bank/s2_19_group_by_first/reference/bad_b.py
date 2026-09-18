def group_by_first(words):
    out = {}
    for w in words:
        out.setdefault(w[:1].lower(), []).append(w)
    return out
