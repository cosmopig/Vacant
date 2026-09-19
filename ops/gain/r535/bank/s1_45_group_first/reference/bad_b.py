def group_first(words):
    out = {}
    for w in words:
        out.setdefault(w[0].lower(), []).append(w)
    return sorted(out.items())
