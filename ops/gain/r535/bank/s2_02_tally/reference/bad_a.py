def tally(words):
    out = {}
    for w in words:
        out[w] = out.get(w, 0) + 1
    return out
