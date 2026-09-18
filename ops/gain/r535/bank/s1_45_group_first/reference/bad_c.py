def group_by_first_letter(words):
    out = {}
    for w in words:
        out.setdefault(w[0].lower(), []).append(w)
    return out
