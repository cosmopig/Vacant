def by_length(words):
    return sorted(words, key=lambda w: (len(w), w))
