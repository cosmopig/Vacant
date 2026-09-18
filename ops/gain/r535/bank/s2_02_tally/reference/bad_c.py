def count_words(words):
    out = {}
    for w in words:
        k = w.lower()
        out[k] = out.get(k, 0) + 1
    return out
